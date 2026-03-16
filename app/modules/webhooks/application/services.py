"""Webhook application services."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.proposals.domain.exceptions import (
    InvalidProposalStateError,
    ProposalNotFoundError,
)
from app.modules.proposals.infrastructure.models import ProposalModel, ProposalStatus
from app.modules.webhooks.infrastructure.repository import WebhookRepository


@dataclass(frozen=True)
class BankCallbackCommand:
    protocol: str
    event: str
    status: str
    data: dict
    timestamp: str | None = None


class WebhookService:
    """Processes callbacks from the external mock bank."""

    def __init__(self, repository: WebhookRepository) -> None:
        self._repository = repository

    def handle_bank_callback(self, *, command: BankCallbackCommand) -> ProposalModel:
        proposal = self._repository.get_by_external_protocol(external_protocol=command.protocol)
        if proposal is None:
            raise ProposalNotFoundError()

        next_status = self._map_callback_status(
            event=command.event,
            external_status=command.status,
        )

        payload = {
            "protocol": command.protocol,
            "event": command.event,
            "status": command.status,
            "data": command.data,
            "timestamp": command.timestamp,
        }
        if proposal.status == next_status and proposal.bank_response == payload:
            return proposal

        proposal.status = next_status
        proposal.bank_response = payload
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
