"""Build a Windows .ico from the school logo for PyInstaller and the taskbar."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
LOGO_CANDIDATES = (
    ROOT / "School Logo.jpeg",
    ROOT / "frontend" / "assets" / "school_logo.png",
    ROOT / "frontend" / "assets" / "ace_school_logo.jpeg",
)
OUT_DIR = ROOT / "build"
OUT_ICO = OUT_DIR / "ace_school_management.ico"


def _find_logo() -> Path:
    for path in LOGO_CANDIDATES:
        if path.is_file():
            return path
    raise FileNotFoundError("No school logo found for icon generation.")


def main() -> int:
    app = QApplication(sys.argv)
    logo_path = _find_logo()
    pixmap = QPixmap(str(logo_path))
    if pixmap.isNull():
        raise RuntimeError(f"Could not load logo: {logo_path}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sizes = (16, 24, 32, 48, 64, 128, 256)
    images: list[QImage] = []
    for size in sizes:
        scaled = pixmap.scaled(
            QSize(size, size),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        images.append(scaled.toImage())

    if not images[-1].save(str(OUT_ICO), "ICO"):
        raise RuntimeError(f"Failed to write icon: {OUT_ICO}")

    print(f"Wrote {OUT_ICO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
