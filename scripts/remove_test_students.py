"""
Remove students created by pytest (test_core.py). Safe: matches exact full_name values only.

Usage (from project root):
    python -m scripts.remove_test_students
"""

from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.models import FeePlan, Invoice, Payment, PaymentAllocation, Student

# Exact full_name strings used in tests/test_core.py only
TEST_STUDENT_FULL_NAMES = (
    "Test User",
    "Own Transport Test",
    "Van Transport Test",
    "Split Pay Test",
    "Discount Pay Test",
    "Zero Net Discount Test",
    "Payment Date Test",
    "Future Date Test",
    "Due Merge Test",
    "Class Fee Test",
    "Village Van Fee Test",
    "Discount Cap Test",
    "Service Split Test",
)


def main() -> None:
    session = SessionLocal()
    try:
        ids = [
            row[0]
            for row in session.execute(
                select(Student.id).where(Student.full_name.in_(TEST_STUDENT_FULL_NAMES))
            ).all()
        ]
        if not ids:
            print("No matching test students found.")
            return

        pay_ids = session.scalars(select(Payment.id).where(Payment.student_id_fk.in_(ids))).all()
        if pay_ids:
            session.execute(delete(PaymentAllocation).where(PaymentAllocation.payment_id.in_(pay_ids)))
        session.execute(delete(Payment).where(Payment.student_id_fk.in_(ids)))
        session.execute(delete(Invoice).where(Invoice.student_id_fk.in_(ids)))
        session.execute(delete(FeePlan).where(FeePlan.student_id_fk.in_(ids)))
        session.execute(delete(Student).where(Student.id.in_(ids)))
        session.commit()
        print(f"Removed {len(ids)} test student(s) and related fee plans, invoices, and payments.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
