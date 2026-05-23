from sqlalchemy import func, or_, select

from backend.models import Student


class StudentRepository:
    def __init__(self, session):
        self.session = session

    def search(self, query: str):
        q = (query or "").strip()
        if not q:
            return self.session.scalars(select(Student).limit(100)).all()
        p = f"%{q}%"
        stmt = select(Student).where(
            or_(
                Student.student_id.ilike(p),
                Student.full_name.ilike(p),
                Student.phone.ilike(p),
                Student.village.ilike(p),
            )
        ).limit(100)
        return self.session.scalars(stmt).all()

    def create_student(
        self,
        student_id: str,
        full_name: str,
        class_name: str,
        section: str,
        phone: str,
        village: str,
        guardian_name: str,
        status: str = "active",
        van_fees: float = 0.0,
        school_fees: float = 20000.0,
        transport_mode: str = "van",
    ):
        student = Student(
            student_id=student_id.strip(),
            full_name=full_name.strip(),
            class_name=class_name.strip(),
            section=section.strip(),
            phone=phone.strip(),
            village=(village or "").strip(),
            guardian_name=guardian_name.strip(),
            status=(status or "active").strip(),
            transport_mode=(transport_mode or "van").strip().lower(),
            van_fees=float(van_fees or 0.0),
            school_fees=float(school_fees),
        )
        self.session.add(student)
        self.session.commit()
        self.session.refresh(student)
        from backend.repositories.student_year_fee_repository import StudentYearFeeRepository

        StudentYearFeeRepository(self.session).sync_student_to_current_year(student)
        self.session.commit()
        return student

    def update_student(
        self,
        student: Student,
        student_id: str,
        full_name: str,
        class_name: str,
        section: str,
        phone: str,
        village: str,
        guardian_name: str,
        status: str = "active",
        van_fees: float = 0.0,
        school_fees: float = 20000.0,
        transport_mode: str = "van",
    ):
        student.student_id = (student_id or "").strip()
        student.full_name = (full_name or "").strip()
        student.class_name = (class_name or "").strip()
        student.section = (section or "").strip()
        student.phone = (phone or "").strip()
        student.village = (village or "").strip()
        student.guardian_name = (guardian_name or "").strip()
        student.status = (status or "active").strip()
        student.transport_mode = (transport_mode or "van").strip().lower()
        student.van_fees = float(van_fees or 0.0)
        student.school_fees = float(school_fees)
        self.session.add(student)
        self.session.commit()
        self.session.refresh(student)
        from backend.repositories.student_year_fee_repository import StudentYearFeeRepository

        StudentYearFeeRepository(self.session).sync_student_to_current_year(student)
        self.session.commit()
        return student

    def list_students(self):
        return self.session.scalars(select(Student).order_by(Student.student_id.asc())).all()

    def count_active_inactive(self) -> tuple[int, int]:
        """Return (active_count, inactive_count) using case-insensitive status."""
        active = self.session.scalar(
            select(func.count())
            .select_from(Student)
            .where(func.lower(Student.status) == "active")
        ) or 0
        inactive = self.session.scalar(
            select(func.count())
            .select_from(Student)
            .where(func.lower(Student.status) != "active")
        ) or 0
        return int(active), int(inactive)

    def promote_all_student_classes(self, class_fee_lookup) -> int:
        """Advance each student one class (LKG→UKG→1→…→10). Returns count promoted."""
        from backend.core.fee_control_constants import canonical_class_for_student_class, next_class_key

        promoted = 0
        for student in self.session.scalars(select(Student)).all():
            current = canonical_class_for_student_class(student.class_name)
            if current is None:
                continue
            nxt = next_class_key(current)
            if nxt is None:
                continue
            student.class_name = nxt
            student.school_fees = float(class_fee_lookup(nxt))
            self.session.add(student)
            promoted += 1
        if promoted:
            self.session.flush()
        return promoted
