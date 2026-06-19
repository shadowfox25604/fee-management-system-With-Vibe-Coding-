from datetime import date

import pytest

from backend.core.app_roles import ROLE_ACCOUNTANT, ROLE_ADMIN, can_modify_ledger_entries, format_operator_display
from backend.services.misc_expense_service import MiscExpenseService
from backend.services.misc_income_service import MiscIncomeService


def test_can_modify_ledger_entries():
    assert can_modify_ledger_entries(ROLE_ADMIN) is True
    assert can_modify_ledger_entries(ROLE_ACCOUNTANT) is False


def test_format_operator_display():
    assert format_operator_display(ROLE_ADMIN) == ROLE_ADMIN
    assert format_operator_display(ROLE_ACCOUNTANT) == ROLE_ACCOUNTANT
    assert format_operator_display("desktop_user") == ""
    assert format_operator_display("") == ""


def test_misc_entry_stores_operator(db_session):
    svc = MiscExpenseService(db_session)
    expense = svc.add_new_expense("Rent", date(2026, 6, 1))
    entry = svc.add_entry(
        expense.id,
        "June rent",
        5000.0,
        operator_name=ROLE_ACCOUNTANT,
    )
    rows = svc.list_entry_history()
    assert rows[0]["operator"] == ROLE_ACCOUNTANT
    assert entry.operator_name == ROLE_ACCOUNTANT

    income_svc = MiscIncomeService(db_session)
    income = income_svc.add_new_income("Books", date(2026, 6, 1))
    income_svc.add_entry(
        income.id,
        "Sales",
        1200.0,
        operator_name=ROLE_ADMIN,
    )
    income_rows = income_svc.list_entry_history()
    assert income_rows[0]["operator"] == ROLE_ADMIN


def test_accountant_cannot_update_or_delete_misc_expense_entry(db_session):
    svc = MiscExpenseService(db_session)
    expense = svc.add_new_expense("Rent", date(2026, 6, 1))
    entry = svc.add_entry(expense.id, "June rent", 5000.0)

    with pytest.raises(ValueError, match="Only an administrator"):
        svc.update_entry(
            entry.id,
            particular="Changed",
            amount=6000.0,
            actor_role=ROLE_ACCOUNTANT,
        )
    with pytest.raises(ValueError, match="Only an administrator"):
        svc.delete_entry(entry.id, actor_role=ROLE_ACCOUNTANT)

    rows = svc.list_entry_history()
    assert rows[0]["particular"] == "June rent"
    assert rows[0]["is_reverted"] is False


def test_accountant_cannot_update_or_delete_income_entry(db_session):
    svc = MiscIncomeService(db_session)
    income = svc.add_new_income("Books", date(2026, 6, 1))
    entry = svc.add_entry(income.id, "Sales", 1200.0)

    with pytest.raises(ValueError, match="Only an administrator"):
        svc.update_entry(
            entry.id,
            particular="Changed",
            amount=1500.0,
            actor_role=ROLE_ACCOUNTANT,
        )
    with pytest.raises(ValueError, match="Only an administrator"):
        svc.delete_entry(entry.id, actor_role=ROLE_ACCOUNTANT)

    rows = svc.list_entry_history()
    assert rows[0]["particular"] == "Sales"
    assert rows[0]["is_reverted"] is False


def test_accountant_can_still_add_misc_expense_and_entry(db_session):
    svc = MiscExpenseService(db_session)
    expense = svc.add_new_expense("Stationary", date(2026, 6, 10))
    svc.add_entry(expense.id, "Forms", 300.0)
    assert len(svc.list_entry_history()) == 1
    assert svc.total_spent() == pytest.approx(300.0, abs=0.01)


def test_accountant_can_still_add_income_and_entry(db_session):
    svc = MiscIncomeService(db_session)
    income = svc.add_new_income("Uniform", date(2026, 6, 10))
    svc.add_entry(income.id, "Batch A", 800.0)
    assert len(svc.list_entry_history()) == 1
    assert svc.total_received() == pytest.approx(800.0, abs=0.01)


def test_admin_can_update_and_delete_misc_entry(db_session):
    svc = MiscExpenseService(db_session)
    expense = svc.add_new_expense("Infra", date(2026, 3, 10))
    entry = svc.add_entry(expense.id, "Chair", 1200.0)

    svc.update_entry(
        entry.id,
        particular="Chair (updated)",
        amount=1300.0,
        actor_role=ROLE_ADMIN,
    )
    svc.delete_entry(entry.id, actor_role=ROLE_ADMIN)

    rows = svc.list_entry_history()
    assert rows[0]["status"] == "Expense reverted"
    assert svc.total_spent() == pytest.approx(0.0, abs=0.01)
