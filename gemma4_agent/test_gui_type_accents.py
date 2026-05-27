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
             patch.object(ToolRegistry, "_foreground_is_chromium", return_value=False), \
             patch.object(ToolRegistry, "_gui_type_via_paste") as paste:
            out = self.reg.gui_type({"text": "mamá"})
        si.assert_called_once()
        paste.assert_not_called()
        self.assertEqual(out.get("method"), "sendinput")

    def test_accented_text_falls_back_to_paste_without_sendinput(self):
        # Si SendInput no está disponible (no-Windows / sin ctypes -> None), el
        # texto con acentos cae a clipboard-paste (UTF-8-safe), preservando el fix.
        with patch.object(ToolRegistry, "_send_text_via_sendinput", return_value=None), \
             patch.object(ToolRegistry, "_foreground_is_chromium", return_value=False), \
             patch.object(ToolRegistry, "_gui_type_via_paste",
                          return_value={"ok": True, "method": "paste", "chars": 4}) as paste:
            out = self.reg.gui_type({"text": "mamá"})
        paste.assert_called_once()
        self.assertEqual(out.get("method"), "paste")

    def test_ascii_text_uses_sendinput(self):
        # "hello world" ASCII puro -> SendInput in-process (no toca el clipboard).
        with patch.object(ToolRegistry, "_send_text_via_sendinput",
                          return_value={"ok": True, "method": "sendinput", "events": 22}) as si, \
             patch.object(ToolRegistry, "_foreground_is_chromium", return_value=False), \
             patch.object(ToolRegistry, "_gui_type_via_paste") as paste:
            out = self.reg.gui_type({"text": "hello world"})
        si.assert_called_once()
        paste.assert_not_called()
        self.assertEqual(out.get("method"), "sendinput")

    def test_webview_text_uses_paste_not_sendinput(self):
        # WhatsApp/Discord son WebView2/Electron: SendInput no entra fiable al input
        # web. En ese foreground, gui_type debe saltar SendInput y pegar.
        with patch.object(ToolRegistry, "_foreground_is_chromium", return_value=True), \
             patch.object(ToolRegistry, "_send_text_via_sendinput") as si, \
             patch.object(ToolRegistry, "_gui_type_via_paste",
                          return_value={"ok": True, "method": "paste", "chars": 5}) as paste:
            out = self.reg.gui_type({"text": "hello"})
        si.assert_not_called()
        paste.assert_called_once()
        self.assertEqual(out.get("method"), "paste")

    def test_forced_sendkeys_never_uses_clipboard(self):
        # WhatsApp puede pedir escritura real sin tocar el portapapeles.
        import subprocess
        with patch.object(ToolRegistry, "_foreground_is_chromium", return_value=True), \
             patch.object(ToolRegistry, "_send_text_via_sendinput") as si, \
             patch.object(ToolRegistry, "_gui_type_via_paste") as paste, \
             patch("gemma4_agent.tools.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            out = self.reg.gui_type({"text": "hello", "method": "sendkeys"})
        si.assert_not_called()
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


def _fake_sendinput_machine():
    """Maquina SendInput de mentira: cuenta eventos pero NO toca el teclado real.

    CRITICO (2026-05-25): _keypress_via_sendinput llama user32.SendInput de VERDAD
    via ctypes. Como Claude Code corre como TERMINAL DE VS CODE, un combo real como
    'alt+f4' o 'ctrl+w' cierra VS Code (Claude se mata a si mismo y el user pierde
    su trabajo). Pasó >=3 veces. Estos tests verifican la CONSTRUCCION de los eventos,
    NUNCA su emisión: mockeamos _sendinput_machine para que SendInput sea un no-op.
    """
    class _KI:
        def __init__(self, *a, **k): pass
    class _U:
        ki = None
    class _INMeta(type):
        # (_INPUT * n) se resuelve en la METACLASE; devuelve un ctor (*seq)->list.
        def __mul__(cls, n):
            return lambda *items: list(items)
    class _IN(metaclass=_INMeta):
        def __init__(self, *a, **k):
            self.type = 0
            self.u = _U()
    class _User32:
        def SendInput(self, n, buf, size):
            return n  # devuelve el conteo, sin emitir NADA al teclado real
    return {"user32": _User32(), "INPUT": _IN, "KEYBD": _KI, "size": 40}


class KeypressComboTest(unittest.TestCase):
    """Combos con modificador (ctrl+k, ctrl+shift+t, alt+f4) deben ir por SendInput
    IN-PROCESS, no por PowerShell-SendKeys (cuyo cold-start + parpadeo de consola
    roba/devuelve el foreground y hacía que ctrl+k a Discord no aterrizara fiable,
    bug medido 2026-05-25). _keypress_via_sendinput ahora mapea modificador(es) +
    tecla base. None solo si algún token no se puede mapear (cae a SendKeys).

    SEGURIDAD: _sendinput_machine SIEMPRE mockeado -> SendInput jamás emite teclas
    reales (si no, 'alt+f4' cierra VS Code; ver _fake_sendinput_machine)."""

    def setUp(self):
        self.reg = ToolRegistry.__new__(ToolRegistry)

    def test_modifier_combos_go_in_process(self):
        with patch("gemma4_agent.tools._sendinput_machine",
                   side_effect=lambda: _fake_sendinput_machine()):
            for combo, n_events in (("ctrl+k", 4), ("ctrl+a", 4),
                                    ("ctrl+shift+t", 6), ("alt+f4", 4),
                                    ("enter", 2), ("f5", 2)):
                r = self.reg._keypress_via_sendinput(combo)
                self.assertIsNotNone(r, combo)
                self.assertTrue(r.get("ok"), combo)
                self.assertEqual(r.get("method"), "sendinput", combo)
                self.assertEqual(r.get("events"), n_events, combo)

    def test_unknown_modifier_falls_back(self):
        # un modificador no mapeable -> None (el caller usa SendKeys legacy).
        # Mock de SendInput igual, por si el mapeo cambiara y llegara a emitir.
        with patch("gemma4_agent.tools._sendinput_machine",
                   side_effect=lambda: _fake_sendinput_machine()):
            self.assertIsNone(self.reg._keypress_via_sendinput("hyper+x"))

    def test_webview_keypress_uses_sendkeys_not_sendinput(self):
        # En WhatsApp/Discord, ctrl+f/ctrl+k deben volver al camino pre-23:
        # PowerShell SendKeys. SendInput queda para apps nativas.
        import subprocess
        with patch.object(ToolRegistry, "_foreground_is_chromium", return_value=True), \
             patch.object(ToolRegistry, "_keypress_via_sendinput") as si, \
             patch("gemma4_agent.tools.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            out = self.reg.gui_keypress({"keys": "ctrl+f"})
        si.assert_not_called()
        self.assertEqual(out.get("method"), "sendkeys")
        self.assertEqual(out.get("sendkeys"), "^f")


if __name__ == "__main__":
    unittest.main()
