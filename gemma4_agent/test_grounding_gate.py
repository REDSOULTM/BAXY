"""Tests for Bug 3: grounding gate (inline + async NLI).

The inline gate uses morphological heuristics (suffix + stem hint), NOT a
closed verb list. We test that it generalizes to verbs NOT pre-enumerated.
"""
from __future__ import annotations

import threading
import unittest
from unittest.mock import MagicMock

from gemma4_agent.grounding_gate import (
    GROUNDING_LABELS,
    GroundingVerdict,
    _looks_like_first_person_preterit,
    _starts_with_action_claim,
    build_evidence_premise,
    detect_action_claim_without_evidence,
    schedule_grounding_check,
)


class TestPreteritMorphology(unittest.TestCase):
    """The verb detector recognizes 1st-person past based on suffix+stem."""

    def test_canonical_action_verbs_with_accent(self):
        for w in ("abrí", "busqué", "envié", "agendé", "ejecuté", "registré",
                   "mandé", "lancé", "navegué", "encontré"):
            self.assertTrue(_looks_like_first_person_preterit(w), f"failed: {w}")

    def test_canonical_action_verbs_without_accent(self):
        # Voice-transcribed; accents often dropped.
        for w in ("abri", "busque", "envie", "agende", "ejecute", "registre"):
            self.assertTrue(_looks_like_first_person_preterit(w), f"failed: {w}")

    def test_rejects_infinitive(self):
        for w in ("abrir", "buscar", "enviar", "agendar"):
            self.assertFalse(_looks_like_first_person_preterit(w), f"falsely flagged: {w}")

    def test_rejects_future_conditional(self):
        for w in ("abrira", "buscara", "abriria"):
            self.assertFalse(_looks_like_first_person_preterit(w))

    def test_rejects_common_non_verbs(self):
        for w in ("hola", "casi", "examen", "nombre", "siete", "ese"):
            self.assertFalse(_looks_like_first_person_preterit(w))

    def test_rejects_present_tense(self):
        # cargo, busco, abro — 1st-person present, NOT past.
        for w in ("cargo", "busco", "abro", "envío"):
            self.assertFalse(_looks_like_first_person_preterit(w))


class TestStartsWithActionClaim(unittest.TestCase):

    def test_simple_opening(self):
        self.assertEqual(_starts_with_action_claim("Abrí Disney+"), "Abrí")

    def test_after_clause_connector(self):
        # "Listo," is a common prefix; the real claim is right after.
        self.assertEqual(_starts_with_action_claim("Listo, abrí Disney+"), "abrí")

    def test_after_two_connectors(self):
        self.assertIsNotNone(_starts_with_action_claim("Listo, hecho, agendé el evento"))

    def test_unrelated_opening(self):
        self.assertIsNone(_starts_with_action_claim("Hola, cómo estás"))

    def test_empty(self):
        self.assertIsNone(_starts_with_action_claim(""))
        self.assertIsNone(_starts_with_action_claim("   "))


class TestInlineGate(unittest.TestCase):

    def test_daredevil_real_case_flagged(self):
        # The exact reply from turn 20260516_180344_8072d16b.
        reply = ("Abrí Disney+ y busqué Daredevil Born Again, pero no pude "
                 "confirmar visualmente que el video haya comenzado a reproducirse.")
        v = detect_action_claim_without_evidence(reply, tool_events=[])
        self.assertTrue(v.should_replace)
        self.assertEqual(v.reason, "action_claim_without_evidence")
        self.assertIn(v.claim_word.lower(), {"abrí", "abri"})

    def test_when_tool_ran_no_flag(self):
        reply = "Abrí Disney+ y busqué Daredevil Born Again..."
        events = [MagicMock(name="media_result")]
        v = detect_action_claim_without_evidence(reply, tool_events=events)
        self.assertFalse(v.should_replace)
        self.assertEqual(v.reason, "tool_events_nonempty")

    def test_legitimate_smalltalk_no_flag(self):
        v = detect_action_claim_without_evidence("Hola, ¿cómo estás?", [])
        self.assertFalse(v.should_replace)

    def test_factual_answer_no_flag(self):
        v = detect_action_claim_without_evidence("GTA V salió en 2013.", [])
        self.assertFalse(v.should_replace)

    def test_future_tense_no_flag(self):
        # "Voy a abrir" is a promise (Bug 1 territory), not a false-confirmation.
        # The inline grounding gate doesn't flag it; the existing promise guard
        # handles future-tense claims.
        v = detect_action_claim_without_evidence("Voy a abrir Disney+", [])
        self.assertFalse(v.should_replace)

    def test_fallback_text_present(self):
        v = detect_action_claim_without_evidence("Envié el mensaje", [])
        self.assertTrue(v.should_replace)
        self.assertTrue(v.fallback)
        self.assertIn("No alcancé", v.fallback)


