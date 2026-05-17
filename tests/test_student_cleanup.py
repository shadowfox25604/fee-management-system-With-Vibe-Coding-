"""Meta-tests: pytest must not touch the production database file."""

from pathlib import Path

from backend.core.config import DB_PATH


def test_pytest_does_not_use_production_db_path(isolated_test_database):
    import backend.core.database as database

    url = str(isolated_test_database.url)
    assert Path(DB_PATH).as_posix() not in url.replace("\\", "/")
    assert str(database.engine.url) == url
