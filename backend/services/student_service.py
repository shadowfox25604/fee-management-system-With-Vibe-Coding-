from datetime import date, datetime

from backend.core.student_roll_number import (
    parse_roll_number,
    validate_roll_number_for_create,
    validate_roll_number_suffix_change,
)
from backend.repositories.student_repository import StudentRepository


class StudentService:
    def __init__(self, session):
        self.repo = StudentRepository(session)

    def search_students(self, query):
        return self.repo.search(query)

    def list_students(self):
        return self.repo.list_students()

    def get_student(self, student_id: str):
        return self.repo.get_by_id(student_id)

    def suggest_next_roll_number(self, *, is_old: bool) -> str:
        return self.repo.suggest_next_roll_number(is_old=is_old)

    def delete_student(self, student_id: str) -> str:
        student = self.repo.get_by_id(student_id)
        if student is None:
            raise ValueError(f"Student not found: {(student_id or '').strip()}")
        name = str(student.full_name or student_id)
        self.repo.delete_student_cascade(student.student_id)
        return name

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
            value = value.date()
        if isinstance(value, date):
            if value > date.today():
                raise ValueError("Date of Birth cannot be in the future.")
            return value
        text = str(value or "").strip()
        if not text:
            return None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                parsed = datetime.strptime(text, fmt).date()
                if parsed > date.today():
                    raise ValueError("Date of Birth cannot be in the future.")
                return parsed
            except ValueError as exc:
                if str(exc) == "Date of Birth cannot be in the future.":
                    raise
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
        initial_pending_fees: float | None = None,
        *,
        is_old_student: bool = False,
    ):
        if not (student_id or "").strip():
            raise ValueError("Student ID is required")
        student_id = validate_roll_number_for_create(
            self.repo.session,
            student_id,
            is_old=is_old_student,
        )
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
            sf = 0.0
        pending_amount = None
        if initial_pending_fees is not None:
            pending_amount = self._parse_fee_amount(initial_pending_fees, "Pending fees")
        student = self.repo.create_student(
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
        if pending_amount is not None and pending_amount > 0:
            self._seed_import_pending_fees(student, pending_amount)
        return student

    def _seed_import_pending_fees(self, student, amount: float) -> None:
        from backend.core.academic_year_dates import (
            academic_year_bounds_for_start_year,
            academic_year_start_year_for_date,
        )
        from backend.repositories.academic_year_repository import AcademicYearRepository
        from backend.repositories.student_year_fee_repository import StudentYearFeeRepository

        session = self.repo.session
        year_repo = AcademicYearRepository(session)
        current = year_repo.get_current()
        if current is None:
            years = year_repo.list_all()
            if not years:
                raise ValueError("No current academic year is configured.")
            current = years[-1]

        prior = year_repo.get_predecessor(current)
        if prior is None:
            prior_start_year = academic_year_start_year_for_date(current.start_date) - 1
            start, end = academic_year_bounds_for_start_year(prior_start_year)
            prior = year_repo.find_by_start_date(start)
            if prior is None:
                prior = year_repo.create(start, end)
                session.commit()

        student.created_at = datetime(
            prior.start_date.year,
            prior.start_date.month,
            prior.start_date.day,
            10,
            0,
            0,
        )
        sy = StudentYearFeeRepository(session)
        prior_row = sy.get_or_create(
            student,
            prior.id,
            school_fees=float(amount),
            van_fees=0.0,
            allow_inactive=True,
        )
        prior_row.opening_pending_fees = 0.0
        current_row = sy.get(student.student_id, current.id)
        if current_row is None:
            current_row = sy.get_or_create(
                student,
                current.id,
                school_fees=float(student.school_fees or 0.0),
                van_fees=float(student.van_fees or 0.0),
                allow_inactive=True,
            )
        else:
            current_row.school_fees = float(student.school_fees or 0.0)
            current_row.van_fees = float(student.van_fees or 0.0)
        current_row.opening_pending_fees = 0.0
        session.add(student)
        session.add(prior_row)
        session.add(current_row)
        session.commit()

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
        old_id = str(getattr(student, "student_id", "") or "").strip()
        new_id = (student_id or "").strip()
        if old_id.lower() != new_id.lower():
            if parse_roll_number(old_id) is not None:
                new_id = validate_roll_number_suffix_change(old_id, new_id)
                if self.repo.get_by_id(new_id) is not None and new_id.lower() != old_id.lower():
                    raise ValueError("Student ID already exists.")
            else:
                self.repo._ensure_unique_student_values(
                    student_id=new_id,
                    aadhaar=(aadhaar or "").strip(),
                    exclude_student_id=old_id,
                )
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
            new_id,
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

    def student_join_date_bounds(self) -> tuple[date | None, date | None]:
        return self.repo.student_join_date_bounds()

    def list_export_students(
        self,
        *,
        search: str | None = None,
        search_basis: str | None = None,
        month: tuple[int, int] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        class_names: list[str] | None = None,
        sections: list[str] | None = None,
        status: str | None = None,
        student_id: str | None = None,
    ):
        from backend.core.student_search_match import student_matches_search

        students = self.repo.list_for_export(
            month=month,
            date_from=date_from,
            date_to=date_to,
            class_names=class_names,
            sections=sections,
            status=status,
            student_id=student_id,
        )
        q = (search or "").strip()
        basis = (search_basis or "Name").strip()
        if q:
            students = [s for s in students if student_matches_search(s, basis, q)]
        return students

    def count_export_rows(self, **filters) -> int:
        student_filters = dict(filters)
        student_filters.pop("columns", None)
        return len(self.list_export_students(**student_filters))

    @staticmethod
    def _format_export_date(value) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.strftime("%d/%m/%Y")
        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")
        return str(value)

    @staticmethod
    def _format_export_gender(value) -> str:
        text = str(value or "").strip()
        lower = text.lower()
        if lower in ("male", "boy"):
            return "Male"
        if lower in ("female", "girl"):
            return "Female"
        return text.title() if text else ""

    def build_list_export_rows(
        self,
        students,
        *,
        summaries: dict | None = None,
        van_summaries: dict | None = None,
        due_map: dict | None = None,
        discount_map: dict | None = None,
    ) -> list[dict]:
        from backend.core.fee_due_display import pending_fees

        summaries = summaries or {}
        van_summaries = van_summaries or {}
        due_map = due_map or {}
        discount_map = discount_map or {}
        rows: list[dict] = []
        for student in students:
            student_id = getattr(student, "student_id", None)
            summary = summaries.get(
                student_id,
                {"fee_paid": 0.0, "fee_due": 0.0, "total_fees": 0.0},
            )
            van_summary = van_summaries.get(student_id, {"van_paid": 0.0, "van_due": 0.0})
            due = due_map.get(
                student_id,
                {
                    "pending_fees": 0.0,
                    "van_due": 0.0,
                    "fee_due": 0.0,
                    "total": 0.0,
                },
            )
            rows.append(
                {
                    "student_id": str(student_id or ""),
                    "full_name": str(getattr(student, "full_name", None) or ""),
                    "gender": self._format_export_gender(getattr(student, "gender", None)),
                    "father_name": str(
                        getattr(student, "father_name", None)
                        or getattr(student, "guardian_name", None)
                        or ""
                    ),
                    "mother_name": str(getattr(student, "mother_name", None) or ""),
                    "class_name": str(getattr(student, "class_name", None) or ""),
                    "section": str(getattr(student, "section", None) or ""),
                    "mobile_number_1": str(
                        getattr(student, "mobile_number_1", None)
                        or getattr(student, "phone", None)
                        or ""
                    ),
                    "mobile_number_2": str(getattr(student, "mobile_number_2", None) or ""),
                    "date_of_birth": self._format_export_date(getattr(student, "date_of_birth", None)),
                    "caste": str(getattr(student, "caste", None) or ""),
                    "aadhaar": str(getattr(student, "aadhaar", None) or ""),
                    "village": str(getattr(student, "village", None) or ""),
                    "status": str(getattr(student, "status", None) or ""),
                    "van_fees": float(getattr(student, "van_fees", 0) or 0.0),
                    "van_paid": float(van_summary.get("van_paid", 0) or 0.0),
                    "van_due": float(due.get("van_due", 0) or 0.0),
                    "school_fees": float(getattr(student, "school_fees", 0) or 0.0),
                    "school_paid": float(summary.get("fee_paid", 0) or 0.0),
                    "discount": float(discount_map.get(student_id, 0) or 0.0),
                    "pending_fees": float(pending_fees(due)),
                    "school_due": float(due.get("fee_due", 0) or 0.0),
                    "school_payable": float(due.get("school_payable", 0) or 0.0),
                    "total_due": float(due.get("total", 0) or 0.0),
                }
            )
        return rows

    def export_list_excel(
        self,
        output_path,
        students,
        *,
        summaries: dict | None = None,
        van_summaries: dict | None = None,
        due_map: dict | None = None,
        discount_map: dict | None = None,
        columns: list[str] | None = None,
    ):
        from pathlib import Path

        from backend.reports.student_list_excel_export import StudentListExcelExporter

        path = Path(output_path)
        rows = self.build_list_export_rows(
            students,
            summaries=summaries,
            van_summaries=van_summaries,
            due_map=due_map,
            discount_map=discount_map,
        )
        StudentListExcelExporter.export(rows, path, columns=columns)
        return path

    def export_list_excel_filtered(self, output_path, payment_service, **filters):
        columns = filters.pop("columns", None)
        students = self.list_export_students(**filters)
        student_ids = [s.student_id for s in students]
        fee_maps = {
            "summaries": payment_service.get_students_school_fee_summary(student_ids),
            "van_summaries": payment_service.get_students_van_fee_summary(student_ids),
            "due_map": payment_service.get_students_due_breakdown(student_ids),
            "discount_map": payment_service.get_students_cumulative_payment_discount(student_ids),
        }
        return self.export_list_excel(
            output_path,
            students,
            summaries=fee_maps["summaries"],
            van_summaries=fee_maps["van_summaries"],
            due_map=fee_maps["due_map"],
            discount_map=fee_maps["discount_map"],
            columns=columns,
        )
