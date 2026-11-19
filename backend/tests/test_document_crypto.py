import base64
import secrets
from types import SimpleNamespace

import pytest

from app.services.document_crypto import (
    ENVELOPE_VERSION,
    FILE_MAGIC,
    TEXT_MAGIC,
    DocumentEncryptionError,
    KeyRing,
    create_document_key,
    decrypt_file,
    decrypt_text,
    encrypt_file,
    encrypt_text,
    generate_dek,
    is_encrypted_file,
    is_encrypted_text,
    rewrap_dek,
    unwrap_dek,
    unwrap_document_key,
    wrap_dek,
)

KEY_V1 = secrets.token_bytes(32)
KEY_V2 = bytes(byte ^ 0xFF for byte in KEY_V1)


def _b64(key: bytes) -> str:
    return base64.b64encode(key).decode("ascii")


def _key_json(**keys: bytes) -> str:
    return "{" + ",".join(
        f'"{key_id}":"{_b64(key)}"' for key_id, key in keys.items()
    ) + "}"


def _ring(**keys: bytes) -> KeyRing:
    active_key_id = next(iter(keys))
    return KeyRing(keys, active_key_id)


def test_key_ring_parses_json_and_selects_active_key():
    raw = _key_json(v1=KEY_V1, v2=KEY_V2)
    ring = KeyRing.from_json(raw, "v2")

    assert ring.active_key_id == "v2"
    assert ring.active_key == KEY_V2
    assert ring.get_key("v1") == KEY_V1


def test_key_ring_from_settings_reads_explicit_configuration():
    config = SimpleNamespace(
        document_encryption_keys=_key_json(v1=KEY_V1),
        document_encryption_active_key_id="v1",
    )

    ring = KeyRing.from_settings(config)

    assert ring.get_key("v1") == KEY_V1


def test_key_ring_repr_does_not_expose_key_material():
    ring = _ring(v1=KEY_V1)

    text = repr(ring)

    assert "v1" in text
    assert _b64(KEY_V1) not in text
    assert KEY_V1.hex() not in text


@pytest.mark.parametrize(
    "keys,active_key_id",
    [
        ({}, "v1"),
        ({"v1": b"short"}, "v1"),
        ({"v1": KEY_V1}, "v2"),
        ({"bad key": KEY_V1}, "bad key"),
        ({"v1": KEY_V1}, ""),
    ],
)
def test_invalid_key_ring_is_rejected(keys, active_key_id):
    with pytest.raises(DocumentEncryptionError):
        KeyRing(keys, active_key_id)


@pytest.mark.parametrize(
    "raw,active_key_id",
    [
        ("not-json", "v1"),
        ("[]", "v1"),
        ('{"v1":"not-base64!"}', "v1"),
        ('{"v1":"eA=="}', "v1"),
        (
            '{"v1":"AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=",'
            '"v1":"AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="}',
            "v1",
        ),
    ],
)
def test_invalid_key_ring_json_is_rejected(raw, active_key_id):
    with pytest.raises(DocumentEncryptionError):
        KeyRing.from_json(raw, active_key_id)


def test_generate_dek_returns_unique_32_byte_keys():
    first = generate_dek()
    second = generate_dek()

    assert len(first) == 32
    assert len(second) == 32
    assert first != second


def test_wrapped_dek_round_trip_and_unique_nonce():
    dek = generate_dek()
    first = wrap_dek(dek, KEY_V1, document_id=42, key_id="v1")
    second = wrap_dek(dek, KEY_V1, document_id=42, key_id="v1")

    assert first != second
    assert len(base64.b64decode(first)) == 12 + 32 + 16
    assert unwrap_dek(first, KEY_V1, document_id=42, key_id="v1") == dek


def test_wrapped_dek_rejects_wrong_document_key_id_or_kek():
    dek = generate_dek()
    wrapped = wrap_dek(dek, KEY_V1, document_id=42, key_id="v1")

    for document_id, key_id in [(43, "v1"), (42, "v2")]:
        with pytest.raises(DocumentEncryptionError):
            unwrap_dek(
                wrapped,
                KEY_V1,
                document_id=document_id,
                key_id=key_id,
            )

    with pytest.raises(DocumentEncryptionError):
        unwrap_dek(wrapped, KEY_V2, document_id=42, key_id="v1")


@pytest.mark.parametrize(
    "wrapped",
    [
        "",
        "not-base64!",
        _b64(b"short"),
        _b64(b"\x00" * 60),
    ],
)
def test_wrapped_dek_rejects_invalid_envelopes(wrapped):
    with pytest.raises(DocumentEncryptionError):
        unwrap_dek(wrapped, KEY_V1, document_id=42, key_id="v1")


def test_create_and_unwrap_document_key_uses_active_key():
    ring = _ring(v1=KEY_V1)

    dek, wrapped, key_id = create_document_key(ring, document_id=42)

    assert key_id == "v1"
    assert len(dek) == 32
    assert unwrap_document_key(
        wrapped,
        ring,
        document_id=42,
        key_id=key_id,
    ) == dek


