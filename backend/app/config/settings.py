import secrets
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

_INSECURE_SECRETS = {
    "dev-insecure-secret-change-me",
    "changeme",
    "change-me",
    "secret",
    "secret-key",
}


class Settings(BaseSettings):
    app_name: str = "JURISCAN-AI"
    app_env: Literal["development", "production", "test", "staging"] = "development"
    app_debug: bool = False
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

    max_upload_size_mb: int = Field(default=25, ge=1)
    max_pdf_pages: int = Field(default=500, ge=1)
    log_level: str = "INFO"

    # Auth-layer session signing. Production/staging must provide a strong,
    # explicit SECRET_KEY. Development/test without one get a random per-process
    # key, so there is no known default that can be used to forge tokens.
    secret_key: str = ""
    access_token_ttl_seconds: int = 60 * 60 * 24 * 7

    # Brute-force protection for the unauthenticated auth endpoints
    # (/auth/login, /auth/register). Limits are per client IP, per process.
    # Set AUTH_RATE_LIMIT_MAX_REQUESTS=0 to disable (not recommended).
    auth_rate_limit_max_requests: int = Field(default=10, ge=0)
    auth_rate_limit_window_seconds: float = Field(default=60, ge=1)

    # Development/test-only convenience identity. Disabled by default so a
    # missing token can never silently authenticate a request. Production and
    # staging ignore this flag even if it is set.
    allow_demo_user: bool = False

    # OCR (scanned/image-only PDF pages). Requires the optional
    # ``rapidocr-onnxruntime`` and ``pymupdf`` packages; when they are not
    # installed OCR is skipped and scanned documents fail with a clear error.
    ocr_enabled: bool = True
    ocr_min_page_chars: int = Field(default=20, ge=1)
    ocr_render_dpi: int = Field(default=200, ge=72, le=600)
    ocr_page_batch_size: int = Field(default=1, ge=1, le=10)
    ocr_timeout_seconds: int = Field(default=300, ge=1)
    ocr_max_concurrent_inferences: int = Field(default=1, ge=1, le=8)
    ocr_preprocess_enabled: bool = True
    ocr_deskew_enabled: bool = True
    ocr_rotation_detection_enabled: bool = True
    ocr_layout_analysis_enabled: bool = True
    ocr_low_confidence_threshold: float = Field(default=0.75, ge=0, le=1)
    ocr_quality_warning_threshold: float = Field(default=0.65, ge=0, le=1)
    ocr_native_recheck_threshold: float = Field(default=0.45, ge=0, le=1)
    ocr_merge_margin: float = Field(default=0.08, ge=0, le=1)

    # Documents left in PROCESSING for longer than this are treated as stale
    # and marked FAILED so they can be retried instead of getting stuck. This
    # must stay longer than the OCR deadline to avoid failing active work.
    processing_stale_seconds: int = Field(default=900, ge=1)
    processing_stale_sweep_seconds: int = Field(default=300, ge=0)
    processing_max_concurrent_jobs: int = Field(default=2, ge=1, le=16)

    # Company team invitations expire after this many hours. A fresh token is
    # required after expiry; only its hash is stored.
    company_invitation_ttl_hours: int = 24 * 7

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

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if self.app_env in ("production", "staging"):
            if not self.secret_key:
                raise ValueError(
                    "SECRET_KEY must be set to a strong random value in "
                    f"{self.app_env}."
                )
            if (
                self.secret_key in _INSECURE_SECRETS
                or len(self.secret_key) < 32
            ):
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters and must not be a "
                    "known default value."
                )
            if self.app_debug:
                raise ValueError(f"APP_DEBUG must be false in {self.app_env}.")
        elif not self.secret_key:
            self.secret_key = secrets.token_urlsafe(48)
        return self


settings = Settings()

__all__ = ["settings", "Settings"]