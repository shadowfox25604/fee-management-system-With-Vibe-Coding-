"""Set a student's computed pending fees by adding unpaid prior-year tariffs."""

from __future__ import annotations

import argparse
from datetime import datetime

from sqlalchemy import select

from backend.core.database import SessionLocal, engine
from backend.core.schema_migrations import apply_sqlite_column_migrations, apply_sqlite_data_migrations
from backend.models import AcademicYear, Student
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.repositories.student_year_fee_repository import StudentYearFeeRepository
from backend.services.fee_balance_service import FeeBalanceService


def set_pending_fees(student_name: str, pending_amount: float) -> None:
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)

    session = SessionLocal()
    try:
        st = session.scalars(
            select(Student).where(Student.full_name.ilike(student_name.strip()))
        ).first()
        if st is None:
            raise SystemExit(f"Student not found: {student_name!r}")

        year_repo = AcademicYearRepository(session)
        current = year_repo.get_current()
        if current is None:
            raise SystemExit("No current academic year in database.")

        # Academic years may overlap by 1 day (31 May -> 1 June).
        # Using "end_date < current.start_date" can therefore return none.
        # Instead, pick the academic year immediately before by start_date.
        prior = (
            session.scalars(
                select(AcademicYear)
                .where(AcademicYear.start_date < current.start_date)
                .order_by(AcademicYear.start_date.desc())
                .limit(1)
            ).first()
        )
        if prior is None:
            raise SystemExit("No prior academic year exists to attach pending fees.")
        sy = StudentYearFeeRepository(session)

        # Must be enrolled on/before the prior year's end so the prior year is included
        # in pending calculations.
        st.created_at = datetime(prior.end_date.year, prior.end_date.month, prior.end_date.day, 10, 0, 0)

        prior_row = sy.get_or_create(
            st, prior.id, school_fees=float(pending_amount), van_fees=0.0
        )
        prior_row.opening_pending_fees = 0.0

        current_row = sy.get(st.student_id, current.id)
        if current_row is None:
            current_row = sy.get_or_create(
                st,
                current.id,
                school_fees=float(st.school_fees or 0.0),
                van_fees=float(st.van_fees or 0.0),
            )
        current_row.opening_pending_fees = 0.0

        session.commit()

        due = FeeBalanceService(session).get_students_due_breakdown([st.student_id])[st.student_id]
        pending = float(due.get("pending_fees") or 0.0)
        print(f"Updated {st.full_name!r} ({st.student_id})")
        print(f"Prior year: {prior.label} — school_fees={pending_amount:.2f}")
        print(f"pending_fees: {pending:.2f}")
        print(f"fee_due: {float(due.get('fee_due') or 0):.2f}")
        print(f"van_due: {float(due.get('van_due') or 0):.2f}")
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Set student pending fees for manual testing.")
    parser.add_argument("name", help="Student full name (case-insensitive)")
    parser.add_argument("amount", type=float, help="Pending fees amount")
    args = parser.parse_args()
    set_pending_fees(args.name, args.amount)


if __name__ == "__main__":
    main()
