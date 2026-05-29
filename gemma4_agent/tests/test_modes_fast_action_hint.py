"""Regression test for the fast_action system_hint.

User reported "Perfecto, gracias" → GEMMA responded "Listo." which is
absurd as an answer to a thank-you. The fix split the old single rule
('if a tool finished, say Listo, X.') into a positive case + an
explicit negative case ('if NO tool ran, do NOT use Listo'). This
test pins the contract on the text of the final system_hint so we
can't silently regress.

modes.py builds the fast_action mode inline inside `choose_mode`;
there is no `_build_mode_fast_action`. We force the fast_action
branch by passing `configured='fast_action'` directly.
"""
from __future__ import annotations

import unittest

from gemma4_agent.support.modes import choose_mode


class FastActionHintTest(unittest.TestCase):
    def setUp(self) -> None:
        mode = choose_mode("hola", configured="fast_action", base_max_tokens=4096)
        self.assertEqual(mode.name, "fast_action")
        self.hint = mode.system_hint or ""

    def test_hint_still_has_tool_ack_template(self) -> None:
        # The positive case must remain: tool ack uses 'Listo, X.'
        self.assertIn("Listo", self.hint)

    def test_hint_warns_against_listo_on_no_tool_turn(self) -> None:
        # The negative case must be explicit so the LLM doesn't apply
        # 'Listo' as a universal ack template.
        self.assertIn("NO tool ran", self.hint)

    def test_hint_offers_natural_social_ack_counterexample(self) -> None:
        # A concrete 'gracias → de nada' counter-example anchors the
        # LLM. 'no hay de qué' is the equivalent alternative.
        self.assertTrue(
            "de nada" in self.hint or "no hay de qué" in self.hint,
            f"hint should suggest a non-'Listo' social ack: {self.hint!r}",
        )


if __name__ == "__main__":
    unittest.main()
