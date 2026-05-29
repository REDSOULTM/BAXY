"""Brillo de pantalla por voz para baja visión (2026-05-27). El brillo vive en
`system` (brightness_get/set) pero el 4B lo pide por `device_settings` (es un
ajuste de pantalla) o con variantes (brightness_up/down). Ambos caminos deben
funcionar (delegan a la misma impl) y "subí/bajá el brillo" sin número debe
aplicar un delta relativo. subprocess (PowerShell/WMI) mockeado — no toca la
pantalla real. Mock-only.
"""
from __future__ import annotations

import unittest
from unittest import mock

from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.infra.config import AgentConfig


class BrightnessDelegationTest(unittest.TestCase):
    def setUp(self):
        self.tools = Gemma4Agent(AgentConfig.from_env()).tools

    def _ps_ok(self, stdout=""):
        m = mock.Mock(); m.returncode = 0; m.stdout = stdout; m.stderr = ""
        return m

    # --- device_settings delega a system brightness ---
    def test_device_settings_brightness_set_delegates(self):
        with mock.patch("gemma4_agent.tools.subprocess.run",
                        return_value=self._ps_ok()) as run:
            res = self.tools.t_device_settings({"action": "brightness_set", "level": 70})
        self.assertTrue(res["ok"])
        self.assertEqual(res["level"], 70)
        self.assertEqual(res.get("delegated_from"), "device_settings.brightness_set")
        # el script WMI debe llevar el nivel 70
        self.assertIn("70", run.call_args.args[0][-1])

    def test_device_settings_brightness_up_uses_delta(self):
        # brightness_get devuelve 40 -> up (+20) -> 60
        def _run(cmd, *a, **k):
            if "WmiMonitorBrightnessMethods" in cmd[-1]:
                return self._ps_ok()                 # set
            return self._ps_ok('{"CurrentBrightness": 40}')  # get
        with mock.patch("gemma4_agent.tools.subprocess.run", side_effect=_run):
            res = self.tools.t_device_settings({"action": "brightness_up"})
        self.assertTrue(res["ok"])
        self.assertEqual(res["level"], 60)

    def test_device_settings_brightness_down_uses_delta(self):
        def _run(cmd, *a, **k):
            if "WmiMonitorBrightnessMethods" in cmd[-1]:
                return self._ps_ok()
            return self._ps_ok('{"CurrentBrightness": 50}')
        with mock.patch("gemma4_agent.tools.subprocess.run", side_effect=_run):
            res = self.tools.t_device_settings({"action": "brightness_down"})
        self.assertEqual(res["level"], 30)

    # --- system path acepta las mismas variantes ---
    def test_system_brightness_up_variant(self):
        def _run(cmd, *a, **k):
            if "WmiMonitorBrightnessMethods" in cmd[-1]:
                return self._ps_ok()
            return self._ps_ok('{"CurrentBrightness": 90}')
        with mock.patch("gemma4_agent.tools.subprocess.run", side_effect=_run):
            res = self.tools.t_system({"action": "brightness_up"})
        # 90 + 20 -> clamp 100
        self.assertEqual(res["level"], 100)

    def test_system_set_brightness_alias(self):
        with mock.patch("gemma4_agent.tools.subprocess.run",
                        return_value=self._ps_ok()):
            res = self.tools.t_system({"action": "set_brightness", "level": 25})
        self.assertEqual(res["level"], 25)

    # --- delta sin DDC/CI (monitor desktop, get devuelve null) parte de 50 ---
    def test_delta_without_ddc_falls_back_to_midpoint(self):
        def _run(cmd, *a, **k):
            if "WmiMonitorBrightnessMethods" in cmd[-1]:
                return self._ps_ok()
            return self._ps_ok("null")  # WmiMonitorBrightness null
        with mock.patch("gemma4_agent.tools.subprocess.run", side_effect=_run):
            res = self.tools.system_brightness_set({"delta": 10})
        self.assertEqual(res["level"], 60)  # 50 + 10

    # --- regresión: device_settings NO-brillo sigue yendo al tool normal ---
    def test_device_settings_non_brightness_unaffected(self):
        with mock.patch("gemma4_agent.tools.shutil.which", return_value="netsh"):
            res = self.tools.t_device_settings({"action": "status"})
        self.assertIsNone(res.get("delegated_from"))


if __name__ == "__main__":
    unittest.main()
