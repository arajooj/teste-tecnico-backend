from app.core.security import decode_access_token, hash_password


def test_login_returns_bearer_token(client, seeded_identity):
    response = client.post(
        "/api/auth/login",
        json={
            "tenant_id": str(seeded_identity["tenant_alpha"].id),
            "email": "alpha@example.com",
            "password": "123456",
        },
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_token_exposes_authenticated_context(client, seeded_identity):
    response = client.post(
        "/api/auth/login",
        json={
            "tenant_id": str(seeded_identity["tenant_alpha"].id),
            "email": "alpha@example.com",
            "password": "123456",
        },
    )

    payload = decode_access_token(response.json()["access_token"])
    alpha_user = seeded_identity["alpha_user"]

    assert payload.user_id == alpha_user.id
    assert payload.tenant_id == alpha_user.tenant_id
    assert payload.role == alpha_user.role


def test_login_rejects_invalid_credentials(client, seeded_identity):
    response = client.post(
        "/api/auth/login",
        json={
            "tenant_id": str(seeded_identity["tenant_alpha"].id),
            "email": "alpha@example.com",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


def test_login_requires_tenant_id(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "alpha@example.com", "password": "123456"},
    )

    assert response.status_code == 422


def test_login_uses_tenant_id_to_disambiguate_same_email(
    client,
    db_session,
    seeded_identity,
):
    shared_email = "shared@example.com"
    tenant_alpha = seeded_identity["tenant_alpha"]
    tenant_beta = seeded_identity["tenant_beta"]
    alpha_user = seeded_identity["alpha_user"]
    beta_user = seeded_identity["beta_user"]
    alpha_user.email = shared_email
    beta_user.email = shared_email
    db_session.commit()

    alpha_response = client.post(
        "/api/auth/login",
        json={
            "tenant_id": str(tenant_alpha.id),
            "email": shared_email,
            "password": "123456",
        },
    )
    beta_response = client.post(
        "/api/auth/login",
        json={
            "tenant_id": str(tenant_beta.id),
            "email": shared_email,
            "password": "123456",
        },
    )

    alpha_payload = decode_access_token(alpha_response.json()["access_token"])
    beta_payload = decode_access_token(beta_response.json()["access_token"])

    assert alpha_response.status_code == 200
    assert beta_response.status_code == 200
    assert alpha_payload.user_id == alpha_user.id
    assert beta_payload.user_id == beta_user.id


def test_login_rejects_password_from_other_tenant(client, db_session, seeded_identity):
    shared_email = "shared@example.com"
    tenant_alpha = seeded_identity["tenant_alpha"]
    alpha_user = seeded_identity["alpha_user"]
    beta_user = seeded_identity["beta_user"]
    alpha_user.email = shared_email
    beta_user.email = shared_email
    beta_user.password_hash = hash_password("654321")
    db_session.commit()

    response = client.post(
        "/api/auth/login",
        json={
            "tenant_id": str(tenant_alpha.id),
            "email": shared_email,
            "password": "123456",
        },
    )

    assert response.status_code == 200
    assert decode_access_token(response.json()["access_token"]).user_id == alpha_user.id
