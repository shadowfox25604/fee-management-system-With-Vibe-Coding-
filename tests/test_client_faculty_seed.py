"""Client faculty roster is seeded automatically on first app launch."""

from sqlalchemy.orm import sessionmaker

from backend.core.client_faculty_data import (
    CLIENT_FACULTY_ROWS,
    CLIENT_NON_TEACHING_FACULTY,
    CLIENT_TEACHING_FACULTY,
)
from backend.core.database import Base
from backend.core.schema_migrations import (
    apply_sqlite_column_migrations,
    apply_sqlite_data_migrations,
)
from backend.models import FacultySalary, entities  # noqa: F401


def test_client_faculty_catalog_counts():
    assert len(CLIENT_TEACHING_FACULTY) == 26
    assert len(CLIENT_NON_TEACHING_FACULTY) == 13
    assert len(CLIENT_FACULTY_ROWS) == 39


def test_seed_client_faculty_v1_on_empty_database(isolated_test_database):
    Base.metadata.create_all(bind=isolated_test_database)
    apply_sqlite_column_migrations(isolated_test_database)
    apply_sqlite_data_migrations(isolated_test_database)

    session = sessionmaker(bind=isolated_test_database)()
    try:
        rows = session.query(FacultySalary).order_by(FacultySalary.employee_id.asc()).all()
        assert len(rows) == 39
        assert sum(1 for row in rows if row.faculty_type == "Teaching") == 26
        assert sum(1 for row in rows if row.faculty_type == "Non Teaching") == 13
        assert {row.employee_id.lower() for row in rows} == {
            emp.lower() for emp, _, _, _, _ in CLIENT_FACULTY_ROWS
        }
    finally:
        session.close()
