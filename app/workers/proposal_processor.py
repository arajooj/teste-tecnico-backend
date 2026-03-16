"""Reusable proposal job processor used by Lambda handlers."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from uuid import UUID

from app.core.db import SessionLocal
from app.modules.clients.infrastructure.repository import ClientRepository
from app.modules.identity.infrastructure import models as identity_models
from app.modules.proposals.domain.exceptions import (
    InvalidProposalStateError,
    ProposalClientNotFoundError,
    ProposalNotFoundError,
)
from app.modules.proposals.infrastructure.bank_client import MockBankClient
from app.modules.proposals.infrastructure.models import ProposalStatus, ProposalType
from app.modules.proposals.infrastructure.repository import ProposalRepository

MODEL_REGISTRY = (identity_models,)
logger = logging.getLogger(__name__)


def process_proposal_job(
    *,
    action: str,
    proposal_id: UUID,
    session_factory: Callable = SessionLocal,
    bank_client_factory: Callable = MockBankClient,
) -> None:
    logger.info(
        "Processing proposal job",
        extra={"action": action, "proposal_id": str(proposal_id)},
    )
    with session_factory() as session:
        proposal_repository = ProposalRepository(session)
        client_repository = ClientRepository(session)
        bank_client = bank_client_factory()

        proposal = proposal_repository.get_by_id(proposal_id=proposal_id)
        if proposal is None:
            raise ProposalNotFoundError()

        client = client_repository.get_by_tenant_and_id(
            tenant_id=proposal.tenant_id,
            client_id=proposal.client_id,
        )
        if client is None:
            raise ProposalClientNotFoundError()

        proposal.status = ProposalStatus.PROCESSING.value
        proposal_repository.save(proposal)

        if action == "simulate":
            protocol = bank_client.simulate(
                cpf=client.cpf,
                amount=proposal.amount,
                installments=proposal.installments,
            )
            proposal.external_protocol = protocol
            proposal.type = ProposalType.SIMULATION.value
            proposal_repository.save(proposal)
            logger.info("Simulation sent to bank", extra={"proposal_id": str(proposal.id)})
            return

        if action == "submit":
            if proposal.external_protocol is None:
                raise InvalidProposalStateError("Proposal has no simulation protocol")

            simulation_protocol = proposal.external_protocol
            protocol = bank_client.submit(
                protocol=simulation_protocol,
                client_name=client.name,
                client_cpf=client.cpf,
                client_birth_date=client.birth_date,
                amount=proposal.amount,
                installments=proposal.installments,
            )
            proposal.external_protocol = protocol
            proposal.type = ProposalType.PROPOSAL.value
            proposal.status = ProposalStatus.SUBMITTED.value
            proposal_repository.save(proposal)
            logger.info("Proposal submitted to bank", extra={"proposal_id": str(proposal.id)})
            return

        raise InvalidProposalStateError("Unsupported proposal queue action")


def process_queue_message(
    message_body: str,
    *,
    session_factory: Callable = SessionLocal,
    bank_client_factory: Callable = MockBankClient,
) -> None:
    payload = json.loads(message_body)
    process_proposal_job(
        action=payload["action"],
        proposal_id=UUID(payload["proposal_id"]),
        session_factory=session_factory,
        bank_client_factory=bank_client_factory,
    )
