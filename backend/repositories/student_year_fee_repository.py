from sqlalchemy import select

from backend.models import Student, StudentAcademicYearFee


class StudentYearFeeRepository:
    def __init__(self, session):
        self.session = session

    def get(self, student_id: int, academic_year_id: int) -> StudentAcademicYearFee | None:
        return self.session.scalars(
            select(StudentAcademicYearFee).where(
                StudentAcademicYearFee.student_id_fk == int(student_id),
                StudentAcademicYearFee.academic_year_id == int(academic_year_id),
            )
        ).first()

    def get_or_create(
        self,
        student: Student,
        academic_year_id: int,
        school_fees: float | None = None,
        van_fees: float | None = None,
    ) -> StudentAcademicYearFee:
        row = self.get(student.id, academic_year_id)
        if row is not None:
            return row
        sf = float(school_fees if school_fees is not None else student.school_fees or 0.0)
        vf = float(van_fees if van_fees is not None else student.van_fees or 0.0)
        row = StudentAcademicYearFee(
            student_id_fk=student.id,
            academic_year_id=int(academic_year_id),
            school_fees=sf,
            van_fees=vf,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def set_tariffs(self, student_id: int, academic_year_id: int, school_fees: float, van_fees: float) -> None:
        row = self.get(student_id, academic_year_id)
        if row is None:
            raise ValueError("Student academic year fee record not found.")
        row.school_fees = float(school_fees)
        row.van_fees = float(van_fees)
        self.session.add(row)
        self.session.flush()

    def tariffs_for_student_year(self, student: Student, academic_year_id: int) -> tuple[float, float]:
        row = self.get(student.id, academic_year_id)
        if row is not None:
            return float(row.school_fees or 0.0), float(row.van_fees or 0.0)
        return float(student.school_fees or 0.0), float(student.van_fees or 0.0)

    def sync_student_to_current_year(self, student: Student) -> None:
        from backend.repositories.academic_year_repository import AcademicYearRepository

        current = AcademicYearRepository(self.session).get_current()
        if current is None:
            return
        row = self.get_or_create(
            student,
            current.id,
            school_fees=float(student.school_fees or 0.0),
            van_fees=float(student.van_fees or 0.0),
        )
        row.school_fees = float(student.school_fees or 0.0)
        row.van_fees = float(student.van_fees or 0.0)
        self.session.add(row)
        self.session.flush()

    def provision_all_students_for_year(
        self,
        academic_year_id: int,
        class_fee_lookup,
        village_fee_lookup,
    ) -> int:
        """Create year-fee rows for students missing them (tariffs from class/village services)."""
        students = list(self.session.scalars(select(Student)).all())
        count = 0
        for st in students:
            if self.get(st.id, academic_year_id) is not None:
                continue
            sf = float(class_fee_lookup(st.class_name))
            tm = (getattr(st, "transport_mode", None) or "van").strip().lower()
            vf = 0.0 if tm == "own" else float(village_fee_lookup(getattr(st, "village", None)))
            self.get_or_create(st, academic_year_id, school_fees=sf, van_fees=vf)
            count += 1
        return count
