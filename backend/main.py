from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.cases import router as cases_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.lawyers import router as lawyers_router
from app.api.status import router as status_router
from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import RequestLoggingMiddleware, setup_logging

API_VERSION = "0.1.0"


def create_app() -> FastAPI:
    setup_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=API_VERSION,
        debug=settings.app_debug,
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
    app.include_router(documents_router, prefix=settings.api_prefix)
    app.include_router(cases_router, prefix=settings.api_prefix)
    app.include_router(lawyers_router, prefix=settings.api_prefix)

    return app


app = create_app()

__all__ = ["app", "create_app"]