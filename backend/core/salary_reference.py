"""Human-friendly unique salary payout reference codes (alphanumeric, fixed length)."""

from __future__ import annotations

import secrets
import string
from collections.abc import Callable

SALARY_REF_LEN = 12
SALARY_REF_ALPHABET = string.ascii_uppercase + string.digits


def random_salary_reference() -> str:
    return "".join(secrets.choice(SALARY_REF_ALPHABET) for _ in range(SALARY_REF_LEN))


def allocate_unique_salary_reference(exists: Callable[[str], bool]) -> str:
    for _ in range(500):
        cand = random_salary_reference()
        if not exists(cand):
            return cand
    raise RuntimeError("Could not allocate a unique salary reference; try again.")
