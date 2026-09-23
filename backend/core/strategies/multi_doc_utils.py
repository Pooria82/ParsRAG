import os
import re

from backend.core.interfaces.repository import AbstractDocumentRepository
from backend.core.models.domain import ExtractedNode

_BROAD_INDICATORS = (
    "هر سه",
    "هر دو",
    "همه فایل",
    "تمام فایل",
    "کل اسناد",
    "همه اسناد",
    "بین اسناد",
    "بین فایل",
    "خلاصه جامع",
    "جمع‌بندی",
    "جمع بندی",
    "نتیجه‌گیری",
    "نتیجه گیری",
    "مقایسه",
    "all files",
    "all documents",
    "compare",
    "summary of all",
)
_GENERIC_FILENAME_WORDS = {
    "گزارش",
    "فایل",
    "سند",
    "پروژه",
    "فاز",
    "file",
    "report",
    "doc",
}
_MENTION = re.compile(r"@\{((?:\\[{}]|[^{}]){1,510})\}")
_CLAUSE_BREAK = re.compile(r"\s+(?:و|and)\s+|[؟?!؛;.\n]+\s*", re.IGNORECASE)
MAX_TAGGED_SEGMENTS = 20


def _mention_filename(token: str) -> str:
    """Decode escaped braces in a document name shown inside a mention."""
    return re.sub(r"\\([{}])", r"\1", token)


def parse_tagged_segments(
    prompt: str, available_files: list[str]
) -> list[tuple[str, str]]:
    """Bind each explicit document mention to its adjacent question text."""
    matches = list(_MENTION.finditer(prompt))
    if prompt.count("@{") != len(matches):
        raise ValueError("A document mention is incomplete or malformed.")
    if not matches:
        return []
    if len(matches) > MAX_TAGGED_SEGMENTS:
        raise ValueError("Too many document mentions in one question.")
    allowed = set(available_files)
    filenames = [_mention_filename(match.group(1)) for match in matches]
    unknown = set(filenames) - allowed
    if unknown:
        raise ValueError("A mentioned document is not indexed in this session.")
    full_question = _MENTION.sub(" ", prompt).strip()
    segments: list[tuple[str, str]] = []
    leading = prompt[: matches[0].start()].strip()
    for index, match in enumerate(matches):
        between = prompt[
            match.end() : matches[index + 1].start()
            if index + 1 < len(matches)
            else len(prompt)
        ]
        boundaries = (
            list(_CLAUSE_BREAK.finditer(between)) if index + 1 < len(matches) else []
        )
        if boundaries:
            boundary = boundaries[-1]
            trailing = between[: boundary.start()]
            next_leading = between[boundary.end() :]
        else:
            trailing, next_leading = between, ""
        question = " ".join(
            part for part in (leading, trailing.strip()) if part
        ).strip()
        segments.append(
            (filenames[index], question if len(question) >= 3 else full_question)
        )
        leading = next_leading.strip()
    return segments


