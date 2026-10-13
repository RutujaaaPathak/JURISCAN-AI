from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    app_name: str = "JURISCAN-AI"
    app_env: Literal["development", "production", "test", "staging"] = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    api_prefix: str = "/api"

    frontend_origin: str = "http://localhost:5173"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "juriscan"
    db_user: str = "postgres"
    db_password: str = ""
    database_url: str | None = None
    db_pool_size: int = 5
    db_max_overflow: int = 10

    max_upload_size_mb: int = 25
    log_level: str = "INFO"

    # Auth-layer session signing. The default key is development-only and must be
    # overridden via SECRET_KEY before any production deployment.
    secret_key: str = "dev-insecure-secret-change-me"
    access_token_ttl_seconds: int = 60 * 60 * 24 * 7

    # OCR (scanned/image-only PDF pages). Requires the optional
    # ``rapidocr-onnxruntime`` and ``pymupdf`` packages; when they are not
    # installed OCR is skipped and scanned documents fail with a clear error.
    ocr_enabled: bool = True
    ocr_min_page_chars: int = 20
    ocr_render_dpi: int = 200

    # Documents left in PROCESSING for longer than this are treated as stale
    # and marked FAILED so they can be retried instead of getting stuck.
    processing_stale_seconds: int = 900

    data_dir: Path = BASE_DIR.parent / "data"
    models_dir: Path = BASE_DIR.parent / "models"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def resolve_database_url(self) -> "Settings":
        if self.database_url:
            return self
        userinfo = (
            f"{self.db_user}:{self.db_password}"
            if self.db_password
            else self.db_user
        )
        self.database_url = (
            f"postgresql+psycopg://{userinfo}@{self.db_host}:{self.db_port}/{self.db_name}"
        )
        return self


settings = Settings()

__all__ = ["settings", "Settings"]