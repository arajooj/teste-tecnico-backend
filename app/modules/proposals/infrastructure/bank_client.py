"""HTTP client for the provided mock bank service."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx

from app.core.config import get_settings


class MockBankClient:
    """Wraps synchronous HTTP calls to the mock bank."""

    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.mock_bank_base_url).rstrip("/")
        self._timeout = timeout

    def simulate(
        self,
        *,
        cpf: str,
        amount: Decimal,
        installments: int,
        webhook_url: str | None = None,
    ) -> str:
        payload = {
            "cpf": cpf,
            "amount": float(amount),
            "installments": installments,
            "webhook_url": webhook_url,
        }
        response = httpx.post(
            f"{self._base_url}/api/simular",
            json=payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()["protocol"]

    def submit(
        self,
        *,
        protocol: str,
        client_name: str,
        client_cpf: str,
        client_birth_date: date,
        amount: Decimal,
        installments: int,
        webhook_url: str | None = None,
    ) -> str:
        payload = {
            "protocol": protocol,
            "client_name": client_name,
            "client_cpf": client_cpf,
            "client_birth_date": client_birth_date.isoformat(),
            "amount": float(amount),
            "installments": installments,
            "webhook_url": webhook_url,
        }
        response = httpx.post(
            f"{self._base_url}/api/incluir",
            json=payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()["protocol"]
