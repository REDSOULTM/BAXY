"""Fixes de la cadena de transcripción (2026-06-11), medidos con
scripts/voice_chain_eval.py sobre 84 comandos reales × 3 condiciones:

1. EOS TRI-ESTADO: con fondo hablado el VAD ve "speech" eterno y la captura
   jamás cerraba (75/84 atascadas a SNR 5 → timeout 8 s + diálogo ajeno al
   LLM). Ahora decide contra el nivel típico del fondo (p75): quieto cuenta,
   evidencia-de-usuario resetea, zona gris mantiene.
2. PISO ROBUSTO: el EMA por-chunk se inflaba con la PROPIA frase de wake
   (~64% hacia nivel de voz) → cortes a mitad de comando. Ahora p25/p75 de
   ventana rodante.
3. Drops de alucinación SOLO para texto de Whisper: Parakeet no alucina en
   silencio — "gracias"/"okay" son palabras reales y van al LLM.
4. SEGUNDA OPORTUNIDAD: "Baxy" solo (transcript vacío post-strip) reabre la
   ventana de escucha una vez, en vez de descartar en silencio.
"""
from __future__ import annotations

import numpy as np
import pytest

from gemma4_agent.voice.noise_calibration import NoiseFloorCalibrator
from gemma4_agent.voice.pipeline import (
    VoicePipeline, State, _energy_trim, SAMPLE_RATE,
)


# ---------- calibrador robusto ----------

def test_floor_no_se_infla_con_rafaga_de_voz():
    """La frase de wake (~20 chunks de voz) NO debe arrastrar el piso hacia el
    nivel de voz (el EMA viejo lo movía ~64%)."""
    cal = NoiseFloorCalibrator()
    assert cal.calibrate([50.0] * 40)
    base = cal.noise_floor
    for _ in range(80):
        cal.observe(50.0)
    for _ in range(20):       # ráfaga de voz (wake)
        cal.observe(3000.0)
    assert cal.noise_floor < base * 2.0, \
        f"piso inflado por la voz: {base} -> {cal.noise_floor}"


def test_background_level_sigue_al_fondo():
    """Con fondo continuo (película) el nivel p75 converge al nivel del fondo."""
    cal = NoiseFloorCalibrator()
    assert cal.calibrate([50.0] * 40)
    for _ in range(400):
        cal.observe(800.0)    # película constante
    assert cal.background_level is not None
    assert cal.background_level > 400, cal.background_level


# ---------- energy trim ----------

def test_energy_trim_recorta_fondo_lateral():
    sr = SAMPLE_RATE
    bg = (np.random.RandomState(7).randn(3 * sr) * 300).astype(np.int16)
    voice = (np.random.RandomState(8).randn(sr) * 3000).astype(np.int16)
    audio = np.concatenate([bg, voice, bg])
    out = _energy_trim(audio, rms_threshold=800.0)
    assert out is not None
    assert out.size < audio.size * 0.5          # recortó el fondo lateral
    assert out.size >= voice.size               # conservó la voz + pads


def test_energy_trim_none_si_nada_supera():
    audio = (np.random.RandomState(9).randn(SAMPLE_RATE) * 100).astype(np.int16)
    assert _energy_trim(audio, rms_threshold=5000.0) is None


# ---------- EOS tri-estado ----------

def _pipe_stub() -> VoicePipeline:
    p = VoicePipeline.__new__(VoicePipeline)
    p._manual_rms_override = False
    p._eos_silence_count = 0
    p._eos_silence_chunks_needed = 5
    p._capture_buf = []
    import time as _t
    p._capture_start_ts = _t.monotonic() - 2.0   # MIN_CAPTURE pasó, timeout no
    p._state = State.CAPTURE
    import threading
    p._state_lock = threading.Lock()
    p._finishes = []
    p._finish_capture = lambda reason: p._finishes.append(reason)  # type: ignore

    class _VadSpeechAlways:
        def is_speech(self, chunk, threshold=0.5):
            return True   # el fondo hablado: VAD dice speech SIEMPRE

    p._vad = _VadSpeechAlways()

    class _Cal:
        background_level = 800.0
        noise_floor = 300.0
    p._noise_cal = _Cal()
    return p


def _chunk(rms: float) -> np.ndarray:
    x = np.random.RandomState(3).randn(512)
    x = x / (np.sqrt(np.mean(x ** 2)) + 1e-9) * rms
    return x.astype(np.int16)


def test_eos_cierra_con_fondo_hablado():
    """VAD dice speech eterno (película) pero los chunks están AL nivel del
    fondo -> cuentan como quietos y el EOS dispara. (El stub de
    _finish_capture no transiciona estado, así que alimentamos EXACTO los
    chunks necesarios; en prod la transición corta el feed.)"""
    p = _pipe_stub()
    for _ in range(5):
        p._handle_capture(_chunk(700.0))   # ~nivel fondo (<= bg*1.10)
    assert p._finishes == ["eos_silence"]


def test_eos_resetea_con_voz_del_usuario():
    p = _pipe_stub()
    for _ in range(4):
        p._handle_capture(_chunk(700.0))
    p._handle_capture(_chunk(2000.0))      # voz del usuario (> bg*1.25)
    assert p._eos_silence_count == 0
    assert p._finishes == []


