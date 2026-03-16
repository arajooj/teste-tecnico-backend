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


@dataclass(frozen=True)
class BankCallbackCommand:
    protocol: str
    event: str
    status: str
    data: dict
    timestamp: str | None = None


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

    def handle_bank_callback(self, *, command: BankCallbackCommand) -> ProposalModel:
        proposal = self._repository.get_by_external_protocol(external_protocol=command.protocol)
        if proposal is None:
            raise ProposalNotFoundError()

        next_status = self._map_callback_status(event=command.event, external_status=command.status)

        if proposal.status == next_status and proposal.bank_response == command.__dict__:
            return proposal

        proposal.status = next_status
        proposal.bank_response = command.__dict__
        if command.event == "simulation_completed" and command.status == "approved":
            proposal.interest_rate = command.data.get("interest_rate")
            proposal.installment_value = command.data.get("installment_value")

        return self._repository.save(proposal)

    def _map_callback_status(self, *, event: str, external_status: str) -> str:
        if event == "simulation_completed":
            if external_status == "approved":
                return ProposalStatus.SIMULATED.value
            return ProposalStatus.SIMULATION_FAILED.value
        if event == "inclusion_completed":
            if external_status == "approved":
                return ProposalStatus.APPROVED.value
            return ProposalStatus.REJECTED.value
        raise InvalidProposalStateError("Unsupported bank callback event")
