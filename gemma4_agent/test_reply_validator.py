"""Reply validator detects structural anti-patterns post-reply.

Hotfix I 2026-05-17.
"""
from __future__ import annotations

import unittest

from gemma4_agent.reply_validator import (
    LISTO_REGEN_HINT,
    is_listo_on_no_tool_turn,
    is_unverified_claim,
    UNVERIFIED_CLAIM_REGEN_HINT,
    _ensure_claim_centroids,
)

_HAS_ENCODER = _ensure_claim_centroids()


class ListoValidatorTest(unittest.TestCase):
    def test_listo_with_no_tool_calls_triggers(self) -> None:
        self.assertTrue(is_listo_on_no_tool_turn("Listo, hecho.", []))

    def test_listo_with_successful_tool_does_not_trigger(self) -> None:
        # 'Listo' is OK post-tool — the prompt teaches it.
        calls = [{"tool": "app", "result": {"ok": True, "verified": True}}]
        self.assertFalse(is_listo_on_no_tool_turn("Listo, abrí Chrome.", calls))

    def test_non_listo_reply_does_not_trigger(self) -> None:
        self.assertFalse(is_listo_on_no_tool_turn("De nada.", []))

    def test_listo_with_only_unverified_calls_triggers(self) -> None:
        # An unverified tool result doesn't count as 'tool ran'.
        calls = [{"tool": "app", "result": {"ok": False}}]
        self.assertTrue(is_listo_on_no_tool_turn("Listo.", calls))

    def test_listo_with_needs_confirmation_call_triggers(self) -> None:
        # needs_confirmation status is unverified.
        calls = [{"tool": "x", "result": {"ok": True, "status": "needs_confirmation"}}]
        self.assertTrue(is_listo_on_no_tool_turn("Listo.", calls))

    def test_listo_case_insensitive(self) -> None:
        self.assertTrue(is_listo_on_no_tool_turn("LISTO!", []))
        self.assertTrue(is_listo_on_no_tool_turn("listo,", []))

    def test_listo_with_trailing_punctuation_variants(self) -> None:
        self.assertTrue(is_listo_on_no_tool_turn("Listo!", []))
        self.assertTrue(is_listo_on_no_tool_turn("Listo, terminé.", []))
        self.assertTrue(is_listo_on_no_tool_turn("Listo. Algo más?", []))

    def test_word_starting_with_listo_does_not_match(self) -> None:
        # Defensive: a sentence starting with 'listones' or
        # similar should NOT match — \b enforces word boundary.
        self.assertFalse(is_listo_on_no_tool_turn("Listones de madera", []))

    def test_hint_text_is_non_empty(self) -> None:
        self.assertGreater(len(LISTO_REGEN_HINT), 50)

    def test_empty_reply_does_not_trigger(self) -> None:
        self.assertFalse(is_listo_on_no_tool_turn("", []))


class UnverifiedClaimTest(unittest.TestCase):
    """Guarda estructural: el reply afirma un efecto externo sin tool verificada.
    Multilingüe (embeddings) + fallback seguro (sin encoder no flaggea)."""

    _OK = {"ok": True, "verified": True}
    _BAD = {"ok": False}

    def test_no_encoder_never_flags(self):
        # invariante de seguridad: sin encoder, jamás molesta
        import gemma4_agent.reply_validator as rv
        saved = (rv._CC.ready, rv._CC.claim, rv._CC.conv)
        rv._CC.ready, rv._CC.claim, rv._CC.conv = True, None, None
        try:
            self.assertFalse(is_unverified_claim("ya abrí la calculadora", []))
        finally:
            rv._CC.ready, rv._CC.claim, rv._CC.conv = saved

    def test_short_reply_never_flags(self):
        self.assertFalse(is_unverified_claim("ok", []))

    def test_claim_with_successful_tool_not_flagged(self):
        # afirmación SUSTENTADA por una tool exitosa -> OK
        self.assertFalse(is_unverified_claim("ya abrí la calculadora",
                                             [{"result": self._OK}]))

    def test_hint_non_empty(self):
        self.assertGreater(len(UNVERIFIED_CLAIM_REGEN_HINT), 50)

    @unittest.skipUnless(_HAS_ENCODER, "encoder multilingüe no disponible")
    def test_claim_without_tool_flagged_multilang(self):
        for reply in ("ya abrí la calculadora", "the window is now open",
                      "listo, subí el volumen"):
            self.assertTrue(is_unverified_claim(reply, []), reply)

    @unittest.skipUnless(_HAS_ENCODER, "encoder multilingüe no disponible")
    def test_conversational_not_flagged(self):
        for reply in ("¿cuál archivo querés abrir?", "no estoy seguro de qué pediste",
                      "no tengo esa herramienta"):
            self.assertFalse(is_unverified_claim(reply, []), reply)

    @unittest.skipUnless(_HAS_ENCODER, "encoder multilingüe no disponible")
    def test_claim_with_failed_tool_flagged(self):
        # tool corrió pero falló -> la afirmación NO está sustentada -> flag
        self.assertTrue(is_unverified_claim("listo, lo cerré", [{"result": self._BAD}]))


if __name__ == "__main__":
    unittest.main()
