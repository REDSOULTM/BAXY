"""Contract tests for the Qt SettingsDialog + module-level helpers.

Sprint 5b is going to split SettingsDialog (1 148 LOC, 22 methods)
tab-by-tab. These tests pin:
  - load_persisted / apply_to_env / apply_persisted_on_startup
    behaviour (pure-Python, no Qt)
  - SettingsDialog instantiates under Qt offscreen
  - All 11 expected tab titles are present in the QTabWidget

If PyQt6 cannot offscreen-init, the Qt classes are skipped; the
pure-Python helpers run unconditionally.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


# Expected tab titles, in display order. Sprint 5b is supposed to
# split SettingsDialog tab-by-tab — any drift in this list signals a
# rename or removal.
EXPECTED_TABS = (
    "CONNECTION", "AGENT", "SAMPLING", "BEHAVIOUR", "VOICE",
    "PROFILES", "OPTIM", "TOGGLES", "PATHS", "PROMPT", "ABOUT",
)


class TestApplyToEnv(unittest.TestCase):
    """apply_to_env(data) is a pure function — pushes env + toggles
    into os.environ. No Qt needed."""

    def setUp(self) -> None:
        # Snapshot the env keys we'll touch so we can restore them.
        self._saved = {
            k: os.environ.get(k)
            for k in ("GEMMA4_AGENT_TEST_KEY",
                      "GEMMA4_AGENT_TEST_TOGGLE",
                      "GEMMA4_AGENT_TEST_NONE")
        }

    def tearDown(self) -> None:
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_env_keys_pushed_as_strings(self) -> None:
        from ..ui.settings import apply_to_env
        apply_to_env({"env": {"GEMMA4_AGENT_TEST_KEY": "value_42"}})
        self.assertEqual(os.environ.get("GEMMA4_AGENT_TEST_KEY"), "value_42")

    def test_env_value_none_removes_key(self) -> None:
        from ..ui.settings import apply_to_env
        os.environ["GEMMA4_AGENT_TEST_NONE"] = "stale"
        apply_to_env({"env": {"GEMMA4_AGENT_TEST_NONE": None}})
        self.assertNotIn("GEMMA4_AGENT_TEST_NONE", os.environ)

    def test_env_value_empty_string_removes_key(self) -> None:
        from ..ui.settings import apply_to_env
        os.environ["GEMMA4_AGENT_TEST_NONE"] = "stale"
        apply_to_env({"env": {"GEMMA4_AGENT_TEST_NONE": ""}})
        self.assertNotIn("GEMMA4_AGENT_TEST_NONE", os.environ)

    def test_toggles_serialize_as_true_false_lowercase(self) -> None:
        from ..ui.settings import apply_to_env
        apply_to_env({"toggles": {"GEMMA4_AGENT_TEST_TOGGLE": True}})
        self.assertEqual(os.environ.get("GEMMA4_AGENT_TEST_TOGGLE"), "true")
        apply_to_env({"toggles": {"GEMMA4_AGENT_TEST_TOGGLE": False}})
        self.assertEqual(os.environ.get("GEMMA4_AGENT_TEST_TOGGLE"), "false")

    def test_empty_data_is_a_noop(self) -> None:
        from ..ui.settings import apply_to_env
        # Should not raise on either branch missing.
        apply_to_env({})
        apply_to_env({"env": {}, "toggles": {}})


class TestLoadPersisted(unittest.TestCase):
    """load_persisted reads SETTINGS_PATH; we redirect it to a tmpdir."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="gemma4_settings_"))

    def test_missing_file_returns_empty_dict(self) -> None:
        with patch("gemma4_agent.ui.settings.SETTINGS_PATH", self.tmp / "absent.json"):
            from ..ui.settings import load_persisted
            self.assertEqual(load_persisted(), {})

    def test_valid_json_returned(self) -> None:
        p = self.tmp / "gui.json"
        p.write_text(json.dumps({"env": {"X": "1"}}), encoding="utf-8")
        with patch("gemma4_agent.ui.settings.SETTINGS_PATH", p):
            from ..ui.settings import load_persisted
            self.assertEqual(load_persisted(), {"env": {"X": "1"}})

    def test_malformed_json_falls_back_to_empty(self) -> None:
        p = self.tmp / "gui.json"
        p.write_text("{not valid json", encoding="utf-8")
        with patch("gemma4_agent.ui.settings.SETTINGS_PATH", p):
            from ..ui.settings import load_persisted
            self.assertEqual(load_persisted(), {})

    def test_non_dict_root_falls_back_to_empty(self) -> None:
        p = self.tmp / "gui.json"
        p.write_text("[1, 2, 3]", encoding="utf-8")
        with patch("gemma4_agent.ui.settings.SETTINGS_PATH", p):
            from ..ui.settings import load_persisted
            self.assertEqual(load_persisted(), {})


