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
    callback_token: str
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
        proposal = self._repository.get_by_callback_token(callback_token=command.callback_token)
        if proposal is None:
            raise ProposalNotFoundError()

        next_status = self._map_callback_status(event=command.event, external_status=command.status)
        payload = {
            "protocol": command.protocol,
            "event": command.event,
            "status": command.status,
            "data": command.data,
            "timestamp": command.timestamp,
        }
        if proposal.status == next_status and proposal.bank_response == payload:
            return proposal

        phase = self._resolve_phase(proposal=proposal, callback_token=command.callback_token)
        self._validate_protocol(proposal=proposal, phase=phase, protocol=command.protocol)
        self._validate_transition(proposal=proposal, event=command.event, phase=phase)

        proposal.status = next_status
        proposal.bank_response = payload
        proposal.last_bank_error = None
        if command.status != "approved":
            proposal.last_bank_error = str(command.data.get("reason", "Unknown bank error"))
        if command.event == "simulation_completed" and command.status == "approved":
            proposal.interest_rate = command.data.get("interest_rate")
            proposal.installment_value = command.data.get("installment_value")

        return self._repository.save(proposal)

    def _resolve_phase(self, *, proposal: ProposalModel, callback_token: str) -> str:
        if proposal.simulation_callback_token == callback_token:
            return "simulation"
        if proposal.inclusion_callback_token == callback_token:
            return "inclusion"
        raise ProposalNotFoundError()

    def _validate_protocol(self, *, proposal: ProposalModel, phase: str, protocol: str) -> None:
        expected_protocol = (
            proposal.simulation_protocol if phase == "simulation" else proposal.inclusion_protocol
        )
        if expected_protocol != protocol:
            raise InvalidProposalStateError(
                "Callback protocol does not match the expected operation"
            )

    def _validate_transition(self, *, proposal: ProposalModel, event: str, phase: str) -> None:
        if event == "simulation_completed":
            if phase != "simulation":
                raise InvalidProposalStateError("Simulation callback received for an invalid phase")
            if proposal.status != ProposalStatus.PROCESSING.value:
                raise InvalidProposalStateError(
                    "Simulation callback is not valid for the current state"
                )
            return

        if event == "inclusion_completed":
            if phase != "inclusion":
                raise InvalidProposalStateError("Inclusion callback received for an invalid phase")
            if proposal.status != ProposalStatus.SUBMITTED.value:
                raise InvalidProposalStateError(
                    "Inclusion callback is not valid for the current state"
                )
            return

        raise InvalidProposalStateError("Unsupported bank callback event")

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
