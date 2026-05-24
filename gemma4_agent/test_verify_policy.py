"""Tests de verificación escalonada por riesgo (investigación 3).

email.send es irreversible y a terceros SIN backstop -> confirmación previa.
whatsapp.send_message es irreversible pero YA verifica el chat por OCR -> sin
confirmación previa (no agregar fricción a la vía de voz más usada). Acciones
triviales reversibles -> no verificar (latencia cero).
"""
from __future__ import annotations

import unittest

from gemma4_agent.safety import classify_tool_call
from gemma4_agent.verify_policy import policy_for, Risk, VerifyPolicy


class SafetyGateCommsTest(unittest.TestCase):
    def test_email_send_requires_confirmation(self):
        d = classify_tool_call("email", {"action": "send"})
        self.assertTrue(d.requires_confirmation)
        self.assertEqual(d.risk, "external_message_send")

    def test_email_draft_and_status_are_free(self):
        for act in ("draft", "status"):
            self.assertFalse(
                classify_tool_call("email", {"action": act}).requires_confirmation, act)

    def test_whatsapp_send_stays_fluid(self):
        # whatsapp ya verifica el chat por OCR; no agregamos confirmación previa
        d = classify_tool_call("whatsapp", {"action": "send_message"})
        self.assertFalse(d.requires_confirmation)

    def test_existing_gates_unbroken(self):
        # no rompimos los gates previos (regresión)
        self.assertTrue(classify_tool_call(
            "filesystem", {"action": "delete"}).requires_confirmation)
        self.assertTrue(classify_tool_call(
            "package", {"action": "install"}).requires_confirmation)
        self.assertFalse(classify_tool_call(
            "audio", {"action": "set_volume", "level": 30}).requires_confirmation)


class VerifyPolicyTest(unittest.TestCase):
    def test_high_risk_comms(self):
        p = policy_for("email", {"action": "send"})
        self.assertEqual(p.risk, Risk.HIGH)
        self.assertTrue(p.must_verify)
        self.assertTrue(p.require_user_confirmation)  # sin backstop

        p = policy_for("whatsapp", {"action": "send_message"})
        self.assertEqual(p.risk, Risk.HIGH)
        self.assertTrue(p.must_verify)
        self.assertFalse(p.require_user_confirmation)  # tiene backstop OCR

    def test_filesystem_delete_confirms(self):
        p = policy_for("filesystem", {"action": "delete"})
        self.assertEqual(p.risk, Risk.HIGH)
        self.assertTrue(p.require_user_confirmation)

    def test_trivial_media_not_verified(self):
        p = policy_for("media", {"action": "play"})
        self.assertEqual(p.risk, Risk.TRIVIAL)
        self.assertFalse(p.must_verify)
        self.assertEqual(p.verify_timeout_ms, 0)

    def test_small_volume_delta_is_trivial(self):
        self.assertEqual(policy_for("audio", {"action": "set_volume", "delta": 5}).risk,
                         Risk.TRIVIAL)
        # absoluto / sin delta -> low (verificar barato)
        self.assertEqual(policy_for("audio", {"action": "set_volume", "level": 100}).risk,
                         Risk.LOW)

    def test_app_open_low_risk_verified(self):
        p = policy_for("app", {"action": "open", "name": "Word"})
        self.assertEqual(p.risk, Risk.LOW)
        self.assertTrue(p.must_verify)

    def test_unknown_tool_defaults_medium(self):
        p = policy_for("some_future_tool", {"action": "frobnicate"})
        self.assertEqual(p.risk, Risk.MEDIUM)
        self.assertTrue(p.must_verify)

    def test_never_raises_on_garbage_args(self):
        for bad in (None, {}, {"action": None}, {"action": 123}):
            self.assertIsInstance(policy_for("email", bad), VerifyPolicy)

    def test_policy_coherent_with_safety_gate(self):
        # la tabla y el safety gate deben coincidir en quién confirma email/whatsapp
        self.assertEqual(
            policy_for("email", {"action": "send"}).require_user_confirmation,
            classify_tool_call("email", {"action": "send"}).requires_confirmation)
        self.assertEqual(
            policy_for("whatsapp", {"action": "send_message"}).require_user_confirmation,
            classify_tool_call("whatsapp", {"action": "send_message"}).requires_confirmation)


if __name__ == "__main__":
    unittest.main()