class TestApplyPersistedOnStartup(unittest.TestCase):
    """apply_persisted_on_startup is the helper main_window calls at
    boot. Round-trip: write a gui.json, call the helper, observe
    os.environ."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="gemma4_settings_startup_"))
        self._saved = os.environ.get("GEMMA4_AGENT_TEST_STARTUP")

    def tearDown(self) -> None:
        if self._saved is None:
            os.environ.pop("GEMMA4_AGENT_TEST_STARTUP", None)
        else:
            os.environ["GEMMA4_AGENT_TEST_STARTUP"] = self._saved

    def test_no_file_no_op(self) -> None:
        with patch("gemma4_agent.ui.settings.SETTINGS_PATH", self.tmp / "absent.json"):
            from ..ui.settings import apply_persisted_on_startup
            # Should not raise and should not touch env.
            apply_persisted_on_startup()
            self.assertNotIn("GEMMA4_AGENT_TEST_STARTUP", os.environ)

    def test_with_file_pushes_env(self) -> None:
        p = self.tmp / "gui.json"
        p.write_text(json.dumps({
            "env": {"GEMMA4_AGENT_TEST_STARTUP": "from_disk"},
        }), encoding="utf-8")
        with patch("gemma4_agent.ui.settings.SETTINGS_PATH", p):
            from ..ui.settings import apply_persisted_on_startup
            apply_persisted_on_startup()
            self.assertEqual(os.environ.get("GEMMA4_AGENT_TEST_STARTUP"), "from_disk")


@unittest.skipUnless(_QT_OK, _QT_REASON)
class TestSettingsDialogShell(unittest.TestCase):
    """The dialog instantiates and exposes its tab structure intact."""

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])  # type: ignore[attr-defined]

    def _make(self):
        from ..ui.settings import SettingsDialog
        return SettingsDialog()

    def test_constructor_does_not_raise(self) -> None:
        dlg = self._make()
        self.addCleanup(dlg.deleteLater)
        from PyQt6.QtWidgets import QDialog
        self.assertIsInstance(dlg, QDialog)

    def test_apply_clicked_and_restart_clicked_signals_exposed(self) -> None:
        dlg = self._make()
        self.addCleanup(dlg.deleteLater)
        for sig_name in ("apply_clicked", "restart_clicked"):
            self.assertTrue(hasattr(dlg, sig_name),
                            f"SettingsDialog must expose `{sig_name}` signal")
            sig = getattr(dlg, sig_name)
            self.assertTrue(hasattr(sig, "emit"),
                            f"`{sig_name}` must be a pyqtSignal")

    def test_exactly_11_tabs_in_documented_order(self) -> None:
        """Sprint 5b is going to split tab-by-tab. The displayed titles
        are part of the contract — a rename is a visible UI change."""
        from PyQt6.QtWidgets import QTabWidget
        dlg = self._make()
        self.addCleanup(dlg.deleteLater)
        tabs = dlg.findChild(QTabWidget)
        self.assertIsNotNone(tabs, "SettingsDialog must contain a QTabWidget")
        observed = tuple(tabs.tabText(i) for i in range(tabs.count()))
        self.assertEqual(observed, EXPECTED_TABS)


if __name__ == "__main__":
    unittest.main()
