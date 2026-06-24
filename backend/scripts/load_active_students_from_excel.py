"""Import active old students from the client "ready to add" Excel sheet.

All rows are treated as Old students (O-roll numbers). Status is set to active.
Total Balance is stored as opening pending fees via StudentService old-student import.

Behaviour:
  * Rows missing required fields (name / father / village / phone) are skipped and
    reported (never invented).
  * Students that already exist in the database (matched on name + father + phone)
    are skipped and left untouched, so the import is safe to re-run.
  * Optional columns (Mother Name, Mobile No 2, DOB, Caste, AADHAAR) are captured
    when present.

Usage (development database):
    set PYTHONPATH=. && python backend/scripts/load_active_students_from_excel.py --yes

Usage (installed client database):
    set PYTHONPATH=. && set FEE_MANAGEMENT_DATA_DIR=%LOCALAPPDATA%\\ACE School Management
    python backend/scripts/load_active_students_from_excel.py --yes
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
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

DEFAULT_EXCEL = Path.home() / "Desktop" / "ready to add.xlsx"
SHEET_NAME = "Sheet1"

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

# Known spelling variants of canonical app villages. Other unknown villages are
# stored verbatim (acceptable for own-transport students with no van tariff).
VILLAGE_ALIASES: dict[str, str] = {
    "Burugupalle": "Burugupally",
    "Ramaiahpalle": "Ramaiahpally",
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


def _cell_aadhaar(value) -> str:
    text = _cell_text(value)
    if text.endswith(".0"):
        text = text[:-2]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits if len(digits) == 12 else ""


def _cell_date(value) -> date | None:
    """Parse an optional date of birth. Future or unparseable values are dropped."""
    parsed: date | None = None
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    else:
        text = _cell_text(value)
        if not text:
            return None
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y"):
            try:
                parsed = datetime.strptime(text, fmt).date()
                break
            except ValueError:
                continue
        if parsed is None:
            try:
                ts = pd.to_datetime(text, dayfirst=True, errors="coerce")
                if pd.notna(ts):
                    parsed = ts.date()
            except Exception:
                parsed = None
    if parsed is not None and parsed > date.today():
        return None
    return parsed


def _normalize_class(raw: object) -> str:
    key = _cell_text(raw).upper()
    mapped = CLASS_ALIASES.get(key, key)
    canonical = canonical_class_for_student_class(mapped)
    if canonical is None:
        raise ValueError(f"Unsupported class: {raw!r}")
    return canonical


def _normalize_village(raw: object) -> str:
    name = _cell_text(raw)
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


def parse_active_students_excel(path: Path) -> tuple[list[dict], list[dict]]:
    """Return (importable_rows, skipped_incomplete_rows)."""
    df = pd.read_excel(path, sheet_name=SHEET_NAME)
    required = {"Name", "Gender", "Father Name", "Village", "Mobile No.", "Class", "Total Balance"}
    missing = required - {str(c).strip() for c in df.columns}
    if missing:
        raise ValueError(f"Excel is missing columns: {sorted(missing)}")

    has_mother = "Mother Name" in df.columns
    has_phone2 = "Mobile No 2 ." in df.columns
    has_dob = "DOB" in df.columns
    has_caste = "Caste" in df.columns
    has_aadhaar = "AADHAAR" in df.columns

    rows: list[dict] = []
    skipped: list[dict] = []
    for index, record in df.iterrows():
        row_number = int(index) + 2
        name = _cell_text(record["Name"])
        father = _cell_text(record["Father Name"])
        village = _cell_text(record["Village"])
        phone1 = _cell_phone(record["Mobile No."])

        reasons: list[str] = []
        if not name:
            reasons.append("name")
        if not father:
            reasons.append("father name")
        if not village:
            reasons.append("village")
        if len(phone1) != 10 or not phone1.isdigit():
            reasons.append("valid 10-digit phone")
        if reasons:
            skipped.append({"row_number": row_number, "full_name": name, "missing": reasons})
            continue

        rows.append(
            {
                "row_number": row_number,
                "full_name": name,
                "gender": _normalize_gender(record["Gender"]),
                "father_name": father,
                "mother_name": _cell_text(record["Mother Name"]) if has_mother else "",
                "village": _normalize_village(village),
                "phone": phone1,
                "phone2": _cell_phone(record["Mobile No 2 ."]) if has_phone2 else "",
                "class_name": _normalize_class(record["Class"]),
                "section": "A",
                "date_of_birth": _cell_date(record["DOB"]) if has_dob else None,
                "caste": _cell_text(record["Caste"]) if has_caste else "",
                "aadhaar": _cell_aadhaar(record["AADHAAR"]) if has_aadhaar else "",
                "pending_fees": _normalize_balance(record["Total Balance"]),
            }
        )
    return rows, skipped


def _norm_key(*parts: str) -> tuple[str, ...]:
    return tuple(" ".join((p or "").upper().split()) for p in parts)


def _existing_student_index(session) -> dict[tuple[str, ...], Student]:
    # Matched on name + father only (phone numbers in the source sheet are not a
    # reliable identity key), so an already-loaded student is never duplicated.
    index: dict[tuple[str, ...], Student] = {}
    for student in session.scalars(select(Student)).all():
        key = _norm_key(
            str(student.full_name or ""),
            str(student.father_name or student.guardian_name or ""),
        )
        index[key] = student
    return index


def load_active_students_from_excel(path: Path, *, dry_run: bool = False) -> dict:
    parsed, skipped_incomplete = parse_active_students_excel(path)
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

        existing_index = _existing_student_index(session)
        entry_year = entry_year_from_session(session)
        sequence = suggest_next_sequence(session, entry_year)

        created: list[dict] = []
        skipped_existing: list[dict] = []
        for row in parsed:
            key = _norm_key(row["full_name"], row["father_name"])
            existing = existing_index.get(key)
            if existing is not None:
                skipped_existing.append(
                    {
                        "row_number": row["row_number"],
                        "full_name": row["full_name"],
                        "student_id": existing.student_id,
                        "status": existing.status,
                    }
                )
                continue

            roll = compose_roll_number(is_old=True, entry_year=entry_year, sequence=sequence)
            sequence += 1

            if dry_run:
                created.append({"student_id": roll, **row, "action": "create"})
                continue

            kwargs = dict(
                village=row["village"],
                guardian_name=row["father_name"],
                status="active",
                transport_mode="own",
                gender=row["gender"],
                father_name=row["father_name"],
                mother_name=row["mother_name"],
                mobile_number_1=row["phone"],
                mobile_number_2=row["phone2"],
                date_of_birth=row["date_of_birth"],
                caste=row["caste"],
                aadhaar=row["aadhaar"],
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
            "parsed": len(parsed),
            "created": sum(1 for row in created if row.get("action") == "created"),
            "skipped_existing": skipped_existing,
            "skipped_incomplete": skipped_incomplete,
            "students": created,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Import active old students from Excel.")
    parser.add_argument("--excel", type=Path, default=DEFAULT_EXCEL, help=f"Path to workbook (default: {DEFAULT_EXCEL})")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and preview only.")
    args = parser.parse_args()

    if not args.excel.is_file():
        print(f"Excel file not found: {args.excel}", file=sys.stderr)
        return 1

    parsed, skipped_incomplete = parse_active_students_excel(args.excel)
    print(f"Excel: {args.excel}")
    print(f"Target database: {DATA_DIR / 'fee_management.db'}")
    print(f"Importable rows: {len(parsed)}")
    print(f"With pending fees: {sum(1 for row in parsed if row['pending_fees'] > 0)}")
    print(f"Zero balance: {sum(1 for row in parsed if row['pending_fees'] == 0)}")
    if skipped_incomplete:
        print(f"Skipped (incomplete): {len(skipped_incomplete)}")
        for row in skipped_incomplete:
            print(f"  row {row['row_number']}: {row['full_name']!r} missing {row['missing']}")

    if args.dry_run:
        print("Dry run -- no database changes.")
        return 0

    if not args.yes:
        print("\nAll importable students will be added as OLD + ACTIVE with generated O-roll numbers.")
        answer = input("Type YES to continue: ").strip()
        if answer != "YES":
            print("Cancelled.")
            return 1

    result = load_active_students_from_excel(args.excel, dry_run=False)
    mismatches = [
        row
        for row in result["students"]
        if abs(row["pending_fees"] - row["expected_pending"]) > 0.02
    ]
    print(f"\nImported into {result['database']}")
    print(f"  Created (active): {result['created']}")
    print(f"  Skipped (already in DB): {len(result['skipped_existing'])}")
    for row in result["skipped_existing"]:
        print(f"    row {row['row_number']}: {row['full_name']} -> existing {row['student_id']} ({row['status']})")
    print(f"  Skipped (incomplete): {len(result['skipped_incomplete'])}")
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
