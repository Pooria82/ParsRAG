"""FastAPI application assembly: middleware, error mapping, routes, and the SPA."""

import logging
import os
import shutil
import tempfile
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Thread

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.errors import register_exception_handlers
from backend.api.middleware import (
    ContentLengthLimitMiddleware,
    RequestContextMiddleware,
    TrustedHostMiddleware,
    TrustedOriginMiddleware,
    configured_browser_origins,
    configured_hosts,
)
from backend.api.routes import router as api_router
from backend.core.runtime.readiness import runtime_state
from backend.infrastructure.llm.factory import setup_llm_and_embeddings

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


# Seconds to wait before each retry of a failed start. A busy or still-starting
# Qdrant can time out once; without a retry the service stayed "not ready"
# until it was restarted.
_INIT_RETRY_DELAYS = (5, 10, 20, 40, 60)


def _initialize_runtime(
    delays: tuple[float, ...] = _INIT_RETRY_DELAYS,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Initialize heavyweight model and storage adapters in a background thread.

    Transient failures are retried with growing delays while readiness stays
    "preparing"; only the last failure marks the runtime as failed.
    """
    for attempt in range(len(delays) + 1):
        try:
            from backend.api.dependencies import _shared_document_repository, reranker

            setup_llm_and_embeddings()
            reranker.warm_up()
            repository = _shared_document_repository()
            if not repository.is_ready():
                raise RuntimeError("Qdrant is unavailable")
            runtime_state.mark_ready()
            return
        except Exception:
            if attempt == len(delays):
                runtime_state.mark_failed()
                logger.exception("Runtime initialization failed")
                return
            logger.warning(
                "Runtime initialization failed; retrying in %s s",
                delays[attempt],
                exc_info=True,
            )
            sleep(delays[attempt])


def _max_request_bytes() -> int:
    """Return the HTTP body ceiling, including multipart overhead."""
    from backend.api.dependencies import REQUEST_CEILING_BYTES

    return REQUEST_CEILING_BYTES


def warn_if_upload_spool_is_small(max_request_bytes: int) -> bool:
    """Log when the temporary directory cannot hold the largest upload.

    Starlette spools multipart files above 1 MiB to the temporary directory;
    a smaller filesystem makes large batches fail with a storage error.
    Returns whether a warning was logged.
    """
    directory = tempfile.gettempdir()
    try:
        total = shutil.disk_usage(directory).total
    except OSError:
        return False
    if total >= max_request_bytes:
        return False
    logger.warning(
        "upload_spool_too_small directory=%s size_mb=%d max_request_mb=%d; "
        "raise PARSRAG_TMPFS_SIZE or lower PARSRAG_MAX_REQUEST_BYTES",
        directory,
        total // 1024 // 1024,
        max_request_bytes // 1024 // 1024,
    )
    return True


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Start heavyweight initialization without blocking the local interface."""
    warn_if_upload_spool_is_small(_max_request_bytes())
    if os.getenv("PARSRAG_SKIP_MODEL_SETUP") == "1":
        runtime_state.mark_ready()
    else:
        Thread(target=_initialize_runtime, daemon=True, name="parsrag-init").start()
    yield


app = FastAPI(title="ParsRAG API", version="1.1.0", lifespan=lifespan)

trusted_origins = configured_browser_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=trusted_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(TrustedOriginMiddleware, allowed_origins=trusted_origins)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=configured_hosts())
app.add_middleware(ContentLengthLimitMiddleware, max_bytes=_max_request_bytes())
register_exception_handlers(app)
app.include_router(api_router)

# Mount built frontend SPA if available
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    app.mount(
        "/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend"
    )
