"""School name and logo paths for UI branding (frontend only)."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap

from backend.core.config import BASE_DIR, DATA_DIR

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
_NAME_OVERRIDE = DATA_DIR / "school_name.txt"

APP_ICON_NAME = "ace_school_management.ico"

LOGO_CANDIDATES: tuple[Path, ...] = (
    _FRONTEND_ASSETS / "school_logo.png",
    BASE_DIR / "School Logo.jpeg",
    BASE_DIR / "School Logo.jpg",
    _RESOURCE_ROOT / "School Logo.jpeg",
    _RESOURCE_ROOT / "School Logo.jpg",
    _FRONTEND_ASSETS / "ace_school_logo.jpeg",
)

APP_ICON_CANDIDATES: tuple[Path, ...] = (
    _FRONTEND_ASSETS / APP_ICON_NAME,
    BASE_DIR / "build" / APP_ICON_NAME,
    BASE_DIR / "frontend" / "assets" / APP_ICON_NAME,
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


def resolve_app_icon_path() -> Path | None:
    """Windows taskbar and window chrome prefer a multi-size .ico over a raw logo image."""
    for path in APP_ICON_CANDIDATES:
        if path.is_file():
            return path
    return None


def app_window_icon() -> QIcon | None:
    icon_path = resolve_app_icon_path()
    if icon_path is not None:
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            return icon

    logo_path = resolve_logo_path()
    if logo_path is None:
        return None
    pixmap = QPixmap(str(logo_path))
    if pixmap.isNull():
        return None

    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        scaled = pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        icon.addPixmap(scaled)
    return icon


_LOGIN_LOGO_SOURCE: QPixmap | None = None


def _strip_checkerboard_background(pix: QPixmap) -> QPixmap:
    """Turn baked-in gray/white checkerboard pixels into real transparency."""
    image = pix.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            red, green, blue = color.red(), color.green(), color.blue()
            if (
                red >= 175
                and green >= 175
                and blue >= 175
                and max(red, green, blue) - min(red, green, blue) < 12
            ):
                image.setPixelColor(x, y, QColor(0, 0, 0, 0))
    return QPixmap.fromImage(image)


def _login_logo_source() -> QPixmap | None:
    global _LOGIN_LOGO_SOURCE
    if _LOGIN_LOGO_SOURCE is not None and not _LOGIN_LOGO_SOURCE.isNull():
        return _LOGIN_LOGO_SOURCE
    path = resolve_logo_path()
    if path is None:
        return None
    pix = QPixmap(str(path))
    if pix.isNull():
        return None
    _LOGIN_LOGO_SOURCE = _strip_checkerboard_background(pix)
    return _LOGIN_LOGO_SOURCE


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


def load_login_logo_pixmap(size: int, *, device_pixel_ratio: float = 1.0) -> QPixmap | None:
    """Login-page logo: full circular crest, centered, with checkerboard removed."""
    source = _login_logo_source()
    if source is None:
        return None
    dpr = max(1.0, float(device_pixel_ratio or 1.0))
    physical = max(1, int(round(size * dpr)))
    scaled = source.scaled(
        physical,
        physical,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    canvas = QPixmap(physical, physical)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    x = (physical - scaled.width()) // 2
    y = (physical - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)
    painter.end()
    canvas.setDevicePixelRatio(dpr)
    return canvas
