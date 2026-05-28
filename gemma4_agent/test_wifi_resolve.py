"""Resolución de WiFi por ESTADO DEL SO para usuario sin manos (2026-05-27).

El usuario dice el nombre de la red como lo recuerda ('la de la familia', 'vtr'),
no el SSID exacto guardado. _resolve_wifi_target lo matchea contra perfiles
guardados + SSIDs visibles (netsh), con desambiguación honesta. NO keywords.

Mock-only: netsh (_device_wifi_profiles/_device_wifi_scan/subprocess.run) está
mockeado — NUNCA toca la conexión real del usuario.
"""
from __future__ import annotations

import unittest
from unittest import mock

from gemma4_agent import domain_tools as dt
from gemma4_agent import domain_tools_wifi as dtw  # extraído 2026-05-27 (R2)
from gemma4_agent.state import AgentState

# El refactor R2 movió las funciones wifi a domain_tools_wifi.py; domain_tools
# las re-exporta para compat, pero los mocks de subprocess y de funciones
# wifi internas tienen que apuntar al MÓDULO REAL donde la función las
# resuelve (lookup local). dt.X siguen funcionando para acceso de lectura
# (re-export), pero mockear dt.X no afecta el binding interno de dtw.X.

# perfiles realistas (tomados de la máquina real): duplicado por case, varios VTR
REAL_PROFILES = [
    "Familia Prueba", "RV", "RV 2", "familia prueba", "WiFi_Mesh-000000",
    "VTR-0000001", "VTR-0000002-5G.", "VTR-0000003", "Galaxy Phone 5G 0000",
    "RED_LISTA", "RED3",
]


def _profiles_ret(profiles):
    return {"ok": True, "profiles": list(profiles), "count": len(profiles)}


def _scan_ret(ssids):
    return {"ok": True, "networks": [{"ssid": s} for s in ssids], "count": len(ssids)}


class WifiMatchScoreTest(unittest.TestCase):
    def test_exact_and_case(self):
        self.assertEqual(dt._wifi_match_score("RV", "RV"), 1.0)
        self.assertEqual(dt._wifi_match_score("ev", "RV"), 1.0)

    def test_substring(self):
        self.assertGreaterEqual(dt._wifi_match_score("galaxy", "Galaxy Phone 5G 0000"), 0.6)

    def test_token_overlap_full_cover_is_strong(self):
        self.assertGreaterEqual(dt._wifi_match_score("red lista", "RED_LISTA"), 0.6)

    def test_single_generic_token_in_long_phrase_is_weak(self):
        # 'red' suelto en una frase larga NO debe alcanzar el umbral fuerte
        # (sería falso positivo: conectar a la red equivocada).
        self.assertLess(dt._wifi_match_score("no existe esta red xyz", "RED_LISTA"), 0.6)

    def test_unrelated_is_zero(self):
        self.assertEqual(dt._wifi_match_score("netflix", "VTR-0000003"), 0.0)

    def test_filler_words_stripped(self):
        # "la red wifi de la familia" -> nombre real = "familia" -> matchea fuerte
        self.assertGreaterEqual(
            dt._wifi_match_score("la red wifi de la familia", "Familia Prueba"), 0.6)
        # pero el relleno NO debe crear falso match: 'red' suelta no matchea RED_LISTA
        self.assertEqual(dt._wifi_match_score("no existe esta red xyz", "RED_LISTA"), 0.0)
        self.assertEqual(dt._wifi_match_score("el wifi de casa", "RED_LISTA"), 0.0)


