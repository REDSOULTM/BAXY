"""Cobertura dedicada para domain_tools/device_settings.py (added 2026-06-01).

device_settings.py NO tenía test propio (solo el smoke {action:status}). Despacha
WiFi/Bluetooth/displays/power-plans. Acá cubrimos lo que NO se delega a wifi/
bluetooth: power_plan_list/get/set (powercfg) y las acciones diferidas.

El contrato CRÍTICO de power_plan_set es la HONESTIDAD del `verified`: NO basta
con returncode 0 de powercfg /setactive — el código vuelve a leer el plan activo
y solo declara verified=True si el GUID activo REAL coincide con el pedido.

Todo subprocess (powercfg) se mockea — cero cambios reales de plan de energía.

Propiedades afirmadas contra el código fuente:
  - power_plan_list parsea GUID+nombre+activo desde la salida de powercfg /list
  - power_plan_set con plan inexistente -> ok:False + lista available (honesto)
  - power_plan_set verified=True SOLO si el plan activo post == pedido
  - power_plan_set returncode 0 pero el plan NO cambió -> verified=False (no miente)
  - power_plan_set crea checkpoint con rollback al plan previo
  - acciones diferidas (bluetooth_toggle, night_light, ...) -> needs_implementation
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ..domain_tools import device_settings
from ..memory_pkg.state import AgentState


def _proc(returncode=0, stdout="", stderr=""):
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


_BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"
_POWER = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"

_LIST_OUT = (
    "Existing Power Schemes (* Active)\n"
    "-----------------------------------\n"
    f"Power Scheme GUID: {_BALANCED}  (Balanced) *\n"
    f"Power Scheme GUID: {_POWER}  (High performance)\n"
)


class TestDeviceStatus(unittest.TestCase):
    def test_status_reports_tooling(self):
        with patch.object(device_settings.shutil, "which", return_value="x"):
            r = device_settings.device_settings_tool({"action": "status"}, None)
        self.assertTrue(r["ok"])
        for key in ("netsh", "powercfg", "powershell"):
            self.assertIn(key, r)


class TestPowerPlanList(unittest.TestCase):
    def test_list_parses_guids_and_active(self):
        with patch.object(device_settings.subprocess, "run", return_value=_proc(0, _LIST_OUT)):
            r = device_settings._device_power_plan_list()
        self.assertTrue(r["ok"])
        self.assertEqual(r["count"], 2)
        balanced = next(p for p in r["plans"] if p["guid"] == _BALANCED)
        self.assertEqual(balanced["name"], "Balanced")
        self.assertTrue(balanced["active"])
        high = next(p for p in r["plans"] if p["guid"] == _POWER)
        self.assertFalse(high["active"])

    def test_list_failure_is_honest(self):
        with patch.object(device_settings.subprocess, "run", return_value=_proc(1, "", "denied")):
            r = device_settings._device_power_plan_list()
        self.assertFalse(r["ok"])


class TestPowerPlanSetHonesty(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ds_pp_"))
        self.state = AgentState(self.tmp / "s.json")

    def _run(self, args, *, set_rc=0, active_after=_BALANCED):
        # /list -> _LIST_OUT ; /getactivescheme -> el plan activo ; /setactive -> rc
        def fake_run(argv, *a, **k):
            if "/list" in argv:
                return _proc(0, _LIST_OUT)
            if "/getactivescheme" in argv:
                return _proc(0, f"Power Scheme GUID: {active_after}  (Some)\n")
            if "/setactive" in argv:
                return _proc(set_rc, "")
            return _proc(0, "")
        with patch.object(device_settings.subprocess, "run", side_effect=fake_run):
            return device_settings._device_power_plan_set(args, self.state)

    def test_plan_not_found_is_honest_with_available(self):
        r = self._run({"name": "Nonexistent Plan"})
        self.assertFalse(r["ok"])
        self.assertIn("available", r)

    def test_set_verified_true_when_active_matches(self):
        # pedimos High performance y el getactivescheme post devuelve ese GUID.
        r = self._run({"guid": _POWER}, set_rc=0, active_after=_POWER)
        self.assertTrue(r["ok"])
        self.assertIs(r["verified"], True)
        self.assertEqual(r["target"]["guid"], _POWER)

    def test_set_verified_false_when_active_did_not_change(self):
        # HONESTIDAD: setactive devolvió rc 0 pero el plan activo sigue Balanced
        # (no el pedido High performance) -> verified=False, no se miente éxito.
        r = self._run({"guid": _POWER}, set_rc=0, active_after=_BALANCED)
        self.assertFalse(r["verified"])

    def test_set_verified_false_on_nonzero_returncode(self):
        r = self._run({"guid": _POWER}, set_rc=1, active_after=_POWER)
        self.assertFalse(r["verified"])

    def test_set_creates_checkpoint(self):
        before = self.state.list_checkpoints()["count"]
        self._run({"guid": _POWER}, set_rc=0, active_after=_POWER)
        self.assertEqual(self.state.list_checkpoints()["count"], before + 1)

    def test_set_matches_by_name_substring(self):
        # "performance" debe resolver a High performance por substring.
        r = self._run({"name": "performance"}, set_rc=0, active_after=_POWER)
        self.assertTrue(r["ok"])
        self.assertEqual(r["target"]["guid"], _POWER)

    def test_missing_target(self):
        self.assertFalse(device_settings._device_power_plan_set({}, self.state)["ok"])


class TestDeferredActions(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ds_def_"))
        self.state = AgentState(self.tmp / "s.json")

    def test_deferred_actions_are_honest_needs_implementation(self):
        # HONESTIDAD: las acciones no soportadas devuelven needs_implementation,
        # no fingen haber actuado.
        for action in ("bluetooth_toggle", "night_light", "display_set_resolution", "display_set_scale"):
            r = device_settings.device_settings_tool({"action": action}, self.state)
            self.assertFalse(r["ok"], action)
            self.assertEqual(r["status"], "needs_implementation", action)

    def test_unknown_action_needs_user(self):
        r = device_settings.device_settings_tool({"action": "no_such"}, self.state)
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")


if __name__ == "__main__":
    unittest.main()
