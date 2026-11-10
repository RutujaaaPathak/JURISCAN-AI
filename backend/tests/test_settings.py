import pytest
from pydantic import ValidationError

from app.config.settings import Settings


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
        )


def test_production_rejects_debug_mode():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            app_debug=True,
            secret_key="x" * 48,
        )


def test_production_accepts_strong_secret_with_debug_off():
    s = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        secret_key="x" * 48,
    )
    assert s.secret_key == "x" * 48
    assert s.app_debug is False