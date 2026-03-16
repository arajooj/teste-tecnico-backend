from datetime import date
from decimal import Decimal

import pytest

from app.core.exceptions import AppException
from app.modules.clients.infrastructure.models import ClientModel
from app.modules.proposals.infrastructure.models import ProposalModel, ProposalStatus, ProposalType
from app.modules.proposals.infrastructure.repository import ProposalRepository
from app.modules.webhooks.application.services import BankCallbackCommand, WebhookService
from app.modules.webhooks.infrastructure.repository import WebhookRepository


def create_client_for_user(db_session, user, cpf: str = "12345678901") -> ClientModel:
    client = ClientModel(
        tenant_id=user.tenant_id,
        name="Webhook Client",
        cpf=cpf,
        birth_date=date(1990, 1, 1),
        phone="11999999999",
        created_by=user.id,
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def create_service(db_session) -> WebhookService:
    repository = WebhookRepository(ProposalRepository(db_session))
    return WebhookService(repository)


def test_bank_callback_api_maps_simulation_approval(client, db_session, seeded_identity):
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
        status=ProposalStatus.PROCESSING.value,
        created_by=alpha_user.id,
    )
    db_session.add(proposal)
    db_session.commit()

    response = client.post(
        "/api/webhooks/bank-callback?callback_token=sim-token-1",
        json={
            "protocol": "MOCK-SIM-1",
            "event": "simulation_completed",
            "status": "approved",
            "data": {"interest_rate": 1.99, "installment_value": 245.50},
            "timestamp": "2026-03-16T10:00:00",
        },
    )

    db_session.refresh(proposal)

    assert response.status_code == 204
    assert proposal.status == ProposalStatus.SIMULATED.value
    assert float(proposal.interest_rate) == 1.99
    assert float(proposal.installment_value) == 245.5


def test_bank_callback_api_maps_inclusion_rejection_and_accepts_duplicates(
    client,
    db_session,
    seeded_identity,
):
    alpha_user = seeded_identity["alpha_user"]
    customer = create_client_for_user(db_session, alpha_user)
    proposal = ProposalModel(
        tenant_id=alpha_user.tenant_id,
        client_id=customer.id,
        external_protocol="MOCK-PROP-1",
        inclusion_protocol="MOCK-PROP-1",
        inclusion_callback_token="inc-token-1",
        type=ProposalType.PROPOSAL.value,
        amount=Decimal("5000.00"),
        installments=12,
        status=ProposalStatus.SUBMITTED.value,
        created_by=alpha_user.id,
    )
    db_session.add(proposal)
    db_session.commit()
    payload = {
        "protocol": "MOCK-PROP-1",
        "event": "inclusion_completed",
        "status": "rejected",
        "data": {"reason": "Documentação pendente"},
        "timestamp": "2026-03-16T10:00:00",
    }

    first_response = client.post(
        "/api/webhooks/bank-callback?callback_token=inc-token-1",
        json=payload,
    )
    second_response = client.post(
        "/api/webhooks/bank-callback?callback_token=inc-token-1",
        json=payload,
    )

    db_session.refresh(proposal)

    assert first_response.status_code == 204
    assert second_response.status_code == 204
    assert proposal.status == ProposalStatus.REJECTED.value
    assert proposal.bank_response["data"]["reason"] == "Documentação pendente"


def test_webhook_service_maps_inclusion_approval_to_approved(db_session, seeded_identity):
    alpha_user = seeded_identity["alpha_user"]
    customer = create_client_for_user(db_session, alpha_user)
    proposal = ProposalModel(
        tenant_id=alpha_user.tenant_id,
        client_id=customer.id,
        external_protocol="MOCK-PROP-2",
        inclusion_protocol="MOCK-PROP-2",
        inclusion_callback_token="inc-token-2",
        type=ProposalType.PROPOSAL.value,
        amount=Decimal("5000.00"),
        installments=12,
        status=ProposalStatus.SUBMITTED.value,
        created_by=alpha_user.id,
    )
    db_session.add(proposal)
    db_session.commit()
    db_session.refresh(proposal)
    service = create_service(db_session)

    updated = service.handle_bank_callback(
        command=BankCallbackCommand(
            callback_token="inc-token-2",
            protocol="MOCK-PROP-2",
            event="inclusion_completed",
            status="approved",
            data={"contract_number": "CTR-123"},
            timestamp="2026-03-16T10:00:00",
        )
    )

    assert updated.status == ProposalStatus.APPROVED.value
    assert updated.bank_response["data"]["contract_number"] == "CTR-123"


def test_webhook_service_rejects_unknown_protocol(db_session):
    service = create_service(db_session)

    with pytest.raises(AppException, match="Proposal not found"):
        service.handle_bank_callback(
            command=BankCallbackCommand(
                callback_token="missing-token",
                protocol="UNKNOWN",
                event="simulation_completed",
                status="approved",
                data={},
                timestamp="2026-03-16T10:00:00",
            )
        )


