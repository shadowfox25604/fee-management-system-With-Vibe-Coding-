"""Canonical class labels for Fee Control (case-insensitive match to students.class_name)."""

FIXED_CLASS_KEYS: tuple[str, ...] = (
    "Nursery",
    "LKG",
    "UKG",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
    "12",
)

# Standard division / section letters for data entry (Add Student, etc.)
FIXED_SECTION_KEYS: tuple[str, ...] = ("A", "B", "C", "D", "E", "F", "G", "H")


def normalize_class_name(value: str | None) -> str:
    return (value or "").strip().lower()


def canonical_class_for_student_class(class_name: str | None) -> str | None:
    """Return fixed-list key if student class matches any entry (case-insensitive)."""
    n = normalize_class_name(class_name)
    if not n:
        return None
    for key in FIXED_CLASS_KEYS:
        if normalize_class_name(key) == n:
            return key
    return None
