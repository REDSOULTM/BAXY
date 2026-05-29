"""Memory + experience + tool explorer dialog (tabbed)."""
from __future__ import annotations

import json
from typing import Any, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QTabWidget,
    QVBoxLayout, QWidget,
)

from .theme import C, button_qss, line_edit_qss, mono, text_edit_qss


class MemoryDialog(QDialog):
    def __init__(self, *, agent_getter: Callable[[], Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GEMMA4  ·  MEMORY")
        self.setMinimumSize(820, 560)
        self._agent_getter = agent_getter
        self.setStyleSheet(f"QDialog {{ background: {C.BG}; }} QLabel {{ color: {C.TEXT}; }}")
        self._build()
        self.refresh_all()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)

        title = QLabel("✜  MEMORY  &  EXPERIENCE")
        title.setFont(mono(12, True))
        title.setStyleSheet(f"color: {C.PRI}; padding-bottom: 6px; border-bottom: 1px solid {C.BORDER};")
        lay.addWidget(title)

        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {C.BORDER}; background: {C.PANEL}; }}
            QTabBar::tab {{
                background: {C.DARK}; color: {C.TEXT_DIM};
                padding: 6px 16px; margin-right: 1px;
                border: 1px solid {C.BORDER}; border-bottom: none;
                font-family: 'Courier New'; font-size: 8pt; font-weight: bold;
            }}
            QTabBar::tab:selected {{ background: {C.PANEL}; color: {C.PRI}; border-bottom: 1px solid {C.PANEL}; }}
        """)
        tabs.addTab(self._tab_memory(), "PERSISTENT")
        tabs.addTab(self._tab_experience(), "EXPERIENCE")
        tabs.addTab(self._tab_knowledge(), "KNOWLEDGE")
        lay.addWidget(tabs, stretch=1)

        close = QPushButton("CLOSE")
        close.setStyleSheet(button_qss())
        close.setFixedHeight(28)
        close.clicked.connect(self.accept)
        lay.addWidget(close)

    # ------------------------------------------------------------------
    def _tab_memory(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)

        info = QLabel("Persistent memory entries. auto: prefix = LLM-extracted, others = user-explicit.")
        info.setFont(mono(8))
        info.setStyleSheet(f"color: {C.TEXT_DIM};")
        lay.addWidget(info)

        self._mem_list = QListWidget()
        self._mem_list.setStyleSheet(text_edit_qss())
        self._mem_list.setFont(QFont("Consolas", 9))
        lay.addWidget(self._mem_list, stretch=1)

        row = QHBoxLayout()
        add_b = QPushButton("✚ ADD")
        add_b.setStyleSheet(button_qss(primary=True))
        add_b.clicked.connect(self._on_mem_add)
        row.addWidget(add_b)

        del_b = QPushButton("DELETE")
        del_b.setStyleSheet(button_qss(danger=True))
        del_b.clicked.connect(self._on_mem_del)
        row.addWidget(del_b)

        ref_b = QPushButton("REFRESH")
        ref_b.setStyleSheet(button_qss())
        ref_b.clicked.connect(self._refresh_memory)
        row.addWidget(ref_b)
        row.addStretch()

        clr_b = QPushButton("⚠ CLEAR ALL")
        clr_b.setStyleSheet(button_qss(danger=True))
        clr_b.clicked.connect(self._on_mem_clear)
        row.addWidget(clr_b)

        lay.addLayout(row)
        return w

    def _refresh_memory(self) -> None:
        self._mem_list.clear()
        agent = self._agent_getter()
        if agent is None:
            self._mem_list.addItem(QListWidgetItem("(agent not ready)"))
            return
        try:
            result = agent.memory.recall(None)
            items = result.get("items") or {}
            if not items:
                self._mem_list.addItem(QListWidgetItem("(empty)"))
                return
            for key, entry in sorted(items.items()):
                val = entry.get("value", "") if isinstance(entry, dict) else str(entry)
                ts = entry.get("updated_at", "") if isinstance(entry, dict) else ""
                txt = f"{key}\n  = {val}\n  [{ts}]"
                it = QListWidgetItem(txt)
                it.setData(Qt.ItemDataRole.UserRole, key)
                self._mem_list.addItem(it)
        except Exception as exc:
            self._mem_list.addItem(QListWidgetItem(f"error: {exc}"))

    def _on_mem_add(self) -> None:
        agent = self._agent_getter()
        if agent is None:
            return
        key, ok = QInputDialog.getText(self, "Add memory", "Key:")
        if not ok or not key.strip():
            return
        value, ok = QInputDialog.getText(self, "Add memory", f"Value for '{key}':")
        if not ok:
            return
        agent.memory.save(key.strip(), value.strip())
        self._refresh_memory()

    def _on_mem_del(self) -> None:
        agent = self._agent_getter()
        if agent is None:
            return
        item = self._mem_list.currentItem()
        if not item:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(key, str):
            agent.memory.delete(key)
            self._refresh_memory()

    def _on_mem_clear(self) -> None:
        agent = self._agent_getter()
        if agent is None:
            return
        confirm = QMessageBox.question(
            self, "Clear memory", "Delete ALL persistent memory entries?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            agent.memory.delete("*")
            self._refresh_memory()

    # ------------------------------------------------------------------
    def _tab_experience(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)

        info = QLabel("Experience memory — embedded summaries of past completed turns (sqlite-vec).")
        info.setFont(mono(8))
        info.setStyleSheet(f"color: {C.TEXT_DIM};")
        lay.addWidget(info)

        row = QHBoxLayout()
        self._exp_query = QLineEdit()
        self._exp_query.setStyleSheet(line_edit_qss())
        self._exp_query.setFont(mono(9))
        self._exp_query.setPlaceholderText("semantic query (leave empty to list recent)")
        row.addWidget(self._exp_query, stretch=1)
        srch_b = QPushButton("SEARCH")
        srch_b.setStyleSheet(button_qss(primary=True))
        srch_b.clicked.connect(self._on_exp_search)
        row.addWidget(srch_b)
        lay.addLayout(row)

        self._exp_view = QPlainTextEdit()
        self._exp_view.setReadOnly(True)
        self._exp_view.setStyleSheet(text_edit_qss())
        self._exp_view.setFont(QFont("Consolas", 9))
        lay.addWidget(self._exp_view, stretch=1)
        return w

    def _on_exp_search(self) -> None:
        agent = self._agent_getter()
        if agent is None or not hasattr(agent, "experience"):
            self._exp_view.setPlainText("(experience memory not available)")
            return
        try:
            from ..routing.semantic_router import embed
        except Exception:
            embed = None  # type: ignore[assignment]
        q = self._exp_query.text().strip()
        try:
            if q and embed is not None:
                results = agent.experience.recall(q, embed_fn=embed, k=10)
            else:
                results = agent.experience.recent(limit=20) if hasattr(agent.experience, "recent") else []
        except Exception as exc:
            self._exp_view.setPlainText(f"error: {exc}")
            return
        if not results:
            self._exp_view.setPlainText("(no matches)")
            return
        lines: list[str] = []
        for r in results:
            tid = r.get("turn_id") or ""
            ts = r.get("created_at") or ""
            mission = r.get("mission_status") or ""
            tools = r.get("tools_used") or []
            summary = r.get("summary") or ""
            lines.append(f"[{ts}] {tid} · {mission} · tools={tools}")
            lines.append(f"  {summary}")
            lines.append("")
        self._exp_view.setPlainText("\n".join(lines))

    # ------------------------------------------------------------------
    def _tab_knowledge(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)

        info = QLabel("Knowledge base — local SQLite FTS5 + optional cross-encoder rerank (J1).")
        info.setFont(mono(8))
        info.setStyleSheet(f"color: {C.TEXT_DIM};")
        lay.addWidget(info)

        self._kn_status = QLabel("")
        self._kn_status.setFont(mono(8))
        self._kn_status.setStyleSheet(f"color: {C.PRI};")
        lay.addWidget(self._kn_status)

        row = QHBoxLayout()
        self._kn_query = QLineEdit()
        self._kn_query.setStyleSheet(line_edit_qss())
        self._kn_query.setFont(mono(9))
        self._kn_query.setPlaceholderText("query")
        row.addWidget(self._kn_query, stretch=1)
        s_b = QPushButton("SEARCH")
        s_b.setStyleSheet(button_qss(primary=True))
        s_b.clicked.connect(self._on_kn_search)
        row.addWidget(s_b)
        lay.addLayout(row)

        self._kn_view = QPlainTextEdit()
        self._kn_view.setReadOnly(True)
        self._kn_view.setStyleSheet(text_edit_qss())
        self._kn_view.setFont(QFont("Consolas", 9))
        lay.addWidget(self._kn_view, stretch=1)
        return w

    def _on_kn_search(self) -> None:
        agent = self._agent_getter()
        if agent is None:
            return
        q = self._kn_query.text().strip()
        if not q:
            return
        self._kn_view.setPlainText(f"searching '{q}' ...")
        from .async_tool import run_tool_async
        run_tool_async(
            agent.tools.execute,
            "knowledge",
            {"action": "search", "query": q, "limit": 8},
            lambda res: self._kn_view.setPlainText(json.dumps(res, ensure_ascii=False, indent=2, default=str)),
        )

    # ------------------------------------------------------------------
    def refresh_all(self) -> None:
        self._refresh_memory()
        agent = self._agent_getter()
        if agent is not None:
            try:
                st = agent.tools.execute("knowledge", {"action": "status"})
                self._kn_status.setText(f"knowledge: {st}")
            except Exception:
                pass
