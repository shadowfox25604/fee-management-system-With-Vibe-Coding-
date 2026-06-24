"""Load client teaching and non-teaching faculty into the database."""

from __future__ import annotations

from backend.core.client_faculty_data import (
    CLIENT_FACULTY_ROWS,
    CLIENT_NON_TEACHING_FACULTY,
    CLIENT_TEACHING_FACULTY,
)
from backend.core.database import SessionLocal, engine
from backend.core.schema_migrations import (
    apply_sqlite_column_migrations,
    apply_sqlite_data_migrations,
)
from backend.models import entities  # noqa: F401
from backend.services.expense_service import ExpenseService


def _load_faculty_rows(
    rows: tuple[tuple[str, str, float], ...],
    *,
    faculty_type: str,
    role: str,
) -> int:
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    session = SessionLocal()
    try:
        service = ExpenseService(session)
        created = 0
        for employee_id, faculty_name, monthly_salary in rows:
            service.assign_faculty_salary(
                faculty_name,
                monthly_salary,
                employee_id=employee_id,
                faculty_type=faculty_type,
                role=role,
                default_working_days=26,
                is_active=True,
            )
            created += 1
        return created
    finally:
        session.close()


def load_client_teaching_faculty() -> int:
    return _load_faculty_rows(
        CLIENT_TEACHING_FACULTY,
        faculty_type="Teaching",
        role="Teacher",
    )


def load_client_non_teaching_faculty() -> int:
    return _load_faculty_rows(
        CLIENT_NON_TEACHING_FACULTY,
        faculty_type="Non Teaching",
        role="Staff",
    )


def load_client_faculty() -> int:
    teaching = load_client_teaching_faculty()
    non_teaching = load_client_non_teaching_faculty()
    return teaching + non_teaching


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "non-teaching":
        count = load_client_non_teaching_faculty()
        print(f"Loaded {count} non-teaching faculty records.")
    elif len(sys.argv) > 1 and sys.argv[1] == "teaching":
        count = load_client_teaching_faculty()
        print(f"Loaded {count} teaching faculty records.")
    else:
        count = load_client_faculty()
        print(f"Loaded {count} faculty records (teaching + non-teaching).")