class TestEvidencePremise(unittest.TestCase):

    def test_empty_events(self):
        p = build_evidence_premise([])
        self.assertIn("no se ejecutó", p)

    def test_named_tool_events(self):
        ev1 = MagicMock()
        ev1.name = "media"
        ev2 = MagicMock()
        ev2.name = "browser_real"
        p = build_evidence_premise([ev1, ev2])
        self.assertIn("media", p)
        self.assertIn("browser_real", p)


class TestSchedulesAsyncNLI(unittest.TestCase):
    """Async grounding wires the NLI service correctly."""

    def test_no_op_for_empty_reply(self):
        called = []
        schedule_grounding_check("", [], callback=called.append)
        # Nothing scheduled, no callback fired.
        self.assertEqual(called, [])

    def test_callback_receives_contradiction_verdict(self):
        # Stub the NLI service to return a high "executed actions" score
        # when tool_events is empty -> should flag contradicts=True.
        from gemma4_agent import nli_service as nli_mod
        from gemma4_agent.nli_service import _NLIService
        original_singleton = nli_mod._SINGLETON
        try:
            stub = _NLIService()
            stub._pipe = MagicMock(return_value={
                "labels": [GROUNDING_LABELS[0], GROUNDING_LABELS[1]],
                "scores": [0.85, 0.15],
            })
            nli_mod._SINGLETON = stub
            evt = threading.Event()
            captured = []

            def cb(v):
                captured.append(v)
                evt.set()

            schedule_grounding_check("Abrí Disney+ y busqué algo", [], callback=cb)
            ok = evt.wait(timeout=2.0)
            self.assertTrue(ok)
            self.assertTrue(captured[0]["available"])
            self.assertTrue(captured[0]["contradicts"])
        finally:
            nli_mod._SINGLETON = original_singleton

    def test_callback_no_contradiction_when_tools_ran(self):
        from gemma4_agent import nli_service as nli_mod
        from gemma4_agent.nli_service import _NLIService
        original_singleton = nli_mod._SINGLETON
        try:
            stub = _NLIService()
            stub._pipe = MagicMock(return_value={
                "labels": [GROUNDING_LABELS[0], GROUNDING_LABELS[1]],
                "scores": [0.85, 0.15],
            })
            nli_mod._SINGLETON = stub
            ev1 = MagicMock()
            ev1.name = "media"
            evt = threading.Event()
            captured = []
            schedule_grounding_check("Abrí Disney+", [ev1], callback=lambda v: (captured.append(v), evt.set()))
            evt.wait(timeout=2.0)
            self.assertFalse(captured[0]["contradicts"],
                              "should not flag contradiction when tools actually ran")
        finally:
            nli_mod._SINGLETON = original_singleton

    def test_callback_gets_unavailable_when_service_fails(self):
        from gemma4_agent import nli_service as nli_mod
        from gemma4_agent.nli_service import _NLIService
        original = nli_mod._SINGLETON
        try:
            stub = _NLIService()
            stub._load_failed = True
            nli_mod._SINGLETON = stub
            evt = threading.Event()
            captured = []
            schedule_grounding_check("hi", [], callback=lambda v: (captured.append(v), evt.set()))
            evt.wait(timeout=2.0)
            self.assertEqual(captured[0], {"available": False})
        finally:
            nli_mod._SINGLETON = original


if __name__ == "__main__":
    unittest.main()
