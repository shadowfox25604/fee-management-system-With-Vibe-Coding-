"""Load sample miscellaneous expense ledger rows into the database."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import delete

from backend.core.database import SessionLocal, engine
from backend.core.schema_migrations import apply_sqlite_column_migrations, apply_sqlite_data_migrations
from backend.models import MiscExpense, MiscExpenseEntry
from backend.services.misc_expense_service import MiscExpenseService

# Rows from the school's sample Excel ledger: (date, head, particular, amount).
# Empty head/particular cells are filled while loading (sparse-sheet style).
SAMPLE_LEDGER_ROWS: list[tuple[str, str | None, str | None, float | None]] = [
    ("06-01-2024", "Rent", "June", 30000),
    ("25/5/2024", "Stationary", "Pamphlets", 6000),
    ("07-01-2024", "Rent", "July", 30000),
    ("07-03-2024", "Stationary", "Admission forms", 1150),
    ("07-06-2024", "Donation", "Sai ABVP", 3000),
    ("07-11-2024", "Stationary", "Flex", 450),
    ("20/7/2024", "Water Bill", None, 18000),
    ("23/7/2024", "Donation", "Velupula Pramod K", 2000),
    ("24/7/2024", "Donation", "Varaprasad", 1500),
    ("29/7/2024", None, "Goli Sathann", 730),
    ("30/7/2024", None, None, 970),
    ("31/7/2024", None, None, 1560),
    ("08-01-2024", "Rent", "August", 30000),
    ("08-06-2024", "Infra", "Nokia Mobile", 1300),
    ("08-06-2024", "Miscellaneous", "Recharge", 250),
    ("08-06-2024", "Infra", "2 Ceiling Fans", 2800),
    ("08-06-2024", "Infra", "2 Wall mount fans", 3500),
    ("08-06-2024", "Event", "Ganesh idol", 5000),
    ("08-06-2024", "Stationary", "News Paper", 440),
    ("14/8/2024", "Infra", "Stage frame", 7000),
    ("14/8/2024", "Infra", "Speaker wire", 840),
    ("24/8/2024", None, "OK Store", 690),
    ("08-06-2024", "Infra", "Electrician Charges", 7000),
    ("08-06-2024", "Event", "Ganesh idol transpo", 1000),
    ("08-10-2024", "Stationary", "Halltickets", 2100),
    ("09-03-2024", "Donations", "AISF Akram", 3000),
    ("10-01-2024", "Rent", "October", 30000),
    ("11-01-2024", "Rent", "November", 30000),
    ("12-01-2024", "Rent", "December", 30000),
    ("12-01-2024", "Newspaper", "Sakshi", 1380),
]


def _parse_ledger_date(value: str) -> date:
    text = (value or "").strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value!r}")


def _normalize_head(value: str) -> str:
    text = (value or "").strip()
    if text.lower() == "donations":
        return "Donation"
    return text


def seed_misc_expenses(*, replace: bool = True) -> dict[str, int]:
    apply_sqlite_column_migrations(engine)
    apply_sqlite_data_migrations(engine)

    session = SessionLocal()
    try:
        if replace:
            session.execute(delete(MiscExpenseEntry))
            session.execute(delete(MiscExpense))
            session.commit()

        svc = MiscExpenseService(session)
        expense_ids: dict[str, int] = {}
        last_head = ""
        created_expenses = 0
        created_entries = 0

        for date_text, head_raw, particular_raw, amount_raw in SAMPLE_LEDGER_ROWS:
            if head_raw and str(head_raw).strip():
                last_head = _normalize_head(str(head_raw))
            head = last_head
            amount = float(amount_raw or 0.0)
            if not head or amount <= 0:
                continue

            particular = (particular_raw or "").strip() or head
            entry_date = _parse_ledger_date(date_text)

            expense_id = expense_ids.get(head.lower())
            if expense_id is None:
                expense = svc.add_new_expense(head, entry_date)
                expense_ids[head.lower()] = int(expense.id)
                created_expenses += 1
                expense_id = int(expense.id)

            svc.add_entry(
                expense_id,
                particular,
                amount,
                entry_date=entry_date,
            )
            created_entries += 1

        session.commit()
        return {
            "expenses_created": created_expenses,
            "entries_created": created_entries,
        }
    finally:
        session.close()


if __name__ == "__main__":
    result = seed_misc_expenses(replace=True)
    print(
        "Miscellaneous sample data loaded: "
        f"{result['expenses_created']} expenses, {result['entries_created']} entries."
    )
