import os

# Garante que o lifespan da API não tente conectar ao PostgreSQL/SQS nos testes.
os.environ.setdefault("ENVIRONMENT", "testing")

import uuid
from collections.abc import Callable, Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import get_db
from app.core.security import create_access_token, hash_password
from app.main import create_application
from app.modules.clients.infrastructure.models import ClientModel
from app.modules.identity.infrastructure.models import TenantModel, UserModel, UserRole
from app.modules.proposals.infrastructure.models import ProposalJobModel, ProposalModel

TABLES = [
    TenantModel.__table__,
    UserModel.__table__,
    ClientModel.__table__,
    ProposalModel.__table__,
    ProposalJobModel.__table__,
]


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    TenantModel.metadata.create_all(bind=engine, tables=TABLES)

    with testing_session_local() as session:
        yield session

    TenantModel.metadata.drop_all(bind=engine, tables=TABLES)
    engine.dispose()


@pytest.fixture
def app(db_session: Session) -> Generator[FastAPI, None, None]:
    application = create_application()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seeded_identity(db_session: Session) -> dict[str, object]:
    tenant_alpha = TenantModel(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        name="Tenant Alpha",
        document="11111111000191",
        is_active=True,
    )
    tenant_beta = TenantModel(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        name="Tenant Beta",
        document="22222222000191",
        is_active=True,
    )
    alpha_user = UserModel(
        id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        tenant_id=tenant_alpha.id,
        name="Alice Alpha",
        email="alpha@example.com",
        password_hash=hash_password("123456"),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    beta_user = UserModel(
        id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        tenant_id=tenant_beta.id,
        name="Bob Beta",
        email="beta@example.com",
        password_hash=hash_password("123456"),
        role=UserRole.OPERATOR.value,
        is_active=True,
    )

    db_session.add_all([tenant_alpha, tenant_beta, alpha_user, beta_user])
    db_session.commit()

    return {
        "tenant_alpha": tenant_alpha,
        "tenant_beta": tenant_beta,
        "alpha_user": alpha_user,
        "beta_user": beta_user,
    }


@pytest.fixture
def make_auth_headers() -> Callable[[UserModel], dict[str, str]]:
    def factory(user: UserModel) -> dict[str, str]:
        access_token = create_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            role=user.role,
        )
        return {"Authorization": f"Bearer {access_token}"}

    return factory
