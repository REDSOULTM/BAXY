"""Tests for _translate_keys_to_sendkeys + window.focus visibility rule."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from ..tools_pkg.tools import _translate_keys_to_sendkeys


class TestSendKeysTranslator(unittest.TestCase):
    """Asegura que 'ctrl+f' no quede como texto literal."""

    def test_enter(self):
        self.assertEqual(_translate_keys_to_sendkeys("enter"), "{ENTER}")
        self.assertEqual(_translate_keys_to_sendkeys("ENTER"), "{ENTER}")
        self.assertEqual(_translate_keys_to_sendkeys("Return"), "{ENTER}")

    def test_ctrl_f(self):
        # El bug del 2026-05-15: ctrl+f quedaba como literal "ctrl+f" en el chat.
        self.assertEqual(_translate_keys_to_sendkeys("ctrl+f"), "^f")
        self.assertEqual(_translate_keys_to_sendkeys("Ctrl+F"), "^f")
        self.assertEqual(_translate_keys_to_sendkeys("CTRL+F"), "^f")

    def test_ctrl_combinations(self):
        for combo, expected in [
            ("ctrl+a", "^a"),
            ("ctrl+c", "^c"),
            ("ctrl+v", "^v"),
            ("ctrl+x", "^x"),
            ("ctrl+z", "^z"),
            ("ctrl+s", "^s"),
            ("ctrl+n", "^n"),
        ]:
            self.assertEqual(_translate_keys_to_sendkeys(combo), expected, combo)

    def test_multi_modifier(self):
        self.assertEqual(_translate_keys_to_sendkeys("ctrl+shift+t"), "^+t")
        self.assertEqual(_translate_keys_to_sendkeys("ctrl+alt+del"), "^%{DELETE}")
        self.assertEqual(_translate_keys_to_sendkeys("ctrl+shift+escape"), "^+{ESC}")

    def test_alt_f4(self):
        self.assertEqual(_translate_keys_to_sendkeys("alt+f4"), "%{F4}")
        self.assertEqual(_translate_keys_to_sendkeys("Alt+F4"), "%{F4}")

    def test_function_keys(self):
        self.assertEqual(_translate_keys_to_sendkeys("f1"), "{F1}")
        self.assertEqual(_translate_keys_to_sendkeys("F12"), "{F12}")

    def test_arrows_and_nav(self):
        self.assertEqual(_translate_keys_to_sendkeys("up"), "{UP}")
        self.assertEqual(_translate_keys_to_sendkeys("down"), "{DOWN}")
        self.assertEqual(_translate_keys_to_sendkeys("home"), "{HOME}")
        self.assertEqual(_translate_keys_to_sendkeys("pgdn"), "{PGDN}")
        self.assertEqual(_translate_keys_to_sendkeys("pageup"), "{PGUP}")

    def test_space(self):
        self.assertEqual(_translate_keys_to_sendkeys("space"), " ")

    def test_passthrough_sendkeys_syntax(self):
        # Si ya viene en SendKeys, no tocar.
        self.assertEqual(_translate_keys_to_sendkeys("^f"), "^f")
        self.assertEqual(_translate_keys_to_sendkeys("{ENTER}"), "{ENTER}")
        self.assertEqual(_translate_keys_to_sendkeys("%{F4}"), "%{F4}")

    def test_single_letter(self):
        self.assertEqual(_translate_keys_to_sendkeys("a"), "a")
        self.assertEqual(_translate_keys_to_sendkeys("Z"), "Z")

    def test_empty(self):
        self.assertEqual(_translate_keys_to_sendkeys(""), "")
        self.assertEqual(_translate_keys_to_sendkeys("   "), "")


class TestWhatsAppGuiUsesCorrectHotkey(unittest.TestCase):
    """Verifica que _whatsapp_send_via_gui_search use keypress estructural."""

    def test_gui_dispatch_preserves_keypress_method(self):
        from ..tools_pkg.tools import ToolRegistry

        class Dummy:
            seen = None

            def gui_keypress(self, args):
                self.seen = dict(args)
                return {"ok": True}

        dummy = Dummy()
        ToolRegistry._gui_dispatch_raw(
            dummy,
            "keypress",
            {"action": "keypress", "keys": "ctrl+n",
             "method": "sendkeys", "window": "WhatsApp"},
        )
        self.assertEqual(dummy.seen["keys"], "ctrl+n")
        self.assertEqual(dummy.seen["method"], "sendkeys")
        self.assertEqual(dummy.seen["window"], "WhatsApp")

    def test_keypresses_structural_not_typed_literal(self):
        # ACTUALIZADO (2026-06-01): el flujo viejo usaba Ctrl+N (nuevo chat); d3bf5a1 lo
        # cambió al BUSCADOR PRINCIPAL (type contacto + Down + Enter) porque Ctrl+N NO
        # halla grupos. El valor del test se conserva: los combos van por keypress
        # estructural (method=sendkeys), NUNCA tecleados como texto literal (el bug
        # original 2026-05-15 de "ctrl+f" como texto en el chat).
        from ..domain_tools import _whatsapp_send_via_gui_search
        calls = []
        def _exec(name, args):
            calls.append((name, dict(args)))
            if name == "window" and args.get("action") == "focus":
                return {"ok": True}
            if name == "window" and args.get("action") == "active":
                return {"ok": True, "active": {"title": "WhatsApp"}}
            if name == "gui":
                return {"ok": True}
            return {"ok": False}
        with patch("gemma4_agent.domain_tools.subprocess.Popen"), \
             patch("time.sleep"):
            r = _whatsapp_send_via_gui_search(_exec, "Amor", "te amo", 0.5, True)
        # El flujo nuevo usa keypress estructural (down/enter/ctrl+a) por sendkeys.
        keypress_calls = [
            args for name, args in calls
            if name == "gui" and args.get("action") == "keypress"
        ]
        self.assertGreaterEqual(len(keypress_calls), 1,
                                f"expected structural keypresses, got calls: {calls}")
        self.assertTrue(
            all(a.get("method") == "sendkeys" for a in keypress_calls),
            f"los keypress de WhatsApp deben forzar sendkeys: {keypress_calls}")
        # IMPORTANTE: NUNCA un combo (ctrl+...) tecleado como texto literal (bug original).
        bad_type_calls = [
            args for name, args in calls
            if name == "gui" and args.get("action") == "type"
            and "ctrl" in str(args.get("text", "")).lower()
        ]
        self.assertEqual(len(bad_type_calls), 0,
                         f"un combo NUNCA debe teclearse como texto: {bad_type_calls}")


if __name__ == "__main__":
    unittest.main()
