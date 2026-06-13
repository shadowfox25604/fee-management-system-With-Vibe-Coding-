"""Backup & restore page — database snapshots and recovery."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from backend.services.backup_service import PROTECTED_RECENT_BACKUP_COUNT, BackupInfo
from frontend.ui import theme
from frontend.ui.edudash_widgets import CardTitleBar, SolidMetricCard, SurfaceCard, wrap_page
from frontend.ui.school_branding import breadcrumb_trail
from frontend.ui.table_style import configure_scrollable_data_table, style_fee_action_button, table_item

_DATE_COL_MIN = 200
_SIZE_COL = 96
_STATUS_COL = 118


class _InfoBanner(QFrame):
    """Muted callout for backup policy notes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("backupInfoBanner")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)
        self._icon = QLabel("💾")
        self._icon.setFixedWidth(28)
        self._text = QLabel()
        self._text.setWordWrap(True)
        self._text.setProperty("role", "muted")
        lay.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)
        lay.addWidget(self._text, 1)
        self.refresh_theme()

    def set_text(self, text: str) -> None:
        self._text.setText(text)

    def refresh_theme(self) -> None:
        t = theme.current_tokens()
        self.setStyleSheet(
            f"QFrame#backupInfoBanner {{ background: {t.bg_app}; border: 1px solid {t.border}; "
            f"border-radius: 12px; }}"
        )


