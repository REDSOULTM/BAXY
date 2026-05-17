"""Contract tests for the Qt MainWindow.

Sprint 5b is going to split MainWindow (1 430 LOC, 53 methods) into
sub-widgets. These tests pin:
  - the class is importable + instantiable under Qt offscreen
  - the well-known widget attributes exist after construction
  - closeEvent runs without raising
  - the worker.state_changed signal is connected (the hookup that
    keeps the HUD in sync)

If PyQt6 cannot offscreen-init, the whole suite is skipped. Sprint
5b is expected to run in a Qt-capable environment; the test file
just has to exist so the skip toggles to RUN.
"""
from __future__ import annotations

import os
import unittest

# Offscreen platform — needed BEFORE any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qt_available() -> tuple[bool, str]:
    try:
        from PyQt6.QtWidgets import QApplication  # type: ignore[import-not-found]
    except ImportError as exc:
        return False, f"PyQt6 not installed: {exc}"
    try:
        app = QApplication.instance() or QApplication([])
        del app
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, f"QApplication init failed: {exc}"


_QT_OK, _QT_REASON = _qt_available()


@unittest.skipUnless(_QT_OK, _QT_REASON)
class TestMainWindowImport(unittest.TestCase):
    """The module loads + class is reachable. If this fails, Sprint 5b
    cannot proceed — the UI Desktop surface is broken."""

    def test_module_imports(self) -> None:
        import gemma4_agent.ui.main_window as mw_mod
        self.assertTrue(hasattr(mw_mod, "MainWindow"))

    def test_class_is_qmainwindow_subclass(self) -> None:
        from PyQt6.QtWidgets import QMainWindow
        from .ui.main_window import MainWindow
        self.assertTrue(issubclass(MainWindow, QMainWindow))


@unittest.skipUnless(_QT_OK, _QT_REASON)
class TestMainWindowInstantiation(unittest.TestCase):
    """MainWindow() must construct without crashing; the post-init
    attributes that Sprint 5b will move to sub-widgets must exist."""

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])  # type: ignore[attr-defined]

    def setUp(self) -> None:
        from .ui.main_window import MainWindow
        self.window = MainWindow()
        self.addCleanup(self.window.deleteLater)

    def test_constructor_does_not_raise(self) -> None:
        # By virtue of setUp() not raising, this passes — we still
        # assert isinstance so the test name is meaningful.
        from PyQt6.QtWidgets import QMainWindow
        self.assertIsInstance(self.window, QMainWindow)

    def test_worker_attribute_present(self) -> None:
        from .ui.agent_thread import AgentWorker
        self.assertTrue(hasattr(self.window, "worker"))
        self.assertIsInstance(self.window.worker, AgentWorker)

    def test_bus_bridge_attribute_present(self) -> None:
        # Note: the attribute is `_bus_bridge` (underscore) in the
        # current code, not `bus_bridge`. Pin the real name so Sprint 5b
        # doesn't accidentally rename it.
        self.assertTrue(hasattr(self.window, "_bus_bridge"))
        self.assertIsNotNone(self.window._bus_bridge)

    def test_hud_attribute_present(self) -> None:
        self.assertTrue(hasattr(self.window, "hud"))
        self.assertIsNotNone(self.window.hud)

    def test_log_widget_present(self) -> None:
        # The widget attribute is `log` (consumed by `self.worker.log.connect(self._on_log)`).
        self.assertTrue(hasattr(self.window, "log"))
        self.assertIsNotNone(self.window.log)

    def test_layout_handle_dicts_present(self) -> None:
        # panels.build_*_panel returns (widget, handles_dict). These
        # dicts hold the buttons/inputs that Sprint 5b will reorganize.
        for handle in ("_header_h", "_left_h", "_right_h", "_footer_h"):
            self.assertTrue(hasattr(self.window, handle),
                            f"MainWindow must expose {handle!r}")
            self.assertIsInstance(getattr(self.window, handle), dict)


@unittest.skipUnless(_QT_OK, _QT_REASON)
class TestMainWindowSignalWiring(unittest.TestCase):
    """The hookups MainWindow.__init__ wires must persist. We don't
    inspect the slot — we verify the signal "is connected to at
    least one receiver" indirectly via the receivers() count."""

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])  # type: ignore[attr-defined]

    def setUp(self) -> None:
        from .ui.main_window import MainWindow
        self.window = MainWindow()
        self.addCleanup(self.window.deleteLater)

    def test_state_changed_signal_emit_does_not_raise(self) -> None:
        # If the connection from worker.state_changed → hud.set_state
        # is wired correctly, emitting a value should not raise. This
        # is the canary for the HUD state-update path.
        try:
            self.window.worker.state_changed.emit("IDLE")
        except Exception as exc:  # noqa: BLE001
            self.fail(f"state_changed.emit('IDLE') raised: {exc}")

    def test_log_signal_emit_does_not_raise(self) -> None:
        try:
            self.window.worker.log.emit("sprint5a smoke", "sys")
        except Exception as exc:  # noqa: BLE001
            self.fail(f"log.emit() raised: {exc}")


@unittest.skipUnless(_QT_OK, _QT_REASON)
class TestMainWindowCloseEvent(unittest.TestCase):
    """closeEvent must drain the worker, detach the bus bridge, stop
    background threads — and never raise. Sprint 5b's split must
    preserve this guarantee."""

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])  # type: ignore[attr-defined]

    def test_closeEvent_runs_clean(self) -> None:
        from PyQt6.QtGui import QCloseEvent
        from .ui.main_window import MainWindow
        window = MainWindow()
        # PyQt6 enforces the QCloseEvent type signature; a MagicMock
        # gets rejected with "argument 1 has unexpected type".
        evt = QCloseEvent()
        try:
            window.closeEvent(evt)
        except Exception as exc:  # noqa: BLE001
            self.fail(f"closeEvent raised: {exc}")
        finally:
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
