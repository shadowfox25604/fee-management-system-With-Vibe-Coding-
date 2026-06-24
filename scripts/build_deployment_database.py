"""Build the preloaded client database shipped in Deployment/data/.

Creates a fresh SQLite database with:
  * Login users (Admin / Accountant)
  * Full faculty roster (39)
  * Inactive old students from inactive students.xlsx (41)
  * Active old students from ready to add.xlsx (417; 1 overlap kept inactive,
    1 incomplete row skipped)

Usage (from project root):
    .venv\\Scripts\\python.exe scripts\\build_deployment_database.py
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOYMENT_DATA = ROOT / "Deployment" / "data"
DEFAULT_EXCEL = Path.home() / "Desktop" / "inactive students.xlsx"
DEFAULT_ACTIVE_EXCEL = Path.home() / "Desktop" / "ready to add.xlsx"

EXPECTED_FACULTY = 39
EXPECTED_INACTIVE = 41
EXPECTED_ACTIVE = 417


def build_deployment_database(
    *,
    excel_path: Path = DEFAULT_EXCEL,
    active_excel_path: Path = DEFAULT_ACTIVE_EXCEL,
    output_dir: Path = DEPLOYMENT_DATA,
) -> Path:
    if not excel_path.is_file():
        raise FileNotFoundError(f"Inactive student Excel not found: {excel_path}")
    if not active_excel_path.is_file():
        raise FileNotFoundError(f"Active student Excel not found: {active_excel_path}")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    os.environ["FEE_MANAGEMENT_DATA_DIR"] = str(output_dir.resolve())
    os.environ["PYTHONPATH"] = str(ROOT)

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from backend.core.database import Base, SessionLocal, engine
    from backend.core.master_key import ensure_master_key_file
    from backend.core.schema_migrations import (
        apply_sqlite_column_migrations,
        apply_sqlite_data_migrations,
    )
    from backend.models import FacultySalary, Student, entities  # noqa: F401
    from backend.scripts.load_inactive_students_from_excel import (
        load_inactive_students_from_excel,
    )
    from backend.scripts.load_active_students_from_excel import (
        load_active_students_from_excel,
    )

    Base.metadata.create_all(bind=engine)
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    ensure_master_key_file()

    # Load inactive students first so the single overlapping student is kept as
    # inactive and skipped by the active import.
    inactive_result = load_inactive_students_from_excel(excel_path, dry_run=False)
    active_result = load_active_students_from_excel(active_excel_path, dry_run=False)

    session = SessionLocal()
    try:
        faculty_count = session.query(FacultySalary).count()
        student_count = session.query(Student).count()
        inactive_count = session.query(Student).filter(Student.status == "inactive").count()
        active_count = session.query(Student).filter(Student.status == "active").count()
    finally:
        session.close()

    db_path = output_dir / "fee_management.db"
    if faculty_count != EXPECTED_FACULTY:
        raise RuntimeError(f"Expected {EXPECTED_FACULTY} faculty, found {faculty_count}")
    if inactive_count != EXPECTED_INACTIVE:
        raise RuntimeError(f"Expected {EXPECTED_INACTIVE} inactive students, found {inactive_count}")
    if active_count != EXPECTED_ACTIVE:
        raise RuntimeError(f"Expected {EXPECTED_ACTIVE} active students, found {active_count}")
    if student_count != EXPECTED_INACTIVE + EXPECTED_ACTIVE:
        raise RuntimeError(
            f"Expected {EXPECTED_INACTIVE + EXPECTED_ACTIVE} students, found {student_count}"
        )
    for result in (inactive_result, active_result):
        if result.get("students") and any(
            abs(row["pending_fees"] - row["expected_pending"]) > 0.02 for row in result["students"]
        ):
            raise RuntimeError("Pending fee verification failed while building deployment database.")

    return db_path


def main() -> int:
    excel = Path(os.environ.get("INACTIVE_STUDENTS_XLSX", str(DEFAULT_EXCEL)))
    active_excel = Path(os.environ.get("ACTIVE_STUDENTS_XLSX", str(DEFAULT_ACTIVE_EXCEL)))
    db_path = build_deployment_database(excel_path=excel, active_excel_path=active_excel)
    print(f"Built preloaded client database: {db_path}")
    print(f"  Faculty: {EXPECTED_FACULTY}")
    print(f"  Inactive students: {EXPECTED_INACTIVE}")
    print(f"  Active students: {EXPECTED_ACTIVE}")
    print("Ship this folder with the .exe:")
    print(f"  {DEPLOYMENT_DATA.parent / 'data'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
