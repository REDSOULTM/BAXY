"""B1 (competidores): tests del clasificador de fallos + gate de recuperación.

La recuperación EN VIVO (que el hint específico mejore el self-correct del 4B) es
no-determinista -> validación en vivo en box fresca. Acá sólo el clasificador
estructural (puro) + el gate + el campo error_type.
"""
import os
import unittest

from ..safety_pkg.verify_core import (
    VerifierOutcome, classify_failure,
    ERR_MISSING_PRECONDITION, ERR_PARAM_MISMATCH, ERR_TRANSIENT, ERR_UNKNOWN,
    RECOVERABLE_ERROR_TYPES,
)
from ..agent_core.agent import _error_recovery_enabled


class TestClassifyFailure(unittest.TestCase):
    def test_given_wins(self):
        # si el verifier ya seteó error_type, eso gana sobre la inferencia
        self.assertEqual(classify_failure({"error": "timeout"}, given=ERR_PARAM_MISMATCH),
                         ERR_PARAM_MISMATCH)

    def test_structured_needs_dependency(self):
        self.assertEqual(classify_failure({"status": "needs_dependency"}), ERR_MISSING_PRECONDITION)

    def test_structured_missing_field(self):
        self.assertEqual(classify_failure({"status": "failed", "missing": "name"}), ERR_PARAM_MISMATCH)

    def test_text_not_found_es_en_fr_de(self):
        for err in ("no encontré la ventana", "window not found", "fenêtre introuvable",
                    "nicht gefunden", "no such file"):
            self.assertEqual(classify_failure({"error": err}), ERR_MISSING_PRECONDITION, err)

    def test_text_missing_param(self):
        for err in ("no se especificó qué ventana", "missing argument", "field required",
                    "which window?", "no target provided"):
            self.assertEqual(classify_failure({"error": err}), ERR_PARAM_MISMATCH, err)

    def test_text_transient(self):
        for err in ("connection timeout", "network error", "el recurso está ocupado",
                    "rate limit exceeded"):
            self.assertEqual(classify_failure({"error": err}), ERR_TRANSIENT, err)

    def test_unknown_default_is_conservative(self):
        # sin señal clara -> UNKNOWN -> NO recuperable (skip), nunca recuperación ciega.
        # H3 (perfection roadmap 2026-05-29): TRANSIENT SÍ es recuperable (el agente
        # ya lo retría; antes el set lo OMITÍA = bomba de tiempo latente). Corregido.
        self.assertEqual(classify_failure({"error": "weird internal glitch xyz"}), ERR_UNKNOWN)
        self.assertNotIn(ERR_UNKNOWN, RECOVERABLE_ERROR_TYPES)
        self.assertIn(ERR_TRANSIENT, RECOVERABLE_ERROR_TYPES)  # H3: ahora consistente
        self.assertIn(ERR_MISSING_PRECONDITION, RECOVERABLE_ERROR_TYPES)
        self.assertIn(ERR_PARAM_MISMATCH, RECOVERABLE_ERROR_TYPES)

    def test_empty_result(self):
        self.assertEqual(classify_failure(None), ERR_UNKNOWN)
        self.assertEqual(classify_failure({}), ERR_UNKNOWN)

    def test_tool_not_found_is_structural(self):
        # H3 (perfection roadmap): "unknown tool: X" -> TOOL_NOT_FOUND (budget 0).
        from ..safety_pkg.verify_core import ERR_TOOL_NOT_FOUND
        self.assertEqual(classify_failure({"error": "unknown tool: xyzzy"}), ERR_TOOL_NOT_FOUND)
        self.assertEqual(classify_failure({"error": "Unknown Tool: foo"}), ERR_TOOL_NOT_FOUND)

    def test_invalid_args_is_param_mismatch(self):
        # acción fuera del enum (system(action='calculator')) -> corregible.
        self.assertEqual(
            classify_failure({"error": "invalid tool arguments",
                              "validation_errors": ["action not in enum"]}),
            ERR_PARAM_MISMATCH)

    def test_tool_not_found_beats_text_fallback(self):
        # estructural manda: aunque el texto diga "not found", un unknown-tool
        # es TOOL_NOT_FOUND (irrecuperable), no MISSING_PRECONDITION (recuperable).
        from ..safety_pkg.verify_core import ERR_TOOL_NOT_FOUND
        self.assertEqual(
            classify_failure({"error": "unknown tool: not found anywhere"}),
            ERR_TOOL_NOT_FOUND)


