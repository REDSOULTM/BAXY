"""Tests for Bug 3: grounding gate (inline morphology check only).

The async NLI layer was removed along with the rest of the
NLI stack; tests for it were removed too. The inline gate uses
morphological heuristics (suffix + stem hint), NOT a closed verb list.
We test that it generalizes to verbs NOT pre-enumerated.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from gemma4_agent.safety_pkg.grounding_gate import (
    GroundingVerdict,
    _looks_like_first_person_preterit,
    _starts_with_action_claim,
    all_events_blocked_or_failed,
    detect_action_claim_without_evidence,
)


class _Ev:
    """ToolEvent mínimo (name/args/result) para los tests del gate."""

    def __init__(self, ok: bool | None, **res):
        self.name = res.pop("name", "app")
        self.args = res.pop("args", {})
        self.result = None if ok is None else {"ok": ok, **res}


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


class TestAuxWordBoundary(unittest.TestCase):
    """Los auxiliares multilingües cortos solo cuentan en FRONTERA de palabra
    (regresión 2026-06-10): "sto " (IT) matcheaba DENTRO de "eSTO requiere
    confirmación" y con el stem "confirm" a <5 tokens producía un falso claim
    que pisaba un reply legítimo que YA pedía confirmación."""

    def test_spanish_esto_does_not_trigger_italian_sto(self):
        v = detect_action_claim_without_evidence(
            "Esto requiere confirmación, ¿lo hago?", [])
        self.assertFalse(v.should_replace)

    def test_embedded_aux_with_participle_does_not_fire(self):
        # mecanismo exacto de la regresión: aux embebido ("sto " ⊂ "esto") +
        # forma de participio a <5 tokens — con la frontera ya NO dispara.
        v = detect_action_claim_without_evidence(
            "Esto quedó confirmado para más tarde.", [])
        self.assertFalse(v.should_replace)

    def test_aux_at_boundary_still_fires(self):
        # control positivo: el continuo legítimo sigue detectándose.
        v = detect_action_claim_without_evidence("Estoy abriendo Spotify.", [])
        self.assertTrue(v.should_replace)
        v2 = detect_action_claim_without_evidence("Listo, he abierto la app.", [])
        self.assertTrue(v2.should_replace)


class TestAllEventsFailedGate(unittest.TestCase):
    """Claims de acción con events SOLO fallidos/bloqueados (2026-06-10):
    needs_user (precondición), needs_confirmation, error, tool-call que no
    parseó. La propia tool reportó que NADA pasó -> "estoy abriendo X" /
    "busqué X" contradicen la evidencia igual que en 0-events. Gate por el
    STATUS del result, no por el verbo."""

    def test_progressive_claim_after_needs_user_flagged(self):
        # el caso MEDIDO en vivo: precondición bloqueó (la app no existe) y el
        # reply afirma la acción EN CURSO.
        ev = _Ev(False, status="needs_user", error="app not found")
        v = detect_action_claim_without_evidence(
            "Listo, estoy abriendo jitomatador. Puede tardar unos segundos.", [ev])
        self.assertTrue(v.should_replace)
        self.assertEqual(v.reason, "action_claim_all_events_failed")

    def test_preterit_claim_after_needs_user_flagged(self):
        # también medido: "busqué X en la tienda" sin que nada corriera.
        ev = _Ev(False, status="needs_user")
        v = detect_action_claim_without_evidence(
            "Listo, busqué jitomatador en la tienda de Windows.", [ev])
        self.assertTrue(v.should_replace)

    def test_claim_after_needs_confirmation_flagged(self):
        ev = _Ev(False, status="needs_confirmation")
        v = detect_action_claim_without_evidence(
            "Listo, borré los archivos temporales.", [ev])
        self.assertTrue(v.should_replace)

    def test_honest_failure_reply_passes(self):
        ev = _Ev(False, status="needs_user", error="app not found")
        v = detect_action_claim_without_evidence(
            "No encuentro jitomatador instalado. ¿Está bien escrito el nombre?", [ev])
        self.assertFalse(v.should_replace)

    def test_async_dispatch_ok_is_honest_progressive(self):
        # launch despachado ok (status=dispatched, verified=None): "estoy
        # abriendo Steam" ES honesto -> NO se toca.
        ev = _Ev(True, status="dispatched", completion_status="launch_requested",
                 verified=None)
        v = detect_action_claim_without_evidence(
            "Estoy abriendo Steam, puede tardar unos segundos.", [ev])
        self.assertFalse(v.should_replace)
        self.assertEqual(v.reason, "tool_events_nonempty")

    def test_mixed_results_pass_through(self):
        # un solo ok=True en el turno -> el claim puede ser legítimo, no flagear.
        evs = [_Ev(False, status="needs_user"), _Ev(True, status="done")]
        v = detect_action_claim_without_evidence("Listo, abrí la calculadora.", evs)
        self.assertFalse(v.should_replace)

    def test_unknown_result_fails_open(self):
        # event sin result dict (estado desconocido) -> fail-open, no flagear.
        evs = [_Ev(None)]
        self.assertFalse(all_events_blocked_or_failed(evs))
        v = detect_action_claim_without_evidence("Listo, abrí la calculadora.", evs)
        self.assertFalse(v.should_replace)

    def test_all_events_blocked_helper(self):
        self.assertFalse(all_events_blocked_or_failed([]))
        self.assertTrue(all_events_blocked_or_failed(
            [_Ev(False, status="needs_user"), _Ev(False, error="boom")]))
        self.assertFalse(all_events_blocked_or_failed(
            [_Ev(False, status="needs_user"), _Ev(True)]))


if __name__ == "__main__":
    unittest.main()
