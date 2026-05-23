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

    def test_accented_text_uses_paste(self):
        # "mamá" tiene 'á' (>127) -> debe ir por clipboard-paste.
        with patch.object(ToolRegistry, "_gui_type_via_paste",
                          return_value={"ok": True, "method": "paste", "chars": 4}) as paste:
            out = self.reg.gui_type({"text": "mamá"})
        paste.assert_called_once()
        self.assertEqual(out.get("method"), "paste")

    def test_ascii_text_uses_sendkeys(self):
        # "hello" es ASCII puro -> NO debe tocar el clipboard (usa SendKeys).
        import subprocess
        with patch.object(ToolRegistry, "_gui_type_via_paste") as paste, \
             patch("gemma4_agent.tools.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            out = self.reg.gui_type({"text": "hello world"})
        paste.assert_not_called()
        self.assertEqual(out.get("method"), "sendkeys")

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
