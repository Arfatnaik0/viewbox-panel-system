import os
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    default_path = Path(__file__).resolve().parents[1] / "viewbox.sqlite3"
    return os.environ.get("DATABASE_URL", f"sqlite:///{default_path}")


def make_engine(url: str) -> Engine:
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _record) -> None:
            connection.execute("PRAGMA foreign_keys=ON")

    return engine


engine = make_engine(database_url())
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def lock_for_write(session: Session) -> None:
    # SQLite does not have row locks. Reserve the write lock before reading
    # values that this transaction will change, such as OTP attempts.
    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
