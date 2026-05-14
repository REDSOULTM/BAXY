"""Phrase trigger editor — TriggerCMD-style commands.

Wraps the existing `routine` tool. Each phrase trigger is a routine with
`trigger.type = on_phrase` and a list of `steps`, each step being a
`{tool, args}` pair.

Layout:
  Top:    list of existing triggers (table-like), each row click loads it.
  Middle: form — label, phrase, enabled, type, steps editor.
  Bottom: import from TriggerCMD JSON, save, delete buttons.

The "Steps editor" is a multi-line JSON area for power users plus a
"+ ADD STEP" helper that appends a `{"tool": "...", "args": {}}` template.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from .theme import (
    C, button_qss, combo_qss, line_edit_qss, mono, panel_qss, text_edit_qss,
)


ToolExecFn = Callable[[str, dict[str, Any]], dict[str, Any]]


class TriggersDialog(QDialog):
    saved = pyqtSignal()

    def __init__(self, *, tool_exec: ToolExecFn, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GEMMA4  ·  PHRASE TRIGGERS")
        self.setMinimumSize(820, 620)
        self._tool_exec = tool_exec
        self._current_id: str | None = None
        self.setStyleSheet(f"QDialog {{ background: {C.BG}; }} QLabel {{ color: {C.TEXT}; }}")
        self._build()
        self.refresh()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        title = QLabel("✦  PHRASE TRIGGERS  (Alexa-style local commands)")
        title.setFont(mono(12, True))
        title.setStyleSheet(f"color: {C.PRI}; padding-bottom: 6px; border-bottom: 1px solid {C.BORDER};")
        lay.addWidget(title)

        body = QHBoxLayout()
        body.setSpacing(10)

        # Left — list
        left = QVBoxLayout()
        left.setSpacing(6)
        left_title = QLabel("▸ REGISTERED")
        left_title.setFont(mono(8, True))
        left_title.setStyleSheet(f"color: {C.TEXT_MED};")
        left.addWidget(left_title)

        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: {C.PANEL};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 3px;
                padding: 4px;
            }}
            QListWidget::item {{ padding: 4px; border-bottom: 1px solid {C.BORDER}; }}
            QListWidget::item:selected {{ background: {C.PRI_GHO}; color: {C.PRI}; }}
        """ + text_edit_qss())
        self._list.setMinimumWidth(280)
        self._list.itemClicked.connect(self._on_select)
        left.addWidget(self._list, stretch=1)

        import_btn = QPushButton("⊕  IMPORT TriggerCMD JSON")
        import_btn.setFont(mono(7, True))
        import_btn.setStyleSheet(button_qss())
        import_btn.setFixedHeight(28)
        import_btn.clicked.connect(self._import_json)
        left.addWidget(import_btn)

        body.addLayout(left, stretch=0)

        # Right — form
        right = QVBoxLayout()
        right.setSpacing(6)
        right_title = QLabel("▸ EDIT")
        right_title.setFont(mono(8, True))
        right_title.setStyleSheet(f"color: {C.TEXT_MED};")
        right.addWidget(right_title)

        self._label = QLineEdit()
        self._label.setPlaceholderText("Label (display name)")
        self._label.setStyleSheet(line_edit_qss())
        self._label.setFont(mono(9))
        right.addWidget(self._label)

        self._phrase = QLineEdit()
        self._phrase.setPlaceholderText("Phrase the user will say — e.g. 'baja el volumen'")
        self._phrase.setStyleSheet(line_edit_qss())
        self._phrase.setFont(mono(9))
        right.addWidget(self._phrase)

        opts_row = QHBoxLayout()
        opts_row.setSpacing(8)
        self._enabled = QCheckBox("Enabled")
        self._enabled.setChecked(True)
        self._enabled.setStyleSheet(f"color: {C.TEXT};")
        opts_row.addWidget(self._enabled)

        opts_row.addWidget(QLabel("Type:"))
        self._type = QComboBox()
        self._type.setStyleSheet(combo_qss())
        self._type.addItems(["on_phrase", "on_keyword"])
        opts_row.addWidget(self._type)
        opts_row.addStretch()
        right.addLayout(opts_row)

        steps_lbl = QLabel("STEPS  ·  JSON array of {tool, args}")
        steps_lbl.setFont(mono(7, True))
        steps_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
        right.addWidget(steps_lbl)

        self._steps = QPlainTextEdit()
        self._steps.setFont(QFont("Consolas", 9))
        self._steps.setStyleSheet(text_edit_qss())
        self._steps.setPlaceholderText(
            '[\n  {"tool": "audio", "args": {"action": "set_volume", "level": 20}},\n'
            '  {"tool": "verify", "args": {"action": "current_volume"}}\n]'
        )
        right.addWidget(self._steps, stretch=1)

        helpers_row = QHBoxLayout()
        for tool_name in ("audio", "media", "browser_real", "notification", "uia", "filesystem", "verify"):
            b = QPushButton(f"+ {tool_name}")
            b.setFont(mono(7))
            b.setFixedHeight(24)
            b.setStyleSheet(button_qss())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _checked=False, n=tool_name: self._append_step(n))
            helpers_row.addWidget(b)
        helpers_row.addStretch()
        right.addLayout(helpers_row)

        # Action row
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};")
        right.addWidget(sep)

        actions = QHBoxLayout()
        new_b = QPushButton("✚  NEW")
        new_b.setStyleSheet(button_qss())
        new_b.setFixedHeight(30)
        new_b.clicked.connect(self._on_new)
        actions.addWidget(new_b)

        save_b = QPushButton("💾  SAVE")
        save_b.setStyleSheet(button_qss(primary=True))
        save_b.setFixedHeight(30)
        save_b.clicked.connect(self._on_save)
        actions.addWidget(save_b)

        test_b = QPushButton("▶  RUN NOW")
        test_b.setStyleSheet(button_qss())
        test_b.setFixedHeight(30)
        test_b.clicked.connect(self._on_run_now)
        actions.addWidget(test_b)

        del_b = QPushButton("🗑  DELETE")
        del_b.setStyleSheet(button_qss(danger=True))
        del_b.setFixedHeight(30)
        del_b.clicked.connect(self._on_delete)
        actions.addWidget(del_b)
        actions.addStretch()
        right.addLayout(actions)

        body.addLayout(right, stretch=1)
        lay.addLayout(body, stretch=1)

        # Status
        self._status = QLabel("")
        self._status.setFont(mono(8))
        self._status.setStyleSheet(f"color: {C.TEXT_DIM};")
        lay.addWidget(self._status)

    # ------------------------------------------------------------------
    def _append_step(self, tool_name: str) -> None:
        try:
            current = self._steps.toPlainText().strip()
            if not current:
                arr = []
            else:
                arr = json.loads(current)
                if not isinstance(arr, list):
                    arr = []
        except json.JSONDecodeError:
            self._status.setText("steps JSON malformed — fix it before adding")
            return
        arr.append({"tool": tool_name, "args": {"action": ""}})
        self._steps.setPlainText(json.dumps(arr, ensure_ascii=False, indent=2))

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self._list.clear()
        res = self._tool_exec("routine", {"action": "list", "include_closed": False, "limit": 200})
        if not res.get("ok"):
            it = QListWidgetItem(f"error: {res.get('error') or 'unknown'}")
            self._list.addItem(it)
            return
        items = res.get("items") or res.get("routines") or []
        for r in items:
            meta = r.get("metadata") or r
            tt = str(meta.get("trigger_type") or "").lower()
            if tt not in ("on_phrase", "on_keyword"):
                continue
            label = str(r.get("label") or meta.get("label") or "(no label)")
            phrase = str((meta.get("trigger") or {}).get("phrase") or (meta.get("trigger") or {}).get("keyword") or "?")
            enabled = "✓" if meta.get("enabled", True) else "✗"
            rid = str(r.get("id") or r.get("resource_id") or "")
            entry = f"{enabled}  {label}\n       \"{phrase}\"  ·  {rid}"
            item = QListWidgetItem(entry)
            item.setData(Qt.ItemDataRole.UserRole, {"id": rid, "raw": r})
            item.setFont(QFont("Consolas", 8))
            self._list.addItem(item)

    def _on_select(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return
        raw = data.get("raw") or {}
        meta = raw.get("metadata") or raw
        trigger = meta.get("trigger") or {}
        self._current_id = data.get("id") or ""
        self._label.setText(str(raw.get("label") or meta.get("label") or ""))
        self._phrase.setText(str(trigger.get("phrase") or trigger.get("keyword") or ""))
        self._enabled.setChecked(bool(meta.get("enabled", True)))
        self._type.setCurrentText(str(meta.get("trigger_type") or "on_phrase"))
        steps = meta.get("steps") or []
        self._steps.setPlainText(json.dumps(steps, ensure_ascii=False, indent=2))
        self._status.setText(f"loaded {self._current_id}")

    def _on_new(self) -> None:
        self._current_id = None
        self._label.clear()
        self._phrase.clear()
        self._enabled.setChecked(True)
        self._type.setCurrentText("on_phrase")
        self._steps.setPlainText("[]")
        self._status.setText("new trigger — fill the form and SAVE")

    def _gather_form(self) -> dict | None:
        label = self._label.text().strip()
        phrase = self._phrase.text().strip()
        if not label or not phrase:
            QMessageBox.warning(self, "Missing", "Label and phrase are required.")
            return None
        try:
            steps = json.loads(self._steps.toPlainText() or "[]")
            if not isinstance(steps, list):
                raise ValueError("steps must be a JSON array")
        except (json.JSONDecodeError, ValueError) as exc:
            QMessageBox.warning(self, "Invalid steps JSON", str(exc))
            return None
        return {
            "label": label,
            "trigger": {"type": self._type.currentText(), "phrase": phrase},
            "steps": steps,
            "enabled": self._enabled.isChecked(),
        }

    def _on_save(self) -> None:
        data = self._gather_form()
        if not data:
            return
        if self._current_id:
            # delete + recreate (the routine tool has no update action)
            self._tool_exec("routine", {"action": "delete", "id": self._current_id})
        res = self._tool_exec("routine", {
            "action": "create",
            "label": data["label"],
            "trigger": data["trigger"],
            "steps": data["steps"],
            "enabled": data["enabled"],
        })
        if res.get("ok"):
            self._status.setText(f"saved: {res.get('id') or res.get('resource_id') or ''}")
            self._current_id = res.get("id") or res.get("resource_id") or None
            self.refresh()
            self.saved.emit()
        else:
            QMessageBox.critical(self, "Save failed", str(res.get("error") or res))

    def _on_run_now(self) -> None:
        if not self._current_id:
            QMessageBox.information(self, "Save first", "Save the trigger before running.")
            return
        self._status.setText(f"running trigger {self._current_id} ...")
        from .async_tool import run_tool_async
        run_tool_async(
            self._tool_exec,
            "routine",
            {"action": "run_now", "id": self._current_id},
            lambda res: self._status.setText(f"run_now -> {res}"),
        )

    def _on_delete(self) -> None:
        if not self._current_id:
            return
        confirm = QMessageBox.question(
            self, "Delete", f"Delete trigger {self._current_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        res = self._tool_exec("routine", {"action": "delete", "id": self._current_id})
        self._status.setText(f"delete -> {res}")
        self._on_new()
        self.refresh()

    def _import_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Pick TriggerCMD commands.json", str(Path.home()), "JSON (*.json)")
        if not path:
            return
        res = self._tool_exec("routine", {
            "action": "import",
            "source": "triggercmd",
            "json_path": path,
        })
        if res.get("ok"):
            n = res.get("imported_count", "?")
            sk = len(res.get("skipped") or [])
            self._status.setText(f"imported {n} entries, skipped {sk}")
            self.refresh()
        else:
            QMessageBox.critical(self, "Import failed", str(res.get("error") or res))
