from backend.core.fee_due_display import pending_fees


def test_pending_fees_combines_school_and_van():
    due = {"school_pending": 5000.0, "van_pending": 1000.0}
    assert pending_fees(due) == 6000.0


def test_pending_fees_uses_combined_field_when_present():
    due = {"pending_fees": 7500.0, "school_pending": 5000.0, "van_pending": 1000.0}
    assert pending_fees(due) == 7500.0
