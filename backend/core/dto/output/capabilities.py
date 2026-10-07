"""Outbound DTOs that advertise runtime capabilities to clients."""

from pydantic import BaseModel, Field


class IngestionCapabilities(BaseModel):
    """Runtime upload contract advertised to browser clients."""

    max_files_per_session: int = Field(..., ge=1)
    max_file_size_bytes: int = Field(..., ge=1)
    max_batch_size_bytes: int = Field(..., ge=1)
    supported_extensions: list[str]
    ocr_enabled: bool


class AppCapabilitiesResponse(BaseModel):
    """Discoverable server capabilities that keep clients in sync."""

    ingestion: IngestionCapabilities
