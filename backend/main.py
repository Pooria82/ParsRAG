import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Thread

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router as api_router
from backend.core.exceptions import ParsRAGError
from backend.core.runtime import runtime_state
from backend.core.security import (
    ContentLengthLimitMiddleware,
    RequestContextMiddleware,
    TrustedOriginMiddleware,
    configured_browser_origins,
)
from backend.core.upload_policy import UploadPolicy
from backend.infrastructure.llm.factory import setup_llm_and_embeddings
from backend.infrastructure.parsers.document_parser import EmptyDocumentError

# Load environment variables
load_dotenv()

# Configure minimal logging
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


app = FastAPI(title="ParsRAG API", version="1.0.0", lifespan=lifespan)

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


@app.exception_handler(EmptyDocumentError)
async def empty_document_exception_handler(
    request: Request, exc: EmptyDocumentError
) -> JSONResponse:
    """Handles PDF parsing errors gracefully."""
    logger.warning(f"EmptyDocumentError: {exc}")
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


@app.exception_handler(ParsRAGError)
async def parsrag_exception_handler(
    request: Request, exc: ParsRAGError
) -> JSONResponse:
    """Handles domain-level ParsRAG exceptions cleanly."""
    logger.error(f"ParsRAG Domain Error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "A database or service error occurred. Please try again later."
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catches all unhandled exceptions to prevent stack trace leaks."""
    logger.exception(f"Unhandled Server Error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."},
    )


app.include_router(api_router)

# Mount built frontend SPA if available
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    app.mount(
        "/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend"
    )
