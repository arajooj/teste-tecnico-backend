from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import AppException, register_exception_handlers


def test_app_exception_stores_message_and_status_code():
    exc = AppException("boom", status_code=422)

    assert exc.message == "boom"
    assert exc.status_code == 422


def test_registered_exception_handler_returns_json_response():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/error")
    def error_route():
        raise AppException("expected failure", status_code=409)

    with TestClient(app) as client:
        response = client.get("/error")

    assert response.status_code == 409
    assert response.json() == {"detail": "expected failure"}
