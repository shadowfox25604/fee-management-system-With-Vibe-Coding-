from datetime import date

from sqlalchemy import and_, or_, select

from backend.core.academic_year_dates import auto_label_for_range
from backend.models import AcademicYear


class AcademicYearRepository:
    def __init__(self, session):
        self.session = session

    def ensure_bootstrap_year(self) -> AcademicYear:
        """Guarantee at least one academic year exists (for legacy DBs and in-memory tests)."""
        from datetime import date

        from backend.core.schema_migrations import _default_academic_year_bounds
        from backend.models import Student, StudentAcademicYearFee

        existing = self.list_all()
        if existing:
            return existing[-1]
        start, end = _default_academic_year_bounds(date.today())
        year = self.create(start, end)
        for st in self.session.scalars(select(Student)).all():
            self.session.add(
                StudentAcademicYearFee(
                    student_id_fk=st.student_id,
                    academic_year_id=year.id,
                    school_fees=float(st.school_fees or 0.0),
                    van_fees=float(st.van_fees or 0.0),
                )
            )
        self.session.commit()
        return year

    def list_all(self) -> list[AcademicYear]:
        return list(
            self.session.scalars(select(AcademicYear).order_by(AcademicYear.start_date.asc())).all()
        )

    def get(self, year_id: int) -> AcademicYear | None:
        return self.session.get(AcademicYear, int(year_id))

    def get_for_date(self, d: date) -> AcademicYear | None:
        return self.session.scalars(
            select(AcademicYear)
            .where(AcademicYear.start_date <= d, AcademicYear.end_date >= d)
            .order_by(AcademicYear.start_date.desc())
            .limit(1)
        ).first()

    def get_current(self, as_of: date | None = None) -> AcademicYear | None:
        return self.get_for_date(as_of or date.today())

    def years_before(self, year: AcademicYear) -> list[AcademicYear]:
        return list(
            self.session.scalars(
                select(AcademicYear)
                .where(AcademicYear.end_date < year.start_date)
                .order_by(AcademicYear.start_date.asc())
            ).all()
        )

    def _overlaps(self, start: date, end: date, exclude_id: int | None = None) -> bool:
        stmt = select(AcademicYear.id).where(
            AcademicYear.start_date <= end,
            AcademicYear.end_date >= start,
        )
        if exclude_id is not None:
            stmt = stmt.where(AcademicYear.id != int(exclude_id))
        return self.session.scalar(stmt.limit(1)) is not None

    def create(self, start: date, end: date, label: str | None = None) -> AcademicYear:
        if start > end:
            raise ValueError("Start date must be on or before end date.")
        if self._overlaps(start, end):
            raise ValueError("This date range overlaps an existing academic year.")
        lbl = (label or "").strip() or auto_label_for_range(start, end)
        row = AcademicYear(start_date=start, end_date=end, label=lbl)
        self.session.add(row)
        self.session.flush()
        return row

    def update(self, year: AcademicYear, start: date, end: date, label: str | None = None) -> AcademicYear:
        if start > end:
            raise ValueError("Start date must be on or before end date.")
        if self._overlaps(start, end, exclude_id=year.id):
            raise ValueError("This date range overlaps an existing academic year.")
        year.start_date = start
        year.end_date = end
        year.label = (label or "").strip() or auto_label_for_range(start, end)
        self.session.add(year)
        self.session.flush()
        return year

    def delete(self, year: AcademicYear) -> None:
        self.session.delete(year)
