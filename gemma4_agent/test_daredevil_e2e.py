"""End-to-end test for the Daredevil regression (turn 20260516_180344_8072d16b).

The original failure mode:
  user: "quiero ver daredevil born again"
  → planner returns needs_pc_action=False, subset=[]
  → RAG retrieves past hits including reply text "Abrí Disney+ y busqué..."
  → LLM copies the reply verbatim
  → tool_events=[] but reply claims actions
  → mission_status=PASS (because no tools were "expected")
  → user hears a lie, nothing happened on screen

After the three fixes:
  - Bug 1 (capability classifier): "consumir contenido audiovisual" → bucket
    {media, browser} added to subset, even without a platform mention.
  - Bug 2 (provenance RAG): past summaries are NOT shown to the LLM; only
    policy hints (tools_used, outcome_code, args_signature, capability).
  - Bug 3 (grounding gate): if the LLM still claims an action without
    tool_events (e.g. because tools were available but it didn't call them),
    the inline morphological check replaces the reply with an honest fallback,
    and async NLI flags the experience row so future turns see a WARNING.

This test wires the components together without spinning up llama-server:
we mock the classifier+grounding paths and verify the integration.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from gemma4_agent import capability_classifier as cap_mod
from gemma4_agent.capability_classifier import (
    CAPABILITY_LABELS,
    CapabilityVerdict,
    augment_subset,
    clear_cache,
)
from gemma4_agent.experience import format_recall_for_prompt
from gemma4_agent.grounding_gate import detect_action_claim_without_evidence


class TestDaredevilBugFixed(unittest.TestCase):
    """End-to-end behavioral checks for the Daredevil case."""

    def setUp(self):
        clear_cache()

    def test_step1_capability_classifier_picks_audiovisual(self):
        """Bug 1: 'quiero ver daredevil born again' must map to
        'consumir contenido audiovisual' and add media+browser to subset."""
        v = CapabilityVerdict(
            top_label="consumir contenido audiovisual",
            confidence=0.92,
            bucket=frozenset({"media", "browser"}),
        )
        cap_mod._cache_put("quiero ver daredevil born again", v)
        subset, tel = augment_subset("quiero ver daredevil born again",
                                       ["safety"])
        self.assertIn("media", subset,
                       "media must be added so the agent can act")
        self.assertIn("browser", subset)
        self.assertEqual(tel["capability_used"],
                          "consumir contenido audiovisual")

    def test_step2_rag_no_longer_exposes_reply_template(self):
        """Bug 2: even with a high-similarity past hit, the LLM does NOT
        see the past reply text."""
        recalls = [
            {
                "id": 542, "turn_id": "past1", "ts": "2026-05-16T16:00", "distance": 0.27,
                "user_input": "quiero ver daredevil born again en disney",
                "tools_used": ["media"],
                "mission_status": "PASS",
                "outcome_code": "PASS_VERIFIED",
                "summary": "Listo, estoy viendo Daredevil Born Again en Disney+.",
                "args_signature": {"provider": "disney_plus", "action": "play"},
                "capability_label": "consumir contenido audiovisual",
                "failure_reason_code": None,
                "grounding_flagged": False,
            },
            {
                "id": 528, "turn_id": "past2", "ts": "2026-05-16T13:50", "distance": 0.95,
                "user_input": "Quiero ver daredevil en disney",
                "tools_used": ["media"],
                "mission_status": "PARTIAL",
                "outcome_code": "PARTIAL",
                "summary": ("Abrí Disney+ y busqué Daredevil, pero no pude "
                              "confirmar visualmente que el video haya comenzado "
                              "a reproducirse. Se abrió la página de resultados."),
                "args_signature": {"provider": "disney_plus"},
                "capability_label": "consumir contenido audiovisual",
                "failure_reason_code": "search_page_only_no_playback_confirmed",
                "grounding_flagged": False,
            },
        ]
        prompt_chunk = format_recall_for_prompt(recalls)
        # The exact lying reply that the LLM mimicked MUST NOT be in the prompt.
        self.assertNotIn("Listo, estoy viendo Daredevil", prompt_chunk)
        self.assertNotIn("Abrí Disney+ y busqué Daredevil", prompt_chunk)
        # But the actionable policy info IS in the prompt.
        self.assertIn("media", prompt_chunk)
        self.assertIn("disney_plus", prompt_chunk)
        self.assertIn("PASS_VERIFIED", prompt_chunk)
        self.assertIn("PARTIAL", prompt_chunk)
        self.assertIn("search_page_only_no_playback_confirmed", prompt_chunk)
        # And the prompt explicitly tells the LLM not to copy reply text.
        self.assertIn("NO copiar texto", prompt_chunk)

    def test_step3_grounding_gate_catches_the_lie(self):
        """Bug 3: if the LLM STILL generates the lying reply (e.g. via
        in-context-learning from the prompt itself), the grounding gate
        catches it inline."""
        # The exact reply text from the production turn.
        bad_reply = ("Abrí Disney+ y busqué Daredevil Born Again, "
                     "pero no pude confirmar visualmente que el video "
                     "haya comenzado a reproducirse. Se abrió la página "
                     "de resultados de búsqueda.")
        verdict = detect_action_claim_without_evidence(bad_reply, tool_events=[])
        self.assertTrue(verdict.should_replace,
                         "the lie must be replaced when no tool ran")
        self.assertEqual(verdict.reason, "action_claim_without_evidence")
        # Fallback is honest.
        self.assertIn("No alcancé", verdict.fallback)

    def test_step3_grounding_gate_lets_legit_replies_through(self):
        """Same reply WITH actual tool events must NOT be replaced."""
        legit_events = [MagicMock(name="media")]
        verdict = detect_action_claim_without_evidence(
            "Abrí Disney+ y busqué Daredevil Born Again",
            tool_events=legit_events,
        )
        self.assertFalse(verdict.should_replace)

    def test_step3_grounding_does_not_flag_smalltalk(self):
        verdict = detect_action_claim_without_evidence(
            "Hola, ¿en qué te ayudo?", tool_events=[],
        )
        self.assertFalse(verdict.should_replace)

    def test_combined_pipeline_short_circuits_safely(self):
        """Simulate the full path:
            1. classifier puts media+browser in subset
            2. RAG provides policy hints, NOT reply text
            3. (hypothetical) the LLM still hallucinates → grounding catches it
        """
        # Step 1
        v = CapabilityVerdict(
            top_label="consumir contenido audiovisual",
            confidence=0.93,
            bucket=frozenset({"media", "browser"}),
        )
        cap_mod._cache_put("quiero ver daredevil born again", v)
        subset, _ = augment_subset("quiero ver daredevil born again",
                                     ["safety"])
        self.assertEqual(set(subset), {"safety", "media", "browser"})
        # Step 3 catches the hypothetical worst case.
        bad = "Abrí Disney+ y busqué Daredevil Born Again."
        verdict = detect_action_claim_without_evidence(bad, [])
        self.assertTrue(verdict.should_replace)


if __name__ == "__main__":
    unittest.main()
