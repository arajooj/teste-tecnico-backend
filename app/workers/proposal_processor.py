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
from app.modules.proposals.infrastructure.models import (
    ProposalJobAction,
    ProposalJobStatus,
    ProposalStatus,
    ProposalType,
)
from app.modules.proposals.infrastructure.repository import ProposalRepository

MODEL_REGISTRY = (identity_models,)
logger = logging.getLogger(__name__)


def process_proposal_job(
    *,
    action: str,
    proposal_id: UUID,
    job_id: UUID,
    session_factory: Callable = SessionLocal,
    bank_client_factory: Callable = MockBankClient,
) -> None:
    logger.info(
        "Processing proposal job",
        extra={"action": action, "proposal_id": str(proposal_id), "job_id": str(job_id)},
    )
    with session_factory() as session:
        proposal_repository = ProposalRepository(session)
        client_repository = ClientRepository(session)
        bank_client = bank_client_factory()

        proposal = proposal_repository.get_by_id(proposal_id=proposal_id)
        if proposal is None:
            raise ProposalNotFoundError()
        job = proposal_repository.get_job_by_id(job_id=job_id)
        if job is None:
            raise InvalidProposalStateError("Proposal job not found")
        if job.status == ProposalJobStatus.COMPLETED.value:
            logger.info("Skipping already completed job", extra={"job_id": str(job_id)})
            return

        client = client_repository.get_by_tenant_and_id(
            tenant_id=proposal.tenant_id,
            client_id=proposal.client_id,
        )
        if client is None:
            raise ProposalClientNotFoundError()

        proposal_repository.mark_job_processing(job, proposal)
        proposal.status = ProposalStatus.PROCESSING.value
        proposal_repository.save(proposal)

        try:
            if action == ProposalJobAction.SIMULATE.value:
                if proposal.simulation_callback_token is None:
                    raise InvalidProposalStateError("Proposal has no simulation callback token")

                protocol = bank_client.simulate(
                    cpf=client.cpf,
                    amount=proposal.amount,
                    installments=proposal.installments,
                    webhook_url=bank_client.build_callback_url(
                        callback_token=proposal.simulation_callback_token
                    ),
                )
                proposal.external_protocol = protocol
                proposal.simulation_protocol = protocol
                proposal.type = ProposalType.SIMULATION.value
                proposal_repository.save(proposal)
                proposal_repository.mark_job_completed(job, proposal)
                logger.info("Simulation sent to bank", extra={"proposal_id": str(proposal.id)})
                return

            if action == ProposalJobAction.SUBMIT.value:
                if proposal.simulation_protocol is None:
                    raise InvalidProposalStateError("Proposal has no simulation protocol")
                if proposal.inclusion_callback_token is None:
                    raise InvalidProposalStateError("Proposal has no inclusion callback token")

                protocol = bank_client.submit(
                    protocol=proposal.simulation_protocol,
                    client_name=client.name,
                    client_cpf=client.cpf,
                    client_birth_date=client.birth_date,
                    amount=proposal.amount,
                    installments=proposal.installments,
                    webhook_url=bank_client.build_callback_url(
                        callback_token=proposal.inclusion_callback_token
                    ),
                )
                proposal.external_protocol = protocol
                proposal.inclusion_protocol = protocol
                proposal.type = ProposalType.PROPOSAL.value
                proposal.status = ProposalStatus.SUBMITTED.value
                proposal_repository.save(proposal)
                proposal_repository.mark_job_completed(job, proposal)
                logger.info("Proposal submitted to bank", extra={"proposal_id": str(proposal.id)})
                return

            raise InvalidProposalStateError("Unsupported proposal queue action")
        except Exception as exc:
            proposal_repository.mark_job_failed(
                job=job,
                proposal=proposal,
                error_message=str(exc),
            )
            raise


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
        job_id=UUID(payload["job_id"]),
        session_factory=session_factory,
        bank_client_factory=bank_client_factory,
    )
