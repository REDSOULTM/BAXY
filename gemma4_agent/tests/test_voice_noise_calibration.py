"""Auto-calibración del piso de ruido del micrófono (2026-06-07).

El gate de silencio fijo (MIN_CAPTURE_RMS=350) no era universal: en un mic ruidoso
quedaba por debajo del ambiente -> "oye voces donde no hay". El calibrador estima
el piso de ruido REAL de cada mic y pone el umbral por encima (factor ~2.8), con
pisos/techos de seguridad y re-ajuste EMA. Puro (sin audio) -> testeable.
"""
from __future__ import annotations

import unittest

from gemma4_agent.voice.noise_calibration import (
    NoiseFloorCalibrator,
    estimate_noise_floor,
    threshold_from_floor,
)


class NoiseCalibrationTest(unittest.TestCase):
    def test_threshold_is_relative_to_noise_not_absolute(self):
        # El umbral es RELATIVO al ruido de cada mic (universal): piso × factor.
        # NO un piso absoluto que asuma un nivel de hardware.
        t_low = threshold_from_floor(66.0)    # mic de baja ganancia
        t_high = threshold_from_floor(300.0)  # mic normal
        self.assertGreater(t_low, 66.0)       # por encima del ruido
        self.assertGreater(t_high, t_low)     # escala con el mic
        # proporcional: ~mismo ratio umbral/ruido en ambos
        self.assertAlmostEqual(t_low / 66.0, t_high / 300.0, places=3)

    def test_low_gain_mic_threshold_falls_between_noise_and_voice(self):
        # CASO REAL MEDIDO (2026-06-07): mic de baja ganancia, ruido≈66, voz≈125.
        # El umbral DEBE quedar entre los dos: capta la voz (125), corta el ruido (66).
        # El viejo piso fijo 250 ignoraba esta voz -> el bug "no me oye".
        cal = NoiseFloorCalibrator()
        self.assertTrue(cal.calibrate([60, 70, 66, 64, 72, 62, 68]))
        self.assertGreater(cal.threshold, 66.0)   # > ruido (no dispara con ambiente)
        self.assertLess(cal.threshold, 125.0)     # < voz (la capta)

    def test_noisy_mic_scales_up(self):
        # mic ruidoso (ventilador ~500): el umbral escala SOLO con el ambiente.
        cal = NoiseFloorCalibrator()
        self.assertTrue(cal.calibrate([450, 520, 480, 510, 495, 530, 470]))
        self.assertGreater(cal.threshold, cal.noise_floor)   # voz > ambiente
        self.assertGreater(cal.threshold, 500.0)             # escaló con el ruido

    def test_anti_zero_floor_for_silent_mic(self):
        # un mic en silencio digital total no debe dejar el umbral en 0 (dispararía
        # con cualquier bit). Hay un anti-cero ínfimo (no un piso alto que ignore voz).
        self.assertGreaterEqual(threshold_from_floor(0.0), 1.0)
        self.assertLess(threshold_from_floor(0.0), 130.0)  # pero NO tan alto que ignore voz de mic bajo

    def test_estimate_uses_percentile_not_max(self):
        # un pico aislado (un golpe) NO debe inflar el piso: el percentil 75 lo ignora.
        floor = estimate_noise_floor([50, 55, 52, 48, 60, 5000])  # 5000 = golpe
        assert floor is not None
        self.assertLess(floor, 200.0)  # el golpe no domina

    def test_insufficient_data_returns_none(self):
        self.assertIsNone(estimate_noise_floor([100]))
        cal = NoiseFloorCalibrator()
        self.assertFalse(cal.calibrate([100]))
        self.assertIsNone(cal.threshold)

    def test_ema_redrift_moves_slowly_then_converges(self):
        # el re-ajuste EMA sube despacio (no salta) cuando el ambiente cambia.
        cal = NoiseFloorCalibrator()
        cal.calibrate([50, 60, 55])
        t0 = cal.threshold
        cal.observe_silence(500)              # 1 ventana de ruido alto
        self.assertLess(cal.threshold - t0, 200)  # NO salta de golpe
        for _ in range(60):
            cal.observe_silence(500)
        self.assertGreater(cal.threshold, t0)      # pero converge hacia arriba

    def test_observe_silence_noop_before_calibration(self):
        cal = NoiseFloorCalibrator()
        cal.observe_silence(500)  # sin calibrar -> no-op, no crashea
        self.assertIsNone(cal.threshold)


if __name__ == "__main__":
    unittest.main()
