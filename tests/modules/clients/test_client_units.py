from datetime import date

import pytest

from app.core.exceptions import AppException
from app.core.security import AuthenticatedUser
from app.modules.clients.application.commands import (
    ClientCommands,
    CreateClientCommand,
    UpdateClientCommand,
)
from app.modules.clients.application.queries import ClientQueries
from app.modules.clients.infrastructure.models import ClientModel
from app.modules.clients.infrastructure.repository import ClientRepository


def make_actor(seeded_identity) -> AuthenticatedUser:
    user = seeded_identity["alpha_user"]
    return AuthenticatedUser(user_id=user.id, tenant_id=user.tenant_id, role=user.role)


def create_client(db_session, seeded_identity, cpf: str = "12345678901") -> ClientModel:
    user = seeded_identity["alpha_user"]
    client = ClientModel(
        tenant_id=user.tenant_id,
        name="Client Unit",
        cpf=cpf,
        birth_date=date(1990, 1, 1),
        phone="11999999999",
        created_by=user.id,
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def test_client_commands_create_rejects_duplicate_cpf(db_session, seeded_identity):
    actor = make_actor(seeded_identity)
    repository = ClientRepository(db_session)
    commands = ClientCommands(repository)
    create_client(db_session, seeded_identity)

    with pytest.raises(AppException, match="Client with this CPF already exists"):
        commands.create(
            actor=actor,
            command=CreateClientCommand(
                name="Duplicated",
                cpf="12345678901",
                birth_date=date(1990, 1, 1),
                phone="11999999999",
            ),
        )


def test_client_commands_update_rejects_missing_client(db_session, seeded_identity):
    actor = make_actor(seeded_identity)
    repository = ClientRepository(db_session)
    commands = ClientCommands(repository)

    with pytest.raises(AppException, match="Client not found"):
        commands.update(
            actor=actor,
            command=UpdateClientCommand(
                client_id=seeded_identity["beta_user"].id,
                name="Missing",
                cpf="99988877766",
                birth_date=date(1990, 1, 1),
                phone="11999999999",
            ),
        )


def test_client_commands_update_persists_changes(db_session, seeded_identity):
    actor = make_actor(seeded_identity)
    repository = ClientRepository(db_session)
    commands = ClientCommands(repository)
    client = create_client(db_session, seeded_identity)

    updated = commands.update(
        actor=actor,
        command=UpdateClientCommand(
            client_id=client.id,
            name="Updated Client",
            cpf="12345678901",
            birth_date=date(1991, 2, 2),
            phone="11888888888",
        ),
    )

    assert updated.name == "Updated Client"
    assert str(updated.birth_date) == "1991-02-02"
    assert updated.phone == "11888888888"


def test_client_queries_get_by_id_returns_client(db_session, seeded_identity):
    actor = make_actor(seeded_identity)
    repository = ClientRepository(db_session)
    queries = ClientQueries(repository)
    client = create_client(db_session, seeded_identity)

    found = queries.get_by_id(actor=actor, client_id=client.id)

    assert found.id == client.id


def test_client_repository_save_updates_existing_client(db_session, seeded_identity):
    repository = ClientRepository(db_session)
    client = create_client(db_session, seeded_identity)
    client.phone = "11777777777"

    saved = repository.save(client)

    assert saved.phone == "11777777777"
