from __future__ import annotations

import uuid
from datetime import date, datetime

from backend.core.database import SessionLocal, engine
from backend.core.schema_migrations import apply_sqlite_column_migrations, apply_sqlite_data_migrations
from backend.core.academic_year_dates import academic_year_bounds_for_start_year
from backend.models import FeeHead, Student
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.repositories.student_year_fee_repository import StudentYearFeeRepository
from backend.services.fee_balance_service import FeeBalanceService


def _ensure_fee_heads(session) -> tuple[FeeHead, FeeHead]:
    tuition = session.query(FeeHead).filter(FeeHead.head_name.ilike("tuition")).first()
    transport = session.query(FeeHead).filter(FeeHead.head_name.ilike("transport")).first()

    if tuition is None:
        tuition = FeeHead(head_name="Tuition", frequency="monthly", default_amount=0.0)
        session.add(tuition)
    if transport is None:
        transport = FeeHead(head_name="Transport", frequency="monthly", default_amount=0.0)
        session.add(transport)

    session.flush()
    return tuition, transport


def main() -> None:
    # Ensure schema/data migrations exist for the real DB.
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)

    session = SessionLocal()
    try:
        year_repo = AcademicYearRepository(session)
        current = year_repo.get_current()
        if current is None:
            # Create at least one year if the DB is empty.
            start, end = academic_year_bounds_for_start_year(date.today().year)
            current = year_repo.create(start, end)
            session.commit()

        years_before = year_repo.years_before(current)
        if years_before:
            prior = years_before[-1]
        else:
            # Create the immediately previous academic year.
            start, end = academic_year_bounds_for_start_year(current.start_date.year - 1)
            prior = year_repo.create(start, end)
            session.commit()

        _ensure_fee_heads(session)

        # student_id max length is 20; keep it short and unique.
        student_id = f"PEND{uuid.uuid4().hex[:8].upper()}"

        # Create an active student whose "current year" tariff is 0, but whose
        # prior-year tariff is 30000 with no invoices/paid amounts.
        st = Student(
            student_id=student_id,
            full_name="Manual Pending 30000",
            gender="Male",
            class_name="5",
            section="A",
            phone=f"9{uuid.uuid4().int % 10**9:09d}",
            guardian_name="G",
            status="active",
            # Important: current-year tariff should not contribute to pending.
            school_fees=0.0,
            van_fees=0.0,
            village="Test",
            created_at=datetime(prior.start_date.year, prior.start_date.month, prior.start_date.day, 10, 0, 0),
        )
        session.add(st)
        session.flush()

        sy = StudentYearFeeRepository(session)
        # Prior-year tariff (unpaid) => computed pending_fees == 30000.
        prior_row = sy.get_or_create(st, prior.id, school_fees=30000.0, van_fees=0.0)
        prior_row.opening_pending_fees = 0.0
        # Explicitly set current-year tariff to 0.
        current_row = sy.get_or_create(st, current.id, school_fees=0.0, van_fees=0.0)
        current_row.opening_pending_fees = 0.0

        session.commit()

        due = FeeBalanceService(session).get_students_due_breakdown([student_id])[student_id]
        pending = float(due.get("pending_fees") or 0.0)
        fee_due = float(due.get("fee_due") or 0.0)

        print("Created student for manual pending-fees testing")
        print(f"student_id: {student_id}")
        print(f"full_name : {st.full_name}")
        print(f"class     : {st.class_name}-{st.section}")
        print(f"pending_fees (expected 30000): {pending:.2f}")
        print(f"fee_due (expected 0): {fee_due:.2f}")
        print("Done.")
    finally:
        session.close()


if __name__ == "__main__":
    main()

