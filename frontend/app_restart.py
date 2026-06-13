from __future__ import annotations

import sys

from PySide6.QtCore import QProcess


def relaunch_application() -> bool:
    """Start a new app process and return whether launch was requested successfully."""
    executable = sys.executable
    if getattr(sys, "frozen", False):
        return QProcess.startDetached(executable, sys.argv[1:])
    return QProcess.startDetached(executable, ["-m", "frontend.main"])
