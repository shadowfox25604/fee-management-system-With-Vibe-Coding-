"""Pytest uses an isolated SQLite database — never data/fee_management.db."""

from __future__ import annotations

import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base
from backend.core.schema_migrations import apply_sqlite_column_migrations, apply_sqlite_data_migrations
from backend.models import entities  # noqa: F401


def _patch_test_modules(monkeypatch, test_engine, test_session_factory) -> None:
    import backend.core.database as database

    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "SessionLocal", test_session_factory)
    for mod_name, mod in list(sys.modules.items()):
        if not mod_name.startswith("tests.") or mod is None:
            continue
        if hasattr(mod, "SessionLocal"):
            monkeypatch.setattr(mod, "SessionLocal", test_session_factory)
        if hasattr(mod, "engine"):
            monkeypatch.setattr(mod, "engine", test_engine)


@pytest.fixture(autouse=True)
def isolated_test_database(monkeypatch, tmp_path):
    """Fresh DB file per test; production fee_management.db is never read or written."""
    os.environ["FEE_MANAGEMENT_TESTING"] = "1"
    db_path = tmp_path / "pytest_fee.sqlite"
    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=test_engine)
    apply_sqlite_column_migrations(test_engine)
    apply_sqlite_data_migrations(test_engine)
    TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    _patch_test_modules(monkeypatch, test_engine, TestSession)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db_session(isolated_test_database):
    """SQLAlchemy session bound to the isolated per-test database."""
    factory = sessionmaker(bind=isolated_test_database, autoflush=False, autocommit=False)
    s = factory()
    try:
        yield s
    finally:
        s.close()
