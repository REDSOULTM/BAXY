"""Sessions sidebar — list, search, load, delete, rename, new.

Backed by the existing K1 `SessionStore`. Slides in from the left over the
HUD when toggled.
"""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from .theme import C, button_qss, line_edit_qss, mono, text_edit_qss


class SessionsPanel(QFrame):
    new_clicked = pyqtSignal()
    selected = pyqtSignal(str)
    deleted = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(
        self,
        *,
        on_list_provider: Callable[[], list[dict]],
        on_load: Callable[[str], None],
        on_new: Callable[[], None],
        on_delete: Callable[[str], None],
        on_rename: Callable[[str, str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_list = on_list_provider
        self._on_load = on_load
        self._on_new = on_new
        self._on_delete = on_delete
        self._on_rename = on_rename
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.PANEL};
                border-right: 1px solid {C.BORDER_B};
            }}
        """)
        self.setFixedWidth(300)
        self._build()
        self.refresh()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)

        title_row = QHBoxLayout()
        title = QLabel("◈  SESSIONS")
        title.setFont(mono(10, True))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        title_row.addWidget(title)
        title_row.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet(button_qss())
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.closed.emit)
        title_row.addWidget(close_btn)
        lay.addLayout(title_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};")
        lay.addWidget(sep)

        new_btn = QPushButton("✚  NEW SESSION")
        new_btn.setFont(mono(8, True))
        new_btn.setFixedHeight(30)
        new_btn.setStyleSheet(button_qss(primary=True))
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._on_new_btn)
        lay.addWidget(new_btn)

        search = QLineEdit()
        search.setPlaceholderText("filter...")
        search.setFont(mono(8))
        search.setStyleSheet(line_edit_qss())
        search.textChanged.connect(self._filter)
        lay.addWidget(search)
        self._search = search

        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: {C.PANEL2};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 3px;
                padding: 4px;
            }}
            QListWidget::item {{
                background: transparent;
                border: none;
                padding: 4px 6px;
            }}
            QListWidget::item:selected {{
                background: {C.PRI_GHO};
                color: {C.PRI};
            }}
            QListWidget::item:hover {{
                background: {C.PANEL};
            }}
        """ + text_edit_qss())
        self._list.itemDoubleClicked.connect(self._on_item_double)
        lay.addWidget(self._list, stretch=1)

        row = QHBoxLayout()
        load_btn = QPushButton("LOAD")
        load_btn.setFont(mono(7, True))
        load_btn.setStyleSheet(button_qss(primary=True))
        load_btn.setFixedHeight(28)
        load_btn.clicked.connect(self._on_load_btn)
        row.addWidget(load_btn)

        ren_btn = QPushButton("RENAME")
        ren_btn.setFont(mono(7))
        ren_btn.setStyleSheet(button_qss())
        ren_btn.setFixedHeight(28)
        ren_btn.clicked.connect(self._on_rename_btn)
        row.addWidget(ren_btn)

        del_btn = QPushButton("DELETE")
        del_btn.setFont(mono(7))
        del_btn.setStyleSheet(button_qss(danger=True))
        del_btn.setFixedHeight(28)
        del_btn.clicked.connect(self._on_delete_btn)
        row.addWidget(del_btn)
        lay.addLayout(row)

    def _on_new_btn(self) -> None:
        self._on_new()
        self.refresh()

    def _on_load_btn(self) -> None:
        sid = self._selected_id()
        if not sid:
            return
        self._on_load(sid)

    def _on_item_double(self, item: QListWidgetItem) -> None:
        sid = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(sid, str):
            self._on_load(sid)

    def _on_delete_btn(self) -> None:
        sid = self._selected_id()
        if not sid:
            return
        confirm = QMessageBox.question(
            self, "Delete session", f"Delete session {sid}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self._on_delete(sid)
            self.refresh()

    def _on_rename_btn(self) -> None:
        sid = self._selected_id()
        if not sid:
            return
        item = self._list.currentItem()
        current = item.text() if item else ""
        new_title, ok = QInputDialog.getText(self, "Rename session", "New title:", text=current)
        if ok and new_title.strip():
            self._on_rename(sid, new_title.strip())
            self.refresh()

    def _selected_id(self) -> str | None:
        item = self._list.currentItem()
        if not item:
            return None
        sid = item.data(Qt.ItemDataRole.UserRole)
        return str(sid) if sid else None

    def _filter(self, txt: str) -> None:
        q = txt.lower().strip()
        for i in range(self._list.count()):
            it = self._list.item(i)
            if it is None:
                continue
            visible = q in it.text().lower() if q else True
            it.setHidden(not visible)

    def refresh(self) -> None:
        self._list.clear()
        try:
            entries = self._on_list()
        except Exception as exc:
            it = QListWidgetItem(f"error: {exc}")
            self._list.addItem(it)
            return
        for e in entries:
            t = e.get("title") or "(sin titulo)"
            sid = e.get("id") or ""
            tc = e.get("turn_count") or 0
            updated = (e.get("updated_at") or "")[:16]
            label = f"{t}\n  {updated}  ·  {tc} turns  ·  {sid}"
            item = QListWidgetItem(label)
            item.setFont(QFont("Consolas", 8))
            item.setData(Qt.ItemDataRole.UserRole, sid)
            self._list.addItem(item)
