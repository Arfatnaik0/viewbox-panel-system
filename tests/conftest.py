import os
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path
from shutil import copyfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import create_app


BACKEND = Path(__file__).resolve().parents[1] / "backend"


@pytest.fixture(scope="session")
def migrated_demo_db(tmp_path_factory):
    database = tmp_path_factory.mktemp("viewbox-demo") / "panel.sqlite3"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{database}"}
    for module_args in (("alembic", "upgrade", "head"), ("app.seed",)):
        result = subprocess.run(
            [sys.executable, "-m", *module_args],
            cwd=BACKEND,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    assert database.is_file()
    return database


@pytest.fixture
def database_url(migrated_demo_db, tmp_path):
    database = tmp_path / "panel.sqlite3"
    copyfile(migrated_demo_db, database)
    return f"sqlite:///{database}"


@pytest.fixture
def make_client(database_url):
    app = create_app(database_url=database_url)
    with ExitStack() as stack:
        yield lambda: stack.enter_context(TestClient(app, base_url="https://testserver"))


@pytest.fixture
def session_factory(database_url):
    engine = create_engine(database_url)
    try:
        yield sessionmaker(bind=engine)
    finally:
        engine.dispose()
