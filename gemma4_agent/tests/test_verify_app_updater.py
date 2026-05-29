"""R4: verify_app_opened debe descartar matches de UPDATER (Squirrel/Update.exe)
para no dar false-PASS con la ventana transitoria del instalador (Discord)."""
from __future__ import annotations

import unittest

import gemma4_agent.tools_pkg.tools as T


class UpdaterFilterTest(unittest.TestCase):
    def setUp(self):
        # instancia sin __init__ pesado: solo probamos métodos puros
        self.tb = T.ToolRegistry.__new__(T.ToolRegistry)

    def test_is_updater_proc(self):
        for p in ("Update.exe", "squirrel.exe", "Setup.exe", "Updater.exe",
                  "vcredist_x64.exe", "msiexec.exe"):
            self.assertTrue(self.tb._is_updater_proc(p), p)
        for p in ("Discord.exe", "msedge.exe", "EXCEL.EXE", "notepad.exe", ""):
            self.assertFalse(self.tb._is_updater_proc(p), p)


class VerifyAppOpenedUpdaterTest(unittest.TestCase):
    """verify_app_opened con list_processes/list_windows mockeados: el caso
    'solo el updater está visible' debe dar found=False + updater_only=True."""

    def _make(self, processes, windows):
        tb = T.ToolRegistry.__new__(T.ToolRegistry)
        tb.list_processes = lambda a: {"processes": processes}
        tb.list_windows = lambda a: {"windows": windows}
        # _match_query real (substring/token); lo tomamos de la clase
        return tb

    def test_updater_only_not_found(self):
        # Solo el updater de Squirrel visible: proceso Update.exe + ventana
        # "Discord Updater" (proceso vacío). NO debe contar como "Discord abierto".
        tb = self._make(
            processes=[{"name": "Update.exe"}],
            windows=[{"process": "", "title": "Discord Updater", "pid": 1, "hwnd": 1}],
        )
        r = tb.verify_app_opened({"name": "Discord"})
        self.assertFalse(r["found"])
        self.assertTrue(r["updater_only"])

    def test_real_app_found(self):
        # Discord.exe real corriendo -> found=True, no updater_only.
        tb = self._make(
            processes=[{"name": "Discord.exe"}],
            windows=[{"process": "Discord.exe", "title": "Amigos - Discord", "pid": 2, "hwnd": 2}],
        )
        r = tb.verify_app_opened({"name": "Discord"})
        self.assertTrue(r["found"])
        self.assertFalse(r["updater_only"])

    def test_real_app_coexists_with_updater(self):
        # Discord.exe real + ventana del updater a la vez -> found=True (gana lo real).
        tb = self._make(
            processes=[{"name": "Discord.exe"}, {"name": "Update.exe"}],
            windows=[{"process": "Discord.exe", "title": "Discord", "pid": 2, "hwnd": 2},
                     {"process": "", "title": "Discord Updater", "pid": 1, "hwnd": 1}],
        )
        r = tb.verify_app_opened({"name": "Discord"})
        self.assertTrue(r["found"])
        self.assertFalse(r["updater_only"])
        # el match real no incluye procesos updater
        self.assertTrue(all("update" not in p.get("name", "").lower()
                            for p in r["process_matches"]))


if __name__ == "__main__":
    unittest.main()
