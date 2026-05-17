"""Test helpers for academic year isolation on the shared SQLite DB."""

from sqlalchemy import delete, select, update

from backend.core.schema_migrations import _default_academic_year_bounds
from backend.models import AcademicYear, Invoice, Student, StudentAcademicYearFee
from backend.repositories.academic_year_repository import AcademicYearRepository
from datetime import date


def reset_to_single_academic_year(session) -> AcademicYear:
    """One academic year spanning today; re-link invoices and per-student year tariffs."""
    session.execute(delete(StudentAcademicYearFee))
    session.execute(delete(AcademicYear))
    session.commit()
    start, end = _default_academic_year_bounds(date.today())
    repo = AcademicYearRepository(session)
    year = repo.create(start, end)
    session.commit()
    session.execute(update(Invoice).where(Invoice.academic_year_id.is_(None)).values(academic_year_id=year.id))
    session.execute(
        update(Invoice).where(Invoice.academic_year_id.is_not(None)).values(academic_year_id=year.id)
    )
    for st in session.scalars(select(Student)).all():
        session.add(
            StudentAcademicYearFee(
                student_id_fk=st.id,
                academic_year_id=year.id,
                school_fees=float(st.school_fees or 0.0),
                van_fees=float(st.van_fees or 0.0),
            )
        )
    session.commit()
    return year
