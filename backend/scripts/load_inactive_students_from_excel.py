"""Import inactive old students from the client Excel sheet.

All rows are treated as Old students (O-roll numbers). Status is set to inactive.
Total Balance is stored as opening pending fees via StudentService old-student import.

Usage (development database):
    set PYTHONPATH=. && python backend/scripts/load_inactive_students_from_excel.py --yes

Usage (installed client database):
    set PYTHONPATH=. && set FEE_MANAGEMENT_DATA_DIR=%LOCALAPPDATA%\\ACE School Management
    python backend/scripts/load_inactive_students_from_excel.py --yes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from sqlalchemy import select

from backend.core.config import DATA_DIR
from backend.core.database import SessionLocal, engine
from backend.core.fee_control_constants import canonical_class_for_student_class
from backend.core.schema_migrations import (
    apply_sqlite_column_migrations,
    apply_sqlite_data_migrations,
)
from backend.core.student_roll_number import (
    compose_roll_number,
    entry_year_from_session,
    suggest_next_sequence,
)
from backend.models import Student, entities  # noqa: F401
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.services.class_fee_service import ClassFeeService
from backend.services.fee_balance_service import FeeBalanceService
from backend.services.student_service import StudentService
from backend.services.village_van_fee_service import VillageVanFeeService

DEFAULT_EXCEL = Path.home() / "Desktop" / "inactive students.xlsx"

CLASS_ALIASES: dict[str, str] = {
    "I": "1",
    "II": "2",
    "III": "3",
    "IV": "4",
    "V": "5",
    "VI": "6",
    "VII": "7",
    "VIII": "8",
    "IX": "9",
    "X": "10",
    "LKG": "LKG",
    "UKG": "UKG",
}

VILLAGE_ALIASES: dict[str, str] = {
    "Burugupalle": "Burugupally",
}

GENDER_ALIASES: dict[str, str] = {
    "boy": "Male",
    "girl": "Female",
    "male": "Male",
    "female": "Female",
}


def _cell_text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _cell_phone(value) -> str:
    text = _cell_text(value)
    if not text:
        return ""
    if text.endswith(".0"):
        text = text[:-2]
    if len(text) == 10 and text.isdigit():
        return text
    return ""


def _normalize_class(raw: object) -> str:
    key = _cell_text(raw).upper()
    mapped = CLASS_ALIASES.get(key, key)
    canonical = canonical_class_for_student_class(mapped)
    if canonical is None:
        raise ValueError(f"Unsupported class: {raw!r}")
    return canonical


def _normalize_village(raw: object) -> str:
    name = _cell_text(raw)
    if not name:
        raise ValueError("Village is required.")
    return VILLAGE_ALIASES.get(name, name)


def _normalize_gender(raw: object) -> str:
    key = _cell_text(raw).lower()
    if key not in GENDER_ALIASES:
        raise ValueError(f"Unsupported gender: {raw!r}")
    return GENDER_ALIASES[key]


def _normalize_balance(raw: object) -> float:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return 0.0
    amount = float(raw)
    if amount < 0:
        raise ValueError("Total Balance cannot be negative.")
    return round(amount, 2)


def parse_inactive_students_excel(path: Path) -> list[dict]:
    df = pd.read_excel(path, sheet_name="inactive")
    required = {
        "Name",
        "Gender",
        "Father Name",
        "Village",
        "Mobile No.",
        "Class",
        "Total Balance",
    }
    missing = required - {str(c).strip() for c in df.columns}
    if missing:
        raise ValueError(f"Excel is missing columns: {sorted(missing)}")

    rows: list[dict] = []
    for index, record in df.iterrows():
        name = _cell_text(record["Name"])
        father = _cell_text(record["Father Name"])
        if not name:
            raise ValueError(f"Row {index + 2}: Name is required.")
        if not father:
            raise ValueError(f"Row {index + 2}: Father Name is required.")

        phone1 = _cell_phone(record["Mobile No."])
        if len(phone1) != 10 or not phone1.isdigit():
            raise ValueError(f"Row {index + 2}: Mobile No. must be 10 digits (got {phone1!r}).")

        mother_col = "Mother Name" if "Mother Name" in df.columns else None
        phone2_col = "Mobile No 2 ." if "Mobile No 2 ." in df.columns else None

        rows.append(
            {
                "row_number": int(index) + 2,
                "full_name": name,
                "gender": _normalize_gender(record["Gender"]),
                "father_name": father,
                "mother_name": _cell_text(record[mother_col]) if mother_col else "",
                "village": _normalize_village(record["Village"]),
                "phone": phone1,
                "phone2": _cell_phone(record[phone2_col]) if phone2_col else "",
                "class_name": _normalize_class(record["Class"]),
                "section": "A",
                "pending_fees": _normalize_balance(record["Total Balance"]),
            }
        )
    return rows


def _norm_key(*parts: str) -> tuple[str, str, str]:
    return tuple(" ".join((p or "").upper().split()) for p in parts)


def _find_existing_student(session, row: dict) -> Student | None:
    key = _norm_key(row["full_name"], row["father_name"], row["phone"])
    matches: list[Student] = []
    for student in session.scalars(select(Student)).all():
        student_key = _norm_key(
            str(student.full_name or ""),
            str(student.father_name or student.guardian_name or ""),
            str(student.mobile_number_1 or student.phone or ""),
        )
        if student_key == key:
            matches.append(student)
    if not matches:
        return None
    if len(matches) > 1:
        raise ValueError(
            f"Row {row['row_number']}: multiple existing students match "
            f"{row['full_name']} / {row['father_name']} / {row['phone']}"
        )
    return matches[0]


def _ensure_pending_fees(student_svc: StudentService, balance_svc: FeeBalanceService, student, expected: float) -> float:
    due = balance_svc.get_students_due_breakdown([student.student_id])[student.student_id]
    actual = float(due["pending_fees"])
    if expected <= 0:
        return actual
    if actual + 0.02 >= expected:
        return actual
    student_svc._seed_import_pending_fees(student, expected)
    due = balance_svc.get_students_due_breakdown([student.student_id])[student.student_id]
    return float(due["pending_fees"])


def load_inactive_students_from_excel(
    path: Path,
    *,
    dry_run: bool = False,
) -> dict:
    parsed = parse_inactive_students_excel(path)
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)

    session = SessionLocal()
    try:
        AcademicYearRepository(session).ensure_bootstrap_year()
        session.commit()

        student_svc = StudentService(session)
        class_svc = ClassFeeService(session)
        village_svc = VillageVanFeeService(session)
        balance_svc = FeeBalanceService(session)

        entry_year = entry_year_from_session(session)
        sequence = suggest_next_sequence(session, entry_year)

        created: list[dict] = []
        for row in parsed:
            if dry_run:
                roll = compose_roll_number(is_old=True, entry_year=entry_year, sequence=sequence)
                sequence += 1
                created.append({"student_id": roll, **row, "action": "create"})
                continue

            existing = _find_existing_student(session, row)
            if existing is not None:
                if (existing.status or "").strip().lower() != "inactive":
                    existing.status = "inactive"
                    session.add(existing)
                pending = _ensure_pending_fees(
                    student_svc,
                    balance_svc,
                    existing,
                    float(row["pending_fees"]),
                )
                created.append(
                    {
                        "student_id": existing.student_id,
                        "full_name": existing.full_name,
                        "class_name": existing.class_name,
                        "status": existing.status,
                        "pending_fees": pending,
                        "expected_pending": float(row["pending_fees"]),
                        "row_number": row["row_number"],
                        "action": "updated",
                    }
                )
                continue

            roll = compose_roll_number(is_old=True, entry_year=entry_year, sequence=sequence)
            sequence += 1

            kwargs = dict(
                village=row["village"],
                guardian_name=row["father_name"],
                status="inactive",
                transport_mode="own",
                gender=row["gender"],
                father_name=row["father_name"],
                mother_name=row["mother_name"],
                mobile_number_1=row["phone"],
                mobile_number_2=row["phone2"],
                village_fee_service=village_svc,
                class_fee_service=class_svc,
                is_old_student=True,
            )
            pending = float(row["pending_fees"])
            if pending > 0:
                kwargs["initial_pending_fees"] = pending

            student = student_svc.create_student(
                roll,
                row["full_name"],
                row["class_name"],
                row["section"],
                row["phone"],
                **kwargs,
            )
            due = balance_svc.get_students_due_breakdown([student.student_id])[student.student_id]
            created.append(
                {
                    "student_id": student.student_id,
                    "full_name": student.full_name,
                    "class_name": student.class_name,
                    "status": student.status,
                    "pending_fees": float(due["pending_fees"]),
                    "expected_pending": pending,
                    "row_number": row["row_number"],
                    "action": "created",
                }
            )

        if not dry_run:
            session.commit()

        return {
            "database": str(DATA_DIR / "fee_management.db"),
            "count": len(created),
            "created": sum(1 for row in created if row.get("action") == "created"),
            "updated": sum(1 for row in created if row.get("action") == "updated"),
            "students": created,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Import inactive old students from Excel.")
    parser.add_argument(
        "--excel",
        type=Path,
        default=DEFAULT_EXCEL,
        help=f"Path to inactive students workbook (default: {DEFAULT_EXCEL})",
    )
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and preview only.")
    args = parser.parse_args()

    if not args.excel.is_file():
        print(f"Excel file not found: {args.excel}", file=sys.stderr)
        return 1

    preview = parse_inactive_students_excel(args.excel)
    print(f"Excel: {args.excel}")
    print(f"Target database: {DATA_DIR / 'fee_management.db'}")
    print(f"Rows to import: {len(preview)}")
    print(f"With pending fees: {sum(1 for row in preview if row['pending_fees'] > 0)}")
    print(f"Zero balance: {sum(1 for row in preview if row['pending_fees'] == 0)}")

    if args.dry_run:
        for row in preview[:5]:
            print(
                f"  row {row['row_number']}: {row['full_name']} | class {row['class_name']} | "
                f"pending {row['pending_fees']:.0f}"
            )
        print("Dry run — no database changes.")
        return 0

    if not args.yes:
        print("\nAll students will be imported as OLD + INACTIVE with generated O-roll numbers.")
        answer = input("Type YES to continue: ").strip()
        if answer != "YES":
            print("Cancelled.")
            return 1

    result = load_inactive_students_from_excel(args.excel, dry_run=False)
    mismatches = [
        row
        for row in result["students"]
        if abs(row["pending_fees"] - row["expected_pending"]) > 0.02
    ]
    print(f"\nImported {result['count']} inactive student rows into {result['database']}")
    print(f"  Created: {result.get('created', 0)}  Updated/resumed: {result.get('updated', 0)}")
    if mismatches:
        print(f"WARNING: {len(mismatches)} pending-fee mismatches:")
        for row in mismatches:
            print(
                f"  {row['student_id']} {row['full_name']}: "
                f"expected {row['expected_pending']:.2f}, got {row['pending_fees']:.2f}"
            )
        return 1
    print("Pending fees verified for all imported students.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
