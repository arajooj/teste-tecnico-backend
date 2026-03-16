from sqlalchemy.orm import Mapped, mapped_column

from app.core import db


class DummyModel(db.Base):
    sample: Mapped[int] = mapped_column(primary_key=True)


class DummySession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_base_declared_tablename_uses_lowercase_class_name():
    assert DummyModel.__tablename__ == "dummymodel"


def test_naming_convention_is_configured():
    assert db.Base.metadata.naming_convention["pk"] == "pk_%(table_name)s"


def test_get_db_yields_session_and_closes_it(monkeypatch):
    fake_session = DummySession()
    monkeypatch.setattr(db, "SessionLocal", lambda: fake_session)

    generator = db.get_db()
    yielded = next(generator)

    assert yielded is fake_session

    try:
        next(generator)
    except StopIteration:
        pass

    assert fake_session.closed is True
