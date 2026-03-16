from datetime import date
from decimal import Decimal

from app.modules.proposals.infrastructure.bank_client import MockBankClient
from app.modules.proposals.infrastructure.queue import ProposalQueue


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeSQSClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []

    def get_queue_url(self, QueueName: str) -> dict[str, str]:
        return {"QueueUrl": f"https://example.com/{QueueName}"}

    def send_message(self, **kwargs) -> None:
        self.sent_messages.append(kwargs)


def test_queue_send_message_serializes_expected_payload():
    client = FakeSQSClient()
    queue = ProposalQueue(sqs_client=client, queue_name="proposal-processing-queue")

    queue.send_message(action="simulate", proposal_id="proposal-123")

    assert client.sent_messages == [
        {
            "QueueUrl": "https://example.com/proposal-processing-queue",
            "MessageBody": '{"action": "simulate", "proposal_id": "proposal-123"}',
        }
    ]


def test_bank_client_simulate_returns_protocol(monkeypatch):
    captured_request: dict = {}

    def fake_post(url: str, json: dict, timeout: float):
        captured_request.update({"url": url, "json": json, "timeout": timeout})
        return FakeResponse({"protocol": "MOCK-SIM-1"})

    monkeypatch.setattr("app.modules.proposals.infrastructure.bank_client.httpx.post", fake_post)

    protocol = MockBankClient(base_url="http://mock-bank").simulate(
        cpf="12345678901",
        amount=Decimal("5000.00"),
        installments=12,
    )

    assert protocol == "MOCK-SIM-1"
    assert captured_request["url"] == "http://mock-bank/api/simular"
    assert captured_request["json"]["cpf"] == "12345678901"


def test_bank_client_submit_returns_protocol(monkeypatch):
    captured_request: dict = {}

    def fake_post(url: str, json: dict, timeout: float):
        captured_request.update({"url": url, "json": json, "timeout": timeout})
        return FakeResponse({"protocol": "MOCK-PROP-1"})

    monkeypatch.setattr("app.modules.proposals.infrastructure.bank_client.httpx.post", fake_post)

    protocol = MockBankClient(base_url="http://mock-bank").submit(
        protocol="MOCK-SIM-1",
        client_name="Maria Silva",
        client_cpf="12345678901",
        client_birth_date=date(1990, 1, 1),
        amount=Decimal("5000.00"),
        installments=12,
    )

    assert protocol == "MOCK-PROP-1"
    assert captured_request["url"] == "http://mock-bank/api/incluir"
    assert captured_request["json"]["protocol"] == "MOCK-SIM-1"
