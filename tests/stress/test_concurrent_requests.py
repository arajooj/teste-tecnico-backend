"""Concurrent stress tests for the API.

These tests are excluded from the default pytest run via the `stress` marker.
They can run in-process or against a real API by setting `STRESS_API_URL`.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from time import perf_counter

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("ENVIRONMENT", "testing")

def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


MAX_CONCURRENCY = _env_int("STRESS_MAX_CONCURRENCY", 40)
CLIENT_TIMEOUT_SECONDS = _env_float("STRESS_CLIENT_TIMEOUT_SECONDS", 20.0)

LOGIN_REQUESTS = _env_int("STRESS_LOGIN_REQUESTS", 200)
LIST_REQUESTS = _env_int("STRESS_LIST_REQUESTS", 400)
CREATE_CLIENT_REQUESTS = _env_int("STRESS_CREATE_CLIENT_REQUESTS", 120)
PROPOSAL_LIST_REQUESTS = _env_int("STRESS_PROPOSAL_LIST_REQUESTS", 300)

LOGIN_TIME_LIMIT_SECONDS = _env_float(
    "STRESS_LOGIN_TIME_LIMIT_SECONDS",
    max(10.0, LOGIN_REQUESTS / max(MAX_CONCURRENCY, 1) * 2.0),
)
LIST_TIME_LIMIT_SECONDS = _env_float(
    "STRESS_LIST_TIME_LIMIT_SECONDS",
    max(10.0, LIST_REQUESTS / max(MAX_CONCURRENCY, 1) * 2.0),
)
CREATE_CLIENT_TIME_LIMIT_SECONDS = _env_float(
    "STRESS_CREATE_CLIENT_TIME_LIMIT_SECONDS",
    max(12.0, CREATE_CLIENT_REQUESTS / max(MAX_CONCURRENCY, 1) * 3.0),
)
PROPOSAL_LIST_TIME_LIMIT_SECONDS = _env_float(
    "STRESS_PROPOSAL_LIST_TIME_LIMIT_SECONDS",
    max(10.0, PROPOSAL_LIST_REQUESTS / max(MAX_CONCURRENCY, 1) * 2.0),
)

TENANT_ID = "11111111-1111-1111-1111-111111111111"
EMAIL = "alpha@example.com"
PASSWORD = "123456"

pytestmark = pytest.mark.stress


@dataclass(frozen=True)
class StressContext:
    base_url: str
    transport: httpx.AsyncBaseTransport | None
    tenant_id: str
    email: str
    password: str


@pytest.fixture
def stress_context(tmp_path: pytest.TempPathFactory) -> StressContext:
    from app.core.db import Base, get_db
    from app.main import create_application

    api_url = os.getenv("STRESS_API_URL")
    if api_url:
        return StressContext(
            base_url=api_url.rstrip("/"),
            transport=None,
            tenant_id=os.getenv("STRESS_TENANT_ID", TENANT_ID),
            email=os.getenv("STRESS_EMAIL", EMAIL),
            password=os.getenv("STRESS_PASSWORD", PASSWORD),
        )

    database_path = tmp_path / "stress.sqlite3"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")

    _seed_stress_database(session_local)

    app = create_application()

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    return StressContext(
        base_url="http://testserver",
        transport=httpx.ASGITransport(app=app),
        tenant_id=TENANT_ID,
        email=EMAIL,
        password=PASSWORD,
    )


def _seed_stress_database(session_local: sessionmaker[Session]) -> None:
    from app.core.security import hash_password
    from app.modules.clients.infrastructure.models import ClientModel
    from app.modules.identity.infrastructure.models import TenantModel, UserModel, UserRole
    from app.modules.proposals.infrastructure.models import (
        ProposalModel,
        ProposalStatus,
        ProposalType,
    )

    with session_local() as session:
        tenant = TenantModel(
            id=uuid.UUID(TENANT_ID),
            name="Tenant Alpha",
            document="11111111000191",
            is_active=True,
        )
        user = UserModel(
            id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            tenant_id=tenant.id,
            name="Alice Alpha",
            email=EMAIL,
            password_hash=hash_password(PASSWORD),
            role=UserRole.ADMIN.value,
            is_active=True,
        )
        session.add_all([tenant, user])
        session.commit()

        clients: list[ClientModel] = []
        for index in range(1, 6):
            client = ClientModel(
                tenant_id=tenant.id,
                name=f"Stress Client {index}",
                cpf=f"{index:011d}",
                birth_date=date(1990, 1, index),
                phone=f"1199999000{index}",
                created_by=user.id,
            )
            clients.append(client)
        session.add_all(clients)
        session.commit()

        proposals = [
            ProposalModel(
                tenant_id=tenant.id,
                client_id=clients[0].id,
                type=ProposalType.SIMULATION.value,
                amount=Decimal("5000.00"),
                installments=12,
                status=ProposalStatus.SIMULATED.value,
                created_by=user.id,
            ),
            ProposalModel(
                tenant_id=tenant.id,
                client_id=clients[1].id,
                type=ProposalType.PROPOSAL.value,
                amount=Decimal("7000.00"),
                installments=18,
                status=ProposalStatus.APPROVED.value,
                created_by=user.id,
            ),
        ]
        session.add_all(proposals)
        session.commit()


async def _build_async_client(context: StressContext) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=context.base_url,
        timeout=CLIENT_TIMEOUT_SECONDS,
        transport=context.transport,
    )


async def _login(client: httpx.AsyncClient, context: StressContext) -> httpx.Response:
    return await client.post(
        "/api/auth/login",
        json={
            "tenant_id": context.tenant_id,
            "email": context.email,
            "password": context.password,
        },
    )


async def _auth_headers(
    client: httpx.AsyncClient,
    context: StressContext,
) -> dict[str, str]:
    response = await _login(client, context)
    response.raise_for_status()
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _build_unique_cpf(index: int) -> str:
    suffix = str(uuid.uuid4().int)[-8:]
    return f"321{index:03d}{suffix}"[:11]


async def _assert_all_ok(responses: list[httpx.Response], *, expected_status: int) -> None:
    payloads = [
        {"status": response.status_code, "body": response.text}
        for response in responses
        if response.status_code != expected_status
    ]
    assert not payloads, payloads


async def _run_bounded(
    total_requests: int,
    request_factory,
) -> list[httpx.Response]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async def run_one(index: int) -> httpx.Response:
        async with semaphore:
            return await request_factory(index)

    return await asyncio.gather(*(run_one(index) for index in range(total_requests)))


@pytest.mark.asyncio
async def test_many_concurrent_logins(stress_context: StressContext) -> None:
    async with await _build_async_client(stress_context) as client:
        started_at = perf_counter()
        responses = await _run_bounded(
            LOGIN_REQUESTS,
            lambda _index: _login(client, stress_context),
        )
        elapsed_seconds = perf_counter() - started_at

    await _assert_all_ok(responses, expected_status=200)
    assert elapsed_seconds < LOGIN_TIME_LIMIT_SECONDS


@pytest.mark.asyncio
async def test_many_concurrent_list_clients(stress_context: StressContext) -> None:
    async with await _build_async_client(stress_context) as client:
        headers = await _auth_headers(client, stress_context)
        started_at = perf_counter()
        responses = await _run_bounded(
            LIST_REQUESTS,
            lambda _index: client.get("/api/clients?page=1&page_size=20", headers=headers),
        )
        elapsed_seconds = perf_counter() - started_at

    await _assert_all_ok(responses, expected_status=200)
    assert elapsed_seconds < LIST_TIME_LIMIT_SECONDS
    assert all(response.json()["items"] is not None for response in responses)


@pytest.mark.asyncio
async def test_many_concurrent_create_clients(stress_context: StressContext) -> None:
    async with await _build_async_client(stress_context) as client:
        headers = await _auth_headers(client, stress_context)
        started_at = perf_counter()
        responses = await _run_bounded(
            CREATE_CLIENT_REQUESTS,
            lambda index: client.post(
                "/api/clients",
                headers=headers,
                json={
                    "name": f"Concurrent Client {index}",
                    "cpf": _build_unique_cpf(index),
                    "birth_date": "1991-01-01",
                    "phone": "11999999999",
                },
            ),
        )
        elapsed_seconds = perf_counter() - started_at

    await _assert_all_ok(responses, expected_status=201)
    assert elapsed_seconds < CREATE_CLIENT_TIME_LIMIT_SECONDS


@pytest.mark.asyncio
async def test_many_concurrent_list_proposals(stress_context: StressContext) -> None:
    async with await _build_async_client(stress_context) as client:
        headers = await _auth_headers(client, stress_context)
        started_at = perf_counter()
        responses = await _run_bounded(
            PROPOSAL_LIST_REQUESTS,
            lambda _index: client.get("/api/proposals?page=1&page_size=20", headers=headers),
        )
        elapsed_seconds = perf_counter() - started_at

    await _assert_all_ok(responses, expected_status=200)
    assert elapsed_seconds < PROPOSAL_LIST_TIME_LIMIT_SECONDS
    assert all(isinstance(response.json()["items"], list) for response in responses)
