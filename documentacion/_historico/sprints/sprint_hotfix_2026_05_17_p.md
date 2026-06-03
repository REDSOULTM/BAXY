# HOTFIX 2026-05-17 (P) — Silero-VAD endpointing + offline replay aligned to live pipeline

> Sprint surgido del informe de investigación post-Sprint N
> (compass_artifact_wf-a4b9c930-...). El informe recomendó P
> primero (VAD endpointing post-wake), pero el análisis pre-flight
> reveló que el pipeline LIVE ya tiene endpointing por RMS
> (`VAD_SILENCE_MS=500`). El verdadero problema es que:
>
> 1. El **script offline** `testaudio_analysis.py` usa ventana
>    fija de 15s — NO refleja el pipeline live. Las "false
>    positives" del Sprint N vinieron de darle a Whisper más
>    audio del que recibe en producción.
> 2. El endpointing live usa **RMS threshold** que es brittle —
>    confunde noise sostenido con speech, no detecta cuando el
>    user terminó la frase si murmuró las últimas palabras.
> 3. **Silero VAD ya está cargado** en `_SileroVAD` (line 213
>    stt.py) pero solo se usa para trim PRE-whisper. No se usa
>    para endpoint detection durante streaming.

---

## OBJETIVO

Dos commits chicos:

1. **`fix(voice): align offline analysis to live pipeline
   endpointing`** — `scripts/testaudio_analysis.py` deja de usar
   ventana 15s fija. En su lugar, simula el endpointing live
   (RMS silence o Silero VAD), cortando el segmento al primer
   silencio sostenido. El re-análisis del audio del operador
   con esta nueva lógica va a producir verdicts MUY distintos
   — probablemente revele que el pipeline live no tiene el bug
   que pensábamos.

2. **`feat(voice): upgrade endpoint detection from RMS to
   Silero VAD`** — durante `transcribe_stream`, reemplazar el
   chequeo `chunk_rms > SPEECH_RMS_THRESHOLD` por
   `silero_vad(chunk) > 0.5`. Más robusto contra noise
   sostenido (ventilador, AC, música de fondo). Mantiene
   `VAD_SILENCE_MS=500` o lo afina con sweep post-fix.

El Sprint NO va a hacer overhaul de la arquitectura streaming.
El endpointing ya existe; lo mejoramos donde tiene bug medible.

---

## REGLAS GENERALES

1. PortandoLoMejor. 2 commits chicos.
2. **NO toques** el quality_check de Whisper, BoH list, Plan B
   logic, prompt biasing. Esos van en sprints O / R1 después
   de P (per recomendación de la investigación).
3. **NO reemplaces** Whisper-small por large. Sprint Q.
4. **NO subas** `LISTENING_TIMEOUT_S` (5s sin speech → idle).
   Eso es safety net, no parte del endpointing.
5. **NO modifiques** el wake detector (Vosk). El recall era ~10%
   pero atribuído a m4a→wav conversion damage — descartable solo
   con audio nativo (sprint follow-up R2).
6. Auto-install OK para deps free (operator memory).
7. NO `git add -A`.

---

## FIX P.1 — Align offline analysis to live pipeline endpointing

### P.1.1 — Diagnóstico

`scripts/testaudio_analysis.py` actualmente hace (Sprint N):

```python
WINDOW_S = 15.0
WAKE_TAIL_S = 0.5
...
for wake in detections:
    start_idx = max(0, wake.idx - int(WAKE_TAIL_S * SAMPLE_RATE))
    end_idx = min(len(audio), wake.idx + int(WINDOW_S * SAMPLE_RATE))
    segment = audio[start_idx:end_idx]
    text, reason = stt._transcribe_buffer(segment)
```

Whisper recibe **15 segundos fijos** de audio post-wake. Si el
operador dijo "Gemma X. [pausa 1s] Gemma Y. [pausa 1s] Gemma Z."
todo en 15s, Whisper transcribe `"Gemma X. Gemma Y. Gemma Z."`
y el `ngram_repetition` filter lo mata.

**Pero el pipeline live NO hace eso**. En `stt.py:transcribe_stream`,
el endpoint se cierra cuando hay `VAD_SILENCE_MS=500` de silencio
RMS. Si el operador pausó 1s entre comandos, el live habría
cerrado al primer comando y empezado uno nuevo en el segundo
wake.

**Conclusión**: el Sprint N midió un escenario que el pipeline
live NO produce. Las 4 false_positives de la verdict
distribution probablemente desaparezcan al alinear el análisis
a la lógica real.

