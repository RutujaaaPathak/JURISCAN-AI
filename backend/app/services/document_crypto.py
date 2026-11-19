"""AES-256-GCM envelope encryption for document payloads."""

from __future__ import annotations

import base64
import binascii
import os
import re
from collections.abc import Mapping
from typing import Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config.settings import parse_document_encryption_keys

FILE_MAGIC = b"JSC1"
TEXT_MAGIC = b"JSE1"
ENVELOPE_VERSION = 1
KEY_SIZE = 32
NONCE_SIZE = 12
_HEADER_SIZE = len(FILE_MAGIC) + 1

_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")

_INVALID_CONFIG = "Invalid document encryption key configuration."
_KEY_UNAVAILABLE = "Document encryption key is unavailable."
_INVALID_CIPHERTEXT = (
    "Document ciphertext is invalid, unsupported, or has been tampered with."
)
_ENCRYPTION_FAILED = "Document encryption failed."
_INVALID_INPUT = "Invalid document encryption input."


class DocumentEncryptionError(Exception):
    """Raised when document key configuration or ciphertext validation fails."""


class KeyProvider(Protocol):
    @property
    def active_key_id(self) -> str: ...

    def get_key(self, key_id: str) -> bytes: ...


class KeyRing:
    def __init__(
        self,
        keys: Mapping[str, bytes],
        active_key_id: str,
    ) -> None:
        if not isinstance(active_key_id, str) or not _KEY_ID.fullmatch(
            active_key_id
        ):
            raise DocumentEncryptionError(_INVALID_CONFIG)
        if not keys:
            raise DocumentEncryptionError(_INVALID_CONFIG)
        normalized: dict[str, bytes] = {}
        for key_id, key in keys.items():
            if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
                raise DocumentEncryptionError(_INVALID_CONFIG)
            if not isinstance(key, (bytes, bytearray)) or len(key) != KEY_SIZE:
                raise DocumentEncryptionError(_INVALID_CONFIG)
            normalized[key_id] = bytes(key)
        if active_key_id not in normalized:
            raise DocumentEncryptionError(_INVALID_CONFIG)
        self._keys = normalized
        self._active_key_id = active_key_id

    @property
    def active_key_id(self) -> str:
        return self._active_key_id

    @property
    def active_key(self) -> bytes:
        return self.get_key(self._active_key_id)

    def get_key(self, key_id: str) -> bytes:
        key = self._keys.get(key_id) if isinstance(key_id, str) else None
        if key is None:
            raise DocumentEncryptionError(_KEY_UNAVAILABLE)
        return key

    @classmethod
    def from_base64(
        cls,
        keys: Mapping[str, str],
        active_key_id: str,
    ) -> "KeyRing":
        decoded: dict[str, bytes] = {}
        for key_id, encoded in keys.items():
            if not isinstance(key_id, str) or not isinstance(encoded, str):
                raise DocumentEncryptionError(_INVALID_CONFIG)
            try:
                key = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError):
                raise DocumentEncryptionError(_INVALID_CONFIG) from None
            if len(key) != KEY_SIZE:
                raise DocumentEncryptionError(_INVALID_CONFIG)
            decoded[key_id] = key
        return cls(decoded, active_key_id)

    @classmethod
    def from_json(cls, raw: str, active_key_id: str) -> "KeyRing":
        if not isinstance(raw, str) or not isinstance(active_key_id, str):
            raise DocumentEncryptionError(_INVALID_CONFIG)
        try:
            keys = parse_document_encryption_keys(raw)
        except ValueError:
            raise DocumentEncryptionError(_INVALID_CONFIG) from None
        return cls.from_base64(keys, active_key_id)

    @classmethod
    def from_settings(cls, config: object) -> "KeyRing":
        raw = getattr(config, "document_encryption_keys", "")
        active_key_id = getattr(config, "document_encryption_active_key_id", "")
        if not isinstance(raw, str) or not isinstance(active_key_id, str):
            raise DocumentEncryptionError(_INVALID_CONFIG)
        return cls.from_json(raw, active_key_id)

    def __repr__(self) -> str:
        return (
            f"KeyRing(active_key_id={self._active_key_id!r}, "
            f"key_count={len(self._keys)})"
        )


def _validate_key(key: bytes) -> None:
    if not isinstance(key, (bytes, bytearray)) or len(key) != KEY_SIZE:
        raise DocumentEncryptionError(_INVALID_INPUT)


def _document_id_text(document_id: int | str) -> str:
    if (
        isinstance(document_id, bool)
        or not isinstance(document_id, (int, str))
        or (isinstance(document_id, int) and document_id <= 0)
    ):
        raise DocumentEncryptionError(_INVALID_INPUT)
    text = str(document_id)
    if not text or ":" in text:
        raise DocumentEncryptionError(_INVALID_INPUT)
    return text


