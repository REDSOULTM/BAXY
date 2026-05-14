"""Entry point — `python -m gemma4_agent.ui` launches the Jarvis-style GUI.

Sequence:
  1. apply persisted env settings from ~/.gemma4/gui.json (so the agent picks
     them up at first init)
  2. show splash boot screen while the agent worker initialises
  3. swap to the main window once the agent reports IDLE / OFFLINE
"""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout

from .main_window import MainWindow
from .settings import apply_persisted_on_startup
from .theme import C, display, mono, qcol


class SplashWidget(QWidget):
    """A small animated splash painted directly. Replaces QSplashScreen pixmap."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(620, 360)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._tick = 0
        self._lines: list[str] = [
            "BOOT SEQUENCE 0x00",
            "Initialising MARK I core",
            "Loading tool registry...",
            "Loading sentence embedder...",
            "Loading reranker (lazy)...",
            "Checking llama-server health...",
            "Subsystems online.",
        ]
        self._shown_lines = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(70)
        # screen center
        screen = QApplication.primaryScreen()
        if screen is not None:
            ag = screen.availableGeometry()
            self.move((ag.width() - self.width()) // 2, (ag.height() - self.height()) // 2)

    def _step(self) -> None:
        self._tick += 1
        if self._tick % 6 == 0 and self._shown_lines < len(self._lines):
            self._shown_lines += 1
        self.update()

    def paintEvent(self, a0: object) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), qcol(C.BG))

        # border + corner brackets
        W, H = self.width(), self.height()
        p.setPen(QPen(qcol(C.BORDER_B), 2))
        p.drawRect(8, 8, W - 16, H - 16)
        bl = 26
        p.setPen(QPen(qcol(C.PRI), 2))
        for x, y, dx, dy in [(8, 8, 1, 1), (W-8, 8, -1, 1), (8, H-8, 1, -1), (W-8, H-8, -1, -1)]:
            p.drawLine(x, y, x + dx * bl, y)
            p.drawLine(x, y, x, y + dy * bl)

        # title
        p.setPen(QPen(qcol(C.PRI), 1))
        p.setFont(display(28, True))
        p.drawText(self.rect().adjusted(0, 60, 0, 0),
                   Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                   "G E M M A 4")
        p.setFont(mono(9))
        p.setPen(QPen(qcol(C.PRI_DIM), 1))
        p.drawText(self.rect().adjusted(0, 105, 0, 0),
                   Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                   "Just A Rather Very Intelligent System  ·  MARK I")

        # boot lines
        p.setFont(mono(8))
        for i in range(self._shown_lines):
            line = self._lines[i]
            col = C.GREEN if i < self._shown_lines - 1 else C.ACC2
            p.setPen(QPen(qcol(col), 1))
            sym = "✓" if i < self._shown_lines - 1 else ("▸" if (self._tick // 6) % 2 == 0 else "▹")
            p.drawText(40, 170 + i * 18, f"{sym}  {line}")

        # blinking cursor
        if self._tick % 16 < 8 and self._shown_lines < len(self._lines):
            p.fillRect(40 + (self._shown_lines * 2), 170 + self._shown_lines * 18 - 8, 8, 2, qcol(C.PRI))


def main() -> int:
    apply_persisted_on_startup()
    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication(sys.argv)
    app.setApplicationName("GEMMA4")
    app.setApplicationDisplayName("GEMMA4 · Mark I")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 9))

    splash = SplashWidget()
    splash.show()
    app.processEvents()

    win = MainWindow()

    def _go() -> None:
        win.show()
        win.raise_()
        splash.close()

    # Show splash for a moment, then swap (worker keeps initialising in BG).
    QTimer.singleShot(2200, _go)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
