from __future__ import annotations

from dataclasses import dataclass, field

from scripts import seed


@dataclass
class FakeSession:
    scalar_results: list[object | None]
    added: list[object] = field(default_factory=list)
    committed: int = 0
    scalar_calls: int = 0

    def scalar(self, _query):
        result = self.scalar_results[self.scalar_calls]
        self.scalar_calls += 1
        return result

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.committed += 1


class FakeSessionFactory:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    def __call__(self):
        return self

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb):
        return False


class ExistingTenant:
    def __init__(self) -> None:
        self.name = ""
        self.is_active = False


class ExistingUser:
    def __init__(self) -> None:
        self.name = ""
        self.password_hash = ""
        self.role = ""
        self.is_active = False


def test_upsert_tenants_inserts_missing_records(monkeypatch):
    fake_session = FakeSession([None, None])
    monkeypatch.setattr(seed, "SessionLocal", FakeSessionFactory(fake_session))

    seed.upsert_tenants()

    assert len(fake_session.added) == 2
    assert fake_session.committed == 1


def test_upsert_tenants_updates_existing_records(monkeypatch):
    tenants = [ExistingTenant(), ExistingTenant()]
    fake_session = FakeSession(tenants)
    monkeypatch.setattr(seed, "SessionLocal", FakeSessionFactory(fake_session))

    seed.upsert_tenants()

    assert fake_session.added == []
    assert all(tenant.is_active for tenant in tenants)
    assert fake_session.committed == 1


def test_upsert_users_inserts_missing_records(monkeypatch):
    fake_session = FakeSession([None, None])
    monkeypatch.setattr(seed, "SessionLocal", FakeSessionFactory(fake_session))
    monkeypatch.setattr(seed.pwd_context, "hash", lambda value: f"hashed-{value}")

    seed.upsert_users()

    assert len(fake_session.added) == 2
    assert fake_session.committed == 1


def test_upsert_users_updates_existing_records(monkeypatch):
    users = [ExistingUser(), ExistingUser()]
    fake_session = FakeSession(users)
    monkeypatch.setattr(seed, "SessionLocal", FakeSessionFactory(fake_session))
    monkeypatch.setattr(seed.pwd_context, "hash", lambda value: f"hashed-{value}")

    seed.upsert_users()

    assert fake_session.added == []
    assert all(user.is_active for user in users)
    assert all(user.password_hash.startswith("hashed-") for user in users)
    assert fake_session.committed == 1


def test_main_runs_seed_steps_and_prints_success(monkeypatch):
    calls = []
    monkeypatch.setattr(seed, "upsert_tenants", lambda: calls.append("tenants"))
    monkeypatch.setattr(seed, "upsert_users", lambda: calls.append("users"))
    monkeypatch.setattr("builtins.print", lambda message: calls.append(message))

    seed.main()

    assert calls == ["tenants", "users", "Seed executado com sucesso."]
