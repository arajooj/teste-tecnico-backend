from app.core.config import get_settings


def test_healthcheck_returns_api_status(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_healthcheck_exposes_current_environment(client):
    response = client.get("/health")

    assert response.json()["environment"] == get_settings().environment
