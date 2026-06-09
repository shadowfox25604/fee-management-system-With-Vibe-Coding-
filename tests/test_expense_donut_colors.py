from frontend.ui.theme import PURPLE, YELLOW
from frontend.ui.edudash_widgets import (
    _assign_expense_slice_colors,
    expense_color_for_label,
)


def test_known_expense_labels_have_stable_colours():
    assert expense_color_for_label("Salary") == PURPLE
    assert expense_color_for_label("salary") == PURPLE
    assert expense_color_for_label("Rent") == YELLOW


def test_each_expense_slice_gets_distinct_colour():
    slices = _assign_expense_slice_colors(
        [
            {"label": "Salary", "amount": 24000.0},
            {"label": "Rent", "amount": 5000.0},
            {"label": "Stationary", "amount": 1000.0},
            {"label": "Donation", "amount": 500.0},
        ]
    )
    colours = [color for _, color, _ in slices]
    assert len(colours) == len(set(colours))
    assert slices[0][1] == PURPLE
    assert slices[1][1] == YELLOW
