"""Read use cases for the proposals module."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.core.security import AuthenticatedUser
from app.modules.proposals.domain.exceptions import ProposalNotFoundError
from app.modules.proposals.infrastructure.models import ProposalModel
from app.modules.proposals.infrastructure.repository import ProposalRepository


@dataclass(frozen=True)
class ListProposalsResult:
    items: list[ProposalModel]
    total: int
    page: int
    page_size: int


class ProposalQueries:
    """Coordinates tenant-scoped proposal reads."""

    def __init__(self, repository: ProposalRepository) -> None:
        self._repository = repository

    def list(
        self,
        *,
        actor: AuthenticatedUser,
        page: int,
        page_size: int,
        status: str | None = None,
        proposal_type: str | None = None,
    ) -> ListProposalsResult:
        items = self._repository.list_by_tenant(
            tenant_id=actor.tenant_id,
            page=page,
            page_size=page_size,
            status=status,
            proposal_type=proposal_type,
        )
        total = self._repository.count_by_tenant(
            tenant_id=actor.tenant_id,
            status=status,
            proposal_type=proposal_type,
        )
        return ListProposalsResult(items=items, total=total, page=page, page_size=page_size)

    def get_by_id(self, *, actor: AuthenticatedUser, proposal_id: UUID) -> ProposalModel:
        proposal = self._repository.get_by_tenant_and_id(
            tenant_id=actor.tenant_id,
            proposal_id=proposal_id,
        )
        if proposal is None:
            raise ProposalNotFoundError()
        return proposal
