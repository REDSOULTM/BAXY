"""Entry point — `python -m gemma4_agent.ui` launches the Jarvis-style GUI.

Sequence:
  1. apply persisted env settings from ~/.gemma4/gui.json (so the agent picks
     them up at first init)
  2. show splash boot screen while the agent worker initialises
  3. swap to the main window once the agent reports IDLE / OFFLINE
"""
from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget

from .main_window import MainWindow
from .settings import apply_persisted_on_startup
from .theme import C, display, mono, qcol


# Crash log path: misma carpeta que el pre-session recorder para no
# proliferar lugares de log.
_CRASH_LOG_PATH = Path.home() / ".gemma4" / "logs" / "_pre_session" / "crash.log"


def _install_crash_hooks() -> None:
    """Persist any unhandled exception (Python or Qt) to crash.log.

    Por defecto en Qt+PyQt6, una excepcion dentro de un slot puede matar
    el proceso sin propagar al stdout. Esto persiste el traceback a un
    archivo dedicado para que, cuando la GUI muera "de la nada", tengamos
    evidencia para diagnosticar. Idempotente: re-instalar no duplica
    handlers.
    """
    try:
        _CRASH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Si no podemos crear el dir (read-only HOME, etc.) no abortamos
        # el arranque de la GUI — el hook simplemente no loguea a disco.
        pass

    crash_logger = logging.getLogger("gemma4.crash")
    crash_logger.setLevel(logging.ERROR)
    crash_logger.propagate = False  # no spam stdout

    already_attached = any(
        isinstance(h, logging.FileHandler)
        and getattr(h, "baseFilename", "") == str(_CRASH_LOG_PATH)
        for h in crash_logger.handlers
    )
    if not already_attached:
        try:
            handler = logging.FileHandler(_CRASH_LOG_PATH, encoding="utf-8")
        except OSError:
            handler = None
        if handler is not None:
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            ))
            crash_logger.addHandler(handler)

    def _excepthook(exc_type, exc_value, exc_tb):
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            crash_logger.error("UNHANDLED EXCEPTION:\n%s", tb_text)
        except Exception:
            pass
        # Re-emite al stderr default por si el operador esta viendo
        # la consola.
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook

    # Qt tiene su propio canal de mensajes que normalmente no se loggea
    # (warnings tipo "QObject::connect: No such slot",
    # "Qt has caught an exception thrown from an event handler", etc.).
    try:
        from PyQt6.QtCore import qInstallMessageHandler  # type: ignore
    except Exception:
        return

    def _qt_msg_handler(msg_type, context, message):
        try:
            sev = int(msg_type)
        except Exception:
            sev = 0
        # QtMsgType: Debug=0, Warning=1, Critical=2, Fatal=3, Info=4.
        # Solo loggeamos warning+ para no spamear.
        if sev not in (1, 2, 3):
            return
        try:
            level_name = getattr(msg_type, "name", str(msg_type))
        except Exception:
            level_name = str(msg_type)
        try:
            crash_logger.error("Qt[%s]: %s", level_name, message)
        except Exception:
            pass

    try:
        qInstallMessageHandler(_qt_msg_handler)
    except Exception:
        pass


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


def _setup_logging() -> None:
    """Configura logging para que los logger.info sean visibles en consola.

    Default level = INFO. Override con GEMMA4_LOG_LEVEL=DEBUG/WARNING/etc.
    Si ya hay handlers configurados (otro caller), no toca nada.
    """
    root = logging.getLogger()
    if root.handlers:
        return
    level_name = (os.environ.get("GEMMA4_LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def main() -> int:
    # Crash hooks first — antes de cualquier cosa que pueda crashear, asi
    # el primer traceback queda persistido (fix 2026-05-17: GUI cerro sola
    # sin escribir nada en logs).
    _install_crash_hooks()
    _setup_logging()
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
