"""Tool explorer — browse all registered tools with their schemas.

Left:   list of tool names with search filter.
Right:  schema preview (description + parameters) + a "run" form that lets
        the user invoke any action manually.

This is power-user surface. Outputs are shown as raw JSON.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from .theme import C, button_qss, line_edit_qss, mono, text_edit_qss


class ToolExplorer(QDialog):
    def __init__(self, *, agent_getter: Callable[[], Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GEMMA4  ·  TOOL EXPLORER")
        self.setMinimumSize(960, 620)
        self._agent_getter = agent_getter
        self._current_tool: str = ""
        self.setStyleSheet(f"QDialog {{ background: {C.BG}; }} QLabel {{ color: {C.TEXT}; }}")
        self._build()
        self._refresh()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)

        title = QLabel("☷  TOOL EXPLORER  ·  full registry")
        title.setFont(mono(12, True))
        title.setStyleSheet(f"color: {C.PRI}; padding-bottom: 6px; border-bottom: 1px solid {C.BORDER};")
        lay.addWidget(title)

        split = QSplitter(Qt.Orientation.Horizontal)

        # left ---------------------------------------------------------
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 8, 6, 0)
        left_lay.setSpacing(6)

        self._search = QLineEdit()
        self._search.setStyleSheet(line_edit_qss())
        self._search.setFont(mono(9))
        self._search.setPlaceholderText("filter tools...")
        self._search.textChanged.connect(self._filter)
        left_lay.addWidget(self._search)

        self._list = QListWidget()
        self._list.setStyleSheet(text_edit_qss())
        self._list.setFont(QFont("Consolas", 9))
        self._list.itemClicked.connect(self._on_select)
        left_lay.addWidget(self._list, stretch=1)

        self._count_lbl = QLabel("")
        self._count_lbl.setFont(mono(7))
        self._count_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        left_lay.addWidget(self._count_lbl)

        split.addWidget(left)

        # right --------------------------------------------------------
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(8, 8, 0, 0)
        right_lay.setSpacing(6)

        self._desc = QLabel("Select a tool to view its schema.")
        self._desc.setWordWrap(True)
        self._desc.setFont(mono(8))
        self._desc.setStyleSheet(f"color: {C.TEXT_DIM};")
        right_lay.addWidget(self._desc)

        self._schema = QPlainTextEdit()
        self._schema.setReadOnly(True)
        self._schema.setStyleSheet(text_edit_qss())
        self._schema.setFont(QFont("Consolas", 9))
        right_lay.addWidget(self._schema, stretch=1)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};")
        right_lay.addWidget(sep)

        run_lbl = QLabel("ARGS  ·  JSON object to pass as tool args")
        run_lbl.setFont(mono(7, True))
        run_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
        right_lay.addWidget(run_lbl)

        self._args = QPlainTextEdit()
        self._args.setStyleSheet(text_edit_qss())
        self._args.setFont(QFont("Consolas", 9))
        self._args.setPlainText('{"action": "status"}')
        self._args.setMaximumHeight(110)
        right_lay.addWidget(self._args)

        run_row = QHBoxLayout()
        run_b = QPushButton("▶  RUN")
        run_b.setStyleSheet(button_qss(primary=True))
        run_b.setFixedHeight(30)
        run_b.clicked.connect(self._on_run)
        run_row.addWidget(run_b)
        run_row.addStretch()
        right_lay.addLayout(run_row)

        out_lbl = QLabel("RESULT")
        out_lbl.setFont(mono(7, True))
        out_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
        right_lay.addWidget(out_lbl)

        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)
        self._out.setStyleSheet(text_edit_qss())
        self._out.setFont(QFont("Consolas", 9))
        right_lay.addWidget(self._out, stretch=1)

        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([280, 660])
        lay.addWidget(split, stretch=1)

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        agent = self._agent_getter()
        if agent is None:
            return
        self._list.clear()
        schemas = agent.tools.schemas
        names = sorted(s["function"]["name"] for s in schemas)
        for n in names:
            self._list.addItem(QListWidgetItem(n))
        self._count_lbl.setText(f"{len(names)} tools registered")

    def _filter(self, q: str) -> None:
        q = q.casefold().strip()
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item is None:
                continue
            item.setHidden(q not in item.text().casefold() if q else False)

    def _on_select(self, item: QListWidgetItem) -> None:
        name = item.text()
        agent = self._agent_getter()
        if agent is None:
            return
        for schema in agent.tools.schemas:
            if schema["function"]["name"] == name:
                self._current_tool = name
                fn = schema["function"]
                self._desc.setText(fn.get("description", ""))
                self._schema.setPlainText(json.dumps(schema, ensure_ascii=False, indent=2))
                return

    def _on_run(self) -> None:
        if not self._current_tool:
            return
        agent = self._agent_getter()
        if agent is None:
            return
        try:
            args = json.loads(self._args.toPlainText() or "{}")
            if not isinstance(args, dict):
                raise ValueError("args must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            self._out.setPlainText(f"args error: {exc}")
            return
        try:
            res = agent.tools.execute(self._current_tool, args)
        except Exception as exc:
            self._out.setPlainText(f"exec raised: {exc}")
            return
        try:
            self._out.setPlainText(json.dumps(res, ensure_ascii=False, indent=2, default=str))
        except Exception:
            self._out.setPlainText(str(res))
