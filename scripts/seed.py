"""Seed initial tenants and users required by the technical test."""

from __future__ import annotations

import uuid

from passlib.context import CryptContext
from sqlalchemy import select

from app.core.db import SessionLocal
from app.modules.identity.infrastructure.models import TenantModel, UserModel, UserRole


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


TENANTS = [
    {
        "id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
        "name": "Tenant Alpha",
        "document": "11111111000191",
    },
    {
        "id": uuid.UUID("22222222-2222-2222-2222-222222222222"),
        "name": "Tenant Beta",
        "document": "22222222000191",
    },
]

USERS = [
    {
        "id": uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        "tenant_id": TENANTS[0]["id"],
        "name": "Alice Alpha",
        "email": "alpha@example.com",
        "password": "123456",
        "role": UserRole.ADMIN.value,
    },
    {
        "id": uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        "tenant_id": TENANTS[1]["id"],
        "name": "Bob Beta",
        "email": "beta@example.com",
        "password": "123456",
        "role": UserRole.OPERATOR.value,
    },
]


def upsert_tenants() -> None:
    with SessionLocal() as session:
        for tenant_data in TENANTS:
            tenant = session.scalar(
                select(TenantModel).where(TenantModel.document == tenant_data["document"])
            )
            if tenant is None:
                session.add(TenantModel(**tenant_data))
            else:
                tenant.name = tenant_data["name"]
                tenant.is_active = True

        session.commit()


def upsert_users() -> None:
    with SessionLocal() as session:
        for user_data in USERS:
            user = session.scalar(
                select(UserModel).where(
                    UserModel.tenant_id == user_data["tenant_id"],
                    UserModel.email == user_data["email"],
                )
            )
            password_hash = pwd_context.hash(user_data["password"])

            if user is None:
                session.add(
                    UserModel(
                        id=user_data["id"],
                        tenant_id=user_data["tenant_id"],
                        name=user_data["name"],
                        email=user_data["email"],
                        password_hash=password_hash,
                        role=user_data["role"],
                        is_active=True,
                    )
                )
            else:
                user.name = user_data["name"]
                user.password_hash = password_hash
                user.role = user_data["role"]
                user.is_active = True

        session.commit()


def main() -> None:
    upsert_tenants()
    upsert_users()
    print("Seed executado com sucesso.")


if __name__ == "__main__":
    main()
