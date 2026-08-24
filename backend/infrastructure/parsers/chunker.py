from typing import Any

from llama_index.core.node_parser import SentenceSplitter

from backend.core.models.domain import ExtractedNode


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
