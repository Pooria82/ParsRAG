import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router as api_router
from backend.core.exceptions import ParsRAGError
from backend.infrastructure.llm.factory import setup_llm_and_embeddings
from backend.infrastructure.parsers.document_parser import EmptyDocumentError

# Load environment variables
load_dotenv()

# Configure minimal logging
logger = logging.getLogger(__name__)

# Initialize LLM and Embeddings globally
if os.getenv("PARSRAG_SKIP_MODEL_SETUP") != "1":
    setup_llm_and_embeddings()

app = FastAPI(title="ParsRAG API", version="1.0.0")

# Allow CORS for Chainlit (localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
