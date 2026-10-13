"""Local file storage for uploaded documents.

Uploads are written under ``<data_dir>/uploads`` with a server-generated UUID
prefix. The user-supplied filename is never trusted as a path: directory
components are dropped and unsafe characters are replaced, and every resolved
destination is verified to stay inside the managed upload directory. Stored
paths are considered private and must never be returned to API clients.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from uuid import uuid4

from app.config import settings

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def compute_content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def upload_dir() -> Path:
    """Return (and create) the managed upload directory."""

    directory = Path(settings.data_dir) / "uploads"
    directory.mkdir(parents=True, exist_ok=True)
    return directory.resolve()


def _safe_filename(filename: str) -> str:
    """Reduce an arbitrary filename to a safe basename.

    ``Path(...).name`` strips any directory part, so ``../../etc/passwd`` becomes
    ``passwd``; remaining unsafe characters are replaced.
    """

    stem = Path(filename).name
    cleaned = _UNSAFE.sub("_", stem).strip("._") or "document"
    return cleaned[:120]


def is_managed_path(path: str | Path | None) -> bool:
    """True when ``path`` lives inside the managed upload directory."""

    if not path:
        return False
    try:
        candidate = Path(path).resolve()
    except OSError:
        return False
    return candidate.parent == upload_dir()


def save_upload(data: bytes, filename: str) -> str:
    """Persist raw upload bytes and return the stored (private) path string."""

    directory = upload_dir()
    destination = directory / f"{uuid4().hex}_{_safe_filename(filename)}"
    destination = destination.resolve()
    if destination.parent != directory:
        # Defence in depth: should be unreachable given ``_safe_filename``.
        raise ValueError("Refusing to write outside the managed upload directory.")
    destination.write_bytes(data)
    return str(destination)


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
    "save_upload",
    "upload_dir",
]
