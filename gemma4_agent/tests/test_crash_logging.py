"""Smoke test for the GUI crash hook installation.

Added 2026-05-17 after a GUI session died silently between 15:31 and
15:46 with no traceback in any log. The crash hook persists any
unhandled exception (Python or Qt) to ~/.gemma4/logs/_pre_session/crash.log
so the next silent kill leaves evidence.

These tests do NOT spawn a QApplication — they verify the hook is
installed by calling _install_crash_hooks() and inspecting sys.excepthook.
"""
from __future__ import annotations

import logging
import sys
import unittest
from unittest.mock import patch


class CrashHookInstallTest(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_excepthook = sys.excepthook

    def tearDown(self) -> None:
        sys.excepthook = self._orig_excepthook
        # Limpiar handlers que el test instalo, asi otros tests no los heredan.
        logger = logging.getLogger("gemma4.crash")
        for h in list(logger.handlers):
            logger.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass

    def test_excepthook_replaced_after_install(self) -> None:
        from gemma4_agent.ui import app as ui_app
        ui_app._install_crash_hooks()
        self.assertIsNot(
            sys.excepthook, sys.__excepthook__,
            "sys.excepthook should be replaced by the GUI crash hook",
        )

    def test_install_is_idempotent(self) -> None:
        from gemma4_agent.ui import app as ui_app
        ui_app._install_crash_hooks()
        ui_app._install_crash_hooks()
        logger = logging.getLogger("gemma4.crash")
        crash_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.FileHandler)
            and getattr(h, "baseFilename", "") == str(ui_app._CRASH_LOG_PATH)
        ]
        self.assertLessEqual(
            len(crash_handlers), 1,
            f"crash handler should not be duplicated, got {len(crash_handlers)}",
        )

    def test_excepthook_writes_to_crash_logger(self) -> None:
        from gemma4_agent.ui import app as ui_app
        ui_app._install_crash_hooks()
        logger = logging.getLogger("gemma4.crash")
        with patch.object(logger, "error") as mock_error:
            try:
                raise RuntimeError("smoke test crash")
            except RuntimeError:
                sys.excepthook(*sys.exc_info())
        mock_error.assert_called_once()
        args, _ = mock_error.call_args
        # First positional is the format string, second is the traceback text.
        self.assertIn("UNHANDLED EXCEPTION", args[0])
        self.assertIn("RuntimeError", args[1])
        self.assertIn("smoke test crash", args[1])


if __name__ == "__main__":
    unittest.main()
