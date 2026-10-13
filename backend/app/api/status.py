from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.config import settings
from app.core.logging import logger
from app.schemas.common import StatusResponse

router = APIRouter(tags=["status"])


@router.get("/status", response_model=StatusResponse)
def api_status(db: DbSession) -> StatusResponse:
    database_ok = True
    database_details: dict | None = None
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - depends on environment
        logger.error("Database connectivity check failed: %s", exc)
        database_ok = False
        database_details = {"error": "unavailable"}

    return StatusResponse(
        status="ok" if database_ok else "degraded",
        app=settings.app_name,
        environment=settings.app_env,
        database="ok" if database_ok else "unavailable",
        database_details=database_details,
    )