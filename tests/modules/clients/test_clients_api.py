import uuid
from datetime import date

from app.modules.clients.infrastructure.models import ClientModel


def test_create_client_requires_authentication(client):
    response = client.post(
        "/api/clients",
        json={
            "name": "Maria Silva",
            "cpf": "12345678901",
            "birth_date": "1990-01-01",
            "phone": "11999999999",
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_create_client_scopes_record_to_authenticated_tenant(
    client,
    db_session,
    seeded_identity,
    make_auth_headers,
):
    alpha_user = seeded_identity["alpha_user"]

    response = client.post(
        "/api/clients",
        headers=make_auth_headers(alpha_user),
        json={
            "name": "Maria Silva",
            "cpf": "12345678901",
            "birth_date": "1990-01-01",
            "phone": "11999999999",
        },
    )

    created_client = db_session.get(ClientModel, uuid.UUID(response.json()["id"]))

    assert response.status_code == 201
    assert response.json()["tenant_id"] == str(alpha_user.tenant_id)
    assert created_client is not None
    assert created_client.tenant_id == alpha_user.tenant_id


def test_list_clients_returns_only_authenticated_tenant_records(
    client,
    db_session,
    seeded_identity,
    make_auth_headers,
):
    alpha_user = seeded_identity["alpha_user"]
    beta_user = seeded_identity["beta_user"]
    db_session.add_all(
        [
            ClientModel(
                tenant_id=alpha_user.tenant_id,
                name="Client Alpha",
                cpf="12345678901",
                birth_date=date(1990, 1, 1),
                phone="11999999999",
                created_by=alpha_user.id,
            ),
            ClientModel(
                tenant_id=beta_user.tenant_id,
                name="Client Beta",
                cpf="98765432100",
                birth_date=date(1992, 2, 2),
                phone="11888888888",
                created_by=beta_user.id,
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/clients", headers=make_auth_headers(alpha_user))

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["name"] for item in response.json()["items"]] == ["Client Alpha"]


def test_get_client_returns_404_for_other_tenant_record(
    client,
    db_session,
    seeded_identity,
    make_auth_headers,
):
    alpha_user = seeded_identity["alpha_user"]
    beta_user = seeded_identity["beta_user"]
    beta_client = ClientModel(
        tenant_id=beta_user.tenant_id,
        name="Client Beta",
        cpf="98765432100",
        birth_date=date(1992, 2, 2),
        phone="11888888888",
        created_by=beta_user.id,
    )
    db_session.add(beta_client)
    db_session.commit()

    response = client.get(
        f"/api/clients/{beta_client.id}",
        headers=make_auth_headers(alpha_user),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Client not found"}


def test_get_client_returns_record_for_authenticated_tenant(
    client,
    db_session,
    seeded_identity,
    make_auth_headers,
):
    alpha_user = seeded_identity["alpha_user"]
    alpha_client = ClientModel(
        tenant_id=alpha_user.tenant_id,
        name="Client Alpha",
        cpf="12345678901",
        birth_date=date(1990, 1, 1),
        phone="11999999999",
        created_by=alpha_user.id,
    )
    db_session.add(alpha_client)
    db_session.commit()

    response = client.get(
        f"/api/clients/{alpha_client.id}",
        headers=make_auth_headers(alpha_user),
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(alpha_client.id)
    assert response.json()["name"] == "Client Alpha"


def test_update_client_rejects_duplicate_cpf_within_same_tenant(
    client,
    db_session,
    seeded_identity,
    make_auth_headers,
):
    alpha_user = seeded_identity["alpha_user"]
    first_client = ClientModel(
        tenant_id=alpha_user.tenant_id,
        name="Client One",
        cpf="12345678901",
        birth_date=date(1990, 1, 1),
        phone="11999999999",
        created_by=alpha_user.id,
    )
    second_client = ClientModel(
        tenant_id=alpha_user.tenant_id,
        name="Client Two",
        cpf="10987654321",
        birth_date=date(1991, 1, 1),
        phone="11888888888",
        created_by=alpha_user.id,
    )
    db_session.add_all([first_client, second_client])
    db_session.commit()

    response = client.put(
        f"/api/clients/{second_client.id}",
        headers=make_auth_headers(alpha_user),
        json={
            "name": "Client Two Updated",
            "cpf": "12345678901",
            "birth_date": "1991-01-01",
            "phone": "11777777777",
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Client with this CPF already exists"}


def test_update_client_persists_changes_for_authenticated_tenant(
    client,
    db_session,
    seeded_identity,
    make_auth_headers,
):
    alpha_user = seeded_identity["alpha_user"]
    alpha_client = ClientModel(
        tenant_id=alpha_user.tenant_id,
        name="Client Alpha",
        cpf="12345678901",
        birth_date=date(1990, 1, 1),
        phone="11999999999",
        created_by=alpha_user.id,
    )
    db_session.add(alpha_client)
    db_session.commit()
    db_session.refresh(alpha_client)

    response = client.put(
        f"/api/clients/{alpha_client.id}",
        headers=make_auth_headers(alpha_user),
        json={
            "name": "Client Alpha Updated",
            "cpf": "12345678901",
            "birth_date": "1990-05-10",
            "phone": "11777777777",
        },
    )

    db_session.refresh(alpha_client)

    assert response.status_code == 200
    assert response.json()["name"] == "Client Alpha Updated"
    assert str(alpha_client.birth_date) == "1990-05-10"
    assert alpha_client.phone == "11777777777"
