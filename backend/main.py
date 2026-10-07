"""FastAPI application assembly: middleware, error mapping, routes, and the SPA."""

import logging
import os
from collections.abc import AsyncIterator
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
    TrustedOriginMiddleware,
    configured_browser_origins,
)
from backend.api.routes import router as api_router
from backend.core.domain.upload_policy import UploadPolicy
from backend.core.runtime.readiness import runtime_state
from backend.infrastructure.llm.factory import setup_llm_and_embeddings

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


def _initialize_runtime() -> None:
    """Initialize heavyweight model and storage adapters in a background thread."""
    try:
        from backend.api.dependencies import _shared_document_repository

        setup_llm_and_embeddings()
        repository = _shared_document_repository()
        if not repository.is_ready():
            raise RuntimeError("Qdrant is unavailable")
        runtime_state.mark_ready()
    except Exception:
        runtime_state.mark_failed()
        logger.exception("Runtime initialization failed")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Start heavyweight initialization without blocking the local interface."""
    if os.getenv("PARSRAG_SKIP_MODEL_SETUP") == "1":
        runtime_state.mark_ready()
    else:
        Thread(target=_initialize_runtime, daemon=True, name="parsrag-init").start()
    yield


app = FastAPI(title="ParsRAG API", version="0.2.0", lifespan=lifespan)

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
app.add_middleware(
    ContentLengthLimitMiddleware,
    max_bytes=int(
        os.getenv(
            "PARSRAG_MAX_REQUEST_BYTES",
            str(UploadPolicy.from_environment().max_batch_bytes + 10 * 1024 * 1024),
        )
    ),
)
register_exception_handlers(app)
app.include_router(api_router)

# Mount built frontend SPA if available
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    app.mount(
        "/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend"
    )
