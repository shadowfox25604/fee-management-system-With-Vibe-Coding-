from sqlalchemy import func, or_, select

from backend.core.student_enrollment import student_skips_academic_year_fee_provisioning
from backend.models import Student


class StudentRepository:
    def __init__(self, session):
        self.session = session

    def _ensure_unique_student_values(
        self,
        *,
        student_id: str,
        mobile_number_1: str,
        mobile_number_2: str,
        aadhaar: str,
        exclude_student_id: str | None = None,
    ) -> None:
        sid = (student_id or "").strip()
        m1 = (mobile_number_1 or "").strip()
        m2 = (mobile_number_2 or "").strip()
        aadhaar_text = (aadhaar or "").strip()

        def _exists(stmt):
            return self.session.scalars(stmt.limit(1)).first() is not None

        sid_stmt = select(Student).where(func.lower(Student.student_id) == sid.lower())
        if exclude_student_id is not None:
            sid_stmt = sid_stmt.where(func.lower(Student.student_id) != exclude_student_id.lower())
        if _exists(sid_stmt):
            raise ValueError("Student ID already exists.")

        if m1:
            m1_stmt = select(Student).where(
                or_(
                    Student.mobile_number_1 == m1,
                    Student.mobile_number_2 == m1,
                    Student.phone == m1,
                )
            )
            if exclude_student_id is not None:
                m1_stmt = m1_stmt.where(func.lower(Student.student_id) != exclude_student_id.lower())
            if _exists(m1_stmt):
                raise ValueError("Mobile number 1 already exists.")

        if m2:
            m2_stmt = select(Student).where(
                or_(
                    Student.mobile_number_1 == m2,
                    Student.mobile_number_2 == m2,
                    Student.phone == m2,
                )
            )
            if exclude_student_id is not None:
                m2_stmt = m2_stmt.where(func.lower(Student.student_id) != exclude_student_id.lower())
            if _exists(m2_stmt):
                raise ValueError("Mobile number 2 already exists.")

        if aadhaar_text:
            aadhaar_stmt = select(Student).where(Student.aadhaar == aadhaar_text)
            if exclude_student_id is not None:
                aadhaar_stmt = aadhaar_stmt.where(func.lower(Student.student_id) != exclude_student_id.lower())
            if _exists(aadhaar_stmt):
                raise ValueError("Aadhaar already exists.")

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
                Student.mobile_number_1.ilike(p),
                Student.mobile_number_2.ilike(p),
                Student.village.ilike(p),
                Student.father_name.ilike(p),
                Student.mother_name.ilike(p),
                Student.aadhaar.ilike(p),
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
        *,
        gender: str = "",
        father_name: str = "",
        mother_name: str = "",
        mobile_number_1: str = "",
        mobile_number_2: str = "",
        date_of_birth=None,
        caste: str = "",
        aadhaar: str = "",
    ):
        primary_mobile = (mobile_number_1 or phone or "").strip()
        father = (father_name or guardian_name or "").strip()
        self._ensure_unique_student_values(
            student_id=student_id,
            mobile_number_1=primary_mobile,
            mobile_number_2=mobile_number_2,
            aadhaar=aadhaar,
        )
        student = Student(
            student_id=student_id.strip(),
            full_name=full_name.strip(),
            gender=(gender or "").strip(),
            father_name=father,
            mother_name=(mother_name or "").strip(),
            class_name=class_name.strip(),
            section=section.strip(),
            phone=primary_mobile,
            mobile_number_1=primary_mobile,
            mobile_number_2=(mobile_number_2 or "").strip(),
            date_of_birth=date_of_birth,
            caste=(caste or "").strip(),
            aadhaar=(aadhaar or "").strip(),
            village=(village or "").strip(),
            guardian_name=father,
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
        *,
        gender: str = "",
        father_name: str = "",
        mother_name: str = "",
        mobile_number_1: str = "",
        mobile_number_2: str = "",
        date_of_birth=None,
        caste: str = "",
        aadhaar: str = "",
    ):
        primary_mobile = (mobile_number_1 or phone or "").strip()
        father = (father_name or guardian_name or "").strip()
        self._ensure_unique_student_values(
            student_id=student_id,
            mobile_number_1=primary_mobile,
            mobile_number_2=mobile_number_2,
            aadhaar=aadhaar,
            exclude_student_id=str(getattr(student, "student_id", "") or ""),
        )
        student.student_id = (student_id or "").strip()
        student.full_name = (full_name or "").strip()
        student.gender = (gender or "").strip()
        student.father_name = father
        student.mother_name = (mother_name or "").strip()
        student.class_name = (class_name or "").strip()
        student.section = (section or "").strip()
        student.phone = primary_mobile
        student.mobile_number_1 = primary_mobile
        student.mobile_number_2 = (mobile_number_2 or "").strip()
        student.date_of_birth = date_of_birth
        student.caste = (caste or "").strip()
        student.aadhaar = (aadhaar or "").strip()
        student.village = (village or "").strip()
        student.guardian_name = father
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
        """Advance each student one class (LKG→UKG→1→…→10→Passed Out). Returns count promoted."""
        from backend.core.fee_control_constants import (
            PASSED_OUT_CLASS_KEY,
            canonical_class_for_student_class,
            next_class_key,
        )

        promoted = 0
        for student in self.session.scalars(select(Student)).all():
            if student_skips_academic_year_fee_provisioning(student):
                continue
            current = canonical_class_for_student_class(student.class_name)
            if current is None:
                continue
            nxt = next_class_key(current)
            if nxt is None:
                continue
            student.class_name = nxt
            if nxt == PASSED_OUT_CLASS_KEY:
                student.status = "inactive"
                student.school_fees = 0.0
                student.van_fees = 0.0
            else:
                student.school_fees = float(class_fee_lookup(nxt))
            self.session.add(student)
            promoted += 1
        if promoted:
            self.session.flush()
        return promoted
