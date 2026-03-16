import json
from contextlib import nullcontext
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.exceptions import AppException
from app.core.security import AuthenticatedUser
from app.modules.clients.infrastructure.models import ClientModel
from app.modules.clients.infrastructure.repository import ClientRepository
from app.modules.proposals.application.commands import ProposalCommands
from app.modules.proposals.application.queries import ProposalQueries
from app.modules.proposals.infrastructure.models import ProposalModel, ProposalStatus, ProposalType
from app.modules.proposals.infrastructure.queue import ProposalQueue
from app.modules.proposals.infrastructure.repository import ProposalRepository
from app.modules.webhooks.application.services import BankCallbackCommand, WebhookService
from app.modules.webhooks.infrastructure.repository import WebhookRepository
from app.workers import proposal_processor


def make_actor(seeded_identity) -> AuthenticatedUser:
    user = seeded_identity["alpha_user"]
    return AuthenticatedUser(user_id=user.id, tenant_id=user.tenant_id, role=user.role)


def create_client(db_session, seeded_identity, cpf: str = "12345678901") -> ClientModel:
    user = seeded_identity["alpha_user"]
    client = ClientModel(
        tenant_id=user.tenant_id,
        name=f"Proposal Client {cpf}",
        cpf=cpf,
        birth_date=date(1990, 1, 1),
        phone="11999999999",
        created_by=user.id,
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def create_proposal(
    db_session,
    seeded_identity,
    client_id,
    *,
    proposal_type: str = ProposalType.SIMULATION.value,
    status: str = ProposalStatus.PENDING.value,
    external_protocol: str | None = None,
) -> ProposalModel:
    user = seeded_identity["alpha_user"]
    proposal = ProposalModel(
        tenant_id=user.tenant_id,
        client_id=client_id,
        external_protocol=external_protocol,
        type=proposal_type,
        amount=Decimal("5000.00"),
        installments=12,
        status=status,
        created_by=user.id,
    )
    db_session.add(proposal)
    db_session.commit()
    db_session.refresh(proposal)
    return proposal


class DummyQueue(ProposalQueue):
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def send_message(self, *, action: str, proposal_id: str) -> None:
        self.messages.append({"action": action, "proposal_id": proposal_id})


class DummyBankClient:
    def __init__(self, submit_protocol: str = "MOCK-PROP-1") -> None:
        self.submit_protocol = submit_protocol

    def simulate(self, **kwargs) -> str:
        return "MOCK-SIM-1"

    def submit(self, **kwargs) -> str:
        return self.submit_protocol


def test_proposal_commands_submit_rejects_missing_proposal(db_session, seeded_identity):
    actor = make_actor(seeded_identity)
    commands = ProposalCommands(
        repository=ProposalRepository(db_session),
        client_repository=ClientRepository(db_session),
        queue=DummyQueue(),
    )

    with pytest.raises(AppException, match="Proposal not found"):
        commands.submit(actor=actor, proposal_id=uuid4())


def test_proposal_queries_get_by_id_returns_proposal(db_session, seeded_identity):
    actor = make_actor(seeded_identity)
    client = create_client(db_session, seeded_identity)
    proposal = create_proposal(
        db_session,
        seeded_identity,
        client.id,
        status=ProposalStatus.SIMULATED.value,
    )
    queries = ProposalQueries(ProposalRepository(db_session))

    found = queries.get_by_id(actor=actor, proposal_id=proposal.id)

    assert found.id == proposal.id


def test_proposal_repository_filters_by_status_and_type(db_session, seeded_identity):
    repository = ProposalRepository(db_session)
    client = create_client(db_session, seeded_identity)
    create_proposal(
        db_session,
        seeded_identity,
        client.id,
        proposal_type=ProposalType.SIMULATION.value,
        status=ProposalStatus.SIMULATED.value,
    )
    create_proposal(
        db_session,
        seeded_identity,
        client.id,
        proposal_type=ProposalType.PROPOSAL.value,
        status=ProposalStatus.APPROVED.value,
        external_protocol="MOCK-PROP-2",
    )

    filtered_items = repository.list_by_tenant(
        tenant_id=seeded_identity["alpha_user"].tenant_id,
        page=1,
        page_size=10,
        status=ProposalStatus.APPROVED.value,
        proposal_type=ProposalType.PROPOSAL.value,
    )
    filtered_total = repository.count_by_tenant(
        tenant_id=seeded_identity["alpha_user"].tenant_id,
        status=ProposalStatus.APPROVED.value,
        proposal_type=ProposalType.PROPOSAL.value,
    )

    assert filtered_total == 1
    assert len(filtered_items) == 1
    assert filtered_items[0].type == ProposalType.PROPOSAL.value


def test_webhook_service_maps_simulation_rejection_to_failed(db_session, seeded_identity):
    client = create_client(db_session, seeded_identity, cpf="99988877766")
    proposal = create_proposal(
        db_session,
        seeded_identity,
        client.id,
        status=ProposalStatus.PROCESSING.value,
        external_protocol="MOCK-SIM-REJECTED",
    )
    service = WebhookService(WebhookRepository(ProposalRepository(db_session)))

    updated = service.handle_bank_callback(
        command=BankCallbackCommand(
            protocol="MOCK-SIM-REJECTED",
            event="simulation_completed",
            status="rejected",
            data={"reason": "score too low"},
            timestamp="2026-03-16T10:00:00",
        )
    )

    assert updated.id == proposal.id
    assert updated.status == ProposalStatus.SIMULATION_FAILED.value


def test_worker_rejects_missing_proposal(db_session):
    with pytest.raises(AppException, match="Proposal not found"):
        proposal_processor.process_queue_message(
            json.dumps({"action": "simulate", "proposal_id": str(uuid4())}),
            session_factory=lambda: nullcontext(db_session),
            bank_client_factory=DummyBankClient,
        )


def test_worker_rejects_missing_client(db_session, seeded_identity):
    proposal = ProposalModel(
        tenant_id=seeded_identity["alpha_user"].tenant_id,
        client_id=uuid4(),
        type=ProposalType.SIMULATION.value,
        amount=Decimal("5000.00"),
        installments=12,
        status=ProposalStatus.PENDING.value,
        created_by=seeded_identity["alpha_user"].id,
    )
    db_session.add(proposal)
    db_session.commit()
    db_session.refresh(proposal)

    with pytest.raises(AppException, match="Client not found"):
        proposal_processor.process_queue_message(
            json.dumps({"action": "simulate", "proposal_id": str(proposal.id)}),
            session_factory=lambda: nullcontext(db_session),
            bank_client_factory=DummyBankClient,
        )


def test_worker_rejects_submit_without_simulation_protocol(db_session, seeded_identity):
    client = create_client(db_session, seeded_identity, cpf="55544433322")
    proposal = create_proposal(
        db_session,
        seeded_identity,
        client.id,
        proposal_type=ProposalType.PROPOSAL.value,
        status=ProposalStatus.SIMULATED.value,
    )

    with pytest.raises(AppException, match="Proposal has no simulation protocol"):
        proposal_processor.process_queue_message(
            json.dumps({"action": "submit", "proposal_id": str(proposal.id)}),
            session_factory=lambda: nullcontext(db_session),
            bank_client_factory=DummyBankClient,
        )


def test_worker_rejects_unsupported_queue_action(db_session, seeded_identity):
    client = create_client(db_session, seeded_identity, cpf="33322211100")
    proposal = create_proposal(db_session, seeded_identity, client.id)

    with pytest.raises(AppException, match="Unsupported proposal queue action"):
        proposal_processor.process_queue_message(
            json.dumps({"action": "cancel", "proposal_id": str(proposal.id)}),
            session_factory=lambda: nullcontext(db_session),
            bank_client_factory=DummyBankClient,
        )
