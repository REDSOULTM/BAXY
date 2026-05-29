"""Pin the calibrated abstention head (Step 2 of the 2026-05-21 router rebuild).

We don't assert exact probabilities (they move when the head is retrained);
we assert the contract: the artifact loads, the feature vector matches the
trainer's expectation, and clear meta/self-reference turns score higher
P(no_tool) than clear imperative commands.
"""
from __future__ import annotations

import unittest

from gemma4_agent.safety_pkg.abstain_head import (
    FEATURE_NAMES, build_features, load_model,
)


class AbstainHeadContract(unittest.TestCase):
    def test_artifact_loads_with_matching_features(self):
        m = load_model()
        # If the artifact is missing the head silently disables — that's a
        # valid degraded state, but in this repo it must be present.
        self.assertIsNotNone(m, "data/abstain_head.json missing — run "
                                "scripts/train_abstain_head.py")
        self.assertEqual(m.feature_names, FEATURE_NAMES)
        self.assertEqual(len(m.weights), len(FEATURE_NAMES))

    def test_build_features_is_complete_and_ordered(self):
        feats = build_features("hola", intent=None, scored=None,
                               keyword_fired=False)
        for n in FEATURE_NAMES:
            self.assertIn(n, feats)

    def test_meta_directive_scores_higher_than_command(self):
        m = load_model()
        if m is None:
            self.skipTest("head artifact unavailable")
        from gemma4_agent.routing.intent_router import classify_intent
        from gemma4_agent.routing.semantic_router import suggest_tools_scored

        def p(q: str, kw: bool) -> float:
            intent = classify_intent(q)
            scored = suggest_tools_scored(q, k=12)
            return m.p_no_tool(build_features(
                q, intent=intent, scored=scored, keyword_fired=kw))

        # A clear tool/answer-policy meta-directive should lean no-tool;
        # a crisp imperative with a keyword should lean act.
        p_meta = p("no uses herramientas para esta respuesta", kw=False)
        p_cmd = p("abre Steam", kw=True)
        self.assertGreater(p_meta, p_cmd)


if __name__ == "__main__":
    unittest.main()