class TestRetryBudget(unittest.TestCase):
    """H2 (perfection roadmap): presupuesto de retry por clase. Ataca el
    '466/513 retries desperdiciados': lo irrecuperable NO se reintenta."""

    def test_irrecoverable_budget_zero(self):
        from ..safety_pkg.verify_core import (
            retry_budget_for, ERR_TOOL_NOT_FOUND, ERR_UNKNOWN)
        self.assertEqual(retry_budget_for(ERR_TOOL_NOT_FOUND), 0)
        self.assertEqual(retry_budget_for(ERR_UNKNOWN), 0)

    def test_recoverable_budgets_positive(self):
        from ..safety_pkg.verify_core import (
            retry_budget_for, ERR_PARAM_MISMATCH, ERR_MISSING_PRECONDITION,
            ERR_TRANSIENT)
        self.assertEqual(retry_budget_for(ERR_PARAM_MISMATCH), 1)
        self.assertEqual(retry_budget_for(ERR_MISSING_PRECONDITION), 1)
        self.assertEqual(retry_budget_for(ERR_TRANSIENT), 2)

    def test_none_and_unknown_class_are_zero(self):
        from ..safety_pkg.verify_core import retry_budget_for
        self.assertEqual(retry_budget_for(None), 0)
        self.assertEqual(retry_budget_for("garbage_class_xyz"), 0)

    def test_gate_tool_not_found_zero_transient_retried(self):
        """GATE explícito (perfection roadmap #4): TOOL_NOT_FOUND=0 reintentos,
        TRANSIENT >=80% reintentado. Mide el budget POR CLASE de punta a punta:
        clasificación estructural -> budget. Ataca el '466/513 desperdiciados'."""
        from ..safety_pkg.verify_core import (
            classify_failure, retry_budget_for, ERR_TOOL_NOT_FOUND, ERR_TRANSIENT)
        # Resultados representativos del dispatcher para cada clase.
        tool_not_found_cases = [
            {"error": "unknown tool: xyzzy"},
            {"error": "Unknown Tool: foobar"},
            {"error": "unknown tool: not found anywhere"},
        ]
        transient_cases = [
            {"error": "connection timeout", "status": "failed"},
            {"error": "network error"},
            {"error": "el recurso está ocupado"},
            {"error": "rate limit exceeded"},
            {"error": "timed out, try again"},
        ]
        # GATE 1: TOOL_NOT_FOUND -> budget 0 SIEMPRE (0 reintentos).
        for r in tool_not_found_cases:
            cls = classify_failure(r)
            self.assertEqual(cls, ERR_TOOL_NOT_FOUND, r)
            self.assertEqual(retry_budget_for(cls), 0,
                             f"TOOL_NOT_FOUND debe ser 0 reintentos: {r}")
        # GATE 2: TRANSIENT -> >=80% clasificado correcto Y con budget>0.
        retried = sum(
            1 for r in transient_cases
            if classify_failure(r) == ERR_TRANSIENT and retry_budget_for(ERR_TRANSIENT) > 0
        )
        frac = retried / len(transient_cases)
        self.assertGreaterEqual(frac, 0.80,
                                f"TRANSIENT reintentado {frac:.0%} (<80%)")


class TestErrorTypeField(unittest.TestCase):
    def test_default_none(self):
        o = VerifierOutcome(tool_name="app", confirmed=False, reason="x")
        self.assertIsNone(o.error_type)

    def test_settable(self):
        o = VerifierOutcome(tool_name="app", confirmed=False, reason="x",
                            error_type=ERR_MISSING_PRECONDITION)
        self.assertEqual(o.error_type, ERR_MISSING_PRECONDITION)


