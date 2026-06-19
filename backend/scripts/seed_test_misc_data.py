"""Add sample miscellaneous expenses and income entries for UI testing."""

from __future__ import annotations

from datetime import date

from backend.core.database import SessionLocal, engine
from backend.core.schema_migrations import apply_sqlite_column_migrations, apply_sqlite_data_migrations
from backend.services.misc_expense_service import MiscExpenseService
from backend.services.misc_income_service import MiscIncomeService

# (entry_date, head, particular, amount)
TEST_EXPENSE_ENTRIES: list[tuple[date, str, str, float]] = [
    (date(2026, 4, 2), "Rent", "April 2026", 32_000),
    (date(2026, 5, 3), "Rent", "May 2026", 32_000),
    (date(2026, 6, 2), "Rent", "June 2026", 32_000),
    (date(2026, 4, 10), "Stationary", "Exam answer sheets", 2_400),
    (date(2026, 5, 14), "Stationary", "Pamphlets and notices", 1_850),
    (date(2026, 6, 6), "Stationary", "Hall tickets printing", 2_100),
    (date(2026, 4, 18), "Infra", "Classroom ceiling fans", 6_500),
    (date(2026, 5, 22), "Infra", "Speaker wiring repair", 3_200),
    (date(2026, 6, 12), "Infra", "Projector bulb replacement", 4_800),
    (date(2026, 4, 25), "Water Bill", "April municipal bill", 9_500),
    (date(2026, 5, 28), "Water Bill", "May municipal bill", 10_200),
    (date(2026, 6, 15), "Water Bill", "June municipal bill", 9_800),
    (date(2026, 5, 8), "Event", "Annual day stage rental", 12_000),
    (date(2026, 6, 1), "Event", "Sports day refreshments", 4_500),
    (date(2026, 6, 10), "Miscellaneous", "Office recharge and courier", 1_250),
]

TEST_INCOME_ENTRIES: list[tuple[date, str, str, float]] = [
    (date(2026, 4, 5), "Books", "Class 6–8 textbook sales", 28_500),
    (date(2026, 4, 19), "Books", "Class 9–10 workbook bundle", 34_000),
    (date(2026, 5, 7), "Books", "Library reference books", 8_750),
    (date(2026, 6, 4), "Books", "New academic year textbooks", 41_200),
    (date(2026, 4, 12), "Uniform", "Summer uniform — boys", 22_000),
    (date(2026, 4, 12), "Uniform", "Summer uniform — girls", 19_500),
    (date(2026, 5, 20), "Uniform", "PE kits and ties", 11_400),
    (date(2026, 6, 8), "Uniform", "Monsoon jacket orders", 15_600),
    (date(2026, 5, 15), "Stationary", "Student stationery packs", 9_800),
    (date(2026, 6, 14), "Stationary", "Geometry box sales", 3_450),
    (date(2026, 4, 28), "Donation", "Parent association contribution", 10_000),
    (date(2026, 6, 16), "Donation", "Alumni scholarship fund", 7_500),
]


def _expense_id_for_head(svc: MiscExpenseService, head: str, head_date: date) -> int:
    key = head.strip().lower()
    for row in svc.list_expenses():
        if (row.head or "").strip().lower() == key:
            return int(row.id)
    return int(svc.add_new_expense(head, head_date).id)


def _income_id_for_head(svc: MiscIncomeService, head: str, head_date: date) -> int:
    key = head.strip().lower()
    for row in svc.list_incomes():
        if (row.head or "").strip().lower() == key:
            return int(row.id)
    return int(svc.add_new_income(head, head_date).id)


def seed_test_misc_data() -> dict[str, int]:
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)

    session = SessionLocal()
    try:
        expense_svc = MiscExpenseService(session)
        income_svc = MiscIncomeService(session)

        expense_entries = 0
        for entry_date, head, particular, amount in TEST_EXPENSE_ENTRIES:
            expense_id = _expense_id_for_head(expense_svc, head, entry_date)
            expense_svc.add_entry(expense_id, particular, amount, entry_date=entry_date)
            expense_entries += 1

        income_entries = 0
        for entry_date, head, particular, amount in TEST_INCOME_ENTRIES:
            income_id = _income_id_for_head(income_svc, head, entry_date)
            income_svc.add_entry(income_id, particular, amount, entry_date=entry_date)
            income_entries += 1

        session.commit()
        return {
            "expense_entries": expense_entries,
            "income_entries": income_entries,
            "expense_heads": len({h for _, h, _, _ in TEST_EXPENSE_ENTRIES}),
            "income_heads": len({h for _, h, _, _ in TEST_INCOME_ENTRIES}),
        }
    finally:
        session.close()


if __name__ == "__main__":
    result = seed_test_misc_data()
    print(
        "Test miscellaneous data added: "
        f"{result['expense_entries']} expense entries "
        f"({result['expense_heads']} heads), "
        f"{result['income_entries']} income entries "
        f"({result['income_heads']} heads)."
    )
