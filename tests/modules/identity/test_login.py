from app.core.security import decode_access_token


def test_login_returns_bearer_token(client, seeded_identity):
    response = client.post(
        "/api/auth/login",
        json={"email": "alpha@example.com", "password": "123456"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_token_exposes_authenticated_context(client, seeded_identity):
    response = client.post(
        "/api/auth/login",
        json={"email": "alpha@example.com", "password": "123456"},
    )

    payload = decode_access_token(response.json()["access_token"])
    alpha_user = seeded_identity["alpha_user"]

    assert payload.user_id == alpha_user.id
    assert payload.tenant_id == alpha_user.tenant_id
    assert payload.role == alpha_user.role


def test_login_rejects_invalid_credentials(client, seeded_identity):
    response = client.post(
        "/api/auth/login",
        json={"email": "alpha@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}
