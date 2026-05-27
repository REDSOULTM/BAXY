"""Tests para la guarda estructural anti-'pedir input manual' (modo movilidad).

Nivel lógica: centroides + embeddings SINTÉTICOS (determinista, sin modelo
pesado). La calidad con el encoder real se midió aparte (13/14, 0 falsos-pos).
Mock-only.
"""
from __future__ import annotations

import unittest
from unittest import mock

import numpy as np

from gemma4_agent import reply_validator as rv


# Dos ejes ortogonales: "manual" vs "ok".
_MANUAL = np.array([1, 0, 0], dtype="float32")
_OK = np.array([0, 1, 0], dtype="float32")


def _inject():
    rv._HF.manual = _MANUAL
    rv._HF.ok = _OK
    rv._HF.ready = True


class AsksManualActionTest(unittest.TestCase):
    def setUp(self):
        _inject()

    def _check(self, lean_to, purity=1.0):
        target = _MANUAL if lean_to == "manual" else _OK
        other = _OK if lean_to == "manual" else _MANUAL
        vec = (purity * target + (1 - purity) * other)
        vec = (vec / (np.linalg.norm(vec) or 1.0)).astype("float32")
        with mock.patch.object(rv, "_ensure_hands_free_centroids", return_value=True), \
             mock.patch("gemma4_agent.semantic_router.embed", return_value=vec):
            return rv.asks_user_manual_action("una respuesta cualquiera")

    def test_clear_manual_instruction_flags(self):
        self.assertTrue(self._check("manual"))

    def test_agent_acts_or_asks_does_not_flag(self):
        self.assertFalse(self._check("ok"))

    def test_ambiguous_below_margin_does_not_flag(self):
        # apenas inclinado a manual -> bajo el margen -> NO flaggea (conservador).
        self.assertFalse(self._check("manual", purity=0.55))

    def test_degraded_encoder_does_not_flag(self):
        with mock.patch.object(rv, "_ensure_hands_free_centroids", return_value=False):
            self.assertFalse(rv.asks_user_manual_action("hacé clic en aceptar"))

    def test_too_short_does_not_flag(self):
        self.assertFalse(rv.asks_user_manual_action("ok"))
        self.assertFalse(rv.asks_user_manual_action(""))

    def test_hint_text_mentions_movilidad_and_no_keyboard(self):
        # la corrección debe instruir al LLM a ACTUAR, no delegar.
        self.assertIn("MOVILIDAD", rv.HANDS_FREE_REGEN_HINT)
        self.assertIn("computer_use", rv.HANDS_FREE_REGEN_HINT)


# Ejes ortogonales para la guarda anti-DELEGACIÓN (UNIVERSAL movilidad/no_vidente).
_DELEGATE = np.array([1, 0, 0], dtype="float32")
_PROCEED = np.array([0, 1, 0], dtype="float32")


def _inject_delegate():
    rv._DG.delegate = _DELEGATE
    rv._DG.proceed = _PROCEED
    rv._DG.ready = True


class DelegatesTaskTest(unittest.TestCase):
    """La guarda que detecta cuando el agente le PASA la tarea al usuario
    ('revisá los resultados') en vez de seguir actuando. UNIVERSAL: aplica a
    cualquier tarea, no solo compras. Centroides sintéticos -> determinista."""

    def setUp(self):
        _inject_delegate()

    def _check(self, lean_to, purity=1.0):
        target = _DELEGATE if lean_to == "delegate" else _PROCEED
        other = _PROCEED if lean_to == "delegate" else _DELEGATE
        vec = (purity * target + (1 - purity) * other)
        vec = (vec / (np.linalg.norm(vec) or 1.0)).astype("float32")
        with mock.patch.object(rv, "_ensure_delegate_centroids", return_value=True), \
             mock.patch("gemma4_agent.semantic_router.embed", return_value=vec):
            return rv.reply_delegates_task("una respuesta cualquiera")

    def test_delegating_reply_flags(self):
        self.assertTrue(self._check("delegate"))

    def test_agent_proceeds_or_done_does_not_flag(self):
        self.assertFalse(self._check("proceed"))

    def test_ambiguous_below_margin_does_not_flag(self):
        self.assertFalse(self._check("delegate", purity=0.52))

    def test_degraded_encoder_does_not_flag(self):
        with mock.patch.object(rv, "_ensure_delegate_centroids", return_value=False):
            self.assertFalse(rv.reply_delegates_task("revisá los resultados y elegí"))

    def test_hint_says_do_not_delegate_and_keep_acting(self):
        self.assertIn("NO delegues", rv.DELEGATE_REGEN_HINT)
        self.assertIn("vision", rv.DELEGATE_REGEN_HINT)
        # debe permitir el "me trabé honesto" como salida válida.
        self.assertIn("honestidad", rv.DELEGATE_REGEN_HINT)


if __name__ == "__main__":
    unittest.main()
