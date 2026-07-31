from typing import List, Optional, Dict, Any
from llama_index.core.node_parser import SentenceSplitter
from backend.core.models.domain import ExtractedNode

def chunk_text(text: str, metadata: Optional[Dict[str, Any]] = None) -> List[ExtractedNode]:
    """Chunks text using LlamaIndex SentenceSplitter configured for Persian."""
    if metadata is None:
        metadata = {}
        
    splitter = SentenceSplitter(
        chunk_size=750, 
        chunk_overlap=150, 
    )
    
    chunks = splitter.split_text(text)
    
    nodes = []
    for chunk in chunks:
        nodes.append(
            ExtractedNode(
                text=chunk,
                metadata=metadata
            )
        )
        
    return nodes
