"""Load realistic sample data into the DEVELOPMENT database.

Creates a believable demo dataset for the dev/testing build only:

  * Class school-fee tariffs and village van-fee tariffs for the current year
  * Sample students (new + old, across classes / sections / villages)
  * Sample fee payments (full, partial, with discount, and a few reverted)
  * Sample miscellaneous expenses (Rent, Stationary, Infra, etc.)
  * Sample income sources (Uniform, Books, Shoes, etc.)

It goes through the same services the app uses, so every figure (dues,
pending fees, payment history, dashboard charts) is internally consistent.

This NEVER touches the packaged build / deployment folder. It writes only to
the development database resolved by backend.core.config (data/fee_management.db
when running from source).

Run from the project root:

    set PYTHONPATH=. && python backend/scripts/seed_sample_data.py
"""

from __future__ import annotations

import calendar
import random
from datetime import date, timedelta

from backend.core.database import SessionLocal, engine
from backend.core.fee_control_constants import FIXED_CLASS_KEYS, FIXED_SECTION_KEYS
from backend.core.schema_migrations import (
    apply_sqlite_column_migrations,
    apply_sqlite_data_migrations,
)
from backend.core.student_roll_number import compose_roll_number, suggest_next_sequence
from backend.models import FeeHead
from backend.repositories.academic_year_repository import AcademicYearRepository
from backend.services.class_fee_service import ClassFeeService
from backend.services.misc_expense_service import MiscExpenseService
from backend.services.misc_income_service import MiscIncomeService
from backend.services.payment_service import PaymentService
from backend.services.student_service import StudentService
from backend.services.village_van_fee_service import VillageVanFeeService

SEED = 20260619

# Annual school-fee tariff per class for the current academic year.
CLASS_FEES: dict[str, float] = {
    "Nursery": 10000,
    "LKG": 12000,
    "UKG": 13000,
    "1": 16000,
    "2": 17000,
    "3": 18000,
    "4": 19000,
    "5": 20000,
    "6": 22000,
    "7": 23000,
    "8": 24000,
    "9": 27000,
    "10": 30000,
}

# Annual van-fee tariff per village for the current academic year.
VILLAGE_FEES: dict[str, float] = {
    "Nagaram": 8000,
    "Kamalapur": 9000,
    "Dharmapuri": 7000,
    "Thimmapur": 8500,
    "Thummenala": 9500,
    "Rayapatnam": 10000,
    "Rajaram": 7500,
    "Damannapet": 11000,
    "Jaina": 6500,
    "Edapelly": 12000,
    "Ramaiahpally": 8000,
    "Burugupally": 9000,
    "LN Colony": 6000,
    "Thenuguwada": 10500,
    "ARR Colony": 6000,
}

FIRST_NAMES_M = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh",
    "Krishna", "Ishaan", "Kabir", "Rohan", "Ayaan", "Karthik", "Dhruv", "Aniket",
]
FIRST_NAMES_F = [
    "Ananya", "Diya", "Aadhya", "Myra", "Ira", "Saanvi", "Kiara",
    "Navya", "Riya", "Meera", "Sneha", "Pooja", "Lakshmi", "Sruthi", "Harini",
]
LAST_NAMES = [
    "Sharma", "Verma", "Singh", "Gupta", "Patel", "Kumar", "Yadav", "Reddy",
    "Naidu", "Rao", "Goud", "Mehta", "Joshi", "Agarwal", "Pillai",
]
FATHER_FIRST = [
    "Rakesh", "Sunil", "Amit", "Vijay", "Rajesh", "Suresh", "Deepak",
    "Manish", "Mukesh", "Nitin", "Harish", "Ravi", "Srinivas", "Naresh", "Prakash",
]
MOTHER_FIRST = [
    "Pooja", "Neha", "Anita", "Kavita", "Seema", "Rekha", "Sunita",
    "Lalitha", "Padma", "Geetha", "Vani", "Swathi", "Madhavi", "Sridevi", "Usha",
]
SECTIONS = list(FIXED_SECTION_KEYS)
MODES = ["cash", "cash", "cash", "upi", "upi", "card", "cheque"]

NEW_STUDENT_COUNT = 40
OLD_STUDENT_COUNT = 12  # carry forward pending fees from a prior year

