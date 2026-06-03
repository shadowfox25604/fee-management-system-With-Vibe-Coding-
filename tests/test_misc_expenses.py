from datetime import date

import pytest

from backend.services.misc_expense_service import MiscExpenseService


def test_add_expense_with_entries(db_session):
    svc = MiscExpenseService(db_session)
    expense = svc.add_new_expense("Stationary", date(2026, 5, 6), notes="May purchases")
    svc.add_entry(expense.id, "Pamphlets", 450.0)
    svc.add_entry(expense.id, "Admission forms", 6000.0)

    history = svc.list_entry_history()
    assert len(history) == 2
    assert history[0]["head"] == "Stationary"
    assert history[0]["particular"] == "Admission forms"
    assert history[0]["amount"] == pytest.approx(6000.0, abs=0.01)
    assert svc.total_spent() == pytest.approx(6450.0, abs=0.01)


def test_multiple_expenses(db_session):
    svc = MiscExpenseService(db_session)
    rent_expense = svc.add_new_expense("Rent", date(2026, 1, 6))
    donation_expense = svc.add_new_expense("Donation", date(2026, 7, 23))
    svc.add_entry(rent_expense.id, "June", 30000.0)
    svc.add_entry(donation_expense.id, "Sai ABVP", 500.0)
    svc.add_entry(donation_expense.id, "Velupula Pramod K", 1000.0)

    assert len(svc.list_expenses()) == 2
    assert len(svc.list_entry_history()) == 3


def test_update_and_delete_entry(db_session):
    svc = MiscExpenseService(db_session)
    expense = svc.add_new_expense("Infra", date(2026, 3, 10))
    entry = svc.add_entry(expense.id, "2 Ceiling Fans", 4500.0)

    svc.update_entry(entry.id, particular="2 Ceiling Fans (updated)", amount=4800.0)
    rows = svc.list_entry_history()
    assert rows[0]["particular"] == "2 Ceiling Fans (updated)"
    assert rows[0]["amount"] == pytest.approx(4800.0, abs=0.01)

    svc.delete_entry(entry.id)
    assert svc.list_entry_history() == []
    assert svc.total_spent() == pytest.approx(0.0, abs=0.01)


def test_expense_head_required(db_session):
    svc = MiscExpenseService(db_session)
    with pytest.raises(ValueError, match="head is required"):
        svc.add_new_expense("  ", date(2026, 2, 1))


def test_export_rows_sparse_format(db_session):
    svc = MiscExpenseService(db_session)
    expense = svc.add_new_expense("Donation", date(2026, 7, 23))
    svc.add_entry(expense.id, "Donor A", 500.0)
    svc.add_entry(expense.id, "Donor B", 750.0)

    rows = svc.repo.list_export_rows()
    assert len(rows) == 2
    assert rows[0]["show_date"] is True
    assert rows[0]["show_head"] is True
    assert rows[1]["show_date"] is False
    assert rows[1]["show_head"] is False


def test_duplicate_expense_rejected(db_session):
    svc = MiscExpenseService(db_session)
    svc.add_new_expense("Rent", date(2026, 6, 2))
    with pytest.raises(ValueError, match="already exists"):
        svc.add_new_expense("rent", date(2026, 7, 15))


def test_duplicate_head_rejected_even_with_different_particulars(db_session):
    svc = MiscExpenseService(db_session)
    svc.add_new_expense("Rent", date(2026, 6, 2), notes="June")
    with pytest.raises(ValueError, match="already exists"):
        svc.add_new_expense("Rent", date(2026, 6, 2), notes="July")