### P.1.2 — Fix al script

Editar `scripts/testaudio_analysis.py`. Reemplazar la extracción
de segment por una simulación del endpointing live:

```python
from gemma4_agent.voice.stt import (
    VAD_SILENCE_MS,
    SPEECH_RMS_THRESHOLD,
    SPEECH_MIN_CHUNKS,
    CHUNK_SAMPLES,  # 512 = 32ms
)


def _live_endpoint(audio: np.ndarray, start_idx: int,
                   max_s: float = 15.0) -> tuple[int, str]:
    """Simulate the live pipeline's endpointing logic over a
    pre-recorded audio array. Returns (end_idx, reason).

    Mimics stt.py:transcribe_stream RMS-based endpoint:
    - Wait for SPEECH_MIN_CHUNKS consecutive chunks with rms >
      SPEECH_RMS_THRESHOLD ("first_speech_t").
    - Then close when silence_ms >= VAD_SILENCE_MS since the
      last speech chunk ("last_speech_t").
    - Hard cap at max_s seconds (matches LISTENING_TIMEOUT_S
      ballpark but applied per-segment).

    This is what Whisper actually receives in the live pipeline
    — NOT the fixed 15s window the original analysis used.
    """
    n = len(audio)
    max_samples = int(max_s * SAMPLE_RATE)
    end_cap = min(n, start_idx + max_samples)
    speech_streak = 0
    first_speech_idx = None
    last_speech_idx = None
    silence_samples = 0
    silence_samples_threshold = int((VAD_SILENCE_MS / 1000.0) * SAMPLE_RATE)
    for i in range(start_idx, end_cap, CHUNK_SAMPLES):
        chunk = audio[i:i + CHUNK_SAMPLES]
        if len(chunk) < CHUNK_SAMPLES:
            break
        chunk_rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
        if chunk_rms > SPEECH_RMS_THRESHOLD:
            speech_streak += 1
            if speech_streak >= SPEECH_MIN_CHUNKS:
                if first_speech_idx is None:
                    first_speech_idx = i
                last_speech_idx = i + CHUNK_SAMPLES
                silence_samples = 0
        else:
            speech_streak = 0
            if first_speech_idx is not None:
                silence_samples += CHUNK_SAMPLES
                if silence_samples >= silence_samples_threshold:
                    return last_speech_idx, "endpoint_silence"
    if first_speech_idx is None:
        return start_idx, "no_speech_detected"
    return end_cap, "max_window"
```

(Si `SPEECH_MIN_CHUNKS` no es importable porque está hardcoded,
defínelo localmente con su valor real — buscalo con `grep`.)

Luego, en el loop principal del script, reemplazar:

```python
end_idx = min(len(audio), wake.idx + int(WINDOW_S * SAMPLE_RATE))
segment = audio[start_idx:end_idx]
```

por:

```python
# Sprint P.1: align to live pipeline — endpoint by RMS silence
# instead of fixed 15s window.
end_idx, endpoint_reason = _live_endpoint(
    audio, start_idx=wake.idx, max_s=15.0,
)
segment = audio[start_idx:end_idx]
```

Y agregar `endpoint_reason` y `segment_duration_s` al output
JSON para inspección.

### P.1.3 — Re-correr el análisis

```bash
python scripts/testaudio_analysis.py
```

Esto regenera `testaudio_analysis.json` con la nueva lógica.
**Hipótesis a validar**: los segmentos resultantes serán mucho
más cortos (~1-3s en lugar de 15s), y el verdict distribution
contra el ground truth de Sprint N debería mejorar dramáticamente
— quizás incluso eliminar todos los `small_rejected_false_positive`.

### P.1.4 — Re-comparar contra ground truth

`scripts/testaudio_groundtruth.py` (del Sprint N) también necesita
ajuste: la sección `_transcribe_aligned` usa el mismo `WINDOW_S=15`
hardcoded. Aplicar el mismo fix ahí (importar `_live_endpoint` o
duplicar la lógica). El re-run de groundtruth debe usar **la
misma ventana** que el análisis para que la comparación sea apple-
to-apple.

Verdict re-evaluation post-P.1:
- Si los `small_rejected_false_positive` caen a 0-1: confirma que
  era artifact del script offline. **No hay Sprint O necesario**.
- Si siguen ≥2: el filter genuinamente está rechazando speech
  legítima INCLUSO en ventanas correctas. Sprint O sigue siendo
  valioso.

### P.1.5 — Tests

