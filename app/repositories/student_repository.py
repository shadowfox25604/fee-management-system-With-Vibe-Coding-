from sqlalchemy import or_, select

from app.models import Student


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
        return student

    def list_students(self):
        return self.session.scalars(select(Student).order_by(Student.student_id.asc())).all()
