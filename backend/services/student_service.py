from datetime import date, datetime

from backend.repositories.student_repository import StudentRepository


class StudentService:
    def __init__(self, session):
        self.repo = StudentRepository(session)

    def search_students(self, query):
        return self.repo.search(query)

    def list_students(self):
        return self.repo.list_students()

    def count_active_inactive(self) -> tuple[int, int]:
        return self.repo.count_active_inactive()

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

    @staticmethod
    def _normalize_transport_mode(mode: str | None) -> str:
        m = (mode or "van").strip().lower()
        if m not in ("van", "own"):
            raise ValueError("Transport must be van transport or own transport")
        return m

    @staticmethod
    def _validate_phone(phone: str) -> str:
        value = (phone or "").strip()
        if not value:
            raise ValueError("Mobile number 1 is required")
        if not value.isdigit() or len(value) != 10:
            raise ValueError("Mobile number 1 must be exactly 10 digits")
        return value

    @staticmethod
    def _validate_optional_phone(phone: str) -> str:
        value = (phone or "").strip()
        if not value:
            return ""
        if not value.isdigit() or len(value) != 10:
            raise ValueError("Mobile number 2 must be exactly 10 digits")
        return value

    @staticmethod
    def _validate_aadhaar(aadhaar: str) -> str:
        value = (aadhaar or "").strip()
        if not value:
            return ""
        if not value.isdigit() or len(value) != 12:
            raise ValueError("Aadhaar must be exactly 12 digits")
        return value

    @staticmethod
    def _parse_date_of_birth(value) -> date | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value or "").strip()
        if not text:
            return None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        raise ValueError("Date of Birth must be in DD/MM/YYYY format")

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
        transport_mode="van",
        van_fees=None,
        village_fee_service=None,
        class_fee_service=None,
        gender="",
        father_name="",
        mother_name="",
        mobile_number_1="",
        mobile_number_2="",
        date_of_birth=None,
        caste="",
        aadhaar="",
    ):
        if not (student_id or "").strip():
            raise ValueError("Student ID is required")
        if not (full_name or "").strip():
            raise ValueError("Name is required")
        if not (class_name or "").strip():
            raise ValueError("Class is required")
        if not (section or "").strip():
            raise ValueError("Section is required")
        primary_mobile = self._validate_phone(mobile_number_1 or phone)
        secondary_mobile = self._validate_optional_phone(mobile_number_2)
        father = (father_name or guardian_name or "").strip()
        mother = (mother_name or "").strip()
        gender_value = (gender or "").strip()
        if not gender_value:
            raise ValueError("Gender is required")
        caste_value = (caste or "").strip()
        if not father:
            raise ValueError("Father name is required")
        aadhaar_value = self._validate_aadhaar(aadhaar)
        dob_value = self._parse_date_of_birth(date_of_birth)
        if not (village or "").strip():
            raise ValueError("Village is required")
        if not str(transport_mode or "").strip():
            raise ValueError("Transport is required")
        status_value = (status or "").strip() or "active"
        tm = self._normalize_transport_mode(transport_mode)
        if tm == "own":
            vf = 0.0
        elif village_fee_service is not None:
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
            student_id,
            full_name,
            class_name,
            section,
            primary_mobile,
            village,
            father,
            status_value,
            vf,
            sf,
            transport_mode=tm,
            gender=gender_value,
            father_name=father,
            mother_name=mother,
            mobile_number_1=primary_mobile,
            mobile_number_2=secondary_mobile,
            date_of_birth=dob_value,
            caste=caste_value,
            aadhaar=aadhaar_value,
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
        transport_mode="van",
        van_fees=None,
        village_fee_service=None,
        class_fee_service=None,
        gender="",
        father_name="",
        mother_name="",
        mobile_number_1="",
        mobile_number_2="",
        date_of_birth=None,
        caste="",
        aadhaar="",
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
        primary_mobile = self._validate_phone(mobile_number_1 or phone)
        secondary_mobile = self._validate_optional_phone(mobile_number_2)
        father = (father_name or guardian_name or "").strip()
        mother = (mother_name or "").strip()
        gender_value = (gender or "").strip()
        if not gender_value:
            raise ValueError("Gender is required")
        caste_value = (caste or "").strip()
        if not father:
            raise ValueError("Father name is required")
        aadhaar_value = self._validate_aadhaar(aadhaar)
        dob_value = self._parse_date_of_birth(date_of_birth)
        if not (village or "").strip():
            raise ValueError("Village is required")
        if not str(transport_mode or "").strip():
            raise ValueError("Transport is required")
        status_value = (status or "").strip() or "active"
        tm = self._normalize_transport_mode(transport_mode)
        old_tm = (getattr(student, "transport_mode", None) or "van").strip().lower()
        if tm == "own":
            vf = 0.0
        elif village_fee_service is not None:
            if old_tm == "own" and tm == "van":
                vf = float(village_fee_service.van_fees_for_village_name(village))
            else:
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
            student,
            student_id,
            full_name,
            class_name,
            section,
            primary_mobile,
            village,
            father,
            status_value,
            vf,
            sf,
            transport_mode=tm,
            gender=gender_value,
            father_name=father,
            mother_name=mother,
            mobile_number_1=primary_mobile,
            mobile_number_2=secondary_mobile,
            date_of_birth=dob_value,
            caste=caste_value,
            aadhaar=aadhaar_value,
        )