def _field_name_text(field_name: str) -> str:
    if (
        not isinstance(field_name, str)
        or not field_name
        or any(ord(char) < 32 for char in field_name)
    ):
        raise DocumentEncryptionError(_INVALID_INPUT)
    return field_name


def _content_hash_text(content_hash: str) -> str:
    if (
        not isinstance(content_hash, str)
        or not content_hash
        or ":" in content_hash
        or any(ord(char) < 32 for char in content_hash)
    ):
        raise DocumentEncryptionError(_INVALID_INPUT)
    return content_hash


def _key_id_text(key_id: str) -> str:
    if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
        raise DocumentEncryptionError(_INVALID_INPUT)
    return key_id


def dek_aad(document_id: int | str, key_id: str) -> bytes:
    return (
        f"juriscan:dek:v1:{_document_id_text(document_id)}:"
        f"{_key_id_text(key_id)}"
    ).encode("utf-8")


def file_aad(document_id: int | str, content_hash: str) -> bytes:
    return (
        f"juriscan:file:v1:{_document_id_text(document_id)}:"
        f"{_content_hash_text(content_hash)}"
    ).encode("utf-8")


def text_aad(
    document_id: int | str,
    field_name: str,
) -> bytes:
    return (
        f"juriscan:text:v1:{_document_id_text(document_id)}:"
        f"{_field_name_text(field_name)}"
    ).encode("utf-8")


def generate_dek() -> bytes:
    return AESGCM.generate_key(bit_length=KEY_SIZE * 8)


