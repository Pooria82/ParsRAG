"""Content-based upload validation performed before any parser touches the bytes."""

import io
import zipfile
from pathlib import PurePath

from backend.core.domain.exceptions import DocumentError
from backend.core.domain.upload_policy import (
    IMAGE_EXTENSIONS,
    OFFICE_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    TEXT_EXTENSIONS,
)

# Password-protected Office files are OLE compound files, not ZIP archives.
OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
MAX_ARCHIVE_ENTRIES = 10_000
MAX_ARCHIVE_EXPANDED_BYTES = 200 * 1024 * 1024
MAX_ARCHIVE_RATIO = 200


def validate_archive(data: bytes, extension: str) -> None:
    """Reject forged or explosively expanded Office archives.

    Raises:
        ValueError: The archive is malformed, too large, or not the claimed type.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_ENTRIES:
                raise DocumentError(
                    "The Office archive contains too many entries.", "unsafe_archive"
                )
            expanded = sum(entry.file_size for entry in entries)
            if expanded > MAX_ARCHIVE_EXPANDED_BYTES:
                raise DocumentError(
                    "The Office archive expands beyond the safe limit.",
                    "unsafe_archive",
                )
            for entry in entries:
                if entry.file_size and entry.compress_size == 0:
                    raise DocumentError(
                        "The Office archive has an invalid compression ratio.",
                        "unsafe_archive",
                    )
                if (
                    entry.compress_size
                    and entry.file_size / entry.compress_size > MAX_ARCHIVE_RATIO
                ):
                    raise DocumentError(
                        "The Office archive has a suspicious compression ratio.",
                        "unsafe_archive",
                    )
            names = {entry.filename for entry in entries}
    except zipfile.BadZipFile as exc:
        raise DocumentError(
            "The file is not a valid Office document archive.", "corrupt_file"
        ) from exc
    required = "word/document.xml" if extension == ".docx" else "ppt/presentation.xml"
    if "[Content_Types].xml" not in names or required not in names:
        raise DocumentError(
            f"The file content does not match its {extension.upper()} extension.",
            "file_type_mismatch",
        )


def validate_upload(filename: str, data: bytes) -> None:
    """Validate filename boundaries and file signatures before parser work.

    Raises:
        ValueError: The filename is unsafe or the content contradicts its extension.
    """
    if (
        len(filename) > 255
        or PurePath(filename).name != filename
        or "/" in filename
        or "\\" in filename
    ):
        raise DocumentError("The filename is invalid.", "invalid_filename")
    extension = PurePath(filename).suffix.lower()
    if extension == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise DocumentError(
                "The file content does not match its PDF extension.",
                "file_type_mismatch",
            )
        return
    if extension in OFFICE_EXTENSIONS:
        if data.startswith(OLE_SIGNATURE):
            raise DocumentError(
                "The Office document is password-protected.", "encrypted_document"
            )
        if not data.startswith(b"PK"):
            raise DocumentError(
                "The file content does not match its Office extension.",
                "file_type_mismatch",
            )
        validate_archive(data, extension)
        return
    if extension in (*IMAGE_EXTENSIONS, *TEXT_EXTENSIONS):
        return
    supported = ", ".join(SUPPORTED_EXTENSIONS)
    raise DocumentError(
        f"Unsupported file format. Supported extensions: {supported}.",
        "unsupported_file",
    )
