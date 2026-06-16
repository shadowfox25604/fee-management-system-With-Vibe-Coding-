"""Master key file used for offline password recovery."""

from __future__ import annotations

import secrets
from pathlib import Path

from backend.core.config import DATA_DIR

DEFAULT_MASTER_KEY = "vN7@kQ2$mP9!xL4#rW8&zH"
MASTER_KEY_PATH = DATA_DIR / "master_key.txt"


def ensure_master_key_file() -> Path:
    """Create the master key file with the default value if it does not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not MASTER_KEY_PATH.is_file():
        MASTER_KEY_PATH.write_text(f"{DEFAULT_MASTER_KEY}\n", encoding="utf-8")
    return MASTER_KEY_PATH


def read_master_key() -> str:
    ensure_master_key_file()
    return MASTER_KEY_PATH.read_text(encoding="utf-8").strip()


def verify_master_key(candidate: str) -> bool:
    expected = read_master_key()
    if not expected:
        return False
    return secrets.compare_digest(expected, (candidate or "").strip())