def test_file_round_trip_and_envelope_header():
    dek = generate_dek()
    plaintext = b"%PDF-1.7 confidential contract bytes \x00\xff"

    envelope = encrypt_file(
        plaintext,
        dek,
        document_id=42,
        content_hash="a" * 64,
    )

    assert envelope[:4] == FILE_MAGIC
    assert envelope[4] == ENVELOPE_VERSION
    assert is_encrypted_file(envelope)
    assert decrypt_file(
        envelope,
        dek,
        document_id=42,
        content_hash="a" * 64,
    ) == plaintext


def test_file_encryption_uses_unique_nonces():
    dek = generate_dek()

    nonces = {
        encrypt_file(
            b"same plaintext",
            dek,
            document_id=42,
            content_hash="a" * 64,
        )[5:17]
        for _ in range(20)
    }

    assert len(nonces) == 20


def test_file_encryption_round_trips_empty_input():
    dek = generate_dek()
    envelope = encrypt_file(
        b"",
        dek,
        document_id=42,
        content_hash="a" * 64,
    )

    assert decrypt_file(
        envelope,
        dek,
        document_id=42,
        content_hash="a" * 64,
    ) == b""


def test_file_rejects_wrong_document_or_content_hash():
    dek = generate_dek()
    envelope = encrypt_file(
        b"contract",
        dek,
        document_id=42,
        content_hash="a" * 64,
    )

    for document_id, content_hash in [(43, "a" * 64), (42, "b" * 64)]:
        with pytest.raises(DocumentEncryptionError):
            decrypt_file(
                envelope,
                dek,
                document_id=document_id,
                content_hash=content_hash,
            )


@pytest.mark.parametrize("offset", [0, 4, 5, 16, -1])
def test_file_rejects_header_nonce_and_ciphertext_tampering(offset):
    dek = generate_dek()
    envelope = bytearray(
        encrypt_file(
            b"contract",
            dek,
            document_id=42,
            content_hash="a" * 64,
        )
    )
    envelope[offset] ^= 0x01

    with pytest.raises(DocumentEncryptionError):
        decrypt_file(
            bytes(envelope),
            dek,
            document_id=42,
            content_hash="a" * 64,
        )


@pytest.mark.parametrize("envelope", [b"", b"JSC1", b"JSC1\x01" + b"\x00" * 27])
def test_file_rejects_truncated_or_invalid_envelopes(envelope):
    with pytest.raises(DocumentEncryptionError):
        decrypt_file(
            envelope,
            generate_dek(),
            document_id=42,
            content_hash="a" * 64,
        )


def test_text_round_trip_and_envelope_header():
    dek = generate_dek()
    plaintext = "1. Indemnity\nSupplier shall indemnify the Customer. \u00a7 5"

    envelope = encrypt_text(
        plaintext,
        dek,
        document_id=42,
        field_name="clause:3:text",
    )
    raw = base64.b64decode(envelope)

    assert raw[:4] == TEXT_MAGIC
    assert raw[4] == ENVELOPE_VERSION
    assert is_encrypted_text(envelope)
    assert decrypt_text(
        envelope,
        dek,
        document_id=42,
        field_name="clause:3:text",
    ) == plaintext


def test_text_encryption_uses_unique_nonces():
    dek = generate_dek()

    nonces = {
        base64.b64decode(
            encrypt_text(
                "same text",
                dek,
                document_id=42,
                field_name="text_content",
            )
        )[5:17]
        for _ in range(20)
    }

    assert len(nonces) == 20


def test_text_rejects_wrong_document_or_field():
    dek = generate_dek()
    envelope = encrypt_text(
        "contract",
        dek,
        document_id=42,
        field_name="text_content",
    )

    for document_id, field_name in [
        (43, "text_content"),
        (42, "clause:1:text"),
    ]:
        with pytest.raises(DocumentEncryptionError):
            decrypt_text(
                envelope,
                dek,
                document_id=document_id,
                field_name=field_name,
            )


@pytest.mark.parametrize("offset", [0, 4, 5, 16, -1])
def test_text_rejects_header_nonce_and_ciphertext_tampering(offset):
    dek = generate_dek()
    envelope = bytearray(
        base64.b64decode(
            encrypt_text(
                "contract",
                dek,
                document_id=42,
                field_name="text_content",
            )
        )
    )
    envelope[offset] ^= 0x01

    with pytest.raises(DocumentEncryptionError):
        decrypt_text(
            base64.b64encode(bytes(envelope)).decode("ascii"),
            dek,
            document_id=42,
            field_name="text_content",
        )


@pytest.mark.parametrize("envelope", ["", "legacy plaintext", "not-base64!"])
def test_text_has_no_plaintext_fallback(envelope):
    assert is_encrypted_text(envelope) is False
    with pytest.raises(DocumentEncryptionError):
        decrypt_text(
            envelope,
            generate_dek(),
            document_id=42,
            field_name="text_content",
        )