class ResolveWifiTargetTest(unittest.TestCase):
    def setUp(self):
        self.p = mock.patch.object(dtw, "_device_wifi_profiles",
                                   return_value=_profiles_ret(REAL_PROFILES))
        self.s = mock.patch.object(dtw, "_device_wifi_scan",
                                   return_value=_scan_ret([]))
        self.p.start(); self.s.start()
        self.addCleanup(self.p.stop); self.addCleanup(self.s.stop)

    def test_exact_profile(self):
        r = dt._resolve_wifi_target("Familia Prueba")
        self.assertEqual(r["resolved"], "Familia Prueba")
        self.assertTrue(r["exact"])

    def test_case_insensitive_exact(self):
        r = dt._resolve_wifi_target("ev 2")
        self.assertEqual(r["resolved"], "RV 2")
        self.assertEqual(r["source"], "profile")

    def test_fuzzy_single_hit(self):
        r = dt._resolve_wifi_target("galaxy")
        self.assertEqual(r["resolved"], "Galaxy Phone 5G 0000")
        self.assertFalse(r["exact"])

    def test_ambiguous_multiple_vtr_asks(self):
        r = dt._resolve_wifi_target("vtr")
        self.assertIn("ambiguous", r)
        self.assertEqual(len([x for x in r["ambiguous"] if x.startswith("VTR")]), 3)

    def test_ambiguous_familia_duplicate_asks(self):
        r = dt._resolve_wifi_target("la de la familia")
        self.assertIn("ambiguous", r)

    def test_filler_phrase_resolves_to_core_name(self):
        # frase con relleno ("conectame a la red wifi de la familia") -> 'familia'
        r = dt._resolve_wifi_target("conectame a la red wifi de la familia")
        self.assertIn("ambiguous", r)  # 2 perfiles 'familia' -> pregunta
        r2 = dt._resolve_wifi_target("la red wifi galaxy")
        self.assertEqual(r2.get("resolved"), "Galaxy Phone 5G 0000")

    def test_no_match_returns_none_with_lists(self):
        r = dt._resolve_wifi_target("una red que no existe para nada")
        self.assertTrue(r.get("none"))
        self.assertIn("profiles", r)

    def test_visible_ssid_without_profile(self):
        # un SSID visible que NO está en perfiles -> source=ssid
        with mock.patch.object(dtw, "_device_wifi_scan",
                               return_value=_scan_ret(["CAFE_INVITADOS"])):
            r = dt._resolve_wifi_target("cafe invitados")
        self.assertEqual(r.get("source"), "ssid")
        self.assertEqual(r.get("resolved"), "CAFE_INVITADOS")


class DeviceWifiConnectTest(unittest.TestCase):
    """El connect completo, con netsh (subprocess.run) MOCKEADO — no toca la red."""

    def setUp(self):
        self.p = mock.patch.object(dtw, "_device_wifi_profiles",
                                   return_value=_profiles_ret(REAL_PROFILES))
        self.s = mock.patch.object(dtw, "_device_wifi_scan",
                                   return_value=_scan_ret([]))
        self.p.start(); self.s.start()
        self.addCleanup(self.p.stop); self.addCleanup(self.s.stop)

    def _mock_run(self, returncode=0, stdout="Conexión solicitada", stderr=""):
        m = mock.Mock()
        m.returncode = returncode
        m.stdout = stdout
        m.stderr = stderr
        return m

    def test_connect_resolves_fuzzy_and_calls_netsh_with_real_name(self):
        with mock.patch.object(dtw.subprocess, "run",
                               return_value=self._mock_run()) as run:
            res = dt._device_wifi_connect({"name": "galaxy"})
        self.assertTrue(res["ok"])
        self.assertEqual(res["profile"], "Galaxy Phone 5G 0000")
        self.assertTrue(res["resolved_from_state"])
        # netsh fue llamado con el NOMBRE REAL resuelto, no con 'galaxy'
        called_args = run.call_args.args[0]
        self.assertIn("name=Galaxy Phone 5G 0000", called_args)

    def test_connect_exact_no_resolution_flag(self):
        with mock.patch.object(dtw.subprocess, "run",
                               return_value=self._mock_run()):
            res = dt._device_wifi_connect({"name": "RV"})
        self.assertTrue(res["ok"])
        self.assertEqual(res["profile"], "RV")
        self.assertFalse(res["resolved_from_state"])

    def test_connect_ambiguous_asks_without_netsh(self):
        with mock.patch.object(dtw.subprocess, "run") as run:
            res = dt._device_wifi_connect({"name": "vtr"})
        self.assertFalse(res.get("ok", False))
        self.assertEqual(res.get("status"), "needs_user")
        self.assertIn("ambiguous_matches", res)
        run.assert_not_called()  # NO conectó a nada ambiguo

    def test_connect_visible_ssid_without_password_asks(self):
        with mock.patch.object(dtw, "_device_wifi_scan",
                               return_value=_scan_ret(["HOTEL_WIFI"])), \
             mock.patch.object(dtw.subprocess, "run") as run:
            res = dt._device_wifi_connect({"name": "hotel wifi"})
        self.assertFalse(res.get("ok", False))
        self.assertEqual(res.get("status"), "needs_user")
        run.assert_not_called()

    def test_connect_visible_ssid_with_password_creates_profile(self):
        created = {"ok": True, "profile_added": "HOTEL_WIFI"}
        with mock.patch.object(dtw, "_device_wifi_scan",
                               return_value=_scan_ret(["HOTEL_WIFI"])), \
             mock.patch.object(dtw, "_device_wifi_add_profile",
                               return_value=created) as add, \
             mock.patch.object(dtw.subprocess, "run",
                               return_value=self._mock_run()):
            res = dt._device_wifi_connect({"name": "hotel wifi", "password": "12345678"})
        self.assertTrue(res["ok"])
        add.assert_called_once()
        self.assertEqual(res["profile"], "HOTEL_WIFI")

    def test_connect_unknown_with_password_creates_as_new_ssid(self):
        created = {"ok": True, "profile_added": "NuevaRed"}
        with mock.patch.object(dtw, "_device_wifi_add_profile",
                               return_value=created) as add, \
             mock.patch.object(dtw.subprocess, "run",
                               return_value=self._mock_run()):
            res = dt._device_wifi_connect({"name": "NuevaRed", "password": "claveSegura1"})
        self.assertTrue(res["ok"])
        add.assert_called_once()

    def test_connect_unknown_no_password_asks_honestly(self):
        with mock.patch.object(dtw.subprocess, "run") as run:
            res = dt._device_wifi_connect({"name": "red inexistente zzz"})
        self.assertFalse(res.get("ok", False))
        self.assertEqual(res.get("status"), "needs_user")
        run.assert_not_called()

    def test_missing_name(self):
        res = dt._device_wifi_connect({})
        self.assertFalse(res.get("ok", False))


