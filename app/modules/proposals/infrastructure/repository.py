"""Persistence helpers for tenant-scoped proposal operations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.modules.proposals.infrastructure.models import (
    ProposalJobAction,
    ProposalJobModel,
    ProposalJobStatus,
    ProposalModel,
)


class ProposalRepository:
    """Encapsulates proposal queries used by API handlers, workers and webhook flows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, *, proposal_id: UUID) -> ProposalModel | None:
        statement: Select[tuple[ProposalModel]] = select(ProposalModel).where(
            ProposalModel.id == proposal_id
        )
        return self._session.scalar(statement)

    def get_by_tenant_and_id(self, *, tenant_id: UUID, proposal_id: UUID) -> ProposalModel | None:
        statement: Select[tuple[ProposalModel]] = select(ProposalModel).where(
            ProposalModel.tenant_id == tenant_id,
            ProposalModel.id == proposal_id,
        )
        return self._session.scalar(statement)

    def get_by_callback_token(self, *, callback_token: str) -> ProposalModel | None:
        statement: Select[tuple[ProposalModel]] = select(ProposalModel).where(
            or_(
                ProposalModel.simulation_callback_token == callback_token,
                ProposalModel.inclusion_callback_token == callback_token,
            )
        )
        return self._session.scalar(statement)

    def list_by_tenant(
        self,
        *,
        tenant_id: UUID,
        page: int,
        page_size: int,
        status: str | None = None,
        proposal_type: str | None = None,
    ) -> list[ProposalModel]:
        offset = (page - 1) * page_size
        statement: Select[tuple[ProposalModel]] = (
            select(ProposalModel)
            .where(ProposalModel.tenant_id == tenant_id)
            .order_by(ProposalModel.created_at.desc(), ProposalModel.id.desc())
            .offset(offset)
            .limit(page_size)
        )

        if status is not None:
            statement = statement.where(ProposalModel.status == status)
        if proposal_type is not None:
            statement = statement.where(ProposalModel.type == proposal_type)

        return list(self._session.scalars(statement))

    def count_by_tenant(
        self,
        *,
        tenant_id: UUID,
        status: str | None = None,
        proposal_type: str | None = None,
    ) -> int:
        statement = select(func.count()).select_from(ProposalModel).where(
            ProposalModel.tenant_id == tenant_id
        )

        if status is not None:
            statement = statement.where(ProposalModel.status == status)
        if proposal_type is not None:
            statement = statement.where(ProposalModel.type == proposal_type)

        return int(self._session.scalar(statement) or 0)

    def create_proposal_with_job(
        self,
        *,
        proposal: ProposalModel,
        action: ProposalJobAction,
    ) -> tuple[ProposalModel, ProposalJobModel]:
        self._session.add(proposal)
        self._session.flush()
        job = ProposalJobModel(
            proposal_id=proposal.id,
            action=action.value,
            payload={"action": action.value, "proposal_id": str(proposal.id)},
        )
        self._session.add(job)
        self._commit(proposal, job)
        return proposal, job

    def create_job_for_existing_proposal(
        self,
        *,
        proposal: ProposalModel,
        action: ProposalJobAction,
    ) -> ProposalJobModel:
        self._session.add(proposal)
        self._session.flush()
        job = ProposalJobModel(
            proposal_id=proposal.id,
            action=action.value,
            payload={"action": action.value, "proposal_id": str(proposal.id)},
        )
        self._session.add(job)
        self._commit(proposal, job)
        return job

    def get_job_by_id(self, *, job_id: UUID) -> ProposalJobModel | None:
        return self._session.get(ProposalJobModel, job_id)

    def list_dispatchable_jobs(self) -> list[ProposalJobModel]:
        statement: Select[tuple[ProposalJobModel]] = (
            select(ProposalJobModel)
            .where(
                ProposalJobModel.status.in_(
                    [ProposalJobStatus.PENDING.value, ProposalJobStatus.FAILED.value]
                )
            )
            .order_by(ProposalJobModel.created_at.asc(), ProposalJobModel.id.asc())
        )
        return list(self._session.scalars(statement))

    def mark_job_published(
        self,
        job: ProposalJobModel,
        proposal: ProposalModel,
    ) -> ProposalJobModel:
        job.status = ProposalJobStatus.PUBLISHED.value
        job.last_error = None
        job.published_at = datetime.now(UTC)
        proposal.last_enqueued_at = datetime.now(UTC)
        proposal.last_bank_error = None
        self._commit(job, proposal)
        return job

    def mark_job_processing(
        self,
        job: ProposalJobModel,
        proposal: ProposalModel,
    ) -> ProposalJobModel:
        job.status = ProposalJobStatus.PROCESSING.value
        job.attempts += 1
        proposal.processing_attempts += 1
        proposal.last_bank_error = None
        self._commit(job, proposal)
        return job

    def mark_job_completed(
        self,
        job: ProposalJobModel,
        proposal: ProposalModel,
    ) -> ProposalJobModel:
        job.status = ProposalJobStatus.COMPLETED.value
        job.last_error = None
        job.processed_at = datetime.now(UTC)
        proposal.last_bank_error = None
        self._commit(job, proposal)
        return job

    def mark_job_failed(
        self,
        *,
        job: ProposalJobModel,
        proposal: ProposalModel,
        error_message: str,
    ) -> ProposalJobModel:
        job.status = ProposalJobStatus.FAILED.value
        job.last_error = error_message
        proposal.last_bank_error = error_message
        self._commit(job, proposal)
        return job

    def save(self, proposal: ProposalModel) -> ProposalModel:
        self._session.add(proposal)
        self._commit(proposal)
        return proposal

    def _commit(self, *entities: object) -> None:
        self._session.commit()
        for entity in entities:
            self._session.refresh(entity)
