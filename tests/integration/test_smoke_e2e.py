import os
import time

import httpx
import pytest


def _build_cpf() -> str:
    return str(time.time_ns())[-11:]


def _poll_proposal(
    client: httpx.Client,
    *,
    base_url: str,
    token: str,
    proposal_id: str,
    expected_statuses: set[str],
    timeout_seconds: float = 25.0,
) -> dict:
    deadline = time.monotonic() + timeout_seconds
    headers = {"Authorization": f"Bearer {token}"}

    while time.monotonic() < deadline:
        response = client.get(f"{base_url}/api/proposals/{proposal_id}", headers=headers)
        response.raise_for_status()
        payload = response.json()
        if payload["status"] in expected_statuses:
            return payload
        time.sleep(1.0)

    raise AssertionError(
        f"Proposal {proposal_id} did not reach one of {sorted(expected_statuses)} in time"
    )


@pytest.mark.integration
def test_smoke_e2e_local_async_flow():
    if os.getenv("RUN_DOCKER_E2E") != "1":
        pytest.skip("Set RUN_DOCKER_E2E=1 to run the local docker smoke test")

    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    tenant_id = os.getenv("E2E_TENANT_ID", "11111111-1111-1111-1111-111111111111")
    email = os.getenv("E2E_EMAIL", "alpha@example.com")
    password = os.getenv("E2E_PASSWORD", "123456")

    with httpx.Client(timeout=15.0) as client:
        login_response = client.post(
            f"{base_url}/api/auth/login",
            json={"tenant_id": tenant_id, "email": email, "password": password},
        )
        login_response.raise_for_status()
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        create_client_response = client.post(
            f"{base_url}/api/clients",
            headers=headers,
            json={
                "name": "Smoke Test Client",
                "cpf": _build_cpf(),
                "birth_date": "1990-01-01",
                "phone": "11999999999",
            },
        )
        create_client_response.raise_for_status()
        client_id = create_client_response.json()["id"]

        simulated_payload = None
        for _ in range(3):
            simulate_response = client.post(
                f"{base_url}/api/proposals/simulate",
                headers=headers,
                json={
                    "client_id": client_id,
                    "amount": "5000.00",
                    "installments": 12,
                },
            )
            simulate_response.raise_for_status()
            proposal_id = simulate_response.json()["id"]
            proposal_payload = _poll_proposal(
                client,
                base_url=base_url,
                token=token,
                proposal_id=proposal_id,
                expected_statuses={"simulated", "simulation_failed"},
            )
            if proposal_payload["status"] == "simulated":
                simulated_payload = proposal_payload
                break

        assert simulated_payload is not None, "Simulation never reached a successful state"

        submit_response = client.post(
            f"{base_url}/api/proposals/{simulated_payload['id']}/submit",
            headers=headers,
        )
        submit_response.raise_for_status()

        final_payload = _poll_proposal(
            client,
            base_url=base_url,
            token=token,
            proposal_id=simulated_payload["id"],
            expected_statuses={"approved", "rejected"},
        )

        assert final_payload["status"] in {"approved", "rejected"}
        assert final_payload["bank_response"] is not None
