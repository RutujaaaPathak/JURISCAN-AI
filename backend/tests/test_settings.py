from app.config.settings import Settings


def test_default_settings_shape():
    s = Settings(_env_file=None)
    assert s.app_name == "JURISCAN-AI"
    assert s.app_env in {"development", "production", "test", "staging"}
    assert s.api_prefix == "/api"
    assert s.max_upload_size_mb > 0


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