from datetime import date, datetime
from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    class_name: Mapped[str] = mapped_column(String(20), nullable=False)
    section: Mapped[str] = mapped_column(String(10), default="")
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
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
    student_id_fk: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    fee_head_id: Mapped[int] = mapped_column(ForeignKey("fee_heads.id"), nullable=False)
    period_label: Mapped[str] = mapped_column(String(20), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_due: Mapped[float] = mapped_column(Float, nullable=False)
    amount_paid: Mapped[float] = mapped_column(Float, default=0.0)
    student = relationship("Student", back_populates="invoices")

class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id_fk: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, default=date.today)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default="cash")
    reference_no: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    operator_name: Mapped[str] = mapped_column(String(60), default="admin")
    student = relationship("Student", back_populates="payments")

class ClassSchoolFee(Base):
    __tablename__ = "class_school_fees"
    class_key: Mapped[str] = mapped_column(String(30), primary_key=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)


class VillageVanFee(Base):
    __tablename__ = "village_van_fees"
    village_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)


class FeePlan(Base):
    __tablename__ = "fee_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id_fk: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
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
