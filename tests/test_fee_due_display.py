from backend.core.fee_due_display import (
    combine_rollover_pending_fees,
    pending_fees,
    rollover_pending_from_due,
)


def test_pending_fees_combines_school_and_van():
    due = {"school_pending": 5000.0, "van_pending": 1000.0}
    assert pending_fees(due) == 6000.0


def test_pending_fees_uses_combined_field_when_present():
    due = {"pending_fees": 7500.0, "school_pending": 5000.0, "van_pending": 1000.0}
    assert pending_fees(due) == 7500.0


def test_combine_rollover_pending_fees():
    assert combine_rollover_pending_fees(2500.0, 6000.0, 1000.0) == 9500.0
    assert combine_rollover_pending_fees(0.0, 0.0, 0.0) == 0.0


def test_rollover_pending_from_due():
    due = {
        "pending_fees": 2500.0,
        "school_pending": 2000.0,
        "van_pending": 500.0,
        "fee_due": 6000.0,
        "van_due": 1000.0,
    }
    assert rollover_pending_from_due(due) == 9500.0
