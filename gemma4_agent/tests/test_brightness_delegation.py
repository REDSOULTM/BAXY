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

    def _ps_fail(self, stderr="WMI error", returncode=1):
        m = mock.Mock(); m.returncode = returncode; m.stdout = ""; m.stderr = stderr
        return m

    def _stateful_monitor(self, start: int):
        """Mock subprocess.run que modela un monitor REAL: el set aplica el nivel y
        el GET posterior lo refleja (necesario ahora que brightness_set re-lee para
        verificar — un GET que devolviera siempre el valor viejo simularía un panel
        que ignora el set, que es justo el caso (b) 'no confirmado')."""
        state = {"level": start}
        rx = "WmiSetBrightness(1,"

        def _run(cmd, *a, **k):
            script = cmd[-1]
            if "WmiMonitorBrightnessMethods" in script and rx in script:
                # parsear el nivel del set y aplicarlo al estado
                tail = script.split(rx, 1)[1]
                num = tail.split(")", 1)[0]
                state["level"] = int(num)
                return self._ps_ok()  # set: stdout vacío
            return self._ps_ok('{"CurrentBrightness": %d}' % state["level"])  # get

        return _run

    # --- device_settings delega a system brightness ---
    def test_device_settings_brightness_set_delegates(self):
        with mock.patch("gemma4_agent.tools.subprocess.run",
                        return_value=self._ps_ok()) as run:
            res = self.tools.t_device_settings({"action": "brightness_set", "level": 70})
        self.assertTrue(res["ok"])
        self.assertEqual(res["level"], 70)
        self.assertEqual(res.get("delegated_from"), "device_settings.brightness_set")
        # el script WMI del SET debe llevar el nivel 70 (ahora hay un GET de
        # re-lectura posterior, así que buscamos en la llamada que SETea, no en
        # la última).
        set_scripts = [c.args[0][-1] for c in run.call_args_list
                       if "WmiSetBrightness" in c.args[0][-1]]
        self.assertTrue(set_scripts)
        self.assertIn("70", set_scripts[0])

    def test_device_settings_brightness_up_uses_delta(self):
        # brightness_get devuelve 40 -> up (+20) -> 60 (monitor stateful re-lee 60)
        with mock.patch("gemma4_agent.tools.subprocess.run",
                        side_effect=self._stateful_monitor(40)):
            res = self.tools.t_device_settings({"action": "brightness_up"})
        self.assertTrue(res["ok"])
        self.assertEqual(res["level"], 60)
        self.assertTrue(res["verified"])  # re-leído y confirmado

    def test_device_settings_brightness_down_uses_delta(self):
        with mock.patch("gemma4_agent.tools.subprocess.run",
                        side_effect=self._stateful_monitor(50)):
            res = self.tools.t_device_settings({"action": "brightness_down"})
        self.assertEqual(res["level"], 30)
        self.assertTrue(res["verified"])

    # --- system path acepta las mismas variantes ---
    def test_system_brightness_up_variant(self):
        with mock.patch("gemma4_agent.tools.subprocess.run",
                        side_effect=self._stateful_monitor(90)):
            res = self.tools.t_system({"action": "brightness_up"})
        # 90 + 20 -> clamp 100
        self.assertEqual(res["level"], 100)
        self.assertTrue(res["verified"])

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

    # --- HONESTIDAD (NO MENTIR): tri-estado post-set re-read ---------------
    # brightness_set era fire-and-hope (verified=False fijo). Ahora re-lee el
    # nivel post-set y distingue 3 estados, igual que audio_set_volume/keypress.

    def test_set_confirmed_when_reread_matches(self):
        # (c) CONFIRMADO: set 50, GET post devuelve 50 -> verified=True.
        with mock.patch("gemma4_agent.tools.subprocess.run",
                        side_effect=self._stateful_monitor(10)):
            res = self.tools.system_brightness_set({"level": 50})
        self.assertTrue(res["ok"])
        self.assertIs(res["verified"], True)
        self.assertEqual(res["level"], 50)
        self.assertEqual(res["requested"], 50)

    def test_set_unconfirmed_when_panel_ignores(self):
        # (b) NO CONFIRMADO: set 50 pero el panel NO cambia (GET post = 30).
        # WMI acepta el set (returncode 0) pero el brillo no se movió ->
        # verified=False, ok=False honesto, NO afirmar éxito plano.
        def _run(cmd, *a, **k):
            if "WmiMonitorBrightnessMethods" in cmd[-1]:
                return self._ps_ok()  # set "ok" pero el panel lo ignora
            return self._ps_ok('{"CurrentBrightness": 30}')  # GET siempre 30
        with mock.patch("gemma4_agent.tools.subprocess.run", side_effect=_run):
            res = self.tools.system_brightness_set({"level": 50})
        self.assertFalse(res["ok"])
        self.assertIs(res["verified"], False)
        self.assertEqual(res["requested"], 50)
        self.assertEqual(res["level"], 30)  # reporta lo MEDIDO, no lo pedido
        self.assertEqual(res.get("reason"), "brightness_unchanged")

    def test_set_dispatched_when_not_measurable(self):
        # entre (a) y (c): set NO falla pero el GET post no es medible (null) ->
        # verified=None (dispatched), honesto "no se pudo confirmar", NO es fallo.
        def _run(cmd, *a, **k):
            if "WmiMonitorBrightnessMethods" in cmd[-1]:
                return self._ps_ok()
            return self._ps_ok("null")  # WmiMonitorBrightness null
        with mock.patch("gemma4_agent.tools.subprocess.run", side_effect=_run):
            res = self.tools.system_brightness_set({"level": 50})
        self.assertTrue(res["ok"])           # no es un fallo
        self.assertIsNone(res["verified"])   # pero NO confirmado
        self.assertEqual(res["level"], 50)
        self.assertEqual(res.get("status"), "dispatched")

    def test_set_os_unsupported_is_honest_not_a_lie(self):
        # (a) FALLO DEL SO: WMI rechaza el set (returncode != 0) -> _err honesto
        # con hint de hardware. NO afirma éxito (ok=False, verified=False).
        with mock.patch("gemma4_agent.tools.subprocess.run",
                        return_value=self._ps_fail("WmiSetBrightness failed")):
            res = self.tools.system_brightness_set({"level": 50})
        self.assertFalse(res["ok"])
        self.assertEqual(res.get("reason"), "wmi_unsupported")
        self.assertIn("hint", res)

    def test_set_tolerance_5pct(self):
        # paneles cuantizan a pasos: set 50 / GET post 53 (±5%) -> verified=True.
        def _run(cmd, *a, **k):
            if "WmiMonitorBrightnessMethods" in cmd[-1]:
                return self._ps_ok()
            return self._ps_ok('{"CurrentBrightness": 53}')
        with mock.patch("gemma4_agent.tools.subprocess.run", side_effect=_run):
            res = self.tools.system_brightness_set({"level": 50})
        self.assertTrue(res["ok"])
        self.assertIs(res["verified"], True)
        self.assertEqual(res["level"], 53)  # reporta el nivel medido real

    # --- regresión: device_settings NO-brillo sigue yendo al tool normal ---
    def test_device_settings_non_brightness_unaffected(self):
        with mock.patch("gemma4_agent.tools.shutil.which", return_value="netsh"):
            res = self.tools.t_device_settings({"action": "status"})
        self.assertIsNone(res.get("delegated_from"))


if __name__ == "__main__":
    unittest.main()