def _pack(magic: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    return magic + bytes([ENVELOPE_VERSION]) + nonce + ciphertext


def _unpack(envelope: bytes, magic: bytes) -> tuple[bytes, bytes]:
    header_size = len(magic) + 1
    if (
        not isinstance(envelope, (bytes, bytearray))
        or len(envelope) < header_size + NONCE_SIZE + 16
        or bytes(envelope[: len(magic)]) != magic
    ):
        raise DocumentEncryptionError(_INVALID_CIPHERTEXT)
    if envelope[len(magic)] != ENVELOPE_VERSION:
        raise DocumentEncryptionError(_INVALID_CIPHERTEXT)
    nonce_start = header_size
    nonce_end = nonce_start + NONCE_SIZE
    return bytes(envelope[nonce_start:nonce_end]), bytes(envelope[nonce_end:])


def _b64_decode(value: str) -> bytes:
    if not isinstance(value, str):
        raise DocumentEncryptionError(_INVALID_CIPHERTEXT)
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise DocumentEncryptionError(_INVALID_CIPHERTEXT) from None


def _b64_encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def wrap_dek(
    dek: bytes,
    kek: bytes,
    *,
    document_id: int | str,
    key_id: str,
) -> str:
    _validate_key(dek)
    _validate_key(kek)
    nonce = os.urandom(NONCE_SIZE)
    try:
        wrapped = AESGCM(kek).encrypt(
            nonce,
            dek,
            dek_aad(document_id, key_id),
        )
    except (TypeError, ValueError):
        raise DocumentEncryptionError(_ENCRYPTION_FAILED) from None
    return _b64_encode(nonce + wrapped)


def unwrap_dek(
    wrapped_dek: str,
    kek: bytes,
    *,
    document_id: int | str,
    key_id: str,
) -> bytes:
    _validate_key(kek)
    raw = _b64_decode(wrapped_dek)
    if len(raw) < NONCE_SIZE + KEY_SIZE + 16:
        raise DocumentEncryptionError(_INVALID_CIPHERTEXT)
    nonce = raw[:NONCE_SIZE]
    wrapped = raw[NONCE_SIZE:]
    try:
        dek = AESGCM(kek).decrypt(
            nonce,
            wrapped,
            dek_aad(document_id, key_id),
        )
    except (InvalidTag, TypeError, ValueError):
        raise DocumentEncryptionError(_INVALID_CIPHERTEXT) from None
    if len(dek) != KEY_SIZE:
        raise DocumentEncryptionError(_INVALID_CIPHERTEXT)
    return dek


def rewrap_dek(
    wrapped_dek: str,
    old_kek: bytes,
    new_kek: bytes,
    *,
    document_id: int | str,
    old_key_id: str,
    new_key_id: str,
) -> str:
    dek = unwrap_dek(
        wrapped_dek,
        old_kek,
        document_id=document_id,
        key_id=old_key_id,
    )
    return wrap_dek(
        dek,
        new_kek,
        document_id=document_id,
        key_id=new_key_id,
    )


def create_document_key(
    provider: KeyProvider,
    *,
    document_id: int | str,
) -> tuple[bytes, str, str]:
    key_id = _key_id_text(provider.active_key_id)
    try:
        kek = provider.get_key(key_id)
    except DocumentEncryptionError:
        raise
    except Exception:
        raise DocumentEncryptionError(_KEY_UNAVAILABLE) from None
    dek = generate_dek()
    wrapped = wrap_dek(
        dek,
        kek,
        document_id=document_id,
        key_id=key_id,
    )
    return dek, wrapped, key_id


def unwrap_document_key(
    wrapped_dek: str,
    provider: KeyProvider,
    *,
    document_id: int | str,
    key_id: str,
) -> bytes:
    try:
        kek = provider.get_key(key_id)
    except DocumentEncryptionError:
        raise
    except Exception:
        raise DocumentEncryptionError(_KEY_UNAVAILABLE) from None
    return unwrap_dek(
        wrapped_dek,
        kek,
        document_id=document_id,
        key_id=key_id,
    )


def encrypt_file(
    plaintext: bytes,
    dek: bytes,
    *,
    document_id: int | str,
    content_hash: str,
) -> bytes:
    _validate_key(dek)
    if not isinstance(plaintext, (bytes, bytearray)):
        raise DocumentEncryptionError(_INVALID_INPUT)
    nonce = os.urandom(NONCE_SIZE)
    try:
        ciphertext = AESGCM(dek).encrypt(
            nonce,
            bytes(plaintext),
            file_aad(document_id, content_hash),
        )
    except (TypeError, ValueError):
        raise DocumentEncryptionError(_ENCRYPTION_FAILED) from None
    return _pack(FILE_MAGIC, nonce, ciphertext)


def decrypt_file(
    envelope: bytes,
    dek: bytes,
    *,
    document_id: int | str,
    content_hash: str,
) -> bytes:
    _validate_key(dek)
    nonce, ciphertext = _unpack(envelope, FILE_MAGIC)
    try:
        return AESGCM(dek).decrypt(
            nonce,
            ciphertext,
            file_aad(document_id, content_hash),
        )
    except (InvalidTag, TypeError, ValueError):
        raise DocumentEncryptionError(_INVALID_CIPHERTEXT) from None


def encrypt_text(
    plaintext: str,
    dek: bytes,
    *,
    document_id: int | str,
    field_name: str,
) -> str:
    _validate_key(dek)
    if not isinstance(plaintext, str):
        raise DocumentEncryptionError(_INVALID_INPUT)
    nonce = os.urandom(NONCE_SIZE)
    try:
        ciphertext = AESGCM(dek).encrypt(
            nonce,
            plaintext.encode("utf-8"),
            text_aad(document_id, field_name),
        )
    except (TypeError, ValueError):
        raise DocumentEncryptionError(_ENCRYPTION_FAILED) from None
    return _b64_encode(_pack(TEXT_MAGIC, nonce, ciphertext))


def decrypt_text(
    envelope: str,
    dek: bytes,
    *,
    document_id: int | str,
    field_name: str,
) -> str:
    _validate_key(dek)
    nonce, ciphertext = _unpack(_b64_decode(envelope), TEXT_MAGIC)
    try:
        plaintext = AESGCM(dek).decrypt(
            nonce,
            ciphertext,
            text_aad(document_id, field_name),
        )
    except (InvalidTag, TypeError, ValueError):
        raise DocumentEncryptionError(_INVALID_CIPHERTEXT) from None
    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError:
        raise DocumentEncryptionError(_INVALID_CIPHERTEXT) from None


def is_encrypted_file(envelope: bytes) -> bool:
    return (
        isinstance(envelope, (bytes, bytearray))
        and len(envelope) >= _HEADER_SIZE
        and bytes(envelope[: len(FILE_MAGIC)]) == FILE_MAGIC
        and envelope[len(FILE_MAGIC)] == ENVELOPE_VERSION
    )


def is_encrypted_text(envelope: str) -> bool:
    try:
        raw = _b64_decode(envelope)
    except DocumentEncryptionError:
        return False
    return (
        len(raw) >= _HEADER_SIZE
        and raw[: len(TEXT_MAGIC)] == TEXT_MAGIC
        and raw[len(TEXT_MAGIC)] == ENVELOPE_VERSION
    )


__all__ = [
    "DocumentEncryptionError",
    "ENVELOPE_VERSION",
    "FILE_MAGIC",
    "KEY_SIZE",
    "KeyProvider",
    "KeyRing",
    "NONCE_SIZE",
    "TEXT_MAGIC",
    "create_document_key",
    "decrypt_file",
    "decrypt_text",
    "dek_aad",
    "encrypt_file",
    "encrypt_text",
    "file_aad",
    "generate_dek",
    "is_encrypted_file",
    "is_encrypted_text",
    "rewrap_dek",
    "text_aad",
    "unwrap_dek",
    "unwrap_document_key",
    "wrap_dek",
]
