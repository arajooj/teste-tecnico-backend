"""Write use cases for the proposals module."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from app.core.exceptions import AppException
from app.core.security import AuthenticatedUser
from app.modules.clients.infrastructure.repository import ClientRepository
from app.modules.proposals.domain.exceptions import (
    InvalidProposalStateError,
    ProposalClientNotFoundError,
    ProposalDispatchError,
    ProposalNotFoundError,
)
from app.modules.proposals.infrastructure.models import (
    ProposalJobAction,
    ProposalModel,
    ProposalStatus,
    ProposalType,
)
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
            simulation_callback_token=uuid4().hex,
            created_by=actor.user_id,
        )
        proposal, job = self._repository.create_proposal_with_job(
            proposal=proposal,
            action=ProposalJobAction.SIMULATE,
        )
        self._publish_job(action=ProposalJobAction.SIMULATE, proposal=proposal, job_id=job.id)
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
        proposal.simulation_callback_token = None
        proposal.inclusion_callback_token = uuid4().hex
        job = self._repository.create_job_for_existing_proposal(
            proposal=proposal,
            action=ProposalJobAction.SUBMIT,
        )
        self._publish_job(action=ProposalJobAction.SUBMIT, proposal=proposal, job_id=job.id)
        return proposal

    def _publish_job(
        self,
        *,
        action: ProposalJobAction,
        proposal: ProposalModel,
        job_id: UUID,
    ) -> None:
        job = self._repository.get_job_by_id(job_id=job_id)
        if job is None:  # pragma: no cover
            raise AppException("Proposal job not found", status_code=500)

        try:
            self._queue.send_message(
                action=action.value,
                proposal_id=str(proposal.id),
                job_id=str(job.id),
            )
        except Exception as exc:
            self._repository.mark_job_failed(
                job=job,
                proposal=proposal,
                error_message=f"Failed to publish async job: {exc}",
            )
            raise ProposalDispatchError() from exc

        self._repository.mark_job_published(job, proposal)

