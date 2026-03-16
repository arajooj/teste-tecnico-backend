"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.modules.clients.api.router import router as clients_router
from app.modules.identity.api.router import router as identity_router
from app.modules.proposals.api.router import router as proposals_router
from app.modules.proposals.infrastructure.queue import ProposalQueue
from app.modules.proposals.infrastructure.repository import ProposalRepository
from app.modules.webhooks.api.router import router as webhooks_router

logger = logging.getLogger(__name__)


def dispatch_pending_jobs() -> None:
    with SessionLocal() as session:
        repository = ProposalRepository(session)
        queue = ProposalQueue()

        for job in repository.list_dispatchable_jobs():
            proposal = repository.get_by_id(proposal_id=job.proposal_id)
            if proposal is None:
                logger.warning("Skipping orphan proposal job", extra={"job_id": str(job.id)})
                continue

            try:
                queue.send_message(
                    action=job.action,
                    proposal_id=str(proposal.id),
                    job_id=str(job.id),
                )
            except Exception as exc:  # pragma: no cover - operational safeguard
                repository.mark_job_failed(
                    job=job,
                    proposal=proposal,
                    error_message=f"Failed to redispatch pending job: {exc}",
                )
                logger.warning(
                    "Failed to redispatch pending proposal job",
                    extra={"job_id": str(job.id), "proposal_id": str(proposal.id)},
                )
                continue

            repository.mark_job_published(job, proposal)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    settings = get_settings()
    logger.info(
        "Starting API application",
        extra={"environment": settings.environment, "version": settings.app_version},
    )
    try:
        dispatch_pending_jobs()
    except Exception:  # pragma: no cover - startup safeguard for local/test environments
        logger.warning("Skipping pending job dispatch during startup", exc_info=True)
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
