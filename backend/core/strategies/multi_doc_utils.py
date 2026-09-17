import os
import re

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
