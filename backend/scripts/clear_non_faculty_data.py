"""Remove all data except faculty profiles (salaries) and login users.

Clears: students, payments, invoices, academic years, expenses, misc income/expense,
fee configuration, audit logs, faculty attendance, backups.

Keeps: faculty_salaries, users.

Usage:
    python -m backend.scripts.clear_non_faculty_data --yes
    python -m backend.scripts.clear_non_faculty_data --yes --data-dir "%LOCALAPPDATA%\\ACE School Management"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import delete, func, select

from backend.core.config import DATA_DIR
from backend.core.database import SessionLocal, engine
from backend.core.schema_migrations import apply_sqlite_column_migrations, apply_sqlite_data_migrations
from backend.models import (
    AcademicYear,
    AuditLog,
    ClassSchoolFee,
    Expense,
    FeeHead,
    FeePlan,
    Invoice,
    MiscExpense,
    MiscExpenseEntry,
    MiscIncome,
    MiscIncomeEntry,
    Payment,
    PaymentAllocation,
    Student,
    StudentAcademicYearFee,
    User,
    VillageVanFee,
)
from backend.models.entities import FacultyAttendance, FacultySalary


def _count(session, model) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _clear_backups(data_dir: Path) -> int:
    backup_dir = data_dir / "backups"
    if not backup_dir.is_dir():
        return 0
    removed = 0
    for path in backup_dir.glob("*.db"):
        path.unlink(missing_ok=True)
        removed += 1
    return removed


def clear_non_faculty_data(*, dry_run: bool = False) -> dict[str, int]:
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    session = SessionLocal()
    before = {
        "students": _count(session, Student),
        "payments": _count(session, Payment),
        "invoices": _count(session, Invoice),
        "faculty": _count(session, FacultySalary),
        "faculty_attendance": _count(session, FacultyAttendance),
        "users": _count(session, User),
    }
    try:
        if dry_run:
            session.close()
            return before

        # Child tables first (FK order).
        session.execute(delete(PaymentAllocation))
        session.execute(delete(Payment))
        session.execute(delete(Invoice))
        session.execute(delete(FeePlan))
        session.execute(delete(StudentAcademicYearFee))
        session.execute(delete(Student))
        session.execute(delete(ClassSchoolFee))
        session.execute(delete(VillageVanFee))
        session.execute(delete(AcademicYear))
        session.execute(delete(MiscExpenseEntry))
        session.execute(delete(MiscExpense))
        session.execute(delete(MiscIncomeEntry))
        session.execute(delete(MiscIncome))
        session.execute(delete(Expense))
        session.execute(delete(FacultyAttendance))
        session.execute(delete(FeeHead))
        session.execute(delete(AuditLog))
        session.commit()

        backups_removed = _clear_backups(DATA_DIR)

        after = {
            "students": _count(session, Student),
            "payments": _count(session, Payment),
            "faculty_kept": _count(session, FacultySalary),
            "faculty_attendance_kept": _count(session, FacultyAttendance),
            "users_kept": _count(session, User),
            "backups_removed": backups_removed,
        }
        return {"before": before, "after": after}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear student/payment data; keep faculty and users.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show counts only; do not delete.",
    )
    args = parser.parse_args()

    preview = clear_non_faculty_data(dry_run=True)
    print("Current database counts:")
    for key, value in preview.items():
        print(f"  {key}: {value}")

    if args.dry_run:
        print("\nDry run — no changes made.")
        return 0

    if not args.yes:
        print(
            "\nThis will DELETE all students, payments, academic years, expenses, "
            "misc income/expense, fee heads, audit logs, faculty attendance, and backups."
        )
        print(f"Target database: {DATA_DIR / 'fee_management.db'}")
        print("Faculty salaries and login users will be KEPT.")
        answer = input("Type YES to continue: ").strip()
        if answer != "YES":
            print("Cancelled.")
            return 1

    result = clear_non_faculty_data(dry_run=False)
    print("\nDone.")
    print(f"  Database: {DATA_DIR / 'fee_management.db'}")
    print(f"  Removed {result['before']['students']} students")
    print(f"  Removed {result['before']['payments']} payments")
    print(f"  Kept {result['after']['faculty_kept']} faculty records")
    print(f"  Kept {result['after']['users_kept']} users")
    print(f"  Removed {result['after']['backups_removed']} backup files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