# (head, [(month_offset_from_today, particular, amount), ...])
EXPENSE_HEADS: list[tuple[str, list[tuple[str, float]]]] = [
    ("Rent", [("April 2026", 32000), ("May 2026", 32000), ("June 2026", 32000)]),
    ("Stationary", [("Exam answer sheets", 2400), ("Pamphlets & notices", 1850), ("Hall tickets printing", 2100)]),
    ("Infra", [("Classroom ceiling fans", 6500), ("Speaker wiring repair", 3200), ("Projector bulb", 4800)]),
    ("Water Bill", [("April municipal bill", 9500), ("May municipal bill", 10200)]),
    ("Electricity Bill", [("April bill", 7800), ("May bill", 8600)]),
    ("Maintenance", [("Plumbing repair", 2300), ("Whitewashing classrooms", 9000)]),
    ("Event", [("Annual day stage rental", 12000), ("Sports day refreshments", 4500)]),
    ("Printing", [("Progress report cards", 3100)]),
    ("Miscellaneous", [("Office recharge & courier", 1250), ("Cleaning supplies", 1600)]),
]

INCOME_HEADS: list[tuple[str, list[tuple[str, float]]]] = [
    ("Uniform", [("Summer uniform - boys", 22000), ("Summer uniform - girls", 19500), ("PE kits & ties", 11400)]),
    ("Books", [("Class 6-8 textbooks", 28500), ("Class 9-10 workbooks", 34000), ("New year textbook set", 41200)]),
    ("Shoes", [("Black school shoes", 16800), ("Sports shoes - white", 9400)]),
    ("Stationary", [("Student stationery packs", 9800), ("Geometry box sales", 3450)]),
    ("Application Forms", [("Admission forms", 6000), ("TC application forms", 1500)]),
    ("ID Cards", [("Student ID cards", 4200)]),
    ("Bus Pass", [("Replacement bus passes", 2800)]),
    ("Donation", [("Parent association fund", 10000), ("Alumni scholarship fund", 7500)]),
]


def _round_100(value: float) -> int:
    return max(0, int(round(float(value) / 100.0)) * 100)


def _class_age(class_key: str) -> int:
    if class_key == "Nursery":
        return 3
    if class_key == "LKG":
        return 4
    if class_key == "UKG":
        return 5
    try:
        return int(class_key) + 5
    except ValueError:
        return 10


def set_tariffs(session) -> None:
    class_svc = ClassFeeService(session)
    village_svc = VillageVanFeeService(session)
    for class_key, amount in CLASS_FEES.items():
        class_svc.apply_class_school_fee(class_key, float(amount))
    for village_key, amount in VILLAGE_FEES.items():
        village_svc.apply_village_van_fee(village_key, float(amount))
    session.commit()


def _make_student_kwargs(rng: random.Random, idx: int, class_key: str) -> dict:
    gender = rng.choice(["Male", "Female"])
    first = rng.choice(FIRST_NAMES_M if gender == "Male" else FIRST_NAMES_F)
    last = rng.choice(LAST_NAMES)
    father = f"{rng.choice(FATHER_FIRST)} {last}"
    mother = f"{rng.choice(MOTHER_FIRST)} {last}"
    village = rng.choice(list(VILLAGE_FEES.keys()))
    transport = "van" if rng.random() < 0.8 else "own"
    section = rng.choice(SECTIONS)
    age = _class_age(class_key)
    dob = date(date.today().year - age, rng.randint(1, 12), rng.randint(1, 28))
    mobile1 = f"9{800000000 + idx:09d}"
    mobile2 = f"8{700000000 + idx:09d}" if rng.random() < 0.4 else ""
    aadhaar = f"{700000000000 + idx:012d}"
    return {
        "full_name": f"{first} {last}",
        "class_name": class_key,
        "section": section,
        "phone": mobile1,
        "village": village,
        "status": "active",
        "transport_mode": transport,
        "gender": gender,
        "father_name": father,
        "mother_name": mother,
        "mobile_number_1": mobile1,
        "mobile_number_2": mobile2,
        "date_of_birth": dob,
        "aadhaar": aadhaar,
    }


