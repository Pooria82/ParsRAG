# Technical Standards & Code Quality Guidelines

## 1. Code Quality & Linting
To maintain a FAANG-grade, highly readable, and uniform codebase, all Python code must adhere to strict formatting and linting rules before any commit is accepted.
- **Formatter:** `ruff format`. We rely on Ruff's blazing-fast Rust-based formatter to enforce a strict 88-character line limit (compatible with Black).
- **Linter:** `ruff check`. We replace Flake8, isort, and Pylint entirely with Ruff for massive speed improvements.
- **Rules:**
  - Import sorting is enforced automatically.
  - No unused imports or variables (enforced as errors).
  - Cyclomatic complexity must remain below 10 for any given function/method.

## 2. Type Hinting & Static Analysis
ParsRAG is treated as a strongly-typed project. Dynamic typing is minimized to prevent runtime bugs.
- **Tool:** `mypy` configured in `--strict` mode.
- **Strictness Level:** 100% type hint coverage is mandatory for all function signatures (arguments and return types) and class attributes.
- **Rules:**
  - `Any` is strictly prohibited unless interacting with an un-typed third-party library (and must be justified with an inline comment).
  - Pydantic V2 is used for all data validation at system boundaries (API endpoints, database serialization).

## 3. Documentation Standards
Code explains *what*; documentation explains *why*.
- **Docstrings:** We adhere to the **Google Python Style Guide** for docstrings. Every class, module, and public method must include a docstring detailing its purpose, `Args:`, `Returns:`, and `Raises:`.
- **Inline Comments:** Used sparingly and exclusively to explain complex business logic, algorithmic choices, or non-obvious workarounds. 
- **ADRs (Architecture Decision Records):** Any significant architectural shift must be documented in the `.context/` directory before implementation.

## 4. Testing Strategy
Given the non-deterministic nature of LLMs, testing a RAG pipeline requires specialized approaches.
- **Framework:** `pytest` and `pytest-asyncio` for all asynchronous endpoints.
- **Coverage Expectation:** Minimum **85% global test coverage**, with 100% coverage on core domain models, routers, and strategy classes.
- **RAG/LLM Testing Approach:**
  - **Unit Tests:** Mock the LLM and Qdrant responses using `unittest.mock`. Test the deterministic parts: routing logic, chunking algorithms, and prompt formatting. Ensure assertions validate the strict Pydantic `QueryResponse` structures, not just raw strings.
  - **Integration Tests:** `backend/tests/e2e` (enabled with `PARSRAG_E2E=1`) runs real parsing, multilingual-e5 embeddings, reranking, Qdrant, and SSE streaming, with a deterministic model in place of the LLM. CI starts Qdrant as a GitHub Actions service container; Testcontainers is not used.
  - **LLM Evaluation:** Live evaluation is opt-in and outside CI. `backend/tests/evaluation/run_pdf_evaluation.py` indexes private PDFs and asks questions through the same `IngestDocuments` and `AnswerQuery` use cases the API runs, then scores fact coverage, cited file and page, and refusals with `scoring.py`. Each run names the model, dataset snapshot, configuration, and date. Ragas-style faithfulness metrics are a later plan (roadmap Phase 19).

## 5. Project Directory Structure
Based on our microservices architecture, the repository follows a strict Domain-Driven Design (DDD) layout:

