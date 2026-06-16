"""School name and logo paths for UI branding (frontend only)."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from backend.core.config import BASE_DIR

# Bundled resources (PyInstaller _MEIPASS) or project root in development.
_RESOURCE_ROOT = (
    Path(getattr(sys, "_MEIPASS", BASE_DIR))
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parents[2]
)
_FRONTEND_ASSETS = _RESOURCE_ROOT / "frontend" / "assets"

SCHOOL_NAME = "ACE HIGH SCHOOL"
SCHOOL_MOTTO = "AIMING FOR EXCELLENCE"
SCHOOL_TAGLINE = "School Management System"

APP_WINDOW_WIDTH = 1360
APP_WINDOW_HEIGHT = 860

# Optional override: create data/school_name.txt with a single line to change the name
_NAME_OVERRIDE = BASE_DIR / "data" / "school_name.txt"

LOGO_CANDIDATES: tuple[Path, ...] = (
    BASE_DIR / "School Logo.jpeg",
    BASE_DIR / "School Logo.jpg",
    _RESOURCE_ROOT / "School Logo.jpeg",
    _RESOURCE_ROOT / "School Logo.jpg",
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


def school_tagline() -> str:
    return SCHOOL_TAGLINE


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


def load_logo_pixmap(size: int = 48, *, device_pixel_ratio: float = 1.0) -> QPixmap | None:
    """Load school logo scaled crisply for the given logical size and screen density."""
    path = resolve_logo_path()
    if path is None:
        return None
    pix = QPixmap(str(path))
    if pix.isNull():
        return None
    dpr = max(1.0, float(device_pixel_ratio or 1.0))
    physical = max(1, int(round(size * dpr)))
    scaled = pix.scaled(
        physical,
        physical,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    scaled.setDevicePixelRatio(dpr)
    return scaled
