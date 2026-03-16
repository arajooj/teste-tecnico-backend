import json
from contextlib import nullcontext
from datetime import date
from decimal import Decimal

from app.modules.clients.infrastructure.models import ClientModel
from app.modules.proposals.infrastructure.bank_client import MockBankClient
from app.modules.proposals.infrastructure.models import (
    ProposalJobAction,
    ProposalJobModel,
    ProposalJobStatus,
    ProposalModel,
    ProposalStatus,
    ProposalType,
)
from app.workers import proposal_processor


def create_client_for_user(db_session, user) -> ClientModel:
    client = ClientModel(
        tenant_id=user.tenant_id,
        name="Worker Client",
        cpf="12345678901",
        birth_date=date(1990, 1, 1),
        phone="11999999999",
        created_by=user.id,
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def create_job_for_proposal(db_session, proposal: ProposalModel, action: str) -> ProposalJobModel:
    job = ProposalJobModel(
        proposal_id=proposal.id,
        action=action,
        status=ProposalJobStatus.PUBLISHED.value,
        payload={"action": action, "proposal_id": str(proposal.id)},
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def test_worker_processes_simulation_message(db_session, seeded_identity, monkeypatch):
    alpha_user = seeded_identity["alpha_user"]
    customer = create_client_for_user(db_session, alpha_user)
    proposal = ProposalModel(
        tenant_id=alpha_user.tenant_id,
        client_id=customer.id,
        simulation_callback_token="simulation-token",
        type=ProposalType.SIMULATION.value,
        amount=Decimal("5000.00"),
        installments=12,
        status=ProposalStatus.PENDING.value,
        created_by=alpha_user.id,
    )
    db_session.add(proposal)
    db_session.commit()
    db_session.refresh(proposal)
    job = create_job_for_proposal(db_session, proposal, ProposalJobAction.SIMULATE.value)

    def bank_client_factory() -> MockBankClient:
        return MockBankClient()

    monkeypatch.setattr(MockBankClient, "simulate", lambda self, **kwargs: "MOCK-SIM-1")

    proposal_processor.process_queue_message(
        json.dumps(
            {"action": "simulate", "proposal_id": str(proposal.id), "job_id": str(job.id)}
        ),
        session_factory=lambda: nullcontext(db_session),
        bank_client_factory=bank_client_factory,
    )

    db_session.expire_all()
    proposal = db_session.get(ProposalModel, proposal.id)
    job = db_session.get(ProposalJobModel, job.id)

    assert proposal.status == ProposalStatus.PROCESSING.value
    assert proposal.external_protocol == "MOCK-SIM-1"
    assert proposal.simulation_protocol == "MOCK-SIM-1"
    assert job.status == ProposalJobStatus.COMPLETED.value


def test_worker_processes_submit_message(db_session, seeded_identity, monkeypatch):
    alpha_user = seeded_identity["alpha_user"]
    customer = create_client_for_user(db_session, alpha_user)
    proposal = ProposalModel(
        tenant_id=alpha_user.tenant_id,
        client_id=customer.id,
        external_protocol="MOCK-SIM-1",
        simulation_protocol="MOCK-SIM-1",
        inclusion_callback_token="inclusion-token",
        type=ProposalType.SIMULATION.value,
        amount=Decimal("5000.00"),
        installments=12,
        status=ProposalStatus.SIMULATED.value,
        created_by=alpha_user.id,
    )
    db_session.add(proposal)
    db_session.commit()
    db_session.refresh(proposal)
    job = create_job_for_proposal(db_session, proposal, ProposalJobAction.SUBMIT.value)

    def bank_client_factory() -> MockBankClient:
        return MockBankClient()

    monkeypatch.setattr(MockBankClient, "submit", lambda self, **kwargs: "MOCK-PROP-1")

    proposal_processor.process_queue_message(
        json.dumps({"action": "submit", "proposal_id": str(proposal.id), "job_id": str(job.id)}),
        session_factory=lambda: nullcontext(db_session),
        bank_client_factory=bank_client_factory,
    )

    db_session.expire_all()
    proposal = db_session.get(ProposalModel, proposal.id)
    job = db_session.get(ProposalJobModel, job.id)

    assert proposal.type == ProposalType.PROPOSAL.value
    assert proposal.status == ProposalStatus.SUBMITTED.value
    assert proposal.external_protocol == "MOCK-PROP-1"
    assert proposal.inclusion_protocol == "MOCK-PROP-1"
    assert job.status == ProposalJobStatus.COMPLETED.value
