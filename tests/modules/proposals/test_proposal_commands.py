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
from app.modules.proposals.infrastructure.models import (
    ProposalJobModel,
    ProposalJobStatus,
    ProposalModel,
    ProposalStatus,
    ProposalType,
)
from app.modules.proposals.infrastructure.repository import ProposalRepository


class FakeQueue:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def send_message(self, *, action: str, proposal_id: str, job_id: str) -> None:
        self.messages.append({"action": action, "proposal_id": proposal_id, "job_id": job_id})


class FailingQueue(FakeQueue):
    def send_message(self, *, action: str, proposal_id: str, job_id: str) -> None:
        raise RuntimeError("sqs unavailable")


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
    job = db_session.query(ProposalJobModel).one()
    assert proposal.simulation_callback_token is not None
    assert queue.messages == [
        {"action": "simulate", "proposal_id": str(proposal.id), "job_id": str(job.id)}
    ]
    assert job.status == ProposalJobStatus.PUBLISHED.value


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
        simulation_protocol="MOCK-SIM-1",
        simulation_callback_token="token-sim",
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
    job = db_session.query(ProposalJobModel).one()
    assert updated.simulation_callback_token is None
    assert updated.inclusion_callback_token is not None
    assert queue.messages == [
        {"action": "submit", "proposal_id": str(proposal.id), "job_id": str(job.id)}
    ]
    assert job.status == ProposalJobStatus.PUBLISHED.value


def test_create_simulation_marks_job_failed_when_queue_publish_fails(db_session, seeded_identity):
    alpha_user = seeded_identity["alpha_user"]
    client = create_client_for_user(db_session, alpha_user)
    commands = ProposalCommands(
        repository=ProposalRepository(db_session),
        client_repository=ClientRepository(db_session),
        queue=FailingQueue(),
    )

    with pytest.raises(AppException, match="async job could not be published") as exc_info:
        commands.create_simulation(
            actor=to_actor(alpha_user),
            command=SimulateProposalCommand(
                client_id=client.id,
                amount=Decimal("5000.00"),
                installments=12,
            ),
        )

    job = db_session.query(ProposalJobModel).one()
    proposal = db_session.get(ProposalModel, job.proposal_id)

    assert exc_info.value.status_code == 503
    assert job.status == ProposalJobStatus.FAILED.value
    assert proposal is not None
    assert proposal.last_bank_error == "Failed to publish async job: sqs unavailable"
