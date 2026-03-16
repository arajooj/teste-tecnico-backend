from datetime import date
from decimal import Decimal
from uuid import UUID

from app.modules.clients.infrastructure.models import ClientModel
from app.modules.proposals.infrastructure.models import (
    ProposalJobModel,
    ProposalModel,
    ProposalStatus,
    ProposalType,
)
from app.modules.proposals.infrastructure.queue import ProposalQueue


def create_client_for_user(db_session, user, cpf: str = "12345678901") -> ClientModel:
    client = ClientModel(
        tenant_id=user.tenant_id,
        name=f"Client {cpf}",
        cpf=cpf,
        birth_date=date(1990, 1, 1),
        phone="11999999999",
        created_by=user.id,
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def test_simulate_proposal_returns_202_and_persists_pending(
    client,
    db_session,
    seeded_identity,
    make_auth_headers,
    monkeypatch,
):
    alpha_user = seeded_identity["alpha_user"]
    customer = create_client_for_user(db_session, alpha_user)
    sent_messages: list[dict[str, str]] = []
    monkeypatch.setattr(
        ProposalQueue,
        "send_message",
        lambda self, *, action, proposal_id, job_id: sent_messages.append(
            {"action": action, "proposal_id": proposal_id, "job_id": job_id}
        ),
    )

    response = client.post(
        "/api/proposals/simulate",
        headers=make_auth_headers(alpha_user),
        json={
            "client_id": str(customer.id),
            "amount": "5000.00",
            "installments": 12,
        },
    )

    proposal = db_session.get(ProposalModel, UUID(response.json()["id"]))
    job = db_session.query(ProposalJobModel).one()

    assert response.status_code == 202
    assert response.json()["status"] == ProposalStatus.PENDING.value
    assert proposal is not None
    assert proposal.type == ProposalType.SIMULATION.value
    assert proposal.simulation_callback_token is not None
    assert sent_messages == [
        {"action": "simulate", "proposal_id": str(proposal.id), "job_id": str(job.id)}
    ]


def test_list_proposals_returns_only_authenticated_tenant_items(
    client,
    db_session,
    seeded_identity,
    make_auth_headers,
):
    alpha_user = seeded_identity["alpha_user"]
    beta_user = seeded_identity["beta_user"]
    alpha_client = create_client_for_user(db_session, alpha_user, cpf="12345678901")
    beta_client = create_client_for_user(db_session, beta_user, cpf="98765432100")
    db_session.add_all(
        [
            ProposalModel(
                tenant_id=alpha_user.tenant_id,
                client_id=alpha_client.id,
                type=ProposalType.SIMULATION.value,
                amount=Decimal("5000.00"),
                installments=12,
                status=ProposalStatus.SIMULATED.value,
                created_by=alpha_user.id,
            ),
            ProposalModel(
                tenant_id=beta_user.tenant_id,
                client_id=beta_client.id,
                type=ProposalType.SIMULATION.value,
                amount=Decimal("7000.00"),
                installments=18,
                status=ProposalStatus.PROCESSING.value,
                created_by=beta_user.id,
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/proposals", headers=make_auth_headers(alpha_user))

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["tenant_id"] == str(alpha_user.tenant_id)


def test_get_proposal_returns_404_for_other_tenant_record(
    client,
    db_session,
    seeded_identity,
    make_auth_headers,
):
    alpha_user = seeded_identity["alpha_user"]
    beta_user = seeded_identity["beta_user"]
    beta_client = create_client_for_user(db_session, beta_user, cpf="98765432100")
    beta_proposal = ProposalModel(
        tenant_id=beta_user.tenant_id,
        client_id=beta_client.id,
        type=ProposalType.SIMULATION.value,
        amount=Decimal("7000.00"),
        installments=18,
        status=ProposalStatus.SIMULATED.value,
        created_by=beta_user.id,
    )
    db_session.add(beta_proposal)
    db_session.commit()
    db_session.refresh(beta_proposal)

    response = client.get(
        f"/api/proposals/{beta_proposal.id}",
        headers=make_auth_headers(alpha_user),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Proposal not found"}


def test_get_proposal_returns_record_for_authenticated_tenant(
    client,
    db_session,
    seeded_identity,
    make_auth_headers,
):
    alpha_user = seeded_identity["alpha_user"]
    alpha_client = create_client_for_user(db_session, alpha_user)
    alpha_proposal = ProposalModel(
        tenant_id=alpha_user.tenant_id,
        client_id=alpha_client.id,
        type=ProposalType.SIMULATION.value,
        amount=Decimal("5000.00"),
        installments=12,
        status=ProposalStatus.SIMULATED.value,
        created_by=alpha_user.id,
    )
    db_session.add(alpha_proposal)
    db_session.commit()
    db_session.refresh(alpha_proposal)

    response = client.get(
        f"/api/proposals/{alpha_proposal.id}",
        headers=make_auth_headers(alpha_user),
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(alpha_proposal.id)
    assert response.json()["status"] == ProposalStatus.SIMULATED.value


def test_list_proposals_supports_status_and_type_filters(
    client,
    db_session,
    seeded_identity,
    make_auth_headers,
):
    alpha_user = seeded_identity["alpha_user"]
    alpha_client = create_client_for_user(db_session, alpha_user, cpf="11122233344")
    db_session.add_all(
        [
            ProposalModel(
                tenant_id=alpha_user.tenant_id,
                client_id=alpha_client.id,
                type=ProposalType.SIMULATION.value,
                amount=Decimal("5000.00"),
                installments=12,
                status=ProposalStatus.SIMULATED.value,
                created_by=alpha_user.id,
            ),
            ProposalModel(
                tenant_id=alpha_user.tenant_id,
                client_id=alpha_client.id,
                type=ProposalType.PROPOSAL.value,
                amount=Decimal("7000.00"),
                installments=18,
                status=ProposalStatus.APPROVED.value,
                created_by=alpha_user.id,
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        f"/api/proposals?status=approved&type={ProposalType.PROPOSAL.value}",
        headers=make_auth_headers(alpha_user),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["status"] == ProposalStatus.APPROVED.value
    assert response.json()["items"][0]["type"] == ProposalType.PROPOSAL.value


def test_submit_proposal_requires_simulated_status(
    client,
    db_session,
    seeded_identity,
    make_auth_headers,
):
    alpha_user = seeded_identity["alpha_user"]
    customer = create_client_for_user(db_session, alpha_user)
    proposal = ProposalModel(
        tenant_id=alpha_user.tenant_id,
        client_id=customer.id,
        type=ProposalType.SIMULATION.value,
        amount=Decimal("5000.00"),
        installments=12,
        status=ProposalStatus.PENDING.value,
        created_by=alpha_user.id,
    )
    db_session.add(proposal)
    db_session.commit()
    db_session.refresh(proposal)

    response = client.post(
        f"/api/proposals/{proposal.id}/submit",
        headers=make_auth_headers(alpha_user),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Only simulated proposals can be submitted"}


def test_submit_proposal_returns_202_and_queues_job(
    client,
    db_session,
    seeded_identity,
    make_auth_headers,
    monkeypatch,
):
    alpha_user = seeded_identity["alpha_user"]
    customer = create_client_for_user(db_session, alpha_user)
    proposal = ProposalModel(
        tenant_id=alpha_user.tenant_id,
        client_id=customer.id,
        external_protocol="MOCK-SIM-1",
        simulation_protocol="MOCK-SIM-1",
        simulation_callback_token="sim-token-1",
        type=ProposalType.SIMULATION.value,
        amount=Decimal("5000.00"),
        installments=12,
        status=ProposalStatus.SIMULATED.value,
        created_by=alpha_user.id,
    )
    db_session.add(proposal)
    db_session.commit()
    db_session.refresh(proposal)
    sent_messages: list[dict[str, str]] = []
    monkeypatch.setattr(
        ProposalQueue,
        "send_message",
        lambda self, *, action, proposal_id, job_id: sent_messages.append(
            {"action": action, "proposal_id": proposal_id, "job_id": job_id}
        ),
    )

    response = client.post(
        f"/api/proposals/{proposal.id}/submit",
        headers=make_auth_headers(alpha_user),
    )

    db_session.refresh(proposal)
    job = db_session.query(ProposalJobModel).one()

    assert response.status_code == 202
    assert proposal.type == ProposalType.PROPOSAL.value
    assert proposal.status == ProposalStatus.PENDING.value
    assert proposal.simulation_callback_token is None
    assert proposal.inclusion_callback_token is not None
    assert sent_messages == [
        {"action": "submit", "proposal_id": str(proposal.id), "job_id": str(job.id)}
    ]