```text
ParsRAG/
├── .context/                  # Architecture Decision Records (ADRs) and PRDs
├── backend/                   # FastAPI & LlamaIndex Core
│   ├── api/                   # Driving adapter (HTTP)
│   │   ├── dependencies.py    # Composition root: adapters -> use cases (Depends)
│   │   ├── errors.py          # ApplicationError -> HTTP status mapping
│   │   ├── middleware.py      # Origin, body-size, and correlation-ID middleware
│   │   └── routes.py          # Thin route handlers
│   ├── core/                  # Business logic (framework agnostic, see ADR 08)
│   │   ├── domain/            # Entities, enums, session rules, policies, errors
│   │   ├── dto/
│   │   │   ├── input/         # Request and command DTOs
│   │   │   └── output/        # Response DTOs
│   │   ├── port/              # Protocol contracts implemented by adapters
│   │   ├── use_case/          # One class per operation, grouped by module
│   │   │   ├── ingestion/     # Validate, parse, chunk, and index uploads
│   │   │   ├── query/         # Answer questions and report progress
│   │   │   ├── session/       # List, reuse, and delete session documents
│   │   │   ├── model/         # Model connection and conversation titles
│   │   │   └── system/        # Readiness and capability discovery
│   │   ├── strategies/        # QueryStrategy implementations (Strict, Hybrid, LLM-Only)
│   │   ├── service/           # Condense-question pipeline, retrieval optimizer
│   │   └── runtime/           # Limiter, readiness, progress, locks, correlation
│   ├── infrastructure/        # Driven adapters
│   │   ├── database/          # Qdrant DocumentRepository
│   │   ├── llm/               # Model factory, ModelGateway adapter, endpoint policy
│   │   └── parsers/           # DocumentParser, TextChunker, and OCR adapters
│   ├── tests/                 # Backend pytest suite
│   └── main.py                # FastAPI application entrypoint
├── frontend/                  # React, TypeScript, and Vite UI
│   ├── src/                   # Components, state, API client, and styles
│   ├── public/                # Local fonts and brand assets
│   └── tests/                 # Deterministic frontend tests
├── compose.yaml               # app (FastAPI + built frontend), qdrant, optional ollama
├── requirements*.txt, .lock   # pip dependencies and the tested pins (no Poetry)
├── pyproject.toml             # Project metadata; Ruff, MyPy, pytest, coverage settings
└── README.md
```

## 6. Error Handling & Logging Standards
Errors must never leak stack traces to the user and must not crash the application.
- **Global Exception Handling:** FastAPI will utilize a centralized exception handler to catch unhandled exceptions, returning a clean, standard HTTP 500 JSON response.
- **Custom Domain Exceptions:** Create specific exceptions inherited from a base `ParsRAGError` (e.g., `VectorDBConnectionError`, `LLMInferenceTimeoutError`, `EmptyDocumentError`).
- **Logging:**
  - Use the built-in Python `logging` module. `backend/infrastructure/log_config.py` writes the `backend` and `parsrag` loggers to stdout as one JSON object per line (with the correlation ID), or as plain text when `ENVIRONMENT=development`; `LOG_LEVEL` sets the level.
  - **Traceability:** Every API request must generate a unique `correlation_id` passed through the entire LlamaIndex pipeline and logged alongside every INFO/ERROR message.

## 7. Security Practices
Security must be implemented defensively at every system boundary.
- **Input Validation:** All incoming API requests and uploaded files MUST be rigorously validated using Pydantic before processing.
- **Path Traversal Prevention:** Uploaded filenames must be sanitized (`werkzeug.utils.secure_filename` or similar) to prevent path traversal attacks.
- **Explicit Egress:** No telemetry is permitted. Model traffic may leave the workstation only when the user explicitly selects API mode and accepts the disclosure; parsing, embeddings, and vector storage remain local. The only other outbound request is the daily update check: an anonymous read of the public GitHub release list and notes, with no data about the user or documents, which the user can turn off (`UPDATE_CHECK_ENABLED`).
- **Prompt Injection:** Employ defensive system prompts to mitigate user prompt injection attempting to leak organizational documents out of context.

## 8. Database Optimization & Scalability
While a traditional SQL ORM isn't applicable to a vector database, Qdrant relies on strict Pydantic schemas acting as our data modeling layer.
- **Data Modeling (ORM-like validation):** Pydantic models define the schema for vector payloads. No unstructured dictionaries should be directly written to the database.
- **Scalability & Indexing:** 
  - Ensure Qdrant payload fields (e.g., `session_id`) are explicitly indexed (`create_payload_index`) to allow fast filtering.
- **Optimization:** Use batched upserts instead of single-point inserts to maximize throughput during document ingestion. Maintain connection pooling via `qdrant-client` for high concurrency.
