"""Reply validator detects structural anti-patterns post-reply.

Hotfix I 2026-05-17.
"""
from __future__ import annotations

import unittest

from gemma4_agent.reply_validator import (
    LISTO_REGEN_HINT,
    is_listo_on_no_tool_turn,
)


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


if __name__ == "__main__":
    unittest.main()
