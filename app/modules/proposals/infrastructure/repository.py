"""Persistence helpers for tenant-scoped proposal operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.proposals.infrastructure.models import ProposalModel


class ProposalRepository:
    """Encapsulates proposal queries used by API handlers and worker flows."""

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

    def get_by_external_protocol(self, *, external_protocol: str) -> ProposalModel | None:
        statement: Select[tuple[ProposalModel]] = select(ProposalModel).where(
            ProposalModel.external_protocol == external_protocol
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

    def add(self, proposal: ProposalModel) -> ProposalModel:
        self._session.add(proposal)
        self._session.commit()
        self._session.refresh(proposal)
        return proposal

    def save(self, proposal: ProposalModel) -> ProposalModel:
        self._session.add(proposal)
        self._session.commit()
        self._session.refresh(proposal)
        return proposal
