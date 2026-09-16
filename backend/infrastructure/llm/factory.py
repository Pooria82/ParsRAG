import os

from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding  # type: ignore
from llama_index.llms.ollama import Ollama  # type: ignore
from llama_index.llms.openai_like import OpenAILike  # type: ignore

load_dotenv()


def setup_llm_and_embeddings() -> None:
    """Configures global settings for LLMs and embeddings.

    Sets up the LLM and HuggingFace embeddings in the global LlamaIndex
    Settings object based on environment variables or defaults.
    """
    # LLM Setup
    llm_provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    model_name = os.getenv("LLM_MODEL_NAME", "llama3.1:8b")

    if llm_provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        Settings.llm = OpenAILike(
            model=model_name,
            api_key=api_key,
            api_base="https://openrouter.ai/api/v1",
            is_chat_model=True,
            timeout=120.0,
            max_retries=3,
        )
    else:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        Settings.llm = Ollama(
            model=model_name, base_url=base_url, request_timeout=120.0
        )

    # Embeddings Setup (using intfloat/multilingual-e5-base)
    embed_model_name = os.getenv("EMBED_MODEL_NAME", "intfloat/multilingual-e5-base")
    Settings.embed_model = HuggingFaceEmbedding(model_name=embed_model_name)
