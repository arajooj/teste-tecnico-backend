from contextlib import nullcontext
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app import main
from app.modules.clients.infrastructure.models import ClientModel
from app.modules.proposals.infrastructure.models import (
    ProposalJobAction,
    ProposalJobModel,
    ProposalJobStatus,
    ProposalModel,
    ProposalStatus,
    ProposalType,
)


class FakeQueue:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def send_message(self, *, action: str, proposal_id: str, job_id: str) -> None:
        self.messages.append({"action": action, "proposal_id": proposal_id, "job_id": job_id})


def test_dispatch_pending_jobs_republishes_failed_jobs(db_session, seeded_identity, monkeypatch):
    alpha_user = seeded_identity["alpha_user"]
    client = ClientModel(
        tenant_id=alpha_user.tenant_id,
        name="Redispatch Client",
        cpf="12345678901",
        birth_date=date(1990, 1, 1),
        phone="11999999999",
        created_by=alpha_user.id,
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)

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

    job = ProposalJobModel(
        proposal_id=proposal.id,
        action=ProposalJobAction.SIMULATE.value,
        status=ProposalJobStatus.FAILED.value,
        payload={"action": "simulate", "proposal_id": str(proposal.id)},
        last_error="previous error",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    queue = FakeQueue()
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: SimpleNamespace(environment="development"),
    )
    monkeypatch.setattr(main, "SessionLocal", lambda: nullcontext(db_session))
    monkeypatch.setattr(main, "ProposalQueue", lambda: queue)

    main.dispatch_pending_jobs()

    db_session.refresh(job)
    db_session.refresh(proposal)

    assert queue.messages == [
        {"action": "simulate", "proposal_id": str(proposal.id), "job_id": str(job.id)}
    ]
    assert job.status == ProposalJobStatus.PUBLISHED.value
    assert proposal.last_enqueued_at is not None


def test_dispatch_pending_jobs_skips_orphan_jobs(monkeypatch):
    orphan_job = SimpleNamespace(id=uuid4(), proposal_id=uuid4(), action="simulate")

    class FakeRepository:
        def __init__(self, _session) -> None:
            self.mark_job_published_called = False

        def list_dispatchable_jobs(self):
            return [orphan_job]

        def get_by_id(self, *, proposal_id):
            assert proposal_id == orphan_job.proposal_id
            return None

        def mark_job_published(self, job, proposal):  # pragma: no cover
            self.mark_job_published_called = True

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: SimpleNamespace(environment="development"),
    )
    monkeypatch.setattr(main, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(main, "ProposalRepository", FakeRepository)
    monkeypatch.setattr(main, "ProposalQueue", FakeQueue)

    main.dispatch_pending_jobs()