`gemma4_agent/test_offline_analysis_endpointing.py`:

```python
"""P.1: scripts/testaudio_analysis._live_endpoint must close at
silence, not at fixed 15s. Sprint N analysis was unfairly
penalizing the pipeline because it gave Whisper 15s of audio
when the live pipeline gives only what's up to the first
VAD_SILENCE_MS gap."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _import_script():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "testaudio_analysis",
        ROOT / "scripts" / "testaudio_analysis.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class EndpointSimulationTest(unittest.TestCase):
    def setUp(self) -> None:
        from gemma4_agent.voice.audio_io import SAMPLE_RATE
        self.sr = SAMPLE_RATE
        self.mod = _import_script()

    def _build_audio(self, segments: list[tuple[float, bool]]) -> np.ndarray:
        """Build int16 audio from a list of (duration_s, is_speech).
        Speech = white noise at amplitude 5000; silence = zeros."""
        out = []
        for dur, is_speech in segments:
            n = int(dur * self.sr)
            if is_speech:
                out.append((np.random.randn(n) * 5000).astype(np.int16))
            else:
                out.append(np.zeros(n, dtype=np.int16))
        return np.concatenate(out)

    def test_closes_at_silence_not_at_max(self) -> None:
        # 2s speech + 1s silence + (would be more speech but cut by endpoint)
        audio = self._build_audio([(2.0, True), (1.0, False), (5.0, True)])
        end_idx, reason = self.mod._live_endpoint(audio, 0, max_s=15.0)
        # Should close after first speech + 500ms silence (= 2.5s)
        # not at 15.0s.
        end_s = end_idx / self.sr
        self.assertLess(end_s, 4.0,
                        f"endpoint should close at silence, got {end_s:.2f}s")
        self.assertEqual(reason, "endpoint_silence")

    def test_max_window_when_no_silence(self) -> None:
        audio = self._build_audio([(20.0, True)])
        end_idx, reason = self.mod._live_endpoint(audio, 0, max_s=10.0)
        end_s = end_idx / self.sr
        self.assertAlmostEqual(end_s, 10.0, delta=0.5)
        self.assertEqual(reason, "max_window")

    def test_no_speech_returns_start(self) -> None:
        audio = self._build_audio([(5.0, False)])
        end_idx, reason = self.mod._live_endpoint(audio, 0, max_s=10.0)
        self.assertEqual(end_idx, 0)
        self.assertEqual(reason, "no_speech_detected")

    def test_rapid_fire_split_into_separate_calls(self) -> None:
        # "Gemma X. [800ms silence] Gemma Y." → 2 calls produce
        # 2 separate endpoints when called sequentially.
        audio = self._build_audio([
            (1.5, True),   # "Gemma abre Chrome"
            (0.8, False),  # pause > VAD_SILENCE_MS (500ms)
            (1.5, True),   # "Gemma cierra Steam"
        ])
        # First call from idx=0 closes at first silence.
        end1, _ = self.mod._live_endpoint(audio, 0, max_s=15.0)
        end1_s = end1 / self.sr
        self.assertLess(end1_s, 2.5,
                        f"first endpoint should close <2.5s, got {end1_s:.2f}s")
        # Second call from end1 closes at second silence (or max).
        end2, _ = self.mod._live_endpoint(audio, end1, max_s=15.0)
        end2_s = end2 / self.sr
        self.assertGreater(end2_s, end1_s + 1.0,
                           "second segment should contain the second utterance")
```

### P.1.6 — Commit

`fix(voice): align offline analysis script to live pipeline endpointing`

Mensaje:

```
fix(voice): align offline analysis script to live pipeline endpointing

Sprint N's testaudio_analysis.py used a fixed 15s post-wake
window when extracting segments for Whisper, then compared
small vs large transcriptions of those 15s blocks. That led to
4/6 'small_rejected_false_positive' verdicts driven by
ngram_repetition firing on "Gemma X. Gemma Y. Gemma Z."
sequences captured in the same window.

But the LIVE pipeline does not do that. transcribe_stream in
voice/stt.py closes the segment at the first VAD_SILENCE_MS
(500ms) RMS-silence after speech begins. The 15s "window" was
an artifact of the offline analysis script, not the production
path.

Fix: add a _live_endpoint(audio, start_idx, max_s) helper to
scripts/testaudio_analysis.py that simulates the live RMS-based
endpoint detection. Replace the fixed window slice with
segments cut at the same silence threshold the live pipeline
uses. Re-run produces realistic per-wake segments (~1-3s
typical instead of 15s), enabling apples-to-apples comparison
against the live pipeline.

Same fix applied to scripts/testaudio_groundtruth.py (Sprint
N's aligned analyzer) so the ground truth comparison uses
matching windows.

This is observability + correctness for the offline tooling.
Live pipeline UNCHANGED. The interesting outcome is what the
re-run verdict distribution shows: if 'small_rejected_false_positive'
counts drop dramatically, the production filter is actually
fine and the original Sprint N report was diagnosing an
analysis-script artifact, not a pipeline bug.

Tests pin the endpoint behavior: closes at silence (not max),
hits max_window cap when no silence, returns start_idx when
no speech detected, splits rapid-fire correctly into separate
calls.
```

