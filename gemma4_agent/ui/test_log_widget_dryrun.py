"""Dry-run for the Activity Log widget.

Pins that multiline assistant replies and tool lines are rendered by the real
QTextEdit-based widget. No agent, no llama-server, no visible window.
"""
from __future__ import annotations

import sys
import time
import unittest

from PyQt6.QtWidgets import QApplication

from gemma4_agent.ui.log_widget import LogWidget


class LogWidgetDryRunTest(unittest.TestCase):
    def test_multiline_reply_is_visible(self) -> None:
        app = QApplication.instance() or QApplication(sys.argv)
        log = LogWidget()
        log._char_ms = 0

        reply = (
            "Encontre estos archivos:\n"
            "1. a.docx - C:/Users/u/Downloads/a.docx\n"
            "Cual queres abrir? Responde con el numero o el nombre."
        )
        log.append("Abre el primer Word que encuentres en mi carpeta de Descargas", "you")
        log.append("filesystem(action=search)", "tool")
        log.append(reply, "ai")

        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            app.processEvents()
            if "Cual queres abrir? Responde con el numero o el nombre." in log.toPlainText():
                break
            time.sleep(0.01)

        rendered = log.toPlainText()
        self.assertIn("You: Abre el primer Word", rendered)
        self.assertIn("filesystem(action=search)", rendered)
        self.assertIn("Encontre estos archivos:", rendered)
        self.assertIn("1. a.docx - C:/Users/u/Downloads/a.docx", rendered)
        self.assertIn("Cual queres abrir? Responde con el numero o el nombre.", rendered)


if __name__ == "__main__":
    unittest.main()
