from backend.core.month_label_format import format_month_label_display


def test_format_month_label_display():
    assert format_month_label_display("2026-05") == "May 2026"
    assert format_month_label_display("2026-04") == "April 2026"
    assert format_month_label_display("2026-01") == "January 2026"
    assert format_month_label_display("") == ""
    assert format_month_label_display("invalid") == "invalid"