---

## FIX P.2 — Upgrade endpoint detection from RMS to Silero VAD

### P.2.1 — Diagnóstico

`stt.py:transcribe_stream` cierra el endpoint cuando hay
`VAD_SILENCE_MS=500` de silencio. La detección de silencio usa
**RMS threshold**:

```python
SPEECH_RMS_THRESHOLD = 200  # voz clara segun test de mic (rms ~3500)
...
if chunk_rms > SPEECH_RMS_THRESHOLD:
    speech_streak += 1
    ...
else:
    speech_streak = 0
```

Problemas conocidos del approach RMS:
- **Falso speech**: noise sostenido (ventilador, música de fondo,
  aire acondicionado) tiene RMS >200 — el endpoint nunca cierra.
- **Falso silence**: speech murmurada o final de frase con bajada
  de volumen → RMS <200 → silence streak comienza antes que el
  operador terminó.
- **Speech rapid-fire con pausas <500ms**: si entre "Gemma X" y
  "Gemma Y" el operador pausa 300ms, no llega al endpoint. El
  bug del Sprint N en versión más sutil.

**Silero VAD** (ya cargado en `_SileroVAD`) clasifica chunks como
speech/silence con un MLP entrenado, robusto a noise. La
investigación post-Sprint N específicamente recomienda usarlo
("la misma instancia de Silero recorta silencios dentro de una
ventana ya recortada; ahora casi nunca tiene trabajo. No cargar
el modelo dos veces").

### P.2.2 — Fix

En `stt.py:transcribe_stream` (línea ~956):

```python
# ANTES (RMS-based):
if chunk_rms > SPEECH_RMS_THRESHOLD:
    speech_streak += 1
    ...

# DESPUÉS (Silero VAD-based con RMS como fallback):
# Sprint P.2 2026-05-18: prefer Silero VAD for chunk-level speech
# detection. Falls back to RMS threshold if Silero fails (e.g.
# model load issue). RMS still serves as a sanity check on Silero
# to avoid edge cases where Silero spuriously fires on noise.
speech_detected = False
try:
    # Silero needs 512-sample chunks at 16kHz (matches CHUNK_SAMPLES).
    # The _SileroVAD instance's .predict(chunk) returns float prob.
    speech_prob = self._vad.predict_chunk(chunk)
    speech_detected = speech_prob >= 0.5
except Exception:
    speech_detected = chunk_rms > SPEECH_RMS_THRESHOLD
# Combined: Silero positive OR very clear RMS speech (safety net).
if speech_detected or chunk_rms > SPEECH_RMS_THRESHOLD * 5:
    speech_streak += 1
    ...
```

Esto requiere agregar `predict_chunk(self, chunk)` al `_SileroVAD`
class (línea 213). Buscar si ya existe; si no:

```python
class _SileroVAD:
    def predict_chunk(self, chunk: np.ndarray) -> float:
        """Return speech probability (0.0 to 1.0) for a single
        32ms chunk. Returns 0.0 if Silero is not loaded.

        Sprint P.2 2026-05-18: exposed for use as endpoint
        detection signal in transcribe_stream (was previously
        only used for pre-Whisper trim)."""
        if self._model is None:
            return 0.0
        import torch
        try:
            chunk_f32 = chunk.astype(np.float32) / 32768.0
            tensor = torch.from_numpy(chunk_f32)
            with torch.no_grad():
                prob = self._model(tensor, SAMPLE_RATE).item()
            return float(prob)
        except Exception as exc:
            logger.debug("silero predict_chunk failed: %s", exc)
            return 0.0
```

(Adaptá al shape real del Silero model loaded en `_SileroVAD.load`.
Si la API es `model(chunk, sr)` o similar, ajustá. Si requiere
streaming state, mantené un internal `_silero_state` que se resetea
al inicio de cada `transcribe_stream` call.)

### P.2.3 — Sweep de `VAD_SILENCE_MS` (opcional, encajable en el commit)

Una vez Silero está como source of truth, vale la pena un sweep
del threshold. La investigación recomienda 700ms; el código
actual usa 500ms. Conservar 500ms este sprint y dejar el sweep
para el siguiente — pero exponer la constante como env var para
permitir A/B sin recompile:

```python
VAD_SILENCE_MS = int(os.environ.get("GEMMA4_VOICE_SILENCE_MS", "500"))
```

### P.2.4 — Tests

`gemma4_agent/test_silero_endpoint.py`:

```python
"""P.2: transcribe_stream uses Silero VAD for chunk-level
endpoint detection. Falls back to RMS when Silero unavailable."""
from __future__ import annotations

import numpy as np
import unittest
from unittest.mock import patch


class SileroEndpointTest(unittest.TestCase):
    def test_silero_predict_chunk_returns_float(self) -> None:
        from gemma4_agent.voice.stt import _SileroVAD
        vad = _SileroVAD()
        # Without loading: returns 0.0.
        chunk = np.zeros(512, dtype=np.int16)
        prob = vad.predict_chunk(chunk)
        self.assertIsInstance(prob, float)
        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 1.0)

    def test_silero_predict_chunk_handles_failure_gracefully(self) -> None:
        from gemma4_agent.voice.stt import _SileroVAD
        vad = _SileroVAD()
        # Pass an invalid chunk size; should not raise.
        bad_chunk = np.zeros(100, dtype=np.int16)
        prob = vad.predict_chunk(bad_chunk)
        self.assertIsInstance(prob, float)

    def test_vad_silence_ms_env_override(self) -> None:
        import os
        os.environ["GEMMA4_VOICE_SILENCE_MS"] = "800"
        # Re-import to pick up the override.
        import importlib
        import gemma4_agent.voice.stt as stt_mod
        importlib.reload(stt_mod)
        try:
            self.assertEqual(stt_mod.VAD_SILENCE_MS, 800)
        finally:
            del os.environ["GEMMA4_VOICE_SILENCE_MS"]
            importlib.reload(stt_mod)
```

(El último test toca module reload — si rompe otras suites por
side effects, marcalo skip o reordená.)

### P.2.5 — Smoke test post-fix

Después de aplicar P.1 + P.2, re-correr ambos scripts:

```bash
python scripts/testaudio_analysis.py
python scripts/testaudio_groundtruth.py
```

Comparar:
- `testaudio_analysis.json` post-P.1: segmentos ahora ~1-3s
  típicos en vez de 15s. `endpoint_reason` poblado.
- `testaudio_groundtruth_aligned.json` post-P.1+P.2: verdict
  distribution actualizado. Hipótesis: ≥3 verdicts pasan de
  `small_rejected_false_positive` a `agree`.

### P.2.6 — Commit

`feat(voice): silero-VAD endpoint detection in transcribe_stream`

Mensaje:

```
feat(voice): silero-VAD endpoint detection in transcribe_stream

transcribe_stream closed segments at VAD_SILENCE_MS (500ms) of
silence post-speech. Silence detection used a simple RMS
threshold (SPEECH_RMS_THRESHOLD=200), which has known failure
modes:
- Sustained noise (fan, AC, background music) has RMS > 200,
  endpoint never closes → 15s+ buffers reach Whisper.
- Murmured speech tails fall under 200 RMS → silence streak
  starts before user finished.
- Rapid-fire commands with <500ms inter-pause look like
  continuous speech to RMS → multiple commands captured in
  one segment (the Sprint N bug, but subtler in production).

Fix: prefer Silero VAD's per-chunk speech probability for
endpoint detection. Silero is already loaded in _SileroVAD for
the pre-Whisper trim pass; expose .predict_chunk(chunk) so
transcribe_stream can call it on each 32ms chunk during
streaming. Silero is a small MLP trained on diverse speech;
robust to noise where RMS isn't.

Fallback: if Silero load failed or predict_chunk raises, fall
back to the RMS threshold path. Also keep a safety-net branch
"very clear RMS" (5× threshold) as belt-and-braces — if
chunk_rms is unambiguous speech, accept it regardless of
Silero's opinion.

VAD_SILENCE_MS now reads GEMMA4_VOICE_SILENCE_MS env var with
500 default. Lets operator A/B test 500/700/800ms without
recompile. Investigation post-Sprint N suggested 700ms is the
sweet spot; defer that calibration to a follow-up sprint with
sweep data from real usage.

NO change to: VAD trim pre-Whisper, quality_check, Plan B
logic, prompt biasing. Silero model load is unchanged (still
lazy in _SileroVAD).

Tests pin Silero.predict_chunk's contract (returns float
[0,1], handles bad input gracefully) + the env var override.

Expected impact: the 4 small_rejected_false_positive verdicts
from Sprint N should mostly resolve. If they don't (because
the production filter is genuinely too strict), Sprint O
(filter calibration) becomes the next step.
```

---

## REPORTE FINAL

Devolveme:
1. Hashes de los 2 commits.
2. Output de:
   ```
   python -m pytest gemma4_agent/test_offline_analysis_endpointing.py
                    gemma4_agent/test_silero_endpoint.py -v
   ```
3. Output de `python -m pytest gemma4_agent/ -q --tb=line`
   (suite completa, debe seguir verde).
4. Output de re-correr ambos scripts:
   ```
   python scripts/testaudio_analysis.py
   python scripts/testaudio_groundtruth.py
   ```
5. **Comparación crítica**: verdict distribution de
   `testaudio_groundtruth_aligned.json` ANTES (4
   false_positive, 2 underproduced, 0 agree) vs DESPUÉS.
6. Segment duration distribution post-P.1: cuántos turns
   tienen `segment_duration_s` < 3s, < 5s, < 10s, < 15s.

## CRITERIO DE ÉXITO

- 2 commits aterrizados.
- ≥6 tests nuevos verdes.
- Suite completa verde (modulo Sprint 3a baseline + E.5 xfail).
- `testaudio_analysis.json` regenerado: cada turn tiene
  `endpoint_reason` y `segment_duration_s` field.
- `testaudio_groundtruth_aligned.json` regenerado con la nueva
  ventana.
- **Verdict distribution mejora**: ≥3 turns pasan de
  `small_rejected_false_positive` a `agree` o
  `small_rejected_legit`. Si NO mejora, Sprint O sigue siendo
  válido — reportar honestamente.
- Pipeline live no regresa: confirmá manualmente abriendo una
  sesión de voz, decí "Hey Gemma, abre Chrome" y verificá que
  el agente responde. NO se rompe nada que ya funcionaba.

## NO HACER (anti-scope)

- NO calibres `VAD_SILENCE_MS` arbitrariamente. El default 500
  se mantiene; el env var permite A/B pero hardcoded sigue
  siendo 500.
- NO modifiques quality_check. Sprint O.
- NO modifiques BoH list. Sprint M ya lo hizo.
- NO toques Plan B retry o prompt biasing. Sprint R1.
- NO subas Whisper-small a otro modelo. Sprint Q.
- NO refactorices el `_SileroVAD` class más allá de exponer
  `predict_chunk`. Si la integración requiere refactor pesado
  (multi-instance, state management complejo), parate y reportá.
- NO toques wake.py, controller state machine, recorder. Solo
  el endpoint dentro de transcribe_stream.
- Si Silero predict_chunk no se puede agregar sin tocar la
  inferencia (el modelo loaded usa una API distinta), commit
  P.1 solo y dejá P.2 como follow-up con TODO claro. P.1 ya
  desbloquea la medición correcta.

## Follow-ups documentados

1. **Sprint O — filter calibration**: solo si post-P.2 quedan
   ≥2 false_positives. Calibración de ngram_repetition,
   no_speech_prob threshold, etc.
2. **Sprint R1 — hotwords migration**: per recomendación
   investigación, migrar `initial_prompt` (892 chars) a
   `hotwords="Gemma Chrome Steam Netflix"` + `initial_prompt`
   vacío. Resuelve el bug del code-switch loss (k=4).
3. **Sprint Q — model upgrade**: large-v3-turbo en int8_float16,
   con benchmark de latency y VRAM en hardware operador.
   Solo si post-P+O+R1 sigue WER >0.2 promedio.
4. **Sprint R2 — openWakeWord**: reemplazar Vosk para mejorar
   recall (~10% en m4a; medir con WAV nativo primero antes de
   decidir).
5. **CUDA DLL fix**: el Sprint N corrió Whisper-large en CPU
   por DLL missing. Antes del Sprint Q, asegurar CUDA funciona
   para mediciones de latency reales.
6. **VAD_SILENCE_MS sweep**: con env var expuesto, correr una
   sesión de 30 turns en 500ms y otra en 700ms; comparar UX
   feel y false-cut rate.
