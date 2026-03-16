"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.modules.clients.api.router import router as clients_router
from app.modules.identity.api.router import router as identity_router
from app.modules.proposals.api.router import router as proposals_router
from app.modules.webhooks.api.router import router as webhooks_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    settings = get_settings()
    logger.info(
        "Starting API application",
        extra={"environment": settings.environment, "version": settings.app_version},
    )
    yield
    logger.info("Stopping API application")


def create_application() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    register_exception_handlers(app)
    app.include_router(identity_router)
    app.include_router(clients_router)
    app.include_router(proposals_router)
    app.include_router(webhooks_router)

    @app.get("/health", tags=["health"])
    def healthcheck() -> dict[str, str]:
        return {
            "status": "ok",
            "environment": settings.environment,
        }

    return app


app = create_application()
