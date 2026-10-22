"""FlashRank cross-encoder adapter with a persistent, process-wide model."""

from __future__ import annotations

import importlib
import logging
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import lru_cache, partial
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

from backend.core.domain.documents import ExtractedNode

if TYPE_CHECKING:
    from flashrank import Ranker  # type: ignore[import-untyped]

# Persian/Arabic-script cross-encoder. On the labeled Persian question set it
# ranks the answer chunk higher than vector order, while the English
# ms-marco models used before ranked it lower.
DEFAULT_RERANK_MODEL = "miniReranker_arabic_v1"
DISABLED_VALUES = {"", "0", "false", "none", "off"}
# After a failed load (for example no network on the first start), questions
# use dense order for this long before the download is tried again.
RETRY_AFTER_SECONDS = 300.0
# Connect and read timeouts for the model download, which has none of its own.
DOWNLOAD_TIMEOUT_SECONDS = (10.0, 60.0)
logger = logging.getLogger("parsrag.operations")


def configured_rerank_model() -> str | None:
    """Return the FlashRank model name, or None when reranking is disabled."""
    value = os.getenv("RERANK_MODEL", DEFAULT_RERANK_MODEL).strip()
    return None if value.lower() in DISABLED_VALUES else value


def rerank_cache_dir() -> Path:
    """Keep downloaded models in the persistent cache instead of /tmp."""
    configured = os.getenv("RERANK_CACHE_DIR", "").strip()
    return Path(configured) if configured else Path.home() / ".cache" / "flashrank"


@contextmanager
def _download_timeout() -> Iterator[None]:
    """Give FlashRank's model download a timeout while a ranker loads."""
    namespace = vars(importlib.import_module("flashrank.Ranker"))
    original = namespace["requests"]

    class _TimedRequests:
        get = partial(original.get, timeout=DOWNLOAD_TIMEOUT_SECONDS)

        def __getattr__(self, name: str) -> object:
            return getattr(original, name)

    namespace["requests"] = _TimedRequests()
    try:
        yield
    finally:
        namespace["requests"] = original


@lru_cache(maxsize=2)
def _load_ranker(model_name: str, cache_dir: str) -> Ranker:
    """Load one ranker per model; FlashRank downloads it once into the cache."""
    from flashrank import Ranker

    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    with _download_timeout():
        return Ranker(model_name=model_name, cache_dir=cache_dir, max_length=512)


class FlashRankReranker:
    """``Reranker`` adapter that falls back to dense order when unavailable."""

    def __init__(
        self, model_name: str | None, clock: Callable[[], float] = time.monotonic
    ) -> None:
        """Use ``model_name``; None keeps the dense similarity order."""
        self.model_name = model_name
        self._lock = Lock()
        self._load_lock = Lock()
        self._failed_at: float | None = None
        self._clock = clock

    @classmethod
    def from_environment(cls) -> FlashRankReranker:
        """Build the reranker selected by ``RERANK_MODEL``."""
        return cls(configured_rerank_model())

    def warm_up(self) -> bool:
        """Load or download the model ahead of the first query."""
        return self._ranker() is not None

    def _ranker(self) -> Ranker | None:
        """Load the ranker once; after a failure, wait before trying again.

        A failed load is not cached by ``lru_cache``, so without the wait every
        question retried the download. The lock keeps two first questions from
        downloading into the same folder at once.
        """
        if self.model_name is None:
            return None
        with self._load_lock:
            if (
                self._failed_at is not None
                and self._clock() - self._failed_at < RETRY_AFTER_SECONDS
            ):
                return None
            try:
                ranker = _load_ranker(self.model_name, str(rerank_cache_dir()))
            except Exception:
                self._failed_at = self._clock()
                logger.warning(
                    "reranker_unavailable model=%s; using dense retrieval order",
                    self.model_name,
                    exc_info=True,
                )
                return None
            self._failed_at = None
            return ranker

    def rerank(
        self, query: str, nodes: list[ExtractedNode], top_n: int
    ) -> list[ExtractedNode]:
        """Score nodes with the cross-encoder, or keep the dense order."""
        if not nodes or top_n <= 0:
            return []
        ranker = self._ranker()
        if ranker is None:
            ordered = sorted(nodes, key=lambda node: node.score or 0.0, reverse=True)
            return ordered[:top_n]
        from flashrank import RerankRequest

        request = RerankRequest(
            query=query,
            passages=[
                {"id": index, "text": node.text} for index, node in enumerate(nodes)
            ],
        )
        with self._lock:
            scored = ranker.rerank(request)
        return [
            nodes[int(item["id"])].model_copy(update={"score": float(item["score"])})
            for item in scored[:top_n]
        ]
