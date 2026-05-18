"""School name and logo paths for UI branding (frontend only)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

# Project root: frontend/ui -> frontend -> project
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FRONTEND_ASSETS = Path(__file__).resolve().parents[1] / "assets"

SCHOOL_NAME = "ACE HIGH SCHOOL"
SCHOOL_MOTTO = "AIMING FOR EXCELLENCE"
SCHOOL_TAGLINE = "Fee Management System"

# Optional override: create data/school_name.txt with a single line to change the name
_NAME_OVERRIDE = _PROJECT_ROOT / "data" / "school_name.txt"

LOGO_CANDIDATES: tuple[Path, ...] = (
    _PROJECT_ROOT / "School Logo.jpeg",
    _PROJECT_ROOT / "School Logo.jpg",
    _FRONTEND_ASSETS / "school_logo.png",
    _FRONTEND_ASSETS / "ace_school_logo.jpeg",
)


def school_name() -> str:
    if _NAME_OVERRIDE.is_file():
        line = _NAME_OVERRIDE.read_text(encoding="utf-8").strip()
        if line:
            return line
    return SCHOOL_NAME


def school_motto() -> str:
    return SCHOOL_MOTTO


def school_window_title() -> str:
    return f"{school_name()} — {SCHOOL_TAGLINE}"


def breadcrumb_trail(*parts: str) -> list[str]:
    """Breadcrumb segments starting with the school name."""
    return [school_name(), *parts]


def resolve_logo_path() -> Path | None:
    for path in LOGO_CANDIDATES:
        if path.is_file():
            return path
    return None


def load_logo_pixmap(size: int = 48) -> QPixmap | None:
    path = resolve_logo_path()
    if path is None:
        return None
    pix = QPixmap(str(path))
    if pix.isNull():
        return None
    return pix.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
