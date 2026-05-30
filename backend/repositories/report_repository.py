from datetime import date

from sqlalchemy import and_, func, or_, select

from backend.models import Invoice, Student


class ReportRepository:
    def __init__(self, session):
        self.session = session
    def defaulters(self, as_of=None, student_query=None, class_name=None, section=None):
        as_of = as_of or date.today()
        stmt = select(Student.student_id, Student.full_name, Student.class_name, Student.section, func.sum(Invoice.amount_due-Invoice.amount_paid).label("outstanding")).join(Invoice, Invoice.student_id_fk==Student.student_id).where(and_(Invoice.due_date<=as_of, Invoice.amount_due>Invoice.amount_paid))
        q = (student_query or "").strip()
        if q:
            p = f"%{q}%"
            stmt = stmt.where((Student.student_id.ilike(p)) | (Student.full_name.ilike(p)))
        if class_name:
            stmt = stmt.where(Student.class_name == str(class_name))
        if section:
            stmt = stmt.where(Student.section == str(section))
        stmt = stmt.group_by(Student.student_id, Student.full_name, Student.class_name, Student.section)
        return self.session.execute(stmt).all()
    def distinct_classes(self):
        return [r[0] for r in self.session.execute(select(Student.class_name).distinct().order_by(Student.class_name)).all() if r[0] is not None]
    def distinct_sections(self):
        return [r[0] for r in self.session.execute(select(Student.section).distinct().order_by(Student.section)).all() if r[0] is not None]

    def list_students_for_report(
        self, student_query=None, class_name=None, section=None
    ):
        stmt = select(Student).order_by(Student.class_name, Student.section, Student.student_id)
        q = (student_query or "").strip()
        if q:
            p = f"%{q}%"
            stmt = stmt.where(
                or_(Student.student_id.ilike(p), Student.full_name.ilike(p))
            )
        if class_name:
            stmt = stmt.where(Student.class_name == str(class_name))
        if section:
            stmt = stmt.where(Student.section == str(section))
        return list(self.session.scalars(stmt).all())
