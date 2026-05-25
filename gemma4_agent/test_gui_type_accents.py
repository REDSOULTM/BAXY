"""gui_type debe preservar acentos (bug 'mamá' -> 'mam?', 2026-05-23).

Causa raíz: SendKeys vía stdin de PowerShell se decodifica con la code-page de
consola (cp1252), no UTF-8. Fix: texto con caracteres no-ASCII se tipea por
clipboard-paste (tkinter, UTF-8-safe); ASCII por SendKeys vía env-var.

Estos tests verifican el RUTEO (qué método se elige) y el round-trip del
clipboard, sin tipear en una ventana real (eso requeriría una app con foco).
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from gemma4_agent.tools import ToolRegistry


class GuiTypeAccentRoutingTest(unittest.TestCase):
    def setUp(self):
        self.reg = ToolRegistry.__new__(ToolRegistry)

    def test_accented_text_uses_sendinput_first(self):
        # Migración P0 (§7.1, 2026-05-24): gui_type intenta SendInput IN-PROCESS
        # PRIMERO. SendInput maneja acentos por su rama Unicode (KEYEVENTF_UNICODE),
        # así que "mamá" NO necesita clipboard-paste si SendInput está disponible.
        # (El paste sigue como fallback si SendInput no está / falla.)
        with patch.object(ToolRegistry, "_send_text_via_sendinput",
                          return_value={"ok": True, "method": "sendinput", "events": 8}) as si, \
             patch.object(ToolRegistry, "_gui_type_via_paste") as paste:
            out = self.reg.gui_type({"text": "mamá"})
        si.assert_called_once()
        paste.assert_not_called()
        self.assertEqual(out.get("method"), "sendinput")

    def test_accented_text_falls_back_to_paste_without_sendinput(self):
        # Si SendInput no está disponible (no-Windows / sin ctypes -> None), el
        # texto con acentos cae a clipboard-paste (UTF-8-safe), preservando el fix.
        with patch.object(ToolRegistry, "_send_text_via_sendinput", return_value=None), \
             patch.object(ToolRegistry, "_gui_type_via_paste",
                          return_value={"ok": True, "method": "paste", "chars": 4}) as paste:
            out = self.reg.gui_type({"text": "mamá"})
        paste.assert_called_once()
        self.assertEqual(out.get("method"), "paste")

    def test_ascii_text_uses_sendinput(self):
        # "hello world" ASCII puro -> SendInput in-process (no toca el clipboard).
        with patch.object(ToolRegistry, "_send_text_via_sendinput",
                          return_value={"ok": True, "method": "sendinput", "events": 22}) as si, \
             patch.object(ToolRegistry, "_gui_type_via_paste") as paste:
            out = self.reg.gui_type({"text": "hello world"})
        si.assert_called_once()
        paste.assert_not_called()
        self.assertEqual(out.get("method"), "sendinput")

    def test_paste_preserves_user_clipboard(self):
        # El paste debe guardar y restaurar el portapapeles del usuario.
        calls = {"reads": 0, "writes": []}

        def fake_read(_a):
            calls["reads"] += 1
            return {"ok": True, "content": "ORIGINAL_USER_CLIP"}

        def fake_write(a):
            calls["writes"].append(a.get("content"))
            return {"ok": True}

        import subprocess
        with patch.object(ToolRegistry, "clipboard_read", side_effect=fake_read), \
             patch.object(ToolRegistry, "clipboard_write", side_effect=fake_write), \
             patch("gemma4_agent.tools.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            out = self.reg._gui_type_via_paste("café ñoño")
        self.assertTrue(out["ok"])
        # primero escribe nuestro texto, al final restaura el original
        self.assertEqual(calls["writes"][0], "café ñoño")
        self.assertEqual(calls["writes"][-1], "ORIGINAL_USER_CLIP")

    def test_clipboard_roundtrip_unicode(self):
        # tkinter clipboard preserva acentos/ñ/emoji (UTF-8-safe).
        try:
            import tkinter
            r = tkinter.Tk(); r.withdraw()
            sample = "mamá á é í ó ú ñ ¿qué? 🎵"
            r.clipboard_clear(); r.clipboard_append(sample); r.update()
            got = r.clipboard_get()
            r.destroy()
        except Exception:
            self.skipTest("tkinter/clipboard no disponible en este entorno")
        self.assertEqual(got, sample)


if __name__ == "__main__":
    unittest.main()
