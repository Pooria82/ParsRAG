"""Run an opt-in, live three-mode evaluation against private local PDFs.

Detailed prompts, references, answers, and source chunks are written only to the
ignored output path. The public report generator consumes aggregate metrics and
document hashes, never the private document text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict, cast

from dotenv import load_dotenv

from backend.core.models.domain import ExtractedNode, QueryResponse
from backend.core.strategies.hybrid_rag import HybridRAGStrategy
from backend.core.strategies.llm_only import LLMOnlyStrategy
from backend.core.strategies.strict_rag import StrictRAGStrategy
from backend.infrastructure.database.qdrant_repo import QdrantRepository
from backend.infrastructure.llm.factory import (
    get_model_configuration,
    setup_llm_and_embeddings,
)
from backend.infrastructure.parsers.chunker import chunk_text
from backend.infrastructure.parsers.document_parser import parse_document_sections
from backend.tests.evaluation.scoring import (
    ExpectedFact,
    is_strict_refusal,
    score_answer,
)


class PositiveCase(TypedDict):
    """One document-grounded question and its human-authored reference."""

    question: str
    reference_answer: str
    page: int
    facts: list[ExpectedFact]


class DocumentCase(TypedDict):
    """Evaluation inputs for one private PDF."""

    id: str
    filename: str
    positives: list[PositiveCase]
    negative_question: str


def _serialize_sources(sources: list[ExtractedNode]) -> list[dict[str, object]]:
    return [
        {
            "metadata": source.metadata,
            "score": source.score,
            "text_sha256": hashlib.sha256(source.text.encode("utf-8")).hexdigest(),
        }
        for source in sources
    ]


def _query_with_retry(
    strategy: StrictRAGStrategy | HybridRAGStrategy | LLMOnlyStrategy,
    question: str,
    session_id: str | None,
    *,
    attempts: int,
    delay_seconds: float,
) -> tuple[QueryResponse, float]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        started = time.perf_counter()
        try:
            response = strategy.execute(question, [], session_id=session_id)
            return response, time.perf_counter() - started
        except Exception as exc:  # noqa: BLE001 - live adapters expose varied errors.
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(delay_seconds * (2**attempt))
    assert last_error is not None
    raise last_error


def _evaluate_positive(
    strategy: StrictRAGStrategy | HybridRAGStrategy | LLMOnlyStrategy,
    case: PositiveCase,
    *,
    session_id: str | None,
    filename: str,
    attempts: int,
    delay_seconds: float,
) -> dict[str, object]:
    response, latency = _query_with_retry(
        strategy,
        case["question"],
        session_id,
        attempts=attempts,
        delay_seconds=delay_seconds,
    )
    score = score_answer(
        response.answer,
        case["facts"],
        response.source_nodes,
        filename=filename,
        page=case["page"],
    )
    return {
        "question": case["question"],
        "reference_answer": case["reference_answer"],
        "expected_page": case["page"],
        "answer": response.answer,
        "latency_seconds": round(latency, 3),
        "score": asdict(score),
        "sources": _serialize_sources(response.source_nodes),
    }


def run_evaluation(
    cases_path: Path,
    pdf_root: Path,
    output_path: Path,
    *,
    expected_model: str,
    delay_seconds: float,
    attempts: int,
) -> dict[str, object]:
    """Ingest private PDFs, run all modes, and persist detailed local evidence."""
    load_dotenv()
    setup_llm_and_embeddings()
    configuration = get_model_configuration()
    if configuration.model_name != expected_model:
        raise RuntimeError(
            f"Expected model {expected_model!r}, got {configuration.model_name!r}."
        )
    cases = cast(list[DocumentCase], json.loads(cases_path.read_text(encoding="utf-8")))
    repository = QdrantRepository(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
    )
    results: list[dict[str, object]] = []
    for index, document_case in enumerate(cases, start=1):
        pdf_path = pdf_root / document_case["filename"]
        session_id = f"pdf-eval-{index:02d}"
        repository.delete_session(session_id)
        sections = parse_document_sections(pdf_path.read_bytes(), pdf_path.name)
        nodes: list[ExtractedNode] = []
        for section in sections:
            nodes.extend(
                chunk_text(
                    section.text,
                    metadata={"filename": pdf_path.name, **section.metadata},
                )
            )
        repository.save_nodes(nodes, session_id)
        strict = StrictRAGStrategy(repository)
        hybrid = HybridRAGStrategy(repository)
        llm_only = LLMOnlyStrategy()
        positives = [
            _evaluate_positive(
                strict,
                positive,
                session_id=session_id,
                filename=pdf_path.name,
                attempts=attempts,
                delay_seconds=delay_seconds,
            )
            for positive in document_case["positives"]
        ]
        negative_response, negative_latency = _query_with_retry(
            strict,
            document_case["negative_question"],
            session_id,
            attempts=attempts,
            delay_seconds=delay_seconds,
        )
        primary = document_case["positives"][0]
        hybrid_result = _evaluate_positive(
            hybrid,
            primary,
            session_id=session_id,
            filename=pdf_path.name,
            attempts=attempts,
            delay_seconds=delay_seconds,
        )
        llm_result = _evaluate_positive(
            llm_only,
            primary,
            session_id=None,
            filename=pdf_path.name,
            attempts=attempts,
            delay_seconds=delay_seconds,
        )
        results.append(
            {
                "id": document_case["id"],
                "filename": pdf_path.name,
                "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
                "page_count": len(sections),
                "chunk_count": len(nodes),
                "strict_positive": positives,
                "strict_negative": {
                    "question": document_case["negative_question"],
                    "answer": negative_response.answer,
                    "refused": is_strict_refusal(negative_response.answer),
                    "latency_seconds": round(negative_latency, 3),
                    "sources": _serialize_sources(negative_response.source_nodes),
                },
                "hybrid": hybrid_result,
                "llm_only": llm_result,
            }
        )
        repository.delete_session(session_id)
        time.sleep(delay_seconds)
    payload: dict[str, object] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "model": configuration.model_name,
        "provider": configuration.provider.value,
        "base_url_host": configuration.base_url.split("/", 3)[2],
        "documents": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload


def main() -> None:
    """Parse command-line inputs and execute the explicitly opted-in live run."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--pdf-root", type=Path, default=Path("testData/pdf"))
    parser.add_argument(
        "--output", type=Path, default=Path("scratch/pdf_evaluation_results.json")
    )
    parser.add_argument("--model", default="google/gemma-4-26b-a4b-it")
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()
    payload = run_evaluation(
        args.cases,
        args.pdf_root,
        args.output,
        expected_model=args.model,
        delay_seconds=max(0.0, args.delay_seconds),
        attempts=max(1, args.attempts),
    )
    print(
        json.dumps(
            {
                "model": payload["model"],
                "documents": len(cast(list[object], payload["documents"])),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
