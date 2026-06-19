"""Build a Windows .ico from the school logo for PyInstaller and the taskbar."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QSize, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
LOGO_CANDIDATES = (
    ROOT / "frontend" / "assets" / "school_logo.png",
    ROOT / "School Logo.jpeg",
    ROOT / "School Logo.jpg",
    ROOT / "frontend" / "assets" / "ace_school_logo.jpeg",
)
ICON_OUTPUTS = (
    ROOT / "frontend" / "assets" / "ace_school_management.ico",
    ROOT / "build" / "ace_school_management.ico",
)
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _find_logo() -> Path:
    for path in LOGO_CANDIDATES:
        if path.is_file():
            return path
    raise FileNotFoundError("No school logo found for icon generation.")


def _png_bytes(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError("Failed to encode PNG frame for icon")
    return bytes(buffer.data())


def _write_multi_size_ico(path: Path, images: list[QImage]) -> None:
    if not images:
        raise ValueError("No icon frames to write")

    png_frames = [_png_bytes(image) for image in images]
    header = struct.pack("<HHH", 0, 1, len(png_frames))
    entries: list[bytes] = []
    payload_offset = 6 + (16 * len(png_frames))
    for image, png in zip(images, png_frames):
        width = 0 if image.width() >= 256 else image.width()
        height = 0 if image.height() >= 256 else image.height()
        entries.append(
            struct.pack(
                "<BBBBHHII",
                width,
                height,
                0,
                0,
                1,
                32,
                len(png),
                payload_offset,
            )
        )
        payload_offset += len(png)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(header)
        for entry in entries:
            handle.write(entry)
        for png in png_frames:
            handle.write(png)


def main() -> int:
    app = QApplication(sys.argv)
    logo_path = _find_logo()
    pixmap = QPixmap(str(logo_path))
    if pixmap.isNull():
        raise RuntimeError(f"Could not load logo: {logo_path}")

    images: list[QImage] = []
    for size in ICON_SIZES:
        scaled = pixmap.scaled(
            QSize(size, size),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        square = QImage(size, size, QImage.Format.Format_ARGB32)
        square.fill(Qt.GlobalColor.transparent)
        x = (size - scaled.width()) // 2
        y = (size - scaled.height()) // 2
        painter = QPainter(square)
        painter.drawPixmap(x, y, scaled)
        painter.end()
        images.append(square)

    for out_path in ICON_OUTPUTS:
        _write_multi_size_ico(out_path, images)
        print(f"Wrote {out_path} from {logo_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