def create_students(session, rng: random.Random) -> list[str]:
    student_svc = StudentService(session)
    class_svc = ClassFeeService(session)
    village_svc = VillageVanFeeService(session)
    year_repo = AcademicYearRepository(session)
    current = year_repo.get_current() or year_repo.ensure_bootstrap_year()
    entry_year = current.start_date.year

    created: list[str] = []
    seq = suggest_next_sequence(session, entry_year)
    uid = 1

    for _ in range(NEW_STUDENT_COUNT):
        class_key = rng.choice(list(CLASS_FEES.keys()))
        roll = compose_roll_number(is_old=False, entry_year=entry_year, sequence=seq)
        kwargs = _make_student_kwargs(rng, uid, class_key)
        student_svc.create_student(
            roll,
            kwargs.pop("full_name"),
            kwargs.pop("class_name"),
            kwargs.pop("section"),
            kwargs.pop("phone"),
            class_fee_service=class_svc,
            village_fee_service=village_svc,
            is_old_student=False,
            **kwargs,
        )
        created.append(roll)
        seq += 1
        uid += 1

    for _ in range(OLD_STUDENT_COUNT):
        class_key = rng.choice(list(CLASS_FEES.keys()))
        roll = compose_roll_number(is_old=True, entry_year=entry_year, sequence=seq)
        kwargs = _make_student_kwargs(rng, uid, class_key)
        pending = float(rng.choice([5000, 8000, 12000, 15000, 20000, 25000, 30000]))
        student_svc.create_student(
            roll,
            kwargs.pop("full_name"),
            kwargs.pop("class_name"),
            kwargs.pop("section"),
            kwargs.pop("phone"),
            class_fee_service=class_svc,
            village_fee_service=village_svc,
            initial_pending_fees=pending,
            is_old_student=True,
            **kwargs,
        )
        created.append(roll)
        seq += 1
        uid += 1

    session.commit()
    return created


def _random_payment_date(rng: random.Random) -> date:
    today = date.today()
    span = max(1, (today - date(today.year, 5, 31)).days)
    return today - timedelta(days=rng.randint(0, span))


def record_payments(session, rng: random.Random, student_ids: list[str]) -> dict[str, int]:
    payment_svc = PaymentService(session)
    student_svc = StudentService(session)
    stats = {"full": 0, "partial": 0, "discount": 0, "none": 0, "reverted": 0}

    for sid in student_ids:
        student = student_svc.get_student(sid)
        if student is None:
            continue
        due = payment_svc.get_student_due_breakdown(sid)
        school_cap = float(due.get("school_payable", 0.0) or 0.0)
        van_cap = float(due.get("van_payable", 0.0) or 0.0)
        if float(due.get("total", 0.0) or 0.0) <= 0:
            stats["none"] += 1
            continue

        roll = rng.random()
        school = van = discount = 0
        if roll < 0.22:
            stats["none"] += 1
            continue
        elif roll < 0.55:
            frac = rng.choice([0.3, 0.4, 0.5, 0.6, 0.7])
            school = min(_round_100(school_cap * frac), int(round(school_cap)))
            van = min(_round_100(van_cap * frac), int(round(van_cap)))
            stats["partial"] += 1
        elif roll < 0.80:
            school = int(round(school_cap))
            van = int(round(van_cap))
            stats["full"] += 1
        else:
            school = min(_round_100(school_cap * 0.6), int(round(school_cap)))
            van = min(_round_100(van_cap * 0.5), int(round(van_cap)))
            discount = _round_100(school_cap * 0.05)
            if school + discount > int(round(school_cap)):
                discount = max(0, int(round(school_cap)) - school)
            stats["discount"] += 1

        if school + van + discount <= 0:
            stats["none"] += 1
            continue

        try:
            payment_svc.collect_split_payment(
                student,
                van_amount=float(van),
                school_amount=float(school),
                mode=rng.choice(MODES),
                operator_name="admin",
                discount_amount=float(discount),
                payment_date=_random_payment_date(rng),
            )
        except ValueError:
            # Defensive: skip any student whose computed amount no longer fits.
            stats["none"] += 1

    # A few reverted payments so Payment History shows the "reverted" state.
    reverted_target = 3
    for sid in student_ids:
        if stats["reverted"] >= reverted_target:
            break
        student = student_svc.get_student(sid)
        if student is None:
            continue
        due = payment_svc.get_student_due_breakdown(sid)
        if float(due.get("school_payable", 0.0) or 0.0) < 1000:
            continue
        try:
            payment = payment_svc.collect_split_payment(
                student,
                van_amount=0.0,
                school_amount=1000.0,
                mode="cash",
                operator_name="admin",
                payment_date=_random_payment_date(rng),
                remark="Entered by mistake",
            )
            payment_svc.undo_payment(payment.reference_no)
            stats["reverted"] += 1
        except ValueError:
            continue

    session.commit()
    return stats


