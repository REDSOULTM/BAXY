"""Sprint O calibration regression: `_has_pathological_ngram_repetition`
must accept legitimate operator rapid-fire while still catching real
Whisper hallucination loops.

The pre-O threshold was a hard `dups > 2` over all 2-grams and
3-grams. That rejected 3/6 testaudio turns where the operator
genuinely said the same command twice in a row. The post-O
threshold scales with text length: `dups > max(2, len(ngrams) // 2)`.

Don't make this gate stricter without re-running
`python scripts/stt_filter_audit.py` -- it WILL reject real speech
again.
"""
from __future__ import annotations

import unittest

from gemma4_agent.voice.stt import _has_pathological_ngram_repetition


class NgramRepetitionRegressionTest(unittest.TestCase):
    # --- Negative cases: legitimate operator rapid-fire MUST pass.

    def test_k1_ponme_musica_double_passes(self) -> None:
        # k=1 from testaudio_groundtruth_aligned.json. dups=9 in 29
        # 2-grams (ratio 0.31) -- not pathological.
        text = (
            "Ponme musica tranquila. Gemma, ponme musica tranquila. "
            "Gemma, reproduce algo de los redonditos. "
            "Gemma, reproduce algo de los redonditos. "
            "Gemma, baja el volumen. Gemma, suba el volumen al maximo. Gemma."
        )
        self.assertFalse(_has_pathological_ngram_repetition(text))

    def test_k2_gta_double_passes(self) -> None:
        # k=2: "Gemma, cuando salio GTA V? Gemma. Cuando salio GTA V?"
        text = "Cuando salio GTA V? Gemma. Cuando salio GTA V?"
        self.assertFalse(_has_pathological_ngram_repetition(text))

    def test_k5_buca_info_passes(self) -> None:
        # k=5: dups=12 in 28 2-grams (ratio 0.43) -- operator
        # repeated each command twice. Real speech, not halluc.
        text = (
            "Buca mi info sobre Benson Moon. "
            "Gemma, buca mi info sobre Benson Moon. "
            "Gemma, abre Counter-Strike 2 en Steam. "
            "Gemma, abre Counter-Strike 2 en Steam. "
            "Gemma, reproduce volumen Rhapsody."
        )
        self.assertFalse(_has_pathological_ngram_repetition(text))

    # --- Positive cases: real Whisper hallucination loops MUST be caught.

    def test_subscribe_loop_caught(self) -> None:
        # Real Whisper silence hallucination signature: a single
        # phrase repeated many times.
        text = (
            "gracias por ver el video " * 10
        ).strip()
        self.assertTrue(_has_pathological_ngram_repetition(text))

    def test_gemma_loop_caught(self) -> None:
        # Wake word looped on silence -- another known halluc.
        text = "gemma gemma gemma gemma gemma gemma gemma gemma"
        self.assertTrue(_has_pathological_ngram_repetition(text))

    def test_short_repetition_not_caught(self) -> None:
        # Very short text -- below the 6-word floor, gate skips.
        self.assertFalse(_has_pathological_ngram_repetition("hola hola"))

    def test_three_distinct_commands_passes(self) -> None:
        # Diverse rapid-fire commands -- few duplicate n-grams,
        # should not trip the gate.
        text = (
            "Gemma, abre Chrome. Gemma, cierra Steam. "
            "Gemma, pon musica relajante. Gemma, baja el volumen."
        )
        self.assertFalse(_has_pathological_ngram_repetition(text))


if __name__ == "__main__":
    unittest.main()