def retrieve_document_nodes(
    repo: AbstractDocumentRepository,
    query: str,
    available_files: list[str],
    file_filter: list[str] | None,
    session_id: str | None,
    total_k: int,
    minimum_per_file: int,
    document_segments: list[tuple[str, str]] | None = None,
) -> list[ExtractedNode]:
    """Balance normal retrieval or bind explicit question parts to named files."""
    if document_segments:
        targets = document_segments
    elif len(available_files) > 1 and file_filter is None:
        targets = [(filename, query) for filename in available_files]
    else:
        return repo.similarity_search(
            query, top_k=total_k, session_id=session_id, file_filter=file_filter
        )
    per_file = max(minimum_per_file, total_k // len(targets))
    nodes: list[ExtractedNode] = []
    for filename, question in targets:
        nodes.extend(
            repo.similarity_search(
                question, top_k=per_file, session_id=session_id, file_filter=[filename]
            )
        )
    return nodes


def include_tagged_anchors(
    nodes: list[ExtractedNode],
    filtered: list[ExtractedNode],
    segments: list[tuple[str, str]],
    threshold: float,
) -> list[ExtractedNode]:
    """Retain one sufficiently relevant source from each explicitly named file."""
    result = list(filtered)
    for filename in dict.fromkeys(name for name, _ in segments):
        if any(node.metadata.get("filename") == filename for node in result):
            continue
        candidates = [
            node
            for node in nodes
            if node.metadata.get("filename") == filename
            and (node.score or 0) >= threshold
        ]
        if candidates:
            result.append(max(candidates, key=lambda node: node.score or 0))
    return result


def has_tagged_evidence(
    nodes: list[ExtractedNode], segments: list[tuple[str, str]], threshold: float
) -> bool:
    """Require a relevant chunk for every explicitly named document."""
    supported_files = {
        str(node.metadata.get("filename"))
        for node in nodes
        if node.score is not None and node.score >= threshold
    }
    return all(filename in supported_files for filename, _ in segments)


def _clean_filename_stem(filename: str) -> str:
    """Normalize a filename stem for matching against natural-language queries."""
    stem = os.path.splitext(filename)[0]
    return re.sub(r"[_\-\(\)\.]", " ", stem).strip()


def _match_named_files(query: str, available_files: list[str]) -> list[str]:
    """Return files referenced by full name, clean stem, or distinct stem words."""
    exact = [
        filename
        for filename in available_files
        if filename.lower() in query
        or (
            len(clean_stem := _clean_filename_stem(filename)) >= 4
            and clean_stem.lower() in query
        )
    ]
    if exact:
        return exact
    matched: list[str] = []
    for filename in available_files:
        parts = {
            part.lower()
            for part in _clean_filename_stem(filename).split()
            if len(part) >= 3 and part.lower() not in _GENERIC_FILENAME_WORDS
        }
        if any(part in query for part in parts):
            matched.append(filename)
    return matched


def _location_tag(node: ExtractedNode) -> str:
    """Formats reliable parser metadata for model-visible inline citations."""
    metadata = node.metadata
    for key, label in (
        ("page", "page"),
        ("slide", "slide"),
        ("paragraph", "paragraph"),
        ("section", "section"),
    ):
        value = metadata.get(key)
        if isinstance(value, int):
            return f", {label}: {value}"
    return ""


def resolve_target_files(
    query: str,
    available_files: list[str],
    explicit_filter: list[str] | None = None,
) -> list[str] | None:
    """Determines which files should be queried based on explicit filter or query text.

    Args:
        query (str): The user's input query.
        available_files (list[str]): List of files present in the current session.
        explicit_filter (list[str] | None, optional): Explicit filter passed by caller.

    Returns:
        list[str] | None: A filtered list of filenames, or None to query across all files.
    """
    if explicit_filter == []:
        return []
    if explicit_filter:
        valid_files = [f for f in explicit_filter if f in available_files]
        return valid_files if valid_files else explicit_filter

    if not available_files or len(available_files) <= 1:
        return None

    query_lower = query.lower()
    if any(indicator in query_lower for indicator in _BROAD_INDICATORS):
        return None
    return _match_named_files(query_lower, available_files) or None


def format_multi_doc_context(nodes: list[ExtractedNode]) -> str:
    """Formats retrieved nodes into structured markdown grouped by document.

    Args:
        nodes (list[ExtractedNode]): The retrieved nodes.

    Returns:
        str: Grouped and labeled context string.
    """
    if not nodes:
        return ""

    # Group by filename
    groups: dict[str, list[ExtractedNode]] = {}
    for node in nodes:
        fn = node.metadata.get("filename", "سند نامشخص")
        groups.setdefault(fn, []).append(node)

    # If only one document, format simply
    if len(groups) <= 1:
        parts: list[str] = []
        for idx, n in enumerate(nodes, start=1):
            fn = n.metadata.get("filename", "")
            fn_tag = f" [source: {fn}{_location_tag(n)}]" if fn else ""
            score_tag = f" (امتیاز: {n.score:.2f})" if n.score is not None else ""
            parts.append(f"--- بخش {idx}{fn_tag}{score_tag} ---\n{n.text}")
        return "\n\n".join(parts)

    # If multiple documents, format with clear document headers
    doc_sections: list[str] = []
    for doc_idx, (fn, doc_nodes) in enumerate(groups.items(), start=1):
        doc_header = f"=== سند {doc_idx}: {fn} ==="
        chunk_parts: list[str] = []
        for chunk_idx, n in enumerate(doc_nodes, start=1):
            score_tag = f" (امتیاز: {n.score:.2f})" if n.score is not None else ""
            chunk_parts.append(
                f"--- بخش {chunk_idx} [source: {fn}{_location_tag(n)}]{score_tag} ---\n{n.text}"
            )
        doc_sections.append(f"{doc_header}\n" + "\n\n".join(chunk_parts))

    return "\n\n" + "\n\n".join(doc_sections)
