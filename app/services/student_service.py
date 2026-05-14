from app.repositories.student_repository import StudentRepository


class StudentService:
    def __init__(self, session):
        self.repo = StudentRepository(session)

    def search_students(self, query):
        return self.repo.search(query)

    def list_students(self):
        return self.repo.list_students()

    @staticmethod
    def _parse_fee_amount(value, field_name: str) -> float:
        if value is None or value == "":
            return 0.0
        if isinstance(value, str):
            s = value.strip()
            if s == "":
                return 0.0
            v = float(s)
        else:
            v = float(value)
        if v < 0:
            raise ValueError(f"{field_name} cannot be negative")
        return v

    def create_student(
        self,
        student_id,
        full_name,
        class_name,
        section,
        phone,
        village="",
        guardian_name="",
        status="active",
        van_fees=None,
        village_fee_service=None,
        class_fee_service=None,
    ):
        if not (student_id or "").strip():
            raise ValueError("Student ID is required")
        if not (full_name or "").strip():
            raise ValueError("Name is required")
        if not (class_name or "").strip():
            raise ValueError("Class is required")
        if not (section or "").strip():
            raise ValueError("Section is required")
        if not (phone or "").strip():
            raise ValueError("Phone is required")
        if not (guardian_name or "").strip():
            raise ValueError("Guardian name is required")
        if village_fee_service is not None:
            vf = float(village_fee_service.van_fees_for_village_name(village))
        elif van_fees is not None and van_fees != "":
            vf = self._parse_fee_amount(van_fees, "Van fees")
        else:
            vf = 0.0
        if class_fee_service is not None:
            sf = class_fee_service.school_fees_for_class_name(class_name)
        else:
            sf = 20000.0
        return self.repo.create_student(
            student_id, full_name, class_name, section, phone, village, guardian_name, status, vf, sf
        )

    def update_student(
        self,
        student,
        student_id,
        full_name,
        class_name,
        section,
        phone,
        village="",
        guardian_name="",
        status="active",
        van_fees=None,
        village_fee_service=None,
        class_fee_service=None,
    ):
        if not student:
            raise ValueError("Student is required")
        if not (student_id or "").strip():
            raise ValueError("Student ID is required")
        if not (full_name or "").strip():
            raise ValueError("Name is required")
        if not (class_name or "").strip():
            raise ValueError("Class is required")
        if not (section or "").strip():
            raise ValueError("Section is required")
        if not (phone or "").strip():
            raise ValueError("Phone is required")
        if not (guardian_name or "").strip():
            raise ValueError("Guardian name is required")
        if village_fee_service is not None:
            vf = float(village_fee_service.van_fees_for_student_update(student, village))
        elif van_fees is not None and van_fees != "":
            vf = self._parse_fee_amount(van_fees, "Van fees")
        else:
            vf = float(getattr(student, "van_fees", 0) or 0.0)
        if class_fee_service is not None:
            sf = class_fee_service.school_fees_for_student_update(student, class_name)
        else:
            sf = float(getattr(student, "school_fees", 0) or 0.0)
        return self.repo.update_student(
            student, student_id, full_name, class_name, section, phone, village, guardian_name, status, vf, sf
        )
