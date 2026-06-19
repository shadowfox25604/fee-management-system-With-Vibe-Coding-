"""Load faculty from an Excel sheet (NAME, SALARY) with section headers.

Employee IDs are assigned sequentially: EMPID1, EMPID2, ...

Usage (installed app / taskbar EXE database):
    set PYTHONPATH=. && uv run python backend/scripts/load_faculty_from_excel.py --app-data

Usage (development project database):
    set PYTHONPATH=. && uv run python backend/scripts/load_faculty_from_excel.py
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

_SECTION_TEACHING = re.compile(r"^TEACHING\s+FACULTY", re.IGNORECASE)
_SECTION_NON_TEACHING = re.compile(r"^NON[\s-]*TEACHING\s+FACULTY", re.IGNORECASE)


def _installed_app_data_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return root / "ACE School Management"


@dataclass(frozen=True)
class FacultyRow:
    employee_id: str
    name: str
    salary: float
    faculty_type: str
    role: str


def _normalize_name(raw: object) -> str:
    return str(raw or "").strip()


def _is_section_header(name: str) -> str | None:
    upper = name.upper()
    if _SECTION_NON_TEACHING.match(upper):
        return "Non Teaching"
    if _SECTION_TEACHING.match(upper):
        return "Teaching"
    return None


def _unique_name(name: str, seen: dict[str, int]) -> str:
    key = name.lower()
    if key not in seen:
        seen[key] = 1
        return name
    seen[key] += 1
    return f"{name} ({seen[key]})"


def parse_faculty_excel(path: Path) -> list[FacultyRow]:
    df = pd.read_excel(path, sheet_name=0)
    if df.empty:
        raise ValueError("Excel sheet is empty.")

    columns = {str(c).strip().upper(): c for c in df.columns}
    name_col = columns.get("NAME")
    salary_col = columns.get("SALARY")
    if name_col is None or salary_col is None:
        raise ValueError("Excel must have NAME and SALARY columns.")

    faculty_type = "Teaching"
    role = "Teacher"
    seen_names: dict[str, int] = {}
    rows: list[FacultyRow] = []
    emp_num = 0

    for _, record in df.iterrows():
        name = _normalize_name(record[name_col])
        if not name:
            continue
        section = _is_section_header(name)
        if section is not None:
            faculty_type = section
            role = "Teacher" if section == "Teaching" else "Staff"
            continue

        salary_raw = record[salary_col]
        if pd.isna(salary_raw):
            continue
        salary = float(salary_raw)
        if salary <= 0:
            continue

        emp_num += 1
        unique = _unique_name(name, seen_names)
        rows.append(
            FacultyRow(
                employee_id=f"EMPID{emp_num}",
                name=unique,
                salary=salary,
                faculty_type=faculty_type,
                role=role,
            )
        )

    if not rows:
        raise ValueError("No faculty rows found in Excel.")
    return rows


def load_faculty_from_excel(path: Path) -> list[FacultyRow]:
    from backend.core.config import DB_PATH
    from backend.core.database import SessionLocal, engine
    from backend.core.schema_migrations import (
        apply_sqlite_column_migrations,
        apply_sqlite_data_migrations,
    )
    from backend.models import entities  # noqa: F401
    from backend.services.expense_service import ExpenseService

    print(f"Database: {DB_PATH}")
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    parsed = parse_faculty_excel(path)
    session = SessionLocal()
    try:
        service = ExpenseService(session)
        for row in parsed:
            service.assign_faculty_salary(
                row.name,
                row.salary,
                employee_id=row.employee_id,
                faculty_type=row.faculty_type,
                role=row.role,
                default_working_days=26,
                is_active=True,
            )
        return parsed
    finally:
        session.close()


def main() -> int:
    default_path = Path.home() / "Desktop" / "faculty.xlsx"
    parser = argparse.ArgumentParser(description="Load faculty from Excel into the database.")
    parser.add_argument(
        "excel_path",
        nargs="?",
        default=str(default_path),
        help=f"Path to faculty.xlsx (default: {default_path})",
    )
    parser.add_argument(
        "--app-data",
        action="store_true",
        help="Write to the installed app's database (%LOCALAPPDATA%\\ACE School Management). "
        "Use this when you open ACE School Management from the taskbar / .exe.",
    )
    args = parser.parse_args()

    if args.app_data:
        data_dir = _installed_app_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        os.environ["FEE_MANAGEMENT_DATA_DIR"] = str(data_dir)

    path = Path(args.excel_path).expanduser().resolve()
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    try:
        loaded = load_faculty_from_excel(path)
    except Exception as exc:
        print(f"Load failed: {exc}", file=sys.stderr)
        return 1

    teaching = sum(1 for r in loaded if r.faculty_type == "Teaching")
    non_teaching = len(loaded) - teaching
    print(f"Loaded {len(loaded)} faculty from {path.name} ({teaching} teaching, {non_teaching} non-teaching).")
    for row in loaded:
        print(f"  {row.employee_id:8}  {row.faculty_type:14}  {row.salary:>10.0f}  {row.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