class TestVerifySetsErrorType(unittest.TestCase):
    """H1 (perfection roadmap): el GATE pide que los verifiers SETEEN error_type.

    Antes el campo estaba 100% inerte: declarado en VerifierOutcome pero ningún
    verifier lo poblaba y classify_failure se llamaba con given=None. Ahora
    verify_core.verify() es el chokepoint que lo garantiza por construcción:
    TODO outcome confirmed=False sale con error_type != None.
    """

    def setUp(self):
        # Asegurar registry cargado (los decorators registran al importar).
        import gemma4_agent.verifiers  # noqa: F401

    def test_failed_outcome_always_classified(self):
        from ..safety_pkg.verify_core import verify, ERR_MISSING_PRECONDITION
        # app.open con la tool reportando fallo -> el verifier marca confirmed=False
        # y DEBE traer error_type (no None). El verify_app lo setea explícito a
        # MISSING_PRECONDITION (app no instalada / no resuelta).
        out = verify("app", {"action": "open", "name": "Discord"},
                     {"ok": False, "error": "app not found"})
        self.assertIs(out.confirmed, False)
        self.assertIsNotNone(out.error_type, "H1: failed outcome sin error_type")
        self.assertEqual(out.error_type, ERR_MISSING_PRECONDITION)

    def test_inferred_when_verifier_did_not_set(self):
        # Un fallo transitorio que el verifier reportó sin clase explícita ->
        # verify_core lo infiere con classify_failure (no se queda en None).
        from ..safety_pkg.verify_core import verify, ERR_TRANSIENT
        out = verify("audio", {"action": "set_volume", "level": 50},
                     {"ok": False, "status": "failed", "error": "connection timeout"})
        self.assertIs(out.confirmed, False)
        self.assertEqual(out.error_type, ERR_TRANSIENT)

    def test_confirmed_true_has_no_error_type(self):
        # confirmed=True no es un fallo -> no se le inventa una clase de error.
        from ..safety_pkg.verify_core import verify
        out = verify("app", {"action": "open", "name": "Discord"},
                     {"ok": True, "verified": True})
        self.assertIs(out.confirmed, True)
        self.assertIsNone(out.error_type)

    def test_explicit_error_type_not_overwritten(self):
        # Si el verifier YA seteó error_type, verify_core NO lo pisa con la
        # inferencia de texto (el verifier conoce mejor su semántica).
        from ..safety_pkg.verify_core import (
            verify, _VERIFIERS, ERR_PARAM_MISMATCH)
        from ..safety_pkg.verify_core import VerifierOutcome as VO
        sentinel = "____h1_test_tool____"
        _VERIFIERS[sentinel] = lambda a, r: VO(
            tool_name=sentinel, confirmed=False, reason="boom",
            error_type=ERR_PARAM_MISMATCH)
        try:
            # result dice "timeout" (-> TRANSIENT por texto) pero el verifier
            # ya dijo PARAM_MISMATCH: gana el verifier.
            out = verify(sentinel, {}, {"ok": False, "error": "connection timeout"})
            self.assertEqual(out.error_type, ERR_PARAM_MISMATCH)
        finally:
            _VERIFIERS.pop(sentinel, None)


class TestGate(unittest.TestCase):
    def test_default_on(self):
        # 2026-05-29: flipeado a default-ON (validado en vivo + suite verde).
        # El kill-switch GEMMA4_ERROR_RECOVERY=0 sigue funcionando.
        prev = os.environ.pop("GEMMA4_ERROR_RECOVERY", None)
        try:
            self.assertTrue(_error_recovery_enabled())  # default ON ahora
            os.environ["GEMMA4_ERROR_RECOVERY"] = "0"
            self.assertFalse(_error_recovery_enabled())  # kill-switch
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_ERROR_RECOVERY", None)
            else:
                os.environ["GEMMA4_ERROR_RECOVERY"] = prev

    def test_on(self):
        prev = os.environ.get("GEMMA4_ERROR_RECOVERY")
        os.environ["GEMMA4_ERROR_RECOVERY"] = "1"
        try:
            self.assertTrue(_error_recovery_enabled())
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_ERROR_RECOVERY", None)
            else:
                os.environ["GEMMA4_ERROR_RECOVERY"] = prev


if __name__ == "__main__":
    unittest.main()
