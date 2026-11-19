"""Encryption-aware access to persisted document files and text payloads.

``encryption_version = 0`` marks legacy plaintext rows explicitly. Version 1
requires a wrapped document key and encoded ``JSE1``/``JSC1`` envelopes; there
is no fallback from a failed version-1 decryption to plaintext.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.config import settings
from app.services.document_crypto import (
    DocumentEncryptionError,
    KeyRing,
    create_document_key,
    decrypt_text,
    encrypt_text,
    unwrap_document_key,
)
from app.services.storage import is_managed_path, read_upload

if TYPE_CHECKING:
    from app.models import Clause, Document

LEGACY_PLAINTEXT_VERSION = 0
ENCRYPTED_VERSION = 1
TEXT_CONTENT_FIELD = "text_content"

_MISSING_METADATA = "Document encryption metadata is missing or unsupported."
_FILE_UNAVAILABLE = "Stored document file is unavailable."
_FILE_READ_FAILED = "Stored document file could not be read."
_KEY_REPLACEMENT_REFUSED = "Refusing to replace an active document key."


def key_ring() -> KeyRing:
    return KeyRing.from_settings(settings)


def _require_supported_version(document: Document) -> int:
    version = document.encryption_version
    if version not in (LEGACY_PLAINTEXT_VERSION, ENCRYPTED_VERSION):
        raise DocumentEncryptionError(_MISSING_METADATA)
    return version


def document_dek(document: Document) -> bytes:
    """Unwrap the document data key. Version-0 rows have no key."""

    if _require_supported_version(document) != ENCRYPTED_VERSION:
        raise DocumentEncryptionError(_MISSING_METADATA)
    if not document.encryption_key_id or not document.dek_wrapped:
        raise DocumentEncryptionError(_MISSING_METADATA)
    return unwrap_document_key(
        document.dek_wrapped,
        key_ring(),
        document_id=document.id,
        key_id=document.encryption_key_id,
    )


def document_dek_if_encrypted(document: Document) -> bytes | None:
    if _require_supported_version(document) == LEGACY_PLAINTEXT_VERSION:
        return None
    return document_dek(document)


def assign_document_key(
    db: Session,
    document: Document,
    *,
    reencrypt_existing: bool = False,
) -> bytes:
    """Attach a newly generated DEK, optionally re-encrypting stored clauses.

    Existing version-1 rows keep their key unless ``reencrypt_existing`` is
    requested. That mode decrypts every clause with the old DEK before writing
    ciphertext under the new one, so a retry can rotate keys without orphaning
    clause rows or changing their ids.
    """

    version = _require_supported_version(document)
    if version == ENCRYPTED_VERSION and not reencrypt_existing:
        return document_dek(document)
    if document.id is None:
        db.flush()

    old_dek = document_dek(document) if version == ENCRYPTED_VERSION else None
    new_dek, wrapped, key_id = create_document_key(
        key_ring(), document_id=document.id
    )

    if reencrypt_existing:
        for clause in document.clauses:
            text = clause_plaintext(document, clause, dek=old_dek)
            normalized = clause_plaintext(
                document, clause, dek=old_dek, normalized=True
            )
            if text is not None:
                clause.text = encrypt_clause_text(
                    text, new_dek, document.id, clause.clause_number, "text"
                )
            if normalized is not None:
                clause.normalized_text = encrypt_clause_text(
                    normalized,
                    new_dek,
                    document.id,
                    clause.clause_number,
                    "normalized_text",
                )

    document.encryption_version = ENCRYPTED_VERSION
    document.encryption_key_id = key_id
    document.dek_wrapped = wrapped
    return new_dek


def ensure_document_key(db: Session, document: Document) -> bytes:
    """Return the document DEK, upgrading an explicit legacy row if needed."""

    if _require_supported_version(document) == LEGACY_PLAINTEXT_VERSION:
        return assign_document_key(db, document)
    return document_dek(document)


def encrypt_document_text(text: str, dek: bytes, document_id: int) -> str:
    return encrypt_text(
        text,
        dek,
        document_id=document_id,
        field_name=TEXT_CONTENT_FIELD,
    )


def encrypt_clause_text(
    text: str,
    dek: bytes,
    document_id: int,
    clause_number: int,
    field: str,
) -> str:
    if field not in ("text", "normalized_text"):
        raise DocumentEncryptionError(_MISSING_METADATA)
    return encrypt_text(
        text,
        dek,
        document_id=document_id,
        field_name=f"clause:{clause_number}:{field}",
    )


def document_plaintext(document: Document, *, dek: bytes | None = None) -> str | None:
    value = document.text_content
    if value is None:
        return None
    if _require_supported_version(document) == LEGACY_PLAINTEXT_VERSION:
        return value
    key = dek if dek is not None else document_dek(document)
    return decrypt_text(
        value,
        key,
        document_id=document.id,
        field_name=TEXT_CONTENT_FIELD,
    )


def clause_plaintext(
    document: Document,
    clause: Clause,
    *,
    dek: bytes | None = None,
    normalized: bool = False,
) -> str | None:
    value = clause.normalized_text if normalized else clause.text
    if value is None:
        return None
    if _require_supported_version(document) == LEGACY_PLAINTEXT_VERSION:
        return value
    key = dek if dek is not None else document_dek(document)
    field = f"clause:{clause.clause_number}:{'normalized_text' if normalized else 'text'}"
    return decrypt_text(
        value,
        key,
        document_id=document.id,
        field_name=field,
    )


def plaintext_clause_view(
    document: Document,
    clause: Clause,
    *,
    dek: bytes | None = None,
) -> SimpleNamespace:
    """Return a detached, decrypted clause view for report rendering."""

    return SimpleNamespace(
        id=clause.id,
        document_id=clause.document_id,
        clause_number=clause.clause_number,
        heading=clause.heading,
        text=clause_plaintext(document, clause, dek=dek),
        normalized_text=clause_plaintext(
            document, clause, dek=dek, normalized=True
        ),
        normalization_changes=clause.normalization_changes,
        ocr_quality=clause.ocr_quality,
        start_offset=clause.start_offset,
        end_offset=clause.end_offset,
        page_number=clause.page_number,
        clause_type=clause.clause_type,
        risk_level=clause.risk_level,
        label=clause.label,
        level=clause.level,
        parent_id=clause.parent_id,
        created_at=clause.created_at,
        updated_at=clause.updated_at,
    )


def plaintext_clauses(
    document: Document, clauses: list[Clause]
) -> list[SimpleNamespace]:
    dek = document_dek_if_encrypted(document)
    return [plaintext_clause_view(document, clause, dek=dek) for clause in clauses]


def document_file_bytes(document: Document) -> bytes:
    """Read the original upload, decrypting it for version-1 documents."""

    if not document.storage_path:
        raise DocumentEncryptionError(_FILE_UNAVAILABLE)
    version = _require_supported_version(document)
    if version == ENCRYPTED_VERSION:
        if not document.content_hash:
            raise DocumentEncryptionError(_MISSING_METADATA)
        return read_upload(
            document.storage_path,
            dek=document_dek(document),
            document_id=document.id,
            content_hash=document.content_hash,
        )
    if not is_managed_path(document.storage_path):
        raise DocumentEncryptionError(_FILE_UNAVAILABLE)
    try:
        return Path(document.storage_path).read_bytes()
    except OSError:
        raise DocumentEncryptionError(_FILE_READ_FAILED) from None


__all__ = [
    "ENCRYPTED_VERSION",
    "LEGACY_PLAINTEXT_VERSION",
    "TEXT_CONTENT_FIELD",
    "assign_document_key",
    "clause_plaintext",
    "document_dek",
    "document_dek_if_encrypted",
    "document_file_bytes",
    "document_plaintext",
    "encrypt_clause_text",
    "encrypt_document_text",
    "ensure_document_key",
    "key_ring",
    "plaintext_clause_view",
    "plaintext_clauses",
]
