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


class TestErrorTypeField(unittest.TestCase):
    def test_default_none(self):
        o = VerifierOutcome(tool_name="app", confirmed=False, reason="x")
        self.assertIsNone(o.error_type)

    def test_settable(self):
        o = VerifierOutcome(tool_name="app", confirmed=False, reason="x",
                            error_type=ERR_MISSING_PRECONDITION)
        self.assertEqual(o.error_type, ERR_MISSING_PRECONDITION)


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
