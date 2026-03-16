"""Worker responsible for processing queued proposal jobs."""

from __future__ import annotations

import json
import time
from uuid import UUID

from app.core.db import SessionLocal
from app.modules.clients.infrastructure.repository import ClientRepository
from app.modules.proposals.domain.exceptions import (
    InvalidProposalStateError,
    ProposalClientNotFoundError,
    ProposalNotFoundError,
)
from app.modules.proposals.infrastructure.bank_client import MockBankClient
from app.modules.proposals.infrastructure.models import ProposalStatus, ProposalType
from app.modules.proposals.infrastructure.queue import ProposalQueue
from app.modules.proposals.infrastructure.repository import ProposalRepository


def process_queue_message(message_body: str) -> None:
    payload = json.loads(message_body)
    action = payload["action"]
    proposal_id = UUID(payload["proposal_id"])

    with SessionLocal() as session:
        proposal_repository = ProposalRepository(session)
        client_repository = ClientRepository(session)
        bank_client = MockBankClient()

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
            return

        raise InvalidProposalStateError("Unsupported proposal queue action")


def run_worker(poll_interval_seconds: int = 2) -> None:
    queue = ProposalQueue()
    while True:
        messages = queue.receive_messages(wait_time_seconds=10)
        for message in messages:
            process_queue_message(message["Body"])
            queue.delete_message(receipt_handle=message["ReceiptHandle"])
        time.sleep(poll_interval_seconds)


if __name__ == "__main__":  # pragma: no cover
    run_worker()
