from datetime import date, timedelta
import random
from backend.core.database import SessionLocal, engine
from backend.core.schema_migrations import apply_sqlite_column_migrations, apply_sqlite_data_migrations
from backend.core.fee_control_constants import FIXED_CLASS_KEYS, FIXED_VILLAGE_KEYS
from backend.core.security import hash_password
from backend.models import FeeHead, FeePlan, Invoice, Student, User

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Krishna", "Ishaan", "Kabir",
    "Ananya", "Diya", "Aadhya", "Myra", "Ira", "Saanvi", "Kiara", "Navya", "Riya", "Meera",
]

LAST_NAMES = [
    "Sharma", "Verma", "Singh", "Gupta", "Patel", "Kumar", "Yadav", "Mishra", "Joshi", "Agarwal",
    "Jain", "Reddy", "Nair", "Pillai", "Das", "Bose", "Malhotra", "Chopra", "Khan", "Ali",
]

GUARDIAN_FIRST_NAMES = [
    "Rakesh", "Sunil", "Amit", "Vijay", "Rajesh", "Suresh", "Pooja", "Neha", "Anita", "Kavita",
    "Deepak", "Manish", "Seema", "Rekha", "Mukesh", "Nitin", "Farah", "Ayesha", "Harish", "Ravi",
]

VILLAGES = list(FIXED_VILLAGE_KEYS)
CLASS_POOL = list(FIXED_CLASS_KEYS)
def _unique_student_values(idx, used_ids, used_phones):
    student_id = f"STU{idx:04d}"
    while student_id in used_ids:
        idx += 1
        student_id = f"STU{idx:04d}"

    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    full_name = f"{first} {last}"

    phone = f"9{(700000000 + idx) % 1000000000:09d}"
    while phone in used_phones:
        idx += 1
        phone = f"9{(700000000 + idx) % 1000000000:09d}"

    used_ids.add(student_id)
    used_phones.add(phone)
    guardian = f"{random.choice(GUARDIAN_FIRST_NAMES)} {last}"
    return idx, student_id, full_name, phone, guardian


def seed(target_students=200):
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    s=SessionLocal()
    try:
        if not s.query(User).filter(User.username=="admin").first(): s.add(User(username="admin", password_hash=hash_password("admin123"), role="admin"))
        t = s.query(FeeHead).filter(FeeHead.head_name == "Tuition").first()
        tr = s.query(FeeHead).filter(FeeHead.head_name == "Transport").first()
        if not t:
            t = FeeHead(head_name="Tuition", frequency="monthly", default_amount=2000)
            s.add(t)
        if not tr:
            tr = FeeHead(head_name="Transport", frequency="monthly", default_amount=500)
            s.add(tr)
        s.flush()

        existing_count = s.query(Student).count()
        to_create = max(0, target_students - existing_count)
        if to_create == 0:
            s.commit()
            return

        used_ids = {sid for (sid,) in s.query(Student.student_id).all()}
        used_phones = {ph for (ph,) in s.query(Student.phone).all()}

        students = []
        next_idx = existing_count + 1
        for i in range(to_create):
            next_idx, student_id, full_name, phone, guardian = _unique_student_values(next_idx + i, used_ids, used_phones)
            class_num = random.choice(CLASS_POOL)
            section = random.choice(["A", "B", "C"])
            students.append(
                Student(
                    student_id=student_id,
                    full_name=full_name,
                    class_name=class_num,
                    section=section,
                    phone=phone,
                    village=random.choice(VILLAGES),
                    guardian_name=guardian,
                )
            )

        s.add_all(students)
        s.flush()

        for st in s.query(Student).all():
            if not (getattr(st, "village", None) or "").strip():
                st.village = random.choice(VILLAGES)

        for st in students:
            s.add(FeePlan(student_id_fk=st.id, fee_head_id=t.id, amount=2000, concession_amount=0))
            s.add(FeePlan(student_id_fk=st.id, fee_head_id=tr.id, amount=500, concession_amount=0))
            for idx in range(1, 4):
                d = date.today() - timedelta(days=30 * idx)
                s.add(Invoice(student_id_fk=st.id, fee_head_id=t.id, period_label=f"2026-{idx:02d}", due_date=d, amount_due=2000, amount_paid=0))
                s.add(Invoice(student_id_fk=st.id, fee_head_id=tr.id, period_label=f"2026-{idx:02d}", due_date=d, amount_due=500, amount_paid=0))
        s.commit()
    finally:
        s.close()
if __name__ == "__main__":
    seed(target_students=200); print("Seed data created")
