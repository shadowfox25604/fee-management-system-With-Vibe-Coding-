"""Canonical class labels for Fee Control (case-insensitive match to students.class_name)."""

FIXED_CLASS_KEYS: tuple[str, ...] = (
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


def class_name_matches_query(student_class: str | None, query: str | None) -> bool:
    """True when student class exactly matches query (not substring). Case-insensitive."""
    q = normalize_class_name(query)
    if not q:
        return True
    student_key = canonical_class_for_student_class(student_class)
    query_key = canonical_class_for_student_class(query)
    if student_key is not None and query_key is not None:
        return student_key == query_key
    return normalize_class_name(student_class) == q


def class_section_matches_query(
    student_class: str | None,
    student_section: str | None,
    query: str | None,
) -> bool:
    """Match class-section queries like '10-B', '1', or '10' (section optional after hyphen)."""
    raw = (query or "").strip()
    if not raw:
        return True
    q = raw.lower()
    if "-" in q:
        class_part, section_part = q.split("-", 1)
        class_part = class_part.strip()
        section_part = section_part.strip()
        if not class_name_matches_query(student_class, class_part):
            return False
        if section_part:
            return normalize_class_name(student_section) == section_part
        return True
    return class_name_matches_query(student_class, q)


def next_class_key(class_name: str | None) -> str | None:
    """Next class in the fixed progression (LKG→UKG→1→…→10). None at class 10 or unknown."""
    key = canonical_class_for_student_class(class_name)
    if key is None:
        return None
    idx = FIXED_CLASS_KEYS.index(key)
    if idx >= len(FIXED_CLASS_KEYS) - 1:
        return None
    return FIXED_CLASS_KEYS[idx + 1]


FIXED_VILLAGE_KEYS: tuple[str, ...] = (
    "Nagaram",
    "Kamalapur",
    "Dharmapuri",
    "Thimmapur",
    "Thummenala",
    "Rayapatnam",
    "Rajaram",
    "Damannapet",
    "Jaina",
    "Edapelly",
    "Ramaiahpally",
    "Burugupally",
    "LN Colony",
    "Thenuguwada",
    "ARR Colony",
)


def normalize_village_name(value: str | None) -> str:
    return (value or "").strip().lower()


def canonical_village_for_student_village(village: str | None) -> str | None:
    """Return fixed-list key if student village matches any entry (case-insensitive)."""
    n = normalize_village_name(village)
    if not n:
        return None
    for key in FIXED_VILLAGE_KEYS:
        if normalize_village_name(key) == n:
            return key
    return None
