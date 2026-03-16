from datetime import date
from decimal import Decimal

import pytest

from app.core.exceptions import AppException
from app.core.security import AuthenticatedUser
from app.modules.clients.infrastructure.models import ClientModel
from app.modules.clients.infrastructure.repository import ClientRepository
from app.modules.proposals.application.commands import (
    ProposalCommands,
    SimulateProposalCommand,
)
from app.modules.proposals.infrastructure.models import ProposalModel, ProposalStatus, ProposalType
from app.modules.proposals.infrastructure.repository import ProposalRepository


class FakeQueue:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def send_message(self, *, action: str, proposal_id: str) -> None:
        self.messages.append({"action": action, "proposal_id": proposal_id})


def create_client_for_user(db_session, user) -> ClientModel:
    client = ClientModel(
        tenant_id=user.tenant_id,
        name="Maria Silva",
        cpf="12345678901",
        birth_date=date(1990, 1, 1),
        phone="11999999999",
        created_by=user.id,
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def to_actor(user) -> AuthenticatedUser:
    return AuthenticatedUser(user_id=user.id, tenant_id=user.tenant_id, role=user.role)


def test_create_simulation_creates_pending_proposal_and_enqueues_job(db_session, seeded_identity):
    alpha_user = seeded_identity["alpha_user"]
    client = create_client_for_user(db_session, alpha_user)
    queue = FakeQueue()
    commands = ProposalCommands(
        repository=ProposalRepository(db_session),
        client_repository=ClientRepository(db_session),
        queue=queue,
    )

    proposal = commands.create_simulation(
        actor=to_actor(alpha_user),
        command=SimulateProposalCommand(
            client_id=client.id,
            amount=Decimal("5000.00"),
            installments=12,
        ),
    )

    assert proposal.type == ProposalType.SIMULATION.value
    assert proposal.status == ProposalStatus.PENDING.value
    assert queue.messages == [{"action": "simulate", "proposal_id": str(proposal.id)}]


def test_create_simulation_rejects_client_from_other_tenant(db_session, seeded_identity):
    alpha_user = seeded_identity["alpha_user"]
    beta_user = seeded_identity["beta_user"]
    client = create_client_for_user(db_session, beta_user)
    commands = ProposalCommands(
        repository=ProposalRepository(db_session),
        client_repository=ClientRepository(db_session),
        queue=FakeQueue(),
    )

    with pytest.raises(AppException, match="Client not found"):
        commands.create_simulation(
            actor=to_actor(alpha_user),
            command=SimulateProposalCommand(
                client_id=client.id,
                amount=Decimal("5000.00"),
                installments=12,
            ),
        )


def test_submit_requires_simulated_status(db_session, seeded_identity):
    alpha_user = seeded_identity["alpha_user"]
    client = create_client_for_user(db_session, alpha_user)
    proposal = ProposalModel(
        tenant_id=alpha_user.tenant_id,
        client_id=client.id,
        type=ProposalType.SIMULATION.value,
        amount=Decimal("5000.00"),
        installments=12,
        status=ProposalStatus.PENDING.value,
        created_by=alpha_user.id,
    )
    db_session.add(proposal)
    db_session.commit()
    db_session.refresh(proposal)
    commands = ProposalCommands(
        repository=ProposalRepository(db_session),
        client_repository=ClientRepository(db_session),
        queue=FakeQueue(),
    )

    with pytest.raises(AppException, match="Only simulated proposals can be submitted"):
        commands.submit(actor=to_actor(alpha_user), proposal_id=proposal.id)


def test_submit_reuses_same_record_and_enqueues_submit(db_session, seeded_identity):
    alpha_user = seeded_identity["alpha_user"]
    client = create_client_for_user(db_session, alpha_user)
    proposal = ProposalModel(
        tenant_id=alpha_user.tenant_id,
        client_id=client.id,
        external_protocol="MOCK-SIM-1",
        type=ProposalType.SIMULATION.value,
        amount=Decimal("5000.00"),
        installments=12,
        status=ProposalStatus.SIMULATED.value,
        created_by=alpha_user.id,
    )
    db_session.add(proposal)
    db_session.commit()
    db_session.refresh(proposal)
    queue = FakeQueue()
    commands = ProposalCommands(
        repository=ProposalRepository(db_session),
        client_repository=ClientRepository(db_session),
        queue=queue,
    )

    updated = commands.submit(actor=to_actor(alpha_user), proposal_id=proposal.id)

    assert updated.id == proposal.id
    assert updated.type == ProposalType.PROPOSAL.value
    assert updated.status == ProposalStatus.PENDING.value
    assert queue.messages == [{"action": "submit", "proposal_id": str(proposal.id)}]
