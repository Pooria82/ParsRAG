import os

from llama_index.core import Settings  # type: ignore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding  # type: ignore
from llama_index.llms.ollama import Ollama  # type: ignore


def setup_llm_and_embeddings() -> None:
    """Configures global settings for LLMs and embeddings.

    Sets up the Ollama LLM and HuggingFace embeddings in the global LlamaIndex
    Settings object based on environment variables or defaults.
    """
    # LLM Setup
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name = os.getenv("LLM_MODEL_NAME", "llama3.1:8b")

    Settings.llm = Ollama(model=model_name, base_url=base_url, request_timeout=120.0)

    # Embeddings Setup (using intfloat/multilingual-e5-base)
    embed_model_name = os.getenv("EMBED_MODEL_NAME", "intfloat/multilingual-e5-base")
    Settings.embed_model = HuggingFaceEmbedding(model_name=embed_model_name)
