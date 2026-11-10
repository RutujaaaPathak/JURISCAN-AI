import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.audit_reports import router as audit_reports_router
from app.api.auth import router as auth_router
from app.api.calls import router as calls_router
from app.api.cases import router as cases_router
from app.api.company import router as company_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.lawyers import router as lawyers_router
from app.api.realtime import router as realtime_router
from app.api.settings import router as settings_router
from app.api.status import router as status_router
from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import RequestLoggingMiddleware, logger, setup_logging
from app.services.call_signaling import call_signaling_manager
from app.services.ocr import shutdown_ocr_executor
from app.services.processing import (
    recover_stale_documents_in_new_session,
    shutdown_processing_executor,
)
from app.services.realtime import case_connections

API_VERSION = "0.1.0"


async def _stale_recovery_loop() -> None:
    while True:
        await asyncio.sleep(settings.processing_stale_sweep_seconds)
        try:
            await asyncio.to_thread(recover_stale_documents_in_new_session)
        except Exception:
            logger.exception("Periodic stale-document recovery failed")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Capture the running event loop so the synchronous HTTP send path can
    # schedule WebSocket broadcasts onto it (see services.realtime and services.call_signaling).
    loop = asyncio.get_running_loop()
    case_connections.bind_loop(loop)
    call_signaling_manager.bind_loop(loop)

    recovery_task: asyncio.Task | None = None
    if settings.app_env != "test":
        try:
            await asyncio.to_thread(recover_stale_documents_in_new_session)
        except Exception:
            logger.warning("Startup stale-document recovery failed", exc_info=True)
        if settings.processing_stale_sweep_seconds > 0:
            recovery_task = asyncio.create_task(_stale_recovery_loop())

    try:
        yield
    finally:
        if recovery_task is not None:
            recovery_task.cancel()
            with suppress(asyncio.CancelledError):
                await recovery_task
        await asyncio.to_thread(shutdown_processing_executor, wait=False)
        await asyncio.to_thread(shutdown_ocr_executor, wait=False)


def create_app() -> FastAPI:
    setup_logging(settings.log_level)

    # Interactive API documentation and the OpenAPI schema are a development
    # aid; production and staging must not publish the full route surface.
    docs_enabled = settings.app_env not in ("production", "staging")

    app = FastAPI(
        title=settings.app_name,
        version=API_VERSION,
        debug=settings.app_debug,
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(status_router, prefix=settings.api_prefix)
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(company_router, prefix=settings.api_prefix)
    app.include_router(audit_reports_router, prefix=settings.api_prefix)
    app.include_router(documents_router, prefix=settings.api_prefix)
    app.include_router(cases_router, prefix=settings.api_prefix)
    app.include_router(calls_router, prefix=settings.api_prefix)
    app.include_router(lawyers_router, prefix=settings.api_prefix)
    app.include_router(settings_router, prefix=settings.api_prefix)
    app.include_router(realtime_router, prefix=settings.api_prefix)

    return app


app = create_app()

__all__ = ["app", "create_app"]
