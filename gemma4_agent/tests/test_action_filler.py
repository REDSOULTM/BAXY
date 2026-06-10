"""Confirm filler (2026-06-10, WIP): audio inmediato con personalidad mientras el
LLM piensa. El MÓDULO está testeado; FALTA cablearlo a run_content (ver handoff).
"""
from __future__ import annotations
import os
import unittest
from gemma4_agent.agent_core.action_filler import (
    pick_filler, intent_target_for_filler,
)


class TestActionFiller(unittest.TestCase):
    def test_intent_aware_only_for_safe_open(self):
        # "abrí Spotify" -> target seguro; "qué hora es"/"sube volumen" -> genérico.
        tgt, tool = intent_target_for_filler("abrí Spotify", ["app", "window"])
        self.assertEqual(tgt, "Spotify")
        self.assertEqual(tool, "app")
        for txt, tools in [("qué hora es", ["system"]), ("sube el volumen", ["audio"]),
                           ("poné música de los Beatles", ["media"])]:
            t, _ = intent_target_for_filler(txt, tools)
            self.assertIsNone(t, f"no debe extraer target inseguro: {txt!r}")

    def test_intent_aware_filler_text(self):
        f = pick_filler(lang="es", intent_target="Spotify", intent_tool="app")
        self.assertIn("Spotify", f)

    def test_generic_has_personality_and_rotates(self):
        a = pick_filler(lang="es", rotate=0)
        b = pick_filler(lang="es", rotate=1)
        self.assertTrue(a and b and a != b)

    def test_slow_filler_is_reassuring(self):
        s = pick_filler(lang="es", rotate=0, slow=True)
        self.assertTrue(s)  # banco slow no vacío

    def test_gate_off_disables(self):
        os.environ["GEMMA4_ACTION_FILLER"] = "0"
        try:
            self.assertIsNone(pick_filler(lang="es", rotate=0))
        finally:
            os.environ.pop("GEMMA4_ACTION_FILLER", None)


if __name__ == "__main__":
    unittest.main()