def test_key_rotation_rewraps_without_changing_payload_ciphertexts():
    old_ring = _ring(v1=KEY_V1)
    new_ring = _ring(v2=KEY_V2)
    dek, wrapped, key_id = create_document_key(old_ring, document_id=42)
    file_envelope = encrypt_file(
        b"contract",
        dek,
        document_id=42,
        content_hash="a" * 64,
    )
    text_envelope = encrypt_text(
        "contract text",
        dek,
        document_id=42,
        field_name="text_content",
    )

    rewrapped = rewrap_dek(
        wrapped,
        KEY_V1,
        KEY_V2,
        document_id=42,
        old_key_id=key_id,
        new_key_id="v2",
    )
    rotated_dek = unwrap_document_key(
        rewrapped,
        new_ring,
        document_id=42,
        key_id="v2",
    )

    assert rotated_dek == dek
    assert rewrapped != wrapped
    assert decrypt_file(
        file_envelope,
        rotated_dek,
        document_id=42,
        content_hash="a" * 64,
    ) == b"contract"
    assert decrypt_text(
        text_envelope,
        rotated_dek,
        document_id=42,
        field_name="text_content",
    ) == "contract text"


def test_errors_do_not_expose_key_material():
    dek = generate_dek()
    envelope = encrypt_file(
        b"contract",
        dek,
        document_id=42,
        content_hash="a" * 64,
    )

    with pytest.raises(DocumentEncryptionError) as exc_info:
        decrypt_file(
            envelope,
            KEY_V1,
            document_id=42,
            content_hash="a" * 64,
        )

    message = str(exc_info.value)
    assert _b64(KEY_V1) not in message
    assert KEY_V1.hex() not in message
    assert str(dek) not in message


def test_is_encrypted_helpers_reject_plaintext_and_wrong_magic():
    assert is_encrypted_file(b"plaintext") is False
    assert is_encrypted_text("plaintext") is False
    assert is_encrypted_file(b"XXXX\x01" + b"\x00" * 28) is False
    assert is_encrypted_text(
        base64.b64encode(b"XXXX\x01" + b"\x00" * 28).decode("ascii")
    ) is False


@pytest.mark.parametrize(
    "invalid_id",
    [True, False, 0, -5, "doc:123", "", None, 3.14],
)
def test_aad_rejects_invalid_document_ids(invalid_id):
    dek = generate_dek()
    with pytest.raises(DocumentEncryptionError):
        encrypt_file(b"data", dek, document_id=invalid_id, content_hash="a" * 64)
    with pytest.raises(DocumentEncryptionError):
        encrypt_text("data", dek, document_id=invalid_id, field_name="text_content")
    with pytest.raises(DocumentEncryptionError):
        wrap_dek(dek, KEY_V1, document_id=invalid_id, key_id="v1")


@pytest.mark.parametrize(
    "invalid_hash",
    ["", "hash:with:colon", "hash\nwithnewline", None, 123],
)
def test_file_aad_rejects_invalid_content_hash(invalid_hash):
    dek = generate_dek()
    with pytest.raises(DocumentEncryptionError):
        encrypt_file(b"data", dek, document_id=42, content_hash=invalid_hash)


@pytest.mark.parametrize(
    "invalid_field",
    ["", "field\x00null", "field\nnewline", None, 123],
)
def test_text_aad_rejects_invalid_field_name(invalid_field):
    dek = generate_dek()
    with pytest.raises(DocumentEncryptionError):
        encrypt_text("data", dek, document_id=42, field_name=invalid_field)


def test_cross_envelope_substitution_is_prevented():
    dek = generate_dek()
    file_env = encrypt_file(
        b"contract",
        dek,
        document_id=42,
        content_hash="a" * 64,
    )
    text_env = encrypt_text(
        "contract",
        dek,
        document_id=42,
        field_name="text_content",
    )

    # File envelope passed to text decryptor
    with pytest.raises(DocumentEncryptionError):
        decrypt_text(
            base64.b64encode(file_env).decode("ascii"),
            dek,
            document_id=42,
            field_name="text_content",
        )

    # Text envelope raw bytes passed to file decryptor
    with pytest.raises(DocumentEncryptionError):
        decrypt_file(
            base64.b64decode(text_env),
            dek,
            document_id=42,
            content_hash="a" * 64,
        )


@pytest.mark.parametrize("length", [1, 2, 4, 5, 10, 16, 25, 32])
def test_file_rejects_arbitrary_truncation(length):
    dek = generate_dek()
    envelope = encrypt_file(
        b"confidential document content",
        dek,
        document_id=42,
        content_hash="a" * 64,
    )
    truncated = envelope[:length]
    with pytest.raises(DocumentEncryptionError):
        decrypt_file(
            truncated,
            dek,
            document_id=42,
            content_hash="a" * 64,
        )


def test_unwrap_document_key_fails_if_key_id_unavailable():
    ring = _ring(v1=KEY_V1)
    dek, wrapped, _ = create_document_key(ring, document_id=42)

    with pytest.raises(DocumentEncryptionError):
        unwrap_document_key(
            wrapped,
            ring,
            document_id=42,
            key_id="missing_key_id",
        )
