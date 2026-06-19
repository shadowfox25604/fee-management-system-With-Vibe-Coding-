"""Ensure only one application instance runs at a time."""

from __future__ import annotations

import sys

from PySide6.QtCore import QLockFile, Qt
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QWidget

from backend.core.config import DATA_DIR

_SERVER_NAME = "ACE.SchoolManagement.SingleInstance"
_LOCK_PATH = DATA_DIR / ".single_instance.lock"

_lock: QLockFile | None = None
_server: QLocalServer | None = None


def _raise_window(widget: QWidget) -> None:
    if widget.windowState() & Qt.WindowState.WindowMinimized:
        widget.setWindowState(widget.windowState() & ~Qt.WindowState.WindowMinimized)
    if widget.windowState() & Qt.WindowState.WindowMaximized:
        widget.showMaximized()
    else:
        widget.showNormal()
    widget.raise_()
    widget.activateWindow()
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.SetForegroundWindow(int(widget.winId()))
        except Exception:
            pass


def _activate_running_instance() -> None:
    socket = QLocalSocket()
    socket.connectToServer(_SERVER_NAME)
    if not socket.waitForConnected(500):
        return
    socket.write(b"activate")
    socket.waitForBytesWritten(1000)
    socket.disconnectFromServer()


def _on_activate_requested(app: QApplication) -> None:
    target = app.activeWindow()
    if target is None:
        visible = [widget for widget in app.topLevelWidgets() if widget.isVisible()]
        target = visible[-1] if visible else None
    if target is not None:
        _raise_window(target)


def acquire_single_instance(app: QApplication) -> bool:
    """Return True when this process should continue as the sole instance."""
    global _lock, _server

    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(_LOCK_PATH))
    lock.setStaleLockTime(0)

    if not lock.tryLock(100):
        _activate_running_instance()
        return False

    QLocalServer.removeServer(_SERVER_NAME)
    server = QLocalServer(app)
    if not server.listen(_SERVER_NAME):
        lock.unlock()
        return False

    def handle_connection() -> None:
        connection = server.nextPendingConnection()
        if connection is None:
            return

        def read_activate() -> None:
            connection.waitForReadyRead(300)
            connection.readAll()
            _on_activate_requested(app)

        connection.readyRead.connect(read_activate)

    server.newConnection.connect(handle_connection)
    _lock = lock
    _server = server
    return True


def release_single_instance_lock() -> None:
    """Release the instance lock before a controlled restart."""
    global _lock, _server
    if _server is not None:
        _server.close()
        _server = None
    if _lock is not None:
        _lock.unlock()
        _lock = None
    QLocalServer.removeServer(_SERVER_NAME)
