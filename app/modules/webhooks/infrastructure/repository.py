"""Persistence helpers used by bank webhook processing."""

from app.modules.proposals.infrastructure.models import ProposalModel
from app.modules.proposals.infrastructure.repository import ProposalRepository


class WebhookRepository:
    """Thin wrapper around proposal persistence for callback processing."""

    def __init__(self, proposal_repository: ProposalRepository) -> None:
        self._proposal_repository = proposal_repository

    def get_by_callback_token(self, *, callback_token: str) -> ProposalModel | None:
        return self._proposal_repository.get_by_callback_token(callback_token=callback_token)

    def save(self, proposal: ProposalModel) -> ProposalModel:
        return self._proposal_repository.save(proposal)
