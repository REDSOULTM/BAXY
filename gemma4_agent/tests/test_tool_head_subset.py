"""Pin the per-tool logit head's anti-bloat behaviour (2026-05-21).

The operator flagged the router offering 11 tools for trivial commands. The
per-tool head (each tool clears its OWN calibrated threshold) makes subsets
small by construction. These tests pin the contract: crisp commands yield a
SMALL subset, smalltalk/knowledge abstain, and a real command never goes empty.
We assert subset SIZE bounds and key membership, not exact tool lists (those
move when the head is retrained).
"""
from __future__ import annotations

import unittest

from gemma4_agent.routing.planner import select_tool_names, plan_mission

_UTIL = {"session", "safety", "state", "verify"}


def _domain(q: str) -> list[str]:
    t = select_tool_names(q, plan_mission(q), safety_enabled=True)
    return [x for x in t if x not in _UTIL]


def _total(q: str) -> int:
    return len(select_tool_names(q, plan_mission(q), safety_enabled=True))


class ToolHeadSubsetContract(unittest.TestCase):
    def test_crisp_commands_are_small(self):
        # The operator's exact complaint: no 11-tool subset for a trivial command.
        # 2026-05-28: bump 7→8 — el router agregó `computer_use` como tool
        # universal de operación in-app, lo cual añade un slot al subset
        # para comandos crispy. Sigue siendo lejos del techo 11 original.
        for q in ["abre steam", "abre chrome", "mutea", "pausa", "pon musica",
                  "manda whatsapp a juan"]:
            self.assertLessEqual(_total(q), 8,
                                 f"{q!r} subset too large: {_domain(q)}")

    def test_real_command_not_empty(self):
        # A genuine command must surface its tool — never abstain to nothing.
        self.assertIn("steam", _domain("abre steam"))
        self.assertIn("audio", _domain("mutea"))
        self.assertIn("media", _domain("reproduce daddy yankee"))  # OOV object
        self.assertIn("whatsapp", _domain("manda whatsapp a juan"))

    def test_smalltalk_and_knowledge_abstain(self):
        for q in ["hola", "gracias", "que es pytest"]:
            self.assertEqual(_domain(q), [], f"{q!r} should abstain")

    def test_knowledge_world_question_reaches_web(self):
        # "what is X about" / "who is X" should reach web/knowledge.
        for q in ["de que trata Dune", "quien es Batman"]:
            d = _domain(q)
            self.assertTrue({"web", "knowledge"} & set(d),
                            f"{q!r} should reach web/knowledge: {d}")


if __name__ == "__main__":
    unittest.main()


class CrossEncoderRescueContract(unittest.TestCase):
    """The cross-encoder rescue must recover short/ambiguous real intents that
    the bi-encoder placed too weakly, WITHOUT resurrecting tools on smalltalk."""

    def test_rescues_short_knowledge_and_window(self):
        # These went EMPTY before the rescue stage (encoder placed them weakly).
        self.assertTrue({"web", "knowledge"} & set(_domain("who directed Oppenheimer")))
        self.assertIn("window", _domain("cuantas pestanas tengo abiertas"))

    def test_rescue_does_not_resurrect_smalltalk(self):
        for q in ("hola", "gracias", "como estas"):
            self.assertEqual(_domain(q), [], f"{q!r} must stay empty")

    def test_memory_read_not_reminder(self):
        d = _domain("que recuerdas de mi")
        self.assertIn("memory", d)
        self.assertNotIn("reminder", d)
