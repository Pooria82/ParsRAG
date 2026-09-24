from typing import Any

from llama_index.core.node_parser import SentenceSplitter

from backend.core.models.domain import ExtractedNode

PAGE_BRIDGE_WORDS = 90


def bridge_adjacent_pages(
    previous_text: str,
    current_text: str,
    *,
    filename: str,
    previous_page: int,
    current_page: int,
) -> ExtractedNode | None:
    """Keep a bounded page-boundary window searchable with both page citations."""
    if current_page != previous_page + 1:
        return None
    previous_words = previous_text.split()
    current_words = current_text.split()
    if not previous_words or not current_words:
        return None
    tail = " ".join(previous_words[-PAGE_BRIDGE_WORDS:])
    head = " ".join(current_words[:PAGE_BRIDGE_WORDS])
    return ExtractedNode(
        text=f"[page {previous_page}] {tail}\n[page {current_page}] {head}",
        metadata={
            "filename": filename,
            "page": previous_page,
            "page_end": current_page,
            "kind": "page_bridge",
        },
    )


def chunk_text(
    text: str,
    metadata: dict[str, Any] | None = None,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> list[ExtractedNode]:
    """Splits text into smaller overlapping chunks for vectorization.

    Args:
        text (str): The raw text to chunk.
        metadata (dict[str, Any] | None, optional): Metadata to attach to each chunk. Defaults to None.
        chunk_size (int, optional): The maximum size of each chunk. Defaults to 512.
        chunk_overlap (int, optional): The number of overlapping tokens between chunks. Defaults to 50.

    Returns:
        list[ExtractedNode]: A list of nodes representing the chunks.
    """
    if metadata is None:
        metadata = {}

    splitter = SentenceSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    chunks = splitter.split_text(text)

    nodes = []
    for chunk in chunks:
        nodes.append(ExtractedNode(text=chunk, metadata=metadata))

    return nodes
