import os
import re

from backend.core.domain.documents import ExtractedNode
from backend.core.port.document_repository import DocumentRepository

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
_CLAUSE_BREAK = re.compile(r"\s(?:و|and)\s|[؟?!؛;.\n]", re.IGNORECASE)
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
    repo: DocumentRepository,
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
    page = metadata.get("page")
    page_end = metadata.get("page_end")
    if isinstance(page, int) and isinstance(page_end, int) and page_end > page:
        return f", pages: {page}-{page_end}"
    paragraph = metadata.get("paragraph")
    paragraph_end = metadata.get("paragraph_end")
    if (
        isinstance(paragraph, int)
        and isinstance(paragraph_end, int)
        and paragraph_end > paragraph
    ):
        return f", paragraphs: {paragraph}-{paragraph_end}"
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


def order_by_document(nodes: list[ExtractedNode]) -> list[ExtractedNode]:
    """Group chunks by file (first appearance first), keeping order inside a file.

    The result is the order in which excerpts are numbered for the model and
    returned as sources, so citation ``[n]`` always means ``sources[n - 1]``.
    """
    groups: dict[str, list[ExtractedNode]] = {}
    for node in nodes:
        groups.setdefault(str(node.metadata.get("filename", "")), []).append(node)
    return [node for group in groups.values() for node in group]


def format_multi_doc_context(nodes: list[ExtractedNode]) -> str:
    """Number excerpts [1], [2], ... in the given order for citation.

    Several documents are separated by a header per file. Pass nodes through
    ``order_by_document`` first so each file's excerpts are contiguous.
    """
    if not nodes:
        return ""
    filenames = [str(node.metadata.get("filename", "سند نامشخص")) for node in nodes]
    several = len(set(filenames)) > 1
    parts: list[str] = []
    current: str | None = None
    document = 0
    for number, (node, filename) in enumerate(zip(nodes, filenames, strict=True), 1):
        if several and filename != current:
            document += 1
            parts.append(f"=== سند {document}: {filename} ===")
            current = filename
        parts.append(f"[{number}] {filename}{_location_tag(node)}\n{node.text}")
    return "\n\n".join(parts)
