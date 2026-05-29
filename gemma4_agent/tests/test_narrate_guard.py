"""Tests para la guarda anti-respuesta-muda (modo no_vidente, B4).

Pura lógica (longitud + tool-éxito), sin embeddings -> determinista. Mock-only.
"""
from __future__ import annotations

import unittest

from gemma4_agent.safety_pkg.reply_validator import (
    reply_too_terse_for_blind,
    NARRATE_ACTION_REGEN_HINT,
)


def _ok_call():
    return [{"tool": "app", "result": {"ok": True, "verified": True}}]


def _failed_call():
    return [{"tool": "app", "result": {"ok": False}}]


class TerseReplyForBlindTest(unittest.TestCase):
    def test_terse_ack_after_successful_action_flags(self):
        self.assertTrue(reply_too_terse_for_blind("Listo.", _ok_call()))
        self.assertTrue(reply_too_terse_for_blind("Hecho", _ok_call()))
        self.assertTrue(reply_too_terse_for_blind("Ok, listo", _ok_call()))

    def test_empty_reply_after_action_flags(self):
        self.assertTrue(reply_too_terse_for_blind("", _ok_call()))
        self.assertTrue(reply_too_terse_for_blind("   ", _ok_call()))

    def test_descriptive_reply_does_not_flag(self):
        self.assertFalse(reply_too_terse_for_blind(
            "Abrí Spotify y está sonando tu lista de Favoritos ahora mismo.",
            _ok_call()))
        self.assertFalse(reply_too_terse_for_blind(
            "Listo, abrí el editor de texto y la ventana quedó al frente, vacía.",
            _ok_call()))

    def test_terse_reply_without_any_tool_does_not_flag(self):
        # sin acción que narrar, un reply corto es válido (charla, saludo).
        self.assertFalse(reply_too_terse_for_blind("Listo.", []))
        self.assertFalse(reply_too_terse_for_blind("Hola, ¿en qué ayudo?", []))

    def test_terse_reply_after_FAILED_tool_does_not_flag(self):
        # la tool falló -> no hubo efecto que narrar; el reply maneja el fallo.
        self.assertFalse(reply_too_terse_for_blind("No pude.", _failed_call()))

    def test_hint_mentions_no_vidente_and_describe(self):
        self.assertIn("NO VIDENTE", NARRATE_ACTION_REGEN_HINT)
        self.assertIn("Describí", NARRATE_ACTION_REGEN_HINT)


if __name__ == "__main__":
    unittest.main()
