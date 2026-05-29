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
        # sin señal clara -> UNKNOWN -> NO recuperable (skip), nunca recuperación ciega
        self.assertEqual(classify_failure({"error": "weird internal glitch xyz"}), ERR_UNKNOWN)
        self.assertNotIn(ERR_UNKNOWN, RECOVERABLE_ERROR_TYPES)
        self.assertNotIn(ERR_TRANSIENT, RECOVERABLE_ERROR_TYPES)
        self.assertIn(ERR_MISSING_PRECONDITION, RECOVERABLE_ERROR_TYPES)
        self.assertIn(ERR_PARAM_MISMATCH, RECOVERABLE_ERROR_TYPES)

    def test_empty_result(self):
        self.assertEqual(classify_failure(None), ERR_UNKNOWN)
        self.assertEqual(classify_failure({}), ERR_UNKNOWN)


class TestErrorTypeField(unittest.TestCase):
    def test_default_none(self):
        o = VerifierOutcome(tool_name="app", confirmed=False, reason="x")
        self.assertIsNone(o.error_type)

    def test_settable(self):
        o = VerifierOutcome(tool_name="app", confirmed=False, reason="x",
                            error_type=ERR_MISSING_PRECONDITION)
        self.assertEqual(o.error_type, ERR_MISSING_PRECONDITION)


class TestGate(unittest.TestCase):
    def test_default_off(self):
        prev = os.environ.pop("GEMMA4_ERROR_RECOVERY", None)
        try:
            self.assertFalse(_error_recovery_enabled())
        finally:
            if prev is not None:
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