class NetworkDelegatesWifiConnectTest(unittest.TestCase):
    """El modelo chico a veces rutea 'conectá a la red X' a `network` en vez de
    device_settings. network_tool debe DELEGAR a la conexión WiFi real (no fallar
    con 'unknown action'). netsh mockeado — no toca la red."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.state = AgentState(Path(tempfile.mkdtemp()) / "s.json")
        self.p = mock.patch.object(dtw, "_device_wifi_profiles",
                                   return_value=_profiles_ret(REAL_PROFILES))
        self.s = mock.patch.object(dtw, "_device_wifi_scan",
                                   return_value=_scan_ret([]))
        self.p.start(); self.s.start()
        self.addCleanup(self.p.stop); self.addCleanup(self.s.stop)

    def _ok_run(self):
        m = mock.Mock(); m.returncode = 0; m.stdout = "ok"; m.stderr = ""
        return m

    def test_network_connect_action_delegates(self):
        with mock.patch.object(dtw.subprocess, "run", return_value=self._ok_run()):
            res = dt.network_tool({"action": "connect", "name": "RV"}, self.state)
        self.assertTrue(res["ok"])
        self.assertEqual(res["profile"], "RV")
        self.assertEqual(res.get("delegated_from"), "network.connect")

    def test_network_name_without_action_delegates(self):
        with mock.patch.object(dtw.subprocess, "run", return_value=self._ok_run()):
            res = dt.network_tool({"name": "galaxy"}, self.state)
        self.assertTrue(res["ok"])
        self.assertEqual(res["profile"], "Galaxy Phone 5G 0000")

    def test_network_status_does_not_delegate(self):
        res = dt.network_tool({"action": "status"}, self.state)
        self.assertEqual(res.get("backend"), "windows_net")
        self.assertIsNone(res.get("delegated_from"))

    def test_network_ping_unaffected(self):
        with mock.patch.object(dtw.subprocess, "run", return_value=self._ok_run()):
            res = dt.network_tool({"action": "ping", "host": "8.8.8.8"}, self.state)
        self.assertIsNone(res.get("delegated_from"))


if __name__ == "__main__":
    unittest.main()
