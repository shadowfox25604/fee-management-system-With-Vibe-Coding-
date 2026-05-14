"""Human-friendly unique payment reference codes (alphanumeric, fixed length)."""

from __future__ import annotations

import secrets
import string
from collections.abc import Callable

REF_LEN = 12
REF_ALPHABET = string.ascii_uppercase + string.digits


def random_payment_reference() -> str:
    return "".join(secrets.choice(REF_ALPHABET) for _ in range(REF_LEN))


def is_compact_payment_reference(s: str | None) -> bool:
    if not s:
        return False
    t = s.strip()
    if len(t) != REF_LEN:
        return False
    return all(c in REF_ALPHABET for c in t)


def allocate_unique_payment_reference(exists: Callable[[str], bool]) -> str:
    """Return a new reference that does not collide per ``exists`` (check DB or in-memory set)."""
    for _ in range(500):
        cand = random_payment_reference()
        if not exists(cand):
            return cand
    raise RuntimeError("Could not allocate a unique payment reference; try again.")