def _spread_entry_date(today: date, head_index: int, k: int) -> date:
    """Spread entries across the current month and the two prior months.

    The current month gets the bulk so the dashboard (which defaults to the
    current month) is populated, with older entries for month navigation.
    """
    month_offset = (0, 0, 0, 1, 2)[(head_index + k) % 5]
    y, m = today.year, today.month
    for _ in range(month_offset):
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    last_day = calendar.monthrange(y, m)[1]
    day = 2 + ((head_index * 3 + k * 6) % 22)
    day = min(day, last_day)
    if y == today.year and m == today.month:
        day = min(day, today.day)
    return date(y, m, day)


def seed_misc(session) -> dict[str, int]:
    expense_svc = MiscExpenseService(session)
    income_svc = MiscIncomeService(session)
    today = date.today()
    counts = {"expense_heads": 0, "expense_entries": 0, "income_heads": 0, "income_entries": 0}

    for head_index, (head, entries) in enumerate(EXPENSE_HEADS):
        expense = expense_svc.add_new_expense(head, _spread_entry_date(today, head_index, 0))
        counts["expense_heads"] += 1
        for k, (particular, amount) in enumerate(entries):
            entry_date = _spread_entry_date(today, head_index, k)
            expense_svc.add_entry(int(expense.id), particular, float(amount), entry_date=entry_date)
            counts["expense_entries"] += 1

    for head_index, (head, entries) in enumerate(INCOME_HEADS):
        income = income_svc.add_new_income(head, _spread_entry_date(today, head_index, 0))
        counts["income_heads"] += 1
        for k, (particular, amount) in enumerate(entries):
            entry_date = _spread_entry_date(today, head_index, k)
            income_svc.add_entry(int(income.id), particular, float(amount), entry_date=entry_date)
            counts["income_entries"] += 1

    session.commit()
    return counts


def _ensure_fee_heads(session) -> None:
    """Payments need a Tuition and a Transport fee head to create invoice lines."""
    existing = {h.head_name.strip().lower() for h in session.query(FeeHead).all()}
    if "tuition" not in existing:
        session.add(FeeHead(head_name="Tuition", frequency="monthly", default_amount=0))
    if "transport" not in existing:
        session.add(FeeHead(head_name="Transport", frequency="monthly", default_amount=0))
    session.commit()


def seed_sample_data() -> dict:
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)
    rng = random.Random(SEED)

    session = SessionLocal()
    try:
        AcademicYearRepository(session).ensure_bootstrap_year()
        _ensure_fee_heads(session)
        set_tariffs(session)
        student_ids = create_students(session, rng)
        payment_stats = record_payments(session, rng, student_ids)
        misc_counts = seed_misc(session)
        return {
            "students": len(student_ids),
            "payments": payment_stats,
            "misc": misc_counts,
        }
    finally:
        session.close()


if __name__ == "__main__":
    result = seed_sample_data()
    p = result["payments"]
    m = result["misc"]
    print("Sample data loaded into the development database:")
    print(f"  Students created     : {result['students']}")
    print(
        "  Payments recorded    : "
        f"{p['full']} full, {p['partial']} partial, {p['discount']} with discount, "
        f"{p['reverted']} reverted, {p['none']} left unpaid"
    )
    print(
        "  Miscellaneous expenses: "
        f"{m['expense_heads']} heads, {m['expense_entries']} entries"
    )
    print(
        "  Income sources        : "
        f"{m['income_heads']} heads, {m['income_entries']} entries"
    )
