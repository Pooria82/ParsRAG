import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routes import router as api_router
from backend.infrastructure.parsers.document_parser import EmptyDocumentError

# Configure minimal logging
logger = logging.getLogger(__name__)

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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catches all unhandled exceptions to prevent stack trace leaks."""
    logger.exception(f"Unhandled Server Error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."},
    )


app.include_router(api_router)