def test_export_excel_creates_file(db_session, tmp_path):
    svc = MiscExpenseService(db_session)
    expense = svc.add_new_expense("Water Bill", date(2026, 4, 1))
    svc.add_entry(expense.id, "April bill", 18000.0)

    out = tmp_path / "misc.xlsx"
    svc.export_excel(out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_export_group_totals():
    from backend.reports.misc_expense_excel_export import MiscExpenseExcelExporter

    rows = [
        {"amount": 500.0, "show_head": True},
        {"amount": 750.0, "show_head": False},
        {"amount": 30000.0, "show_head": True},
        {"amount": 450.0, "show_head": True},
    ]
    totals = MiscExpenseExcelExporter._group_totals(rows)
    assert totals[0] == pytest.approx(1250.0, abs=0.01)
    assert totals[2] == pytest.approx(30000.0, abs=0.01)
    assert totals[3] == pytest.approx(450.0, abs=0.01)


def test_export_rows_filter_by_month(db_session):
    svc = MiscExpenseService(db_session)
    rent = svc.add_new_expense("Rent", date(2026, 6, 2))
    water = svc.add_new_expense("Water Bill", date(2026, 4, 1))
    svc.add_entry(rent.id, "June", 30000.0, entry_date=date(2026, 6, 2))
    svc.add_entry(water.id, "April bill", 18000.0, entry_date=date(2026, 4, 1))

    june_rows = svc.repo.list_export_rows(month=(2026, 6))
    assert len(june_rows) == 1
    assert june_rows[0]["head"] == "Rent"


def test_export_rows_filter_by_date_range(db_session):
    svc = MiscExpenseService(db_session)
    expense = svc.add_new_expense("Stationary", date(2026, 5, 6))
    svc.add_entry(expense.id, "Forms", 1000.0, entry_date=date(2026, 5, 10))
    svc.add_entry(expense.id, "Books", 500.0, entry_date=date(2026, 5, 20))
    svc.add_entry(expense.id, "Old stock", 200.0, entry_date=date(2026, 4, 30))

    rows = svc.repo.list_export_rows(
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 31),
    )
    assert len(rows) == 2
    assert sum(row["amount"] for row in rows) == pytest.approx(1500.0, abs=0.01)


def test_export_rows_filter_by_expense(db_session):
    svc = MiscExpenseService(db_session)
    rent = svc.add_new_expense("Rent", date(2026, 6, 2))
    donation = svc.add_new_expense("Donation", date(2026, 7, 23))
    svc.add_entry(rent.id, "June", 30000.0)
    svc.add_entry(donation.id, "Donor", 500.0)

    rows = svc.repo.list_export_rows(expense_id=donation.id)
    assert len(rows) == 1
    assert rows[0]["head"] == "Donation"


def test_export_rows_combined_month_and_expense(db_session):
    svc = MiscExpenseService(db_session)
    rent = svc.add_new_expense("Rent", date(2026, 6, 2))
    donation = svc.add_new_expense("Donation", date(2026, 6, 15))
    svc.add_entry(rent.id, "June rent", 30000.0, entry_date=date(2026, 6, 2))
    svc.add_entry(donation.id, "June gift", 500.0, entry_date=date(2026, 6, 20))
    svc.add_entry(donation.id, "July gift", 750.0, entry_date=date(2026, 7, 5))

    rows = svc.repo.list_export_rows(month=(2026, 6), expense_ids=[donation.id])
    assert len(rows) == 1
    assert rows[0]["particular"] == "June gift"


def test_export_rows_filter_by_multiple_expenses(db_session):
    svc = MiscExpenseService(db_session)
    rent = svc.add_new_expense("Rent", date(2026, 6, 2))
    donation = svc.add_new_expense("Donation", date(2026, 7, 23))
    infra = svc.add_new_expense("Infra", date(2026, 3, 10))
    svc.add_entry(rent.id, "June", 30000.0)
    svc.add_entry(donation.id, "Donor", 500.0)
    svc.add_entry(infra.id, "Fans", 4500.0)

    rows = svc.repo.list_export_rows(expense_ids=[rent.id, infra.id])
    assert len(rows) == 2
    heads = {row["head"] for row in rows}
    assert heads == {"Rent", "Infra"}


def test_entry_date_bounds(db_session):
    svc = MiscExpenseService(db_session)
    assert svc.entry_date_bounds() == (None, None)
    expense = svc.add_new_expense("Rent", date(2026, 4, 1))
    svc.add_entry(expense.id, "April", 1000.0, entry_date=date(2026, 4, 15))
    svc.add_entry(expense.id, "May", 2000.0, entry_date=date(2026, 5, 10))
    assert svc.entry_date_bounds() == (date(2026, 4, 15), date(2026, 5, 10))
