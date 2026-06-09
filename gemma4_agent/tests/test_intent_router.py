"""Tests for the semantic intent classifier (intent_router.py).

The router decides "informational question about the world" vs "PC
action" semantically (multilingual, keyword-free) instead of per-language
regex. These tests pin the behavior in several languages so a future
change can't silently regress it.

The embedding model loads lazily; if it's unavailable the classifier
returns None and wants_knowledge() is False (graceful degrade) — those
environments skip the semantic assertions.
"""
from __future__ import annotations

import unittest

from ..routing.intent_router import (
    classify_intent,
    is_conversational,
    wants_knowledge,
    wants_send_email,
    wants_web_navigation,
    wants_web_store,
)


def _model_available() -> bool:
    return classify_intent("who is Einstein") is not None


@unittest.skipUnless(_model_available(), "embedding model not available")
class TestIntentRouter(unittest.TestCase):

    # Informational questions across languages → wants_knowledge True.
    def test_info_multilingual(self):
        for q in [
            "quien es batman",
            "de que trata marvel rivals",
            "de que murio michael jackson",
            "who is spiderman",
            "what is quantum computing",
            "wer war Napoleon",
            "de quoi parle le film Inception",
            "chi e Leonardo da Vinci",
            "quem foi Pele",
        ]:
            self.assertTrue(
                wants_knowledge(q),
                f"expected informational intent for {q!r}",
            )

    # PC actions across languages → wants_knowledge False (no web stuffing).
    def test_action_multilingual(self):
        for q in [
            "abre Steam",
            "cierra youtube",
            "pon una cancion en spotify",
            "saca un screenshot",
            "open Steam",
            "ferme la fenetre",
            "manda mensaje a juan por whatsapp",
            "instala discord",
        ]:
            self.assertFalse(
                wants_knowledge(q),
                f"expected action intent (not knowledge) for {q!r}",
            )

    def test_empty_and_garbage(self):
        self.assertFalse(wants_knowledge(""))
        self.assertFalse(wants_knowledge("   "))

    def test_scores_shape(self):
        s = classify_intent("quien es batman")
        self.assertIsNotNone(s)
        self.assertTrue(-1.0 <= s.info <= 1.0)
        self.assertTrue(-1.0 <= s.action <= 1.0)
        self.assertTrue(-1.0 <= s.chitchat <= 1.0)
        self.assertTrue(-1.0 <= s.selfref <= 1.0)
        # margin = info over the strongest competing class (4-class).
        self.assertAlmostEqual(
            s.margin,
            s.info - max(s.action, s.chitchat, s.selfref),
            places=6,
        )

    def test_self_reference_not_knowledge(self):
        # Questions about the assistant itself must NOT pull web.
        for q in [
            "quien eres", "que eres exactamente", "que puedes hacer",
            "como te llamas", "who are you", "what can you do",
        ]:
            self.assertFalse(
                wants_knowledge(q),
                f"self-reference {q!r} should not request web",
            )

    def test_chitchat_not_knowledge(self):
        for q in ["jajaja", "nada", "oye", "dale", "mmm", "gracias", "ok",
                  "muchas gracias", "merci beaucoup", "tudo bem"]:
            self.assertFalse(
                wants_knowledge(q),
                f"chitchat {q!r} should not request web",
            )

    def test_conversational_questions_are_knowledge(self):
        # Questions phrased conversationally (close to chitchat in
        # embedding space) must still count as world-knowledge.
        # NB: "cuándo salió X" (when was X released) sits on the action
        # boundary ("salió/released" embeds near action) — a documented
        # borderline, not asserted here. These are the robust ones.
        for q in [
            "hablame de la pelicula emilia perez",
            "quien gana batman vs superman",
            "wer hat den Mond zuerst betreten",
            "chi ha dipinto la Gioconda",
        ]:
            self.assertTrue(
                wants_knowledge(q),
                f"conversational question {q!r} should request web",
            )


    def test_conversational_gate_flags_smalltalk_and_selfref(self):
        # The abstention gate must flag pure conversation so the planner
        # can suppress the semantic router's noisy domain-tool top-k.
        for q in [
            "jajaja", "ok", "nada", "muchas gracias",
            "quien eres", "que puedes hacer", "cual es tu prioridad",
        ]:
            self.assertTrue(
                is_conversational(q),
                f"{q!r} should be flagged conversational (abstain)",
            )

    def test_conversational_gate_spares_world_questions(self):
        # Real world-questions must NOT be flagged conversational, or the
        # planner would silence the web/knowledge they need.
        for q in [
            "quien es batman", "de que trata inception",
            "what is quantum computing",
        ]:
            self.assertFalse(
                is_conversational(q),
                f"world question {q!r} should NOT be flagged conversational",
            )

    def test_tell_me_about_entity_is_knowledge(self):
        # "hablame de X / contame sobre X / dame info de X / qué sabés de X"
        # about a concrete entity are world-knowledge requests.
        # They used to fall into chitchat (the short proper-noun object embeds
        # near smalltalk) or fail the vs-action margin. Anchors anchoring the
        # "verbo-pedir-info + ENTIDAD" pattern fixed it. Multilingual — these
        # must fire wants_knowledge across the longer descriptive subjects that
        # the encoder reliably places (short bare names like "messi" stay a
        # documented hard boundary the LLM resolves from full text).
        for q in [
            "hablame de bruno mars",
            "contame sobre bruno mars",
            "dame info de la nasa",
            "que sabes de napoleon",
            "hablame de la segunda guerra mundial",
            "contame de los dinosaurios",
        ]:
            self.assertTrue(
                wants_knowledge(q),
                f"'tell me about X' {q!r} should request web/knowledge",
            )

    def test_tell_me_about_does_not_overtrigger(self):
        # The new info anchors must NOT pull commands or smalltalk into
        # knowledge: real actions and chitchat stay out (anti-regression).
        for q in [
            "abre whatsapp", "pon musica", "sube el volumen",
            "gracias", "hola", "quien eres",
        ]:
            self.assertFalse(
                wants_knowledge(q),
                f"{q!r} must NOT be misread as a knowledge request",
            )

    # NB: clear imperatives ("abre Steam", "pon una canción") may or may not
    # be flagged conversational by the standalone gate — that's harmless,
    # because the keyword stage and the high-confidence semantic override
    # still put their tools in the subset. We assert the ROUTING OUTCOME,
    # which is what actually matters, in test_router*.py — not the internal
    # gate flag, which is only one of several signals.


if __name__ == "__main__":
    unittest.main()
