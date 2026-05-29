"""Regression test for the WhatsApp tool schema's SLOT FILLING section.

User reported 'Dile a amor en wsp que la amo' was treated as
ambiguous (LLM asked for body and contact, both of which were
present). The fix adds explicit POSITIVE examples for the
'Dile/Decile/Mandale a X en wsp que Y' pattern. This test pins
that those examples remain in the schema description.

In this codebase the schemas list is `COMPOUND_TOOL_SCHEMAS` (the
prompt named `TOOL_SCHEMAS` does not exist).
"""
from __future__ import annotations

import unittest

from gemma4_agent.tools_pkg.tool_schemas import COMPOUND_TOOL_SCHEMAS


class WhatsappSchemaSlotExamplesTest(unittest.TestCase):
    def setUp(self) -> None:
        whatsapp = next(
            (s for s in COMPOUND_TOOL_SCHEMAS
             if s.get("function", {}).get("name") == "whatsapp"),
            None,
        )
        self.assertIsNotNone(whatsapp, "whatsapp schema not found")
        self.description = whatsapp["function"]["description"]

    def test_has_positive_example_dile_amor_pattern(self) -> None:
        self.assertIn("Dile a amor en wsp", self.description)

    def test_has_positive_example_mama(self) -> None:
        self.assertIn("Mandale a mama", self.description)

    def test_distinguishes_positive_from_ambiguous_section(self) -> None:
        # Both sections must exist so the LLM has a clean comparison.
        self.assertIn("POSITIVE examples", self.description)
        self.assertIn("AMBIGUOUS examples", self.description)

    def test_lists_alias_examples(self) -> None:
        # The 'amor / mama / papa / mi novio' aliases should be
        # explicitly endorsed so the LLM treats them as valid contacts.
        # We check for a representative subset.
        for alias in ("amor", "mama"):
            self.assertIn(alias, self.description)

    def test_pattern_hint_present(self) -> None:
        self.assertIn("PATTERN", self.description)


if __name__ == "__main__":
    unittest.main()