class _PathChip(QFrame):
    """Compact monospace path display."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("backupPathChip")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(4)
        self._caption = QLabel("Live database")
        self._caption.setProperty("role", "muted")
        self._path = QLabel()
        self._path.setWordWrap(True)
        self._path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self._caption)
        lay.addWidget(self._path)
        self.refresh_theme()

    def set_path(self, path: Path | str) -> None:
        self._path.setText(str(path))

    def refresh_theme(self) -> None:
        t = theme.current_tokens()
        self.setStyleSheet(
            f"QFrame#backupPathChip {{ background: {t.bg_surface}; border: 1px dashed {t.border}; "
            f"border-radius: 10px; }}"
        )
        self._path.setStyleSheet(
            f"color: {t.text_primary}; font-family: Consolas, 'Courier New', monospace; "
            f"font-size: 12px; background: transparent;"
        )


class BackupPage(QWidget):
    """Backup management UI with summary tiles, file list, and actions."""

    def __init__(
        self,
        *,
        on_create,
        on_restore_selected,
        on_restore_file,
        on_delete,
        parent=None,
    ):
        super().__init__(parent)
        self._on_create = on_create
        self._on_restore_selected = on_restore_selected
        self._on_restore_file = on_restore_file
        self._on_delete = on_delete

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        self._banner = _InfoBanner()
        self._banner.set_text(
            "Your school database is copied automatically once per day when you open the app. "
            f"The {PROTECTED_RECENT_BACKUP_COUNT} most recent backups stay protected — older copies "
            "can be removed to save disk space."
        )
        root.addWidget(self._banner)

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(14)
        self._metric_total = SolidMetricCard("Saved backups", "0", style_idx=3)
        self._metric_latest = SolidMetricCard("Last backup", "—", style_idx=1)
        self._metric_storage = SolidMetricCard("Backup storage", "0 B", style_idx=5)
        for card in (self._metric_total, self._metric_latest, self._metric_storage):
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            metrics_row.addWidget(card, 1)
        root.addLayout(metrics_row)

        self._path_chip = _PathChip()
        root.addWidget(self._path_chip)

        table_card = SurfaceCard()
        table_card.body.addWidget(CardTitleBar("Saved backups"))
        self._empty_label = QLabel("No backups yet. Create one to safeguard your data.")
        self._empty_label.setProperty("role", "muted")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setMinimumHeight(80)
        self._empty_label.hide()
        table_card.body.addWidget(self._empty_label)

        self.backup_table = QTableWidget(0, 4)
        self.backup_table.setHorizontalHeaderLabels(["Date & time", "File name", "Size", "Status"])
        self.backup_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.backup_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.backup_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        configure_scrollable_data_table(self.backup_table)
        header = self.backup_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.backup_table.setColumnWidth(0, _DATE_COL_MIN)
        self.backup_table.setColumnWidth(2, _SIZE_COL)
        self.backup_table.setColumnWidth(3, _STATUS_COL)
        self.backup_table.setMinimumHeight(220)
        self.backup_table.itemSelectionChanged.connect(self._update_delete_button_state)
        table_card.body.addWidget(self.backup_table, 1)
        root.addWidget(table_card, 1)

        actions_card = SurfaceCard()
        actions_lay = QHBoxLayout()
        actions_lay.setSpacing(10)
        self._create_backup_btn = QPushButton("Create backup now")
        style_fee_action_button(self._create_backup_btn)
        self._create_backup_btn.clicked.connect(self._on_create)
        self._restore_backup_btn = QPushButton("Restore selected")
        style_fee_action_button(self._restore_backup_btn)
        self._restore_backup_btn.clicked.connect(self._on_restore_selected)
        self._restore_backup_file_btn = QPushButton("Restore from file…")
        style_fee_action_button(self._restore_backup_file_btn)
        self._restore_backup_file_btn.clicked.connect(self._on_restore_file)
        self._delete_backup_btn = QPushButton("Delete selected")
        style_fee_action_button(self._delete_backup_btn)
        self._delete_backup_btn.setEnabled(False)
        self._delete_backup_btn.clicked.connect(self._on_delete)
        actions_lay.addWidget(self._create_backup_btn)
        actions_lay.addWidget(self._restore_backup_btn)
        actions_lay.addWidget(self._restore_backup_file_btn)
        actions_lay.addStretch(1)
        actions_lay.addWidget(self._delete_backup_btn)
        actions_card.body.addLayout(actions_lay)

        self.backup_status = QLabel("No backup action performed yet.")
        self.backup_status.setProperty("role", "muted")
        self.backup_status.setWordWrap(True)
        actions_card.body.addWidget(self.backup_status)
        root.addWidget(actions_card)

        self._wrapped = wrap_page("Backup", breadcrumb_trail("Backup"), self)

    @property
    def wrapped(self) -> QWidget:
        return self._wrapped

    def refresh_theme(self) -> None:
        self._banner.refresh_theme()
        self._path_chip.refresh_theme()
        for card in (self._metric_total, self._metric_latest, self._metric_storage):
            card.refresh_theme()
        for btn in (
            self._create_backup_btn,
            self._restore_backup_btn,
            self._restore_backup_file_btn,
            self._delete_backup_btn,
        ):
            style_fee_action_button(btn, width=btn.width() if btn.width() > 0 else None)

    @staticmethod
    def _format_storage(total_bytes: int) -> str:
        if total_bytes < 1024:
            return f"{total_bytes} B"
        if total_bytes < 1024 * 1024:
            return f"{total_bytes / 1024:.1f} KB"
        return f"{total_bytes / (1024 * 1024):.1f} MB"

    def set_status(self, message: str) -> None:
        self.backup_status.setText(message)

    def set_db_path(self, path: Path | str) -> None:
        self._path_chip.set_path(path)

    def populate(
        self,
        backups: list[BackupInfo],
        *,
        latest: BackupInfo | None,
        selected_path: Path | None = None,
    ) -> None:
        total_bytes = sum(item.size_bytes for item in backups)
        self._metric_total.update_metric(str(len(backups)))
        if latest is None:
            self._metric_latest.update_metric("—", "Create your first backup")
        else:
            self._metric_latest.update_metric(
                latest.created_at.strftime("%d %b %Y"),
                f"{latest.created_at:%I:%M %p} · {latest.size_label}",
            )
        self._metric_storage.update_metric(self._format_storage(total_bytes))

        self._empty_label.setVisible(len(backups) == 0)
        self.backup_table.setVisible(len(backups) > 0)

        self.backup_table.blockSignals(True)
        self.backup_table.setRowCount(len(backups))
        for row, info in enumerate(backups):
            date_item = table_item(info.created_at.strftime("%d %b %Y, %I:%M %p"))
            date_item.setToolTip(info.created_at.strftime("%A, %d %B %Y · %I:%M:%S %p"))
            self.backup_table.setItem(row, 0, date_item)
            self.backup_table.setItem(row, 1, table_item(info.name))
            self.backup_table.setItem(row, 2, table_item(info.size_label))
            deletable = row >= PROTECTED_RECENT_BACKUP_COUNT
            status_item = table_item("Can delete" if deletable else "Protected")
            if deletable:
                status_item.setForeground(QColor("#0f766e"))
            else:
                status_item.setForeground(QColor("#b45309"))
                status_item.setToolTip(
                    f"The {PROTECTED_RECENT_BACKUP_COUNT} most recent backups cannot be deleted."
                )
            path_item = self.backup_table.item(row, 0)
            if path_item is not None:
                path_item.setData(Qt.ItemDataRole.UserRole, str(info.path.resolve()))
                path_item.setData(Qt.ItemDataRole.UserRole + 1, deletable)

        if selected_path is not None:
            key = str(selected_path.resolve())
            for row in range(self.backup_table.rowCount()):
                item = self.backup_table.item(row, 0)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == key:
                    self.backup_table.selectRow(row)
                    break

        self.backup_table.blockSignals(False)
        if self.backup_table.columnWidth(0) < _DATE_COL_MIN:
            self.backup_table.setColumnWidth(0, _DATE_COL_MIN)
        self._update_delete_button_state()

    def selected_backup_path(self) -> Path | None:
        row = self.backup_table.currentRow()
        if row < 0:
            return None
        item = self.backup_table.item(row, 0)
        if item is None:
            return None
        raw = item.data(Qt.ItemDataRole.UserRole)
        return Path(str(raw)) if raw else None

    def _update_delete_button_state(self) -> None:
        path = self.selected_backup_path()
        if path is None:
            self._delete_backup_btn.setEnabled(False)
            self._delete_backup_btn.setToolTip("Select a backup from the list.")
            return
        row = self.backup_table.currentRow()
        deletable = False
        if row >= 0:
            item = self.backup_table.item(row, 0)
            if item is not None:
                flag = item.data(Qt.ItemDataRole.UserRole + 1)
                if flag is not None:
                    deletable = bool(flag)
        self._delete_backup_btn.setEnabled(deletable)
        if deletable:
            self._delete_backup_btn.setToolTip("Permanently delete this older backup.")
        else:
            self._delete_backup_btn.setToolTip(
                f"The {PROTECTED_RECENT_BACKUP_COUNT} most recent backups are protected "
                "and cannot be deleted."
            )
