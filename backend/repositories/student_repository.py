from sqlalchemy import delete, func, or_, select, text, update

from backend.core.fee_control_constants import PASSED_OUT_CLASS_KEY, normalize_class_name
from backend.core.student_enrollment import student_skips_academic_year_fee_provisioning
from backend.core.student_roll_number import suggest_next_roll_number as _suggest_next_roll_number
from backend.models import FeePlan, Invoice, Payment, PaymentAllocation, Student, StudentAcademicYearFee


class StudentRepository:
    def __init__(self, session):
        self.session = session

    def _ensure_unique_student_values(
        self,
        *,
        student_id: str,
        aadhaar: str,
        exclude_student_id: str | None = None,
    ) -> None:
        sid = (student_id or "").strip()
        aadhaar_text = (aadhaar or "").strip()

        def _exists(stmt):
            return self.session.scalars(stmt.limit(1)).first() is not None

        sid_stmt = select(Student).where(func.lower(Student.student_id) == sid.lower())
        if exclude_student_id is not None:
            sid_stmt = sid_stmt.where(func.lower(Student.student_id) != exclude_student_id.lower())
        if _exists(sid_stmt):
            raise ValueError("Student ID already exists.")

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
        school_fees: float = 0.0,
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
        school_fees: float = 0.0,
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
            aadhaar=aadhaar,
            exclude_student_id=str(getattr(student, "student_id", "") or ""),
        )
        old_id = str(getattr(student, "student_id", "") or "").strip()
        new_id = (student_id or "").strip()
        if old_id.lower() != new_id.lower():
            self.rename_student_id(old_id, new_id)
            student = self.get_by_id(new_id)
            if student is None:
                raise ValueError(f"Student not found after rename: {new_id}")
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

    def student_join_date_bounds(self) -> tuple:
        from datetime import date, datetime

        row = self.session.execute(
            select(func.min(Student.created_at), func.max(Student.created_at))
        ).one()

        def _to_date(value):
            if value is None:
                return None
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            return None

        return _to_date(row[0]), _to_date(row[1])

    def _student_ids_for_class(self, class_key: str) -> list[str]:
        from backend.repositories.class_fee_repository import ClassFeeRepository

        key = (class_key or "").strip()
        if not key:
            return []
        if normalize_class_name(key) == normalize_class_name(PASSED_OUT_CLASS_KEY):
            rows = self.session.scalars(
                select(Student.student_id).where(
                    func.lower(func.trim(Student.class_name))
                    == normalize_class_name(PASSED_OUT_CLASS_KEY)
                )
            ).all()
            return [str(value) for value in rows]
        return [
            student.student_id
            for student in ClassFeeRepository(self.session).students_in_fixed_class(key)
        ]

    def _student_ids_for_classes(self, class_keys: list[str]) -> list[str]:
        ids: list[str] = []
        seen: set[str] = set()
        for key in class_keys:
            for student_id in self._student_ids_for_class(key):
                if student_id not in seen:
                    seen.add(student_id)
                    ids.append(student_id)
        return ids

    def list_for_export(
        self,
        *,
        month: tuple[int, int] | None = None,
        date_from=None,
        date_to=None,
        class_names: list[str] | None = None,
        sections: list[str] | None = None,
        status: str | None = None,
        student_id: str | None = None,
    ):
        import calendar
        from datetime import date, datetime

        stmt = select(Student).order_by(Student.student_id.asc())
        sid = (student_id or "").strip()
        if sid:
            stmt = stmt.where(func.lower(Student.student_id) == sid.lower())
        status_value = (status or "").strip().lower()
        if status_value == "active":
            stmt = stmt.where(func.lower(Student.status) == "active")
        elif status_value == "inactive":
            stmt = stmt.where(func.lower(Student.status) != "active")
        if month is not None:
            year, mon = month
            start = datetime(int(year), int(mon), 1)
            last_day = calendar.monthrange(int(year), int(mon))[1]
            end = datetime(int(year), int(mon), last_day, 23, 59, 59)
            stmt = stmt.where(Student.created_at >= start, Student.created_at <= end)
        else:
            if date_from is not None:
                start = datetime.combine(date_from, datetime.min.time())
                stmt = stmt.where(Student.created_at >= start)
            if date_to is not None:
                end = datetime.combine(date_to, datetime.max.time().replace(microsecond=0))
                stmt = stmt.where(Student.created_at <= end)
        if class_names:
            ids = self._student_ids_for_classes(class_names)
            if not ids:
                return []
            stmt = stmt.where(Student.student_id.in_(ids))
        if sections:
            normalized = [str(section).strip().upper() for section in sections if str(section).strip()]
            if normalized:
                stmt = stmt.where(func.upper(func.trim(Student.section)).in_(normalized))
        return list(self.session.scalars(stmt).all())

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
        """Advance each student one class (Nursery→LKG→UKG→1→…→10→Passed Out). Returns count promoted."""
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

    def delete_student_cascade(self, student_id: str) -> None:
        """Remove student and all related payment, invoice, and fee rows."""
        sid = (student_id or "").strip()
        if not sid:
            raise ValueError("Student ID is required.")
        exists = self.session.scalar(select(Student.student_id).where(Student.student_id == sid))
        if exists is None:
            raise ValueError(f"Student not found: {sid}")

        pay_ids = list(
            self.session.scalars(select(Payment.id).where(Payment.student_id_fk == sid)).all()
        )
        if pay_ids:
            self.session.execute(
                delete(PaymentAllocation).where(PaymentAllocation.payment_id.in_(pay_ids))
            )
        self.session.execute(delete(Payment).where(Payment.student_id_fk == sid))
        self.session.execute(delete(Invoice).where(Invoice.student_id_fk == sid))
        self.session.execute(delete(FeePlan).where(FeePlan.student_id_fk == sid))
        self.session.execute(
            delete(StudentAcademicYearFee).where(StudentAcademicYearFee.student_id_fk == sid)
        )
        self.session.execute(delete(Student).where(Student.student_id == sid))
        self.session.commit()

    def get_by_id(self, student_id: str) -> Student | None:
        sid = (student_id or "").strip()
        if not sid:
            return None
        return self.session.get(Student, sid)

    def suggest_next_roll_number(self, *, is_old: bool) -> str:
        return _suggest_next_roll_number(self.session, is_old=is_old)

    def rename_student_id(self, old_id: str, new_id: str) -> None:
        old = (old_id or "").strip()
        new = (new_id or "").strip()
        if not old or not new:
            raise ValueError("Student ID is required.")
        if old.lower() == new.lower():
            return
        if self.get_by_id(old) is None:
            raise ValueError(f"Student not found: {old}")
        self._ensure_unique_student_values(student_id=new, aadhaar="", exclude_student_id=old)

        bind = self.session.get_bind()
        if bind is not None and bind.dialect.name == "sqlite":
            self.session.execute(text("PRAGMA foreign_keys=OFF"))

        self.session.execute(update(Student).where(Student.student_id == old).values(student_id=new))
        self.session.execute(
            update(StudentAcademicYearFee)
            .where(StudentAcademicYearFee.student_id_fk == old)
            .values(student_id_fk=new)
        )
        self.session.execute(
            update(FeePlan).where(FeePlan.student_id_fk == old).values(student_id_fk=new)
        )
        self.session.execute(
            update(Invoice).where(Invoice.student_id_fk == old).values(student_id_fk=new)
        )
        self.session.execute(
            update(Payment).where(Payment.student_id_fk == old).values(student_id_fk=new)
        )

        if bind is not None and bind.dialect.name == "sqlite":
            self.session.execute(text("PRAGMA foreign_keys=ON"))
        self.session.flush()
