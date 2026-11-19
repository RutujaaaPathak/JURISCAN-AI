import base64
import binascii
import json
import re
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

_DOCUMENT_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")
_DOCUMENT_KEY_BYTES = 32


class _DuplicateKeyId(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyId
        result[key] = value
    return result


def parse_document_encryption_keys(raw: str) -> dict[str, str]:
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw, object_pairs_hook=_unique_object)
    except _DuplicateKeyId:
        raise ValueError(
            "DOCUMENT_ENCRYPTION_KEYS must not contain duplicate key ids."
        ) from None
    except (json.JSONDecodeError, TypeError):
        raise ValueError(
            "DOCUMENT_ENCRYPTION_KEYS must be a JSON object mapping key ids "
            "to base64-encoded 32-byte keys."
        ) from None
    if not isinstance(parsed, dict):
        raise ValueError(
            "DOCUMENT_ENCRYPTION_KEYS must be a JSON object mapping key ids "
            "to base64-encoded 32-byte keys."
        )
    for key_id, encoded in parsed.items():
        if not isinstance(key_id, str) or not _DOCUMENT_KEY_ID.fullmatch(key_id):
            raise ValueError(
                "DOCUMENT_ENCRYPTION_KEYS contains an invalid key id."
            )
        if not isinstance(encoded, str):
            raise ValueError(
                "DOCUMENT_ENCRYPTION_KEYS values must be base64 strings."
            )
        try:
            key = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError(
                "DOCUMENT_ENCRYPTION_KEYS values must be valid base64."
            ) from None
        if len(key) != _DOCUMENT_KEY_BYTES:
            raise ValueError(
                "DOCUMENT_ENCRYPTION_KEYS values must decode to exactly "
                "32 bytes."
            )
    return parsed


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

    document_encryption_active_key_id: str = ""
    document_encryption_keys: str = Field(default="", repr=False)

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

    # Default retention window applied to newly uploaded documents when the
    # owning company has no explicit policy. Zero keeps documents until they
    # are deleted explicitly; a legal hold always blocks deletion.
    document_retention_days: int = Field(default=0, ge=0)

    # Company team invitations expire after this many hours. A fresh token is
    # required after expiry; only its hash is stored.
    company_invitation_ttl_hours: int = 24 * 7

    # Brute-force protection for the unauthenticated invitation-accept endpoint.
    # Limits are per client IP, per process. Set to 0 to disable.
    company_invitation_rate_limit_max_requests: int = Field(default=10, ge=0)
    company_invitation_rate_limit_window_seconds: float = Field(default=60, ge=1)

    data_dir: Path = BASE_DIR.parent / "data"
    models_dir: Path = BASE_DIR.parent / "models"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Never echo submitted settings (including the document key ring) in
        # validation error messages that may be written to startup logs.
        hide_input_in_errors=True,
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

    @model_validator(mode="after")
    def validate_document_encryption_settings(self) -> "Settings":
        raw = self.document_encryption_keys
        active_key_id = self.document_encryption_active_key_id
        if not raw.strip() and not active_key_id:
            if self.app_env in ("production", "staging"):
                raise ValueError(
                    "DOCUMENT_ENCRYPTION_KEYS and "
                    "DOCUMENT_ENCRYPTION_ACTIVE_KEY_ID must be set in "
                    f"{self.app_env}."
                )
            return self
        if not raw.strip() or not active_key_id:
            raise ValueError(
                "DOCUMENT_ENCRYPTION_KEYS and "
                "DOCUMENT_ENCRYPTION_ACTIVE_KEY_ID must be set together."
            )
        keys = parse_document_encryption_keys(raw)
        if not _DOCUMENT_KEY_ID.fullmatch(active_key_id):
            raise ValueError(
                "DOCUMENT_ENCRYPTION_ACTIVE_KEY_ID is not a valid key id."
            )
        if active_key_id not in keys:
            raise ValueError(
                "DOCUMENT_ENCRYPTION_ACTIVE_KEY_ID is not present in "
                "DOCUMENT_ENCRYPTION_KEYS."
            )
        return self


settings = Settings()

__all__ = ["settings", "Settings", "parse_document_encryption_keys"]
