"""Use case: advertise the effective ingestion contract to clients."""

import os
from collections.abc import Callable

from backend.core.domain.upload_policy import UploadPolicy
from backend.core.dto.output.capabilities import (
    AppCapabilitiesResponse,
    IngestionCapabilities,
)

_TRUTHY = {"1", "true", "yes", "on"}


class DescribeCapabilities:
    """Keep browser validation synchronized with server-side limits."""

    def __init__(
        self,
        policy_provider: Callable[[], UploadPolicy] = UploadPolicy.from_environment,
    ) -> None:
        """Bind the upload policy source."""
        self._policy_provider = policy_provider

    def execute(self) -> AppCapabilitiesResponse:
        """Return limits, supported extensions, and OCR availability."""
        policy = self._policy_provider()
        return AppCapabilitiesResponse(
            ingestion=IngestionCapabilities(
                max_files_per_session=policy.max_files_per_session,
                max_file_size_bytes=policy.max_file_bytes,
                max_batch_size_bytes=policy.max_batch_bytes,
                supported_extensions=list(policy.supported_extensions),
                ocr_enabled=os.getenv("OCR_ENABLED", "0").strip().lower() in _TRUTHY,
            )
        )
