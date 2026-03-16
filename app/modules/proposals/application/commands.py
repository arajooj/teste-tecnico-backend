"""Write use cases for the proposals module."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.core.security import AuthenticatedUser
from app.modules.clients.infrastructure.repository import ClientRepository
from app.modules.proposals.domain.exceptions import (
    InvalidProposalStateError,
    ProposalClientNotFoundError,
    ProposalNotFoundError,
)
from app.modules.proposals.infrastructure.models import ProposalModel, ProposalStatus, ProposalType
from app.modules.proposals.infrastructure.queue import ProposalQueue
from app.modules.proposals.infrastructure.repository import ProposalRepository


@dataclass(frozen=True)
class SimulateProposalCommand:
    client_id: UUID
    amount: Decimal
    installments: int


class ProposalCommands:
    """Coordinates proposal mutations and async workflow orchestration."""

    def __init__(
        self,
        repository: ProposalRepository,
        client_repository: ClientRepository,
        queue: ProposalQueue,
    ) -> None:
        self._repository = repository
        self._client_repository = client_repository
        self._queue = queue

    def create_simulation(
        self,
        *,
        actor: AuthenticatedUser,
        command: SimulateProposalCommand,
    ) -> ProposalModel:
        client = self._client_repository.get_by_tenant_and_id(
            tenant_id=actor.tenant_id,
            client_id=command.client_id,
        )
        if client is None:
            raise ProposalClientNotFoundError()

        proposal = ProposalModel(
            tenant_id=actor.tenant_id,
            client_id=command.client_id,
            type=ProposalType.SIMULATION.value,
            amount=command.amount,
            installments=command.installments,
            status=ProposalStatus.PENDING.value,
            created_by=actor.user_id,
        )
        proposal = self._repository.add(proposal)
        self._queue.send_message(action="simulate", proposal_id=str(proposal.id))
        return proposal

    def submit(self, *, actor: AuthenticatedUser, proposal_id: UUID) -> ProposalModel:
        proposal = self._repository.get_by_tenant_and_id(
            tenant_id=actor.tenant_id,
            proposal_id=proposal_id,
        )
        if proposal is None:
            raise ProposalNotFoundError()
        if proposal.status != ProposalStatus.SIMULATED.value:
            raise InvalidProposalStateError("Only simulated proposals can be submitted")

        proposal.type = ProposalType.PROPOSAL.value
        proposal.status = ProposalStatus.PENDING.value
        proposal = self._repository.save(proposal)
        self._queue.send_message(action="submit", proposal_id=str(proposal.id))
        return proposal

