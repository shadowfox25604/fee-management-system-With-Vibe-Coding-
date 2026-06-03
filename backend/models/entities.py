from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.core.database import Base


class AcademicYear(Base):
    __tablename__ = "academic_years"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    label: Mapped[str] = mapped_column(String(40), nullable=False, default="")


class StudentAcademicYearFee(Base):
    __tablename__ = "student_academic_year_fees"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id_fk: Mapped[str] = mapped_column(String(20), ForeignKey("students.student_id"), nullable=False)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"), nullable=False)
    school_fees: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    van_fees: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    __table_args__ = (
        UniqueConstraint("student_id_fk", "academic_year_id", name="uq_student_academic_year"),
    )


class Student(Base):
    __tablename__ = "students"
    student_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    gender: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    father_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    mother_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    class_name: Mapped[str] = mapped_column(String(20), nullable=False)
    section: Mapped[str] = mapped_column(String(10), default="")
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    mobile_number_1: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    mobile_number_2: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    caste: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    aadhaar: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    village: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    guardian_name: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    transport_mode: Mapped[str] = mapped_column(String(20), default="van", nullable=False)
    van_fees: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    school_fees: Mapped[float] = mapped_column(Float, default=20000.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    invoices = relationship("Invoice", back_populates="student", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="student", cascade="all, delete-orphan")
Index("idx_students_name", Student.full_name)
Index("idx_students_phone", Student.phone)

class FeeHead(Base):
    __tablename__ = "fee_heads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    head_name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), default="monthly")
    default_amount: Mapped[float] = mapped_column(Float, default=0.0)

class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id_fk: Mapped[str] = mapped_column(String(20), ForeignKey("students.student_id"), nullable=False)
    academic_year_id: Mapped[int | None] = mapped_column(ForeignKey("academic_years.id"), nullable=True)
    fee_head_id: Mapped[int] = mapped_column(ForeignKey("fee_heads.id"), nullable=False)
    period_label: Mapped[str] = mapped_column(String(20), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_due: Mapped[float] = mapped_column(Float, nullable=False)
    amount_paid: Mapped[float] = mapped_column(Float, default=0.0)
    student = relationship("Student", back_populates="invoices")

class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id_fk: Mapped[str] = mapped_column(String(20), ForeignKey("students.student_id"), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, default=date.today)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    school_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    van_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default="cash")
    reference_no: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    operator_name: Mapped[str] = mapped_column(String(60), default="admin")
    is_reverted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reverted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    student = relationship("Student", back_populates="payments")

class ClassSchoolFee(Base):
    __tablename__ = "class_school_fees"
    class_key: Mapped[str] = mapped_column(String(30), primary_key=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)


class VillageVanFee(Base):
    __tablename__ = "village_van_fees"
    village_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)


class FacultySalary(Base):
    __tablename__ = "faculty_salaries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faculty_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    faculty_type: Mapped[str] = mapped_column(String(20), default="Teaching", nullable=False)
    role: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    monthly_salary: Mapped[float] = mapped_column(Float, nullable=False)
    default_working_days: Mapped[int] = mapped_column(Integer, default=26, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FacultyAttendance(Base):
    __tablename__ = "faculty_attendance"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faculty_id_fk: Mapped[int] = mapped_column(ForeignKey("faculty_salaries.id"), nullable=False)
    month_label: Mapped[str] = mapped_column(String(20), nullable=False)
    marked_days_csv: Mapped[str] = mapped_column(Text, default="", nullable=False)
    checked_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sunday_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attendance_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    working_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("faculty_id_fk", "month_label", name="uq_faculty_attendance_month"),
    )


class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expense_type: Mapped[str] = mapped_column(String(20), nullable=False)  # salary
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    person_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    faculty_type: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    description: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    month_label: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    attendance_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    working_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    base_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reference_no: Mapped[str | None] = mapped_column(String(16), nullable=True)
    operator_name: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    is_reverted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reverted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MiscExpense(Base):
    __tablename__ = "misc_expenses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    head: Mapped[str] = mapped_column(String(80), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    entries = relationship("MiscExpenseEntry", back_populates="expense", cascade="all, delete-orphan")


class MiscExpenseEntry(Base):
    __tablename__ = "misc_expense_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("misc_expenses.id"), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    particular: Mapped[str] = mapped_column(String(240), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    expense = relationship("MiscExpense", back_populates="entries")


class FeePlan(Base):
    __tablename__ = "fee_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id_fk: Mapped[str] = mapped_column(String(20), ForeignKey("students.student_id"), nullable=False)
    fee_head_id: Mapped[int] = mapped_column(ForeignKey("fee_heads.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    concession_amount: Mapped[float] = mapped_column(Float, default=0.0)
    effective_from: Mapped[date] = mapped_column(Date, default=date.today)
    __table_args__ = (UniqueConstraint("student_id_fk", "fee_head_id", name="uq_student_fee_head"),)

class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    allocated_amount: Mapped[float] = mapped_column(Float, nullable=False)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="operator")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    table_name: Mapped[str] = mapped_column(String(40), nullable=False)
    record_id: Mapped[str] = mapped_column(String(40), nullable=False)
    old_value: Mapped[str] = mapped_column(Text, default="")
    new_value: Mapped[str] = mapped_column(Text, default="")
    performed_by: Mapped[str] = mapped_column(String(60), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
