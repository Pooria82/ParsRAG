import os
import re

from backend.core.models.domain import ExtractedNode


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
    if explicit_filter:
        valid_files = [f for f in explicit_filter if f in available_files]
        return valid_files if valid_files else explicit_filter

    if not available_files or len(available_files) <= 1:
        return None

    # Check for broad cross-document intent keywords in Persian / English
    broad_indicators = [
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
    ]
    query_lower = query.lower()
    for indicator in broad_indicators:
        if indicator in query_lower:
            return None

    # Check if query specifically references one or more filenames
    matched: list[str] = []
    # 1. First priority: Exact full filename or clean stem match
    for filename in available_files:
        stem = os.path.splitext(filename)[0]
        clean_stem = re.sub(r"[_\-\(\)\.]", " ", stem).strip()
        if filename.lower() in query_lower or (
            len(clean_stem) >= 4 and clean_stem.lower() in query_lower
        ):
            matched.append(filename)

    if matched:
        return matched

    # 2. Second priority: Distinct non-generic keywords
    stopwords = {"گزارش", "فایل", "سند", "پروژه", "فاز", "file", "report", "doc"}
    for filename in available_files:
        stem = os.path.splitext(filename)[0]
        clean_stem = re.sub(r"[_\-\(\)\.]", " ", stem).strip()
        stem_parts = [
            p.strip().lower()
            for p in clean_stem.split()
            if len(p.strip()) >= 3 and p.strip().lower() not in stopwords
        ]
        matched_distinct = [p for p in stem_parts if p in query_lower]
        if matched_distinct:
            matched.append(filename)

    if matched:
        return matched

    return None


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
            fn_tag = f" [سند: {fn}]" if fn else ""
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
            chunk_parts.append(f"--- بخش {chunk_idx}{score_tag} ---\n{n.text}")
        doc_sections.append(f"{doc_header}\n" + "\n\n".join(chunk_parts))

    return "\n\n" + "\n\n".join(doc_sections)
