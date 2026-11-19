import base64
import secrets

import pytest
from pydantic import ValidationError

from app.config.settings import Settings

_DOCUMENT_KEY_B64 = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
DOCUMENT_ENCRYPTION_KEYS = f'{{"v1":"{_DOCUMENT_KEY_B64}"}}'


def test_default_settings_shape():
    s = Settings(_env_file=None)
    assert s.app_name == "JURISCAN-AI"
    assert s.app_env in {"development", "production", "test", "staging"}
    assert s.api_prefix == "/api"
    assert s.max_upload_size_mb > 0
    assert s.max_pdf_pages > 0
    assert s.ocr_page_batch_size >= 1
    assert s.ocr_timeout_seconds > 0
    assert s.ocr_max_concurrent_inferences >= 1
    assert 0 <= s.ocr_low_confidence_threshold <= 1
    assert 0 <= s.ocr_quality_warning_threshold <= 1
    assert 0 <= s.ocr_native_recheck_threshold <= 1
    assert 0 <= s.ocr_merge_margin <= 1
    assert s.processing_max_concurrent_jobs >= 1
    assert s.processing_stale_sweep_seconds >= 0


def test_database_url_built_from_components():
    s = Settings(
        _env_file=None,
        database_url=None,
        db_host="db.internal",
        db_port=5433,
        db_name="juriscan",
        db_user="app",
        db_password="secret",
    )
    assert s.database_url == "postgresql+psycopg://app:secret@db.internal:5433/juriscan"


def test_database_url_without_password():
    s = Settings(_env_file=None, database_url=None, db_user="app")
    assert s.database_url == "postgresql+psycopg://app@localhost:5432/juriscan"


def test_database_url_explicit_override_wins():
    s = Settings(_env_file=None, database_url="postgresql+psycopg://other@host/x")
    assert s.database_url == "postgresql+psycopg://other@host/x"


def test_unknown_env_fields_ignored():
    s = Settings(_env_file=None, totally_unknown_key=123)
    assert s.app_name == "JURISCAN-AI"


def test_frontend_origin_default():
    s = Settings(_env_file=None)
    assert any("localhost:5173" in origin for origin in s.cors_origins)


def test_development_generates_a_random_secret_instead_of_a_known_default():
    s = Settings(
        _env_file=None,
        app_env="development",
        allow_demo_user=False,
        secret_key="",
    )
    assert len(s.secret_key) >= 32
    assert s.secret_key != "dev-insecure-secret-change-me"
    assert s.allow_demo_user is False


@pytest.mark.parametrize(
    "secret_key",
    ["", "short", "dev-insecure-secret-change-me", "x" * 31],
)
def test_production_rejects_missing_weak_or_default_secret(secret_key):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            app_debug=False,
            secret_key=secret_key,
            document_encryption_active_key_id="v1",
            document_encryption_keys=DOCUMENT_ENCRYPTION_KEYS,
        )


def test_production_rejects_debug_mode():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            app_debug=True,
            secret_key="x" * 48,
            document_encryption_active_key_id="v1",
            document_encryption_keys=DOCUMENT_ENCRYPTION_KEYS,
        )


def test_production_accepts_strong_secret_with_debug_off():
    s = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        secret_key="x" * 48,
        document_encryption_active_key_id="v1",
        document_encryption_keys=DOCUMENT_ENCRYPTION_KEYS,
    )
    assert s.secret_key == "x" * 48
    assert s.app_debug is False


def test_development_allows_document_encryption_keys_to_be_absent():
    s = Settings(
        _env_file=None,
        app_env="development",
        document_encryption_active_key_id="",
        document_encryption_keys="",
    )
    assert s.document_encryption_active_key_id == ""
    assert s.document_encryption_keys == ""


def test_document_encryption_keys_are_accepted_when_valid():
    s = Settings(
        _env_file=None,
        app_env="development",
        document_encryption_active_key_id="v1",
        document_encryption_keys=DOCUMENT_ENCRYPTION_KEYS,
    )
    assert s.document_encryption_active_key_id == "v1"
    assert s.document_encryption_keys == DOCUMENT_ENCRYPTION_KEYS
    assert _DOCUMENT_KEY_B64 not in repr(s)


@pytest.mark.parametrize("app_env", ["production", "staging"])
def test_deployed_environments_require_document_encryption_keys(app_env):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env=app_env,
            app_debug=False,
            secret_key="x" * 48,
            document_encryption_active_key_id="",
            document_encryption_keys="",
        )


@pytest.mark.parametrize(
    "keys",
    [
        "not-json",
        "[]",
        '{"v1":"not-base64!"}',
        '{"v1":"eA=="}',
        f'{{"v1":"{_DOCUMENT_KEY_B64}",'
        f'"v1":"{_DOCUMENT_KEY_B64}"}}',
        f'{{"bad key":"{_DOCUMENT_KEY_B64}"}}',
    ],
)
def test_invalid_document_encryption_key_ring_is_rejected(keys):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="development",
            document_encryption_active_key_id="v1",
            document_encryption_keys=keys,
        )


def test_document_encryption_requires_active_key_to_exist():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="development",
            document_encryption_active_key_id="v2",
            document_encryption_keys=DOCUMENT_ENCRYPTION_KEYS,
        )


def test_document_encryption_requires_keys_and_active_id_together():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="development",
            document_encryption_active_key_id="v1",
            document_encryption_keys="",
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="development",
            document_encryption_active_key_id="",
            document_encryption_keys=DOCUMENT_ENCRYPTION_KEYS,
        )


def test_document_encryption_validation_errors_do_not_expose_key_material():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            app_env="development",
            document_encryption_active_key_id="missing",
            document_encryption_keys=DOCUMENT_ENCRYPTION_KEYS,
        )

    message = str(exc_info.value)
    assert DOCUMENT_ENCRYPTION_KEYS not in message
    assert _DOCUMENT_KEY_B64 not in message
