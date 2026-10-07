"""Embedding model identity shared by the model factory and the vector store.

Asymmetric retrieval models such as ``multilingual-e5`` are trained with
distinct query and passage prefixes. The prefixes change the vector space, so
they are part of the collection version: vectors written with one profile are
never searched with another.

The E5 prefixes are opt-in (``EMBED_E5_PREFIXES=1``). On 125 labeled
questions over the sample documents they raised vector-search mean
reciprocal rank only from 0.672 to 0.682, and switching profiles starts an
empty collection, so every document must be uploaded again.
"""

import hashlib
import os
from dataclasses import dataclass

DEFAULT_EMBED_MODEL = "intfloat/multilingual-e5-base"
_E5_QUERY_PREFIX = "query: "
_E5_PASSAGE_PREFIX = "passage: "


@dataclass(frozen=True)
class EmbeddingProfile:
    """The model name plus the instructions prepended to queries and passages."""

    model_name: str
    query_prefix: str
    passage_prefix: str

    @property
    def collection_name(self) -> str:
        """Return the Qdrant collection versioned by this profile.

        Profiles without prefixes keep the historical model-only digest, so
        existing collections of non-prefixed models remain readable.
        """
        identity = self.model_name
        if self.query_prefix or self.passage_prefix:
            identity = (
                f"{self.model_name}|query={self.query_prefix}"
                f"|passage={self.passage_prefix}"
            )
        version = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
        return f"parsrag_{version}"


def _is_e5(model_name: str) -> bool:
    """Detect E5 models that use plain ``query:``/``passage:`` prefixes.

    Instruction-tuned E5 variants expect task instructions instead, so they
    must be configured explicitly through the prefix variables.
    """
    parts = model_name.rsplit("/", 1)[-1].lower().split("-")
    return "e5" in parts and "instruct" not in parts


def _e5_prefixes_enabled() -> bool:
    """Whether E5 models use their documented prefixes (opt-in)."""
    value = os.getenv("EMBED_E5_PREFIXES", "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _prefix(name: str, default: str) -> str:
    """Read one prefix: empty keeps the default and ``none`` disables it."""
    value = os.getenv(name, "")
    if not value.strip():
        return default
    return "" if value.strip().lower() == "none" else value


def active_embedding_profile() -> EmbeddingProfile:
    """Resolve the embedding profile from the environment.

    With ``EMBED_E5_PREFIXES=1``, E5 models use their documented
    ``query: `` and ``passage: `` prefixes; otherwise no prefixes are used.
    ``EMBED_QUERY_PREFIX`` and ``EMBED_PASSAGE_PREFIX`` override either
    default, and the value ``none`` disables a prefix explicitly.
    """
    model_name = os.getenv("EMBED_MODEL_NAME", "").strip() or DEFAULT_EMBED_MODEL
    e5 = _is_e5(model_name) and _e5_prefixes_enabled()
    return EmbeddingProfile(
        model_name=model_name,
        query_prefix=_prefix("EMBED_QUERY_PREFIX", _E5_QUERY_PREFIX if e5 else ""),
        passage_prefix=_prefix(
            "EMBED_PASSAGE_PREFIX", _E5_PASSAGE_PREFIX if e5 else ""
        ),
    )
