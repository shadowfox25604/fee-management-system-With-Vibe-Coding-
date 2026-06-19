from datetime import date

import pytest

from backend.core.app_roles import ROLE_ADMIN
from backend.services.misc_income_service import MiscIncomeService


def test_add_income_with_entries(db_session):
    svc = MiscIncomeService(db_session)
    income = svc.add_new_income("Books", date(2026, 5, 6), notes="May sales")
    svc.add_entry(income.id, "Grade 1 textbooks", 4500.0)
    svc.add_entry(income.id, "Library set", 6000.0)

    history = svc.list_entry_history()
    assert len(history) == 2
    assert history[0]["head"] == "Books"
    assert history[0]["particular"] == "Library set"
    assert history[0]["amount"] == pytest.approx(6000.0, abs=0.01)
    assert svc.total_received() == pytest.approx(10500.0, abs=0.01)


def test_entry_history_newest_entry_first(db_session):
    svc = MiscIncomeService(db_session)
    old_income = svc.add_new_income("Uniform", date(2024, 1, 1))
    new_income = svc.add_new_income("Stationary", date(2026, 6, 1))
    svc.add_entry(new_income.id, "June batch", 500.0)
    svc.add_entry(old_income.id, "Backdated uniform sale", 1000.0)

    history = svc.list_entry_history()
    assert len(history) == 2
    assert history[0]["particular"] == "Backdated uniform sale"
    assert history[1]["particular"] == "June batch"


def test_multiple_income_sources(db_session):
    svc = MiscIncomeService(db_session)
    books = svc.add_new_income("Books", date(2026, 1, 6))
    donations = svc.add_new_income("Donations", date(2026, 7, 23))
    svc.add_entry(books.id, "Textbooks", 30000.0)
    svc.add_entry(donations.id, "Alumni gift", 500.0)
    svc.add_entry(donations.id, "Community fund", 1000.0)

    assert len(svc.list_incomes()) == 2
    assert len(svc.list_entry_history()) == 3


def test_update_and_delete_entry(db_session):
    svc = MiscIncomeService(db_session)
    income = svc.add_new_income("Uniform", date(2026, 3, 10))
    entry = svc.add_entry(income.id, "Summer batch", 4500.0)

    svc.update_entry(
        entry.id,
        particular="Summer batch (updated)",
        amount=4800.0,
        actor_role=ROLE_ADMIN,
    )
    rows = svc.list_entry_history()
    assert rows[0]["particular"] == "Summer batch (updated)"
    assert rows[0]["amount"] == pytest.approx(4800.0, abs=0.01)

    svc.delete_entry(entry.id, actor_role=ROLE_ADMIN)
    rows = svc.list_entry_history()
    assert len(rows) == 1
    assert rows[0]["particular"] == "Summer batch (updated)"
    assert rows[0]["status"] == "Income reverted"
    assert rows[0]["is_reverted"] is True
    assert svc.total_received() == pytest.approx(0.0, abs=0.01)


def test_income_head_required(db_session):
    svc = MiscIncomeService(db_session)
    with pytest.raises(ValueError, match="head is required"):
        svc.add_new_income("  ", date(2026, 2, 1))


def test_dashboard_income_pie_for_month(db_session):
    svc = MiscIncomeService(db_session)
    books = svc.add_new_income("Books", date(2026, 6, 1))
    uniform = svc.add_new_income("Uniform", date(2026, 6, 1))
    svc.add_entry(books.id, "Sales", 1000.0, entry_date=date(2026, 6, 5))
    svc.add_entry(uniform.id, "Sales", 2500.0, entry_date=date(2026, 6, 10))

    pie = svc.dashboard_income_pie_for_month(2026, 6)
    assert pie["total"] == pytest.approx(3500.0, abs=0.01)
    labels = {s["label"] for s in pie["slices"]}
    assert labels == {"Books", "Uniform"}