def test_webhook_service_rejects_unsupported_event(db_session, seeded_identity):
    alpha_user = seeded_identity["alpha_user"]
    customer = create_client_for_user(db_session, alpha_user, cpf="32165498700")
    proposal = ProposalModel(
        tenant_id=alpha_user.tenant_id,
        client_id=customer.id,
        external_protocol="MOCK-UNKNOWN-1",
        simulation_protocol="MOCK-UNKNOWN-1",
        simulation_callback_token="sim-token-unknown",
        type=ProposalType.SIMULATION.value,
        amount=Decimal("5000.00"),
        installments=12,
        status=ProposalStatus.PROCESSING.value,
        created_by=alpha_user.id,
    )
    db_session.add(proposal)
    db_session.commit()
    service = create_service(db_session)

    with pytest.raises(AppException, match="Unsupported bank callback event"):
        service.handle_bank_callback(
            command=BankCallbackCommand(
                callback_token="sim-token-unknown",
                protocol="MOCK-UNKNOWN-1",
                event="unknown_event",
                status="approved",
                data={},
                timestamp="2026-03-16T10:00:00",
            )
        )


def test_bank_callback_api_rejects_invalid_callback_token(client):
    response = client.post(
        "/api/webhooks/bank-callback?callback_token=invalid-token",
        json={
            "protocol": "UNKNOWN",
            "event": "simulation_completed",
            "status": "approved",
            "data": {},
            "timestamp": "2026-03-16T10:00:00",
        },
    )

    assert response.status_code == 404


def test_webhook_service_rejects_tardy_simulation_callback_after_submit(
    db_session,
    seeded_identity,
):
    alpha_user = seeded_identity["alpha_user"]
    customer = create_client_for_user(db_session, alpha_user, cpf="55566677788")
    proposal = ProposalModel(
        tenant_id=alpha_user.tenant_id,
        client_id=customer.id,
        external_protocol="MOCK-PROP-LATEST",
        simulation_protocol="MOCK-SIM-OLD",
        inclusion_protocol="MOCK-PROP-LATEST",
        simulation_callback_token=None,
        inclusion_callback_token="inc-token-latest",
        type=ProposalType.PROPOSAL.value,
        amount=Decimal("5000.00"),
        installments=12,
        status=ProposalStatus.SUBMITTED.value,
        created_by=alpha_user.id,
    )
    db_session.add(proposal)
    db_session.commit()
    service = create_service(db_session)

    with pytest.raises(AppException, match="Proposal not found"):
        service.handle_bank_callback(
            command=BankCallbackCommand(
                callback_token="old-simulation-token",
                protocol="MOCK-SIM-OLD",
                event="simulation_completed",
                status="approved",
                data={"interest_rate": 1.99},
                timestamp="2026-03-16T10:00:00",
            )
        )


def test_webhook_service_private_guards_cover_invalid_paths(db_session, seeded_identity):
    alpha_user = seeded_identity["alpha_user"]
    customer = create_client_for_user(db_session, alpha_user, cpf="99900011122")
    proposal = ProposalModel(
        tenant_id=alpha_user.tenant_id,
        client_id=customer.id,
        external_protocol="MOCK-SIM-GUARD",
        simulation_protocol="MOCK-SIM-GUARD",
        simulation_callback_token="sim-guard-token",
        inclusion_protocol="MOCK-PROP-GUARD",
        inclusion_callback_token="inc-guard-token",
        type=ProposalType.PROPOSAL.value,
        amount=Decimal("5000.00"),
        installments=12,
        status=ProposalStatus.SUBMITTED.value,
        created_by=alpha_user.id,
    )
    db_session.add(proposal)
    db_session.commit()
    service = create_service(db_session)

    with pytest.raises(AppException, match="Proposal not found"):
        service._resolve_phase(proposal=proposal, callback_token="unknown-token")

    with pytest.raises(AppException, match="Callback protocol does not match"):
        service._validate_protocol(
            proposal=proposal,
            phase="simulation",
            protocol="WRONG-PROTOCOL",
        )

    with pytest.raises(AppException, match="Simulation callback received for an invalid phase"):
        service._validate_transition(
            proposal=proposal,
            event="simulation_completed",
            phase="inclusion",
        )

    with pytest.raises(AppException, match="Simulation callback is not valid for the current state"):
        service._validate_transition(
            proposal=proposal,
            event="simulation_completed",
            phase="simulation",
        )

    with pytest.raises(AppException, match="Inclusion callback received for an invalid phase"):
        service._validate_transition(
            proposal=proposal,
            event="inclusion_completed",
            phase="simulation",
        )

    proposal.status = ProposalStatus.PROCESSING.value
    with pytest.raises(AppException, match="Inclusion callback is not valid for the current state"):
        service._validate_transition(
            proposal=proposal,
            event="inclusion_completed",
            phase="inclusion",
        )

    with pytest.raises(AppException, match="Unsupported bank callback event"):
        service._validate_transition(
            proposal=proposal,
            event="unexpected_event",
            phase="simulation",
        )

    with pytest.raises(AppException, match="Unsupported bank callback event"):
        service._map_callback_status(event="unexpected_event", external_status="approved")
