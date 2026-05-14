"""Activity log widget with typewriter-style appends, color-coded by tag.

Tags:
  you  — user input (white)
  ai   — assistant reply (cyan)
  tool — tool call line (orange)
  ok   — tool success (green)
  err  — error or unverified (red)
  sys  — system/info (amber)
  file — file uploaded (green-bright)

The typewriter speed is 6ms/char by default; the full queue is processed
sequentially.
"""
from __future__ import annotations

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QFont
from PyQt6.QtWidgets import QTextEdit, QWidget

from .theme import C, qcol, text_edit_qss


_PRESETS = {
    "you":  (C.WHITE,    "You: "),
    "ai":   (C.PRI,      ""),
    "tool": (C.ACC,      "→ "),
    "ok":   (C.GREEN,    "✓ "),
    "err":  (C.RED,      "✗ "),
    "sys":  (C.ACC2,     "[sys] "),
    "file": (C.GREEN,    "[file] "),
    "warn": (C.ACC2,     "⚠ "),
}


class LogWidget(QTextEdit):
    _enqueue_sig = pyqtSignal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 9))
        self.setStyleSheet(text_edit_qss())
        self._queue: list[tuple[str, str]] = []
        self._typing = False
        self._buf = ""
        self._pos = 0
        self._tag = "sys"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._enqueue_sig.connect(self._enqueue)
        self._char_ms = 4  # typewriter speed (lower = faster)

    def append(self, text: str, tag: str = "sys") -> None:  # type: ignore[override]
        """Thread-safe append. tag in: you/ai/tool/ok/err/sys/file/warn."""
        self._enqueue_sig.emit(text, tag)

    def _enqueue(self, text: str, tag: str) -> None:
        self._queue.append((text, tag))
        if not self._typing:
            self._next()

    def _next(self) -> None:
        if not self._queue:
            self._typing = False
            return
        self._typing = True
        text, tag = self._queue.pop(0)
        col, prefix = _PRESETS.get(tag, (C.TEXT, ""))
        self._buf = prefix + text
        self._pos = 0
        self._tag = tag
        self._cur_col = col
        self._timer.start(self._char_ms)

    def _step(self) -> None:
        if self._pos < len(self._buf):
            ch = self._buf[self._pos]
            cur = self.textCursor()
            fmt = cur.charFormat()
            fmt.setForeground(QBrush(qcol(self._cur_col)))
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText(ch, fmt)
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            self._pos += 1
        else:
            self._timer.stop()
            cur = self.textCursor()
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText("\n")
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            QTimer.singleShot(15, self._next)

    def clear_log(self) -> None:
        self.clear()
        self._queue.clear()
        self._typing = False
        self._buf = ""
        self._pos = 0
