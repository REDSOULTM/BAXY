"""Tests para la activación por voz de modos de accesibilidad.

DOS niveles:
1. Lógica de decisión (argmax + margen + piso + clase `none`) con centroides y
   embeddings SINTÉTICOS — determinista, sin cargar el modelo pesado.
2. maybe_switch_mode: persiste e ignora no-ops, con ACTIVE_MODE_PATH en tmpdir.

NO carga el encoder real (eso se mide aparte en _a11y_voice_eval.py). Mock-only.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from gemma4_agent.computer_use_pkg import accessibility_voice as av

from gemma4_agent.computer_use_pkg import accessibility as a11y



# Vectores ORTOGONALES por clase: clasificar = "qué centroide está más cerca".
# Cada clase es un eje canónico distinto en R5.
_AXES = {
    "no_vidente": np.array([1, 0, 0, 0, 0], dtype="float32"),
    "movilidad":  np.array([0, 1, 0, 0, 0], dtype="float32"),
    "normal":     np.array([0, 0, 1, 0, 0], dtype="float32"),
    "none":       np.array([0, 0, 0, 1, 0], dtype="float32"),
}


def _inject_centroids():
    av._C.by_class = dict(_AXES)
    av._C.ready = True


def _embed_as(class_name: str, purity: float = 1.0):
    """Devuelve un embed() falso que apunta (con `purity`) al eje de class_name,
    mezclado con `none` para simular un turno ambiguo cuando purity<1."""
    target = _AXES[class_name]
    nonev = _AXES["none"]
    vec = purity * target + (1 - purity) * nonev
    vec = vec / (np.linalg.norm(vec) or 1.0)
    return mock.patch.object(av, "_ensure_centroids", side_effect=lambda: (_inject_centroids() or True)), vec


class DecisionLogicTest(unittest.TestCase):
    def setUp(self):
        _inject_centroids()

    def _detect(self, class_name: str, purity: float = 1.0):
        target = _AXES[class_name] if class_name in _AXES else np.zeros(5, "float32")
        vec = purity * target + (1 - purity) * _AXES["none"]
        vec = (vec / (np.linalg.norm(vec) or 1.0)).astype("float32")
        with mock.patch.object(av, "_ensure_centroids", return_value=True), \
             mock.patch("gemma4_agent.semantic_router.embed", return_value=vec):
            return av.detect_mode_switch("x")

    def test_clear_no_vidente_fires(self):
        self.assertEqual(self._detect("no_vidente"), "no_vidente")

    def test_clear_movilidad_fires(self):
        self.assertEqual(self._detect("movilidad"), "movilidad")

    def test_clear_normal_fires(self):
        self.assertEqual(self._detect("normal"), "normal")

    def test_none_class_does_not_fire(self):
        # un turno que apunta a `none` (uso normal) NO debe disparar switch.
        self.assertIsNone(self._detect("none"))

    def test_ambiguous_turn_below_margin_does_not_fire(self):
        # 55% hacia no_vidente, 45% hacia none: la señal de switch no le gana a
        # none por el margen requerido -> no dispara (preferimos no cambiar).
        self.assertIsNone(self._detect("no_vidente", purity=0.52))

    def test_low_signal_below_floor_does_not_fire(self):
        # casi todo none, pizca de switch -> por debajo del piso absoluto.
        self.assertIsNone(self._detect("movilidad", purity=0.2))

    def test_degraded_encoder_returns_none(self):
        with mock.patch.object(av, "_ensure_centroids", return_value=False):
            self.assertIsNone(av.detect_mode_switch("activá modo no vidente"))

    def test_empty_text_returns_none(self):
        self.assertIsNone(av.detect_mode_switch(""))
        self.assertIsNone(av.detect_mode_switch("   "))


class MaybeSwitchTest(unittest.TestCase):
    def setUp(self):
        _inject_centroids()
        self._td = tempfile.TemporaryDirectory()
        self._path = Path(self._td.name) / "active_accessibility_mode.txt"
        self._p1 = mock.patch.object(a11y, "ACTIVE_MODE_PATH", self._path)
        self._p1.start()
        self._env = os.environ.pop("GEMMA4_ACCESSIBILITY_MODE", None)

    def tearDown(self):
        self._p1.stop()
        self._td.cleanup()
        if self._env is not None:
            os.environ["GEMMA4_ACCESSIBILITY_MODE"] = self._env

    def _detect_to(self, class_name):
        vec = _AXES[class_name].astype("float32")
        return mock.patch("gemma4_agent.semantic_router.embed", return_value=vec)

    def test_switch_persists_new_mode(self):
        with mock.patch.object(av, "_ensure_centroids", return_value=True), \
             self._detect_to("no_vidente"):
            m = av.maybe_switch_mode("x")
        self.assertIsNotNone(m)
        self.assertEqual(m.name, "no_vidente")
        self.assertEqual(a11y.get_active_mode().name, "no_vidente")

    def test_switch_to_current_mode_is_noop(self):
        a11y.set_active_mode("movilidad")
        with mock.patch.object(av, "_ensure_centroids", return_value=True), \
             self._detect_to("movilidad"):
            m = av.maybe_switch_mode("x")
        self.assertIsNone(m)  # ya estaba en ese modo -> no-op

    def test_no_switch_intent_leaves_mode_untouched(self):
        a11y.set_active_mode("no_vidente")
        with mock.patch.object(av, "_ensure_centroids", return_value=True), \
             self._detect_to("none"):
            m = av.maybe_switch_mode("abre el editor")
        self.assertIsNone(m)
        self.assertEqual(a11y.get_active_mode().name, "no_vidente")  # sin cambios


if __name__ == "__main__":
    unittest.main()