def test_eos_zona_gris_mantiene_contador():
    """Una ráfaga de la película (entre bg*1.10 y bg*1.25) NO resetea."""
    p = _pipe_stub()
    for _ in range(4):
        p._handle_capture(_chunk(700.0))
    count = p._eos_silence_count
    p._handle_capture(_chunk(950.0))       # gris: 800*1.10=880 < 950 < 1000
    assert p._eos_silence_count == count
    p._handle_capture(_chunk(700.0))
    assert p._finishes == ["eos_silence"]


# ---------- segunda oportunidad ----------

def test_segunda_oportunidad_reabre_y_solo_una_vez():
    p = VoicePipeline.__new__(VoicePipeline)
    import threading
    import time as _t
    p._state = State.COOLDOWN
    p._state_lock = threading.Lock()
    p._eos_silence_count = 7
    p._capture_buf = [np.zeros(512, np.int16)]
    p._on_wake_event = None
    p._on_state = None
    p._second_chance = False
    assert p._maybe_second_chance("eos_silence") is True
    assert p.state == State.CAPTURE
    assert p._eos_silence_count == 0 and p._capture_buf == []
    assert _t.monotonic() - p._capture_start_ts < 1.0
    # segunda vez: NO reabre (anti-loop)
    assert p._maybe_second_chance("eos_silence") is False


def test_segunda_oportunidad_no_aplica_a_timeout():
    p = VoicePipeline.__new__(VoicePipeline)
    import threading
    p._state = State.COOLDOWN
    p._state_lock = threading.Lock()
    p._second_chance = False
    p._on_wake_event = None
    p._on_state = None
    assert p._maybe_second_chance("timeout") is False
    assert p.state == State.COOLDOWN


# ---------- gate de no-evidencia-de-usuario (2026-06-12) ----------
#
# Fake-wake con música de fondo: la captura es PURO fondo, el STT lo
# transcribe FIELMENTE (Parakeet produjo "Thank you." de la música — no es
# alucinación de silencio, la lista no aplica) y el turno fantasma llegaba al
# LLM. Si ninguna ventana supera fondo×factor, no habló nadie → NO_SPEECH.

def _pipe_for_finish(bg_level: float = 800.0) -> VoicePipeline:
    import threading
    p = VoicePipeline.__new__(VoicePipeline)
    p._manual_rms_override = False
    p._state = State.CAPTURE
    p._state_lock = threading.Lock()
    p._eos_silence_count = 0
    p._states: list[str] = []
    p._emit_state = lambda s: p._states.append(s)  # type: ignore
    p._commands: list[str] = []
    p._on_command = lambda text, dur, raw: p._commands.append(text)  # type: ignore
    p._stt_calls: list[int] = []

    class _Stt:
        def transcribe(self, audio, **kw):
            p._stt_calls.append(audio.size)
            return "pon musica"
    p._stt = _Stt()

    class _Corr:
        def strip_wake_phrase(self, t):
            return t

        def correct(self, t):
            return t
    p._corrector = _Corr()

    class _Prof:
        whisper_language = "es"
    p._lang_profile = _Prof()
    p._hotwords = None
    p._initial_prompt = ""
    p._lid_rescue = lambda audio, raw: None  # type: ignore
    p._stt_engine = "parakeet"
    p._second_chance = False

    class _Vad:
        def reset(self):
            pass

        def trim_silence(self, audio):
            return audio
    p._vad = _Vad()

    class _Wake:
        def reset(self):
            pass
    p._wake = _Wake()

    class _Cal:
        background_level = bg_level
        noise_floor = bg_level / 2
        threshold = bg_level / 2   # gate de silencio bajo: el fondo lo pasa
    p._noise_cal = _Cal()
    return p


def _buf_chunks(rms: float, seconds: float) -> list[np.ndarray]:
    n = int(seconds * SAMPLE_RATE)
    x = np.random.RandomState(11).randn(n)
    x = x / (np.sqrt(np.mean(x ** 2)) + 1e-9) * rms
    return [x.astype(np.int16)]

def test_no_user_evidence_gate_dropea_fondo_puro():
    """Captura = solo música al nivel del fondo -> NO_SPEECH, sin STT ni LLM."""
    p = _pipe_for_finish(bg_level=800.0)
    p._capture_buf = _buf_chunks(rms=850.0, seconds=2.0)   # < 800*1.25
    p._finish_capture("eos_silence")
    assert "NO_SPEECH" in p._states
    assert p._commands == []
    assert p._stt_calls == []          # ni siquiera transcribió (latencia 0)
    assert p.state == State.COOLDOWN


def test_no_user_evidence_gate_deja_pasar_voz_sobre_fondo():
    """Voz real (> fondo*1.41) dentro de la captura -> transcribe y emite."""
    p = _pipe_for_finish(bg_level=800.0)
    bg = _buf_chunks(rms=850.0, seconds=1.0)[0]
    voice = _buf_chunks(rms=2000.0, seconds=0.6)[0]
    p._capture_buf = [bg, voice, bg]
    p._finish_capture("eos_silence")
    assert p._commands == ["pon musica"]
    assert len(p._stt_calls) == 1


def test_no_user_evidence_gate_noop_en_sala_silenciosa():
    """Sin fondo (bg ínfimo): la voz lo supera de sobra -> comportamiento clásico."""
    p = _pipe_for_finish(bg_level=20.0)
    p._capture_buf = _buf_chunks(rms=1500.0, seconds=1.0)
    p._finish_capture("eos_silence")
    assert p._commands == ["pon musica"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
