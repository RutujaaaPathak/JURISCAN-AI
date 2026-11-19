"""Encrypted local file storage for uploaded documents.

Uploads are encrypted with the document's data key and written under
``<data_dir>/uploads`` using opaque UUID filenames. Writes are atomic: the
envelope is fsynced to a temporary file in the managed directory and then
replaced into place, and the temporary file is removed if anything fails.
Stored paths are considered private and must never be returned to API clients.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from uuid import uuid4

from app.config import settings
from app.services.document_crypto import (
    DocumentEncryptionError,
    decrypt_file,
    encrypt_file,
)

_READ_DENIED = "Stored document file is outside the managed upload directory."
_READ_FAILED = "Stored document file could not be read."


def compute_content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def upload_dir() -> Path:
    """Return (and create) the managed upload directory."""

    directory = Path(settings.data_dir) / "uploads"
    directory.mkdir(parents=True, exist_ok=True)
    return directory.resolve()


def is_managed_path(path: str | Path | None) -> bool:
    """True when ``path`` lives inside the managed upload directory."""

    if not path:
        return False
    try:
        candidate = Path(path).resolve()
    except OSError:
        return False
    return candidate.parent == upload_dir()


def save_upload(
    data: bytes,
    *,
    dek: bytes,
    document_id: int,
    content_hash: str,
) -> str:
    """Encrypt and atomically persist raw upload bytes; return the private path."""

    directory = upload_dir()
    destination = (directory / f"{uuid4().hex}.jse").resolve()
    if destination.parent != directory:
        raise ValueError("Refusing to write outside the managed upload directory.")

    envelope = encrypt_file(
        data,
        dek,
        document_id=document_id,
        content_hash=content_hash,
    )

    descriptor, temp_name = tempfile.mkstemp(
        dir=directory, prefix=".upload-", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(envelope)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, destination)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return str(destination)


def read_upload(
    path: str | Path | None,
    *,
    dek: bytes,
    document_id: int,
    content_hash: str,
) -> bytes:
    """Read and decrypt a managed upload, rejecting unmanaged paths."""

    if not is_managed_path(path):
        raise DocumentEncryptionError(_READ_DENIED)
    try:
        envelope = Path(path).read_bytes()
    except OSError:
        raise DocumentEncryptionError(_READ_FAILED) from None
    return decrypt_file(
        envelope,
        dek,
        document_id=document_id,
        content_hash=content_hash,
    )


def delete_upload(path: str | Path | None) -> bool:
    """Delete a stored upload, but only if it is inside the managed directory."""

    if not is_managed_path(path):
        return False
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        return False
    return True


__all__ = [
    "compute_content_hash",
    "delete_upload",
    "is_managed_path",
    "read_upload",
    "save_upload",
    "upload_dir",
]
