# HOTFIX 2026-05-17 (M.1) — Voice recorder polish: TTS capture, wake conf, STT reason, eager finish

> Sprint chico de follow-up al recorder de Sprint L. Análisis de
> la primera sesión real grabada (`~/.gemma4/recordings/
> 20260518_120744/`) surfaceó 4 gaps en el wiring. El bug central
> de Sprint M ya está identificado y queda como sprint separado;
> este es polish del recorder mismo.

---

## Contexto: los 4 gaps observados

Inspecionando la sesión `20260518_120744` (11 turns, manifest +
WAVs preservados):

### Gap M.1.1 — `.tts.wav` solo se generó UNA vez de 3 turns con TTS

WAVs en la sesión:
```
turn_11097718.tts.wav    73260 bytes   ← capturado
turn_11097718.user.wav  415404 bytes
turn_11125031.user.wav  220844 bytes   ← falta .tts.wav (tuvo reply)
turn_11201390.user.wav  128320 bytes   ← falta .tts.wav (tuvo "Listo, abrí Steam")
... (7 turns más, todos rechazados por STT)
```

Solo el primer turn tiene `.tts.wav`. Los otros 2 turns que sí
tuvieron TTS reply NO se capturaron. Causa probable: race entre
`finish_turn` (cierra turn N) y los chunks de TTS del turn N+1
que llegan **antes** que el próximo `start_turn`.

El call order real es:
```
_handle_final(text) → llama al agent → reply text → tts.begin_tts(text)
                                          ↓
                                   piper.synthesize() produce chunks
                                   capture_tts_chunk() <-- aquí
                                          ↓
                                   end_tts() → finish_turn()
```

Si el agent reply tarda > 100ms (que siempre) y el siguiente
wake llega antes de que `end_tts` complete su wait-and-transition,
hay una ventana donde el TTS audio del turn N llega DESPUÉS de
`start_turn(N+1)`. Eso explica por qué solo un turn capturó TTS.

PERO HAY OTRA causa posible: el primer turn fue `quien es Watman`
con reply largo (15 segundos), el segundo `tienes Batman` con
reply corto. Si el segundo reply termina antes que el writer
queue procese sus chunks, y `finish_turn` cierra antes que el
queue procese... → los chunks quedan huérfanos.

### Gap M.1.2 — `wake_confidence: 0.0` en todos los turns

El call en `_on_wake_detected` pasa `wake_confidence=0.0` porque
el caller (`WakeDetector`) no propaga la confidence al
controller. Sprint L lo anotó como TODO; este sprint lo cierra.

Útil para wake-detector calibration y para distinguir
"low-confidence wake (false positive likely)" de "high-confidence
wake (user really said gemma)" en review post-hoc.

### Gap M.1.3 — `stt_reject_reason: "stt_empty_or_vad_reject"` es genérico

7 turns rechazados, todos con la misma razón genérica. El
verdadero motivo era `BoH_match` (Sprint M lo arregla). Para
diagnosticar el bug se tuvo que re-correr Whisper manualmente
en cada WAV — 30 minutos de trabajo que un campo más específico
hubiera ahorrado.

`stt.py:_quality_check` ya devuelve `(False, reason)` con la
razón exacta (`BoH_match`, `low_logprob`, `no_speech_prob`,
`compression_ratio`, etc.). Pero `_transcribe_buffer` solo
devuelve `""` cuando rechaza — la razón se pierde. Necesitamos
propagar la `reason` al controller para que la pase al recorder.

### Gap M.1.4 — Turn cierra recién cuando llega el siguiente wake

Cuando STT rechaza:
- `_handle_final("")` → no llama `tts.begin_tts` → `end_tts` no
  se llama → `finish_turn` no se llama.
- El turn queda abierto hasta el próximo wake → en `start_turn(N+1)`
  el código cierra el anterior con `reason="overlapping_new_turn"`.

Resultado: 7 turns con `finish_reason: "overlapping_new_turn"`
cuando técnicamente fueron `stt_rejected`. El manifest queda
diferido y la finish_reason mientiría sobre la causa real.

---

## OBJETIVO

Un commit chico. **Cerrar los 4 gaps** del recorder identificados
en la sesión real:

1. M.1.1: garantizar que `.tts.wav` se capture en cada reply
   (race fix).
2. M.1.2: propagar `wake_confidence` real desde Vosk al recorder.
3. M.1.3: propagar la razón específica del STT reject (BoH_match
   / low_logprob / etc) al manifest.
4. M.1.4: cerrar el turn cuando STT rechaza con
   `reason="stt_rejected"` en vez de esperar al próximo wake.

---

## REGLAS GENERALES

1. PortandoLoMejor. Un commit chico, prefijo `fix(voice):`.
2. **NO toques** la lógica de wake detection, VAD, Whisper model,
   Piper synthesis, router, prompts.
3. **Mantener zero latency cost al critical path**. Todas las
   anotaciones al recorder van con try/except y no bloquean voice.
4. NO instales libs nuevas.
5. NO `git add -A`.

---

## FIX M.1.1 — TTS capture race condition

### M.1.1a — Diagnóstico

El TTS chunk se captura en `tts.py::_synthesize_and_play` línea
317-321:
```python
if _recorder is not None:
    try:
        _recorder.capture_tts_chunk(audio)
    except Exception:
        pass
```

El problema: `_recorder` se cachea **una vez por utterance**
(línea 298-303). Si `_active_turn` cambia DURANTE la síntesis
(porque el writer drain está atrasado o el nuevo wake llegó),
el `capture_tts_chunk` queda apuntando a un turn que ya no es
el correcto.

PERO el bug real (mirar el code) es que **`capture_tts_chunk`
chequea `self._active_turn is None`** dentro del recorder
(línea 215 del recorder.py). Si entre el `finish_turn` del turn
N y el `start_turn` del turn N+1 llega un chunk TTS del turn N,
el chunk se descarta porque `self._active_turn is None`.

### M.1.1b — Fix: capturar al turn ACTIVO en el momento de
producir el chunk, no a un cached recorder

Cambiar `voice/recorder.py::capture_tts_chunk` para que **no
descarte chunks si hay un turn cerrándose**. La forma simple:
agregar un campo `_just_finished_turn` que recuerda el último
turn cerrado por hasta 2 segundos. Si llega un chunk TTS justo
después de `finish_turn`, se asocia al turn recién cerrado en
lugar de tirarlo.

Editar `gemma4_agent/voice/recorder.py`:

```python
# Add to __init__:
self._just_finished_turn: _ActiveTurn | None = None
self._just_finished_at: float = 0.0
_GRACE_AFTER_FINISH_S = 2.0
```

(Constante `_GRACE_AFTER_FINISH_S = 2.0` near top of module.)

En `finish_turn`, después de `self._active_turn = None`, agregar:
```python
# Race fix M.1.1: TTS chunks may arrive shortly AFTER end_tts
# returns (Piper worker thread is async). Keep a reference to
# the just-closed turn for a short grace window so late chunks
# get appended to the correct .tts.wav instead of being dropped.
with self._writer_lock:
    self._just_finished_turn = turn
    self._just_finished_at = time.time()
```

Y en `capture_tts_chunk`, modificar para usar el grace window:
```python
def capture_tts_chunk(self, chunk: np.ndarray) -> None:
    """Enqueue a TTS chunk for the active turn, OR for a just-
    finished turn within the M.1.1 grace window (handles Piper
    async race)."""
    if not self._enabled:
        return
    # Prefer active turn; fall back to just-finished within grace.
    if self._active_turn is None:
        if (
            self._just_finished_turn is not None
            and time.time() - self._just_finished_at < _GRACE_AFTER_FINISH_S
        ):
            # Route to the just-finished turn. The writer loop
            # resolves the target lazily; we tag here.
            try:
                self._writer_queue.put_nowait(("tts_finished_turn", chunk))
            except _queue.Full:
                self._dropped_chunks += 1
            return
        return
    try:
        self._writer_queue.put_nowait(("tts", chunk))
    except _queue.Full:
        self._dropped_chunks += 1
```

Y en `_writer_loop`, agregar el handling de `"tts_finished_turn"`:
```python
def _writer_loop(self) -> None:
    while True:
        try:
            item = self._writer_queue.get(timeout=0.5)
        except _queue.Empty:
            continue
        kind, chunk = item
        if kind == "__stop__":
            return
        with self._writer_lock:
            turn = self._active_turn
            finished_turn = self._just_finished_turn
        if chunk is None:
            continue
        try:
            if kind == "user" and turn is not None:
                if turn.user_writer is None:
                    turn.user_writer = self._open_wav(turn.user_path)
                if turn.user_writer is not None:
                    self._write_chunk(turn.user_writer, chunk)
                    turn.user_samples_written += int(chunk.size)
            elif kind == "tts" and turn is not None:
                if turn.tts_writer is None:
                    turn.tts_writer = self._open_wav(turn.tts_path)
                if turn.tts_writer is not None:
                    self._write_chunk(turn.tts_writer, chunk)
                    turn.tts_samples_written += int(chunk.size)
            elif kind == "tts_finished_turn" and finished_turn is not None:
                # Race fix M.1.1: late TTS chunk for the just-
                # closed turn. Open or reuse the .tts.wav and
                # append. The writer was already closed; reopen
                # in append mode is tricky with `wave` (no
                # native append). Workaround: keep the writer
                # cached longer — close it in shutdown() or when
                # the grace window expires.
                with self._writer_lock:
                    # Reopen if needed (write mode truncates;
                    # we ONLY do this if no writer was ever
                    # created for tts).
                    if finished_turn.tts_writer is None:
                        finished_turn.tts_writer = self._open_wav(
                            finished_turn.tts_path
                        )
                    if finished_turn.tts_writer is not None:
                        self._write_chunk(finished_turn.tts_writer, chunk)
                        finished_turn.tts_samples_written += int(chunk.size)
        except Exception as exc:
            logger.warning(
                "voice_recorder_write_failed kind=%s error=%s",
                kind, exc,
            )
```

**Caveat**: `wave.open(..., "wb")` truncates. Si llega un chunk
después de que ya cerramos el writer, podríamos sobrescribir.
Mitigación: solo abrir un writer nuevo si `tts_writer is None`
(no fue abierto antes). Si ya tiene chunks escritos pero el
writer fue cerrado, el chunk se pierde. Esto es OK porque el
caso común es "TTS arrancó tarde y nunca escribió chunks antes
del finish_turn".

Alternativamente, simplificar **no cerrando el `tts_writer`
inmediatamente** en `finish_turn`. Mantener el writer abierto
durante la grace window. En `finish_turn`:

```python
# Close user_writer immediately, but DEFER tts_writer close
# until the grace window expires (or shutdown). This handles
# the M.1.1 race where Piper chunks arrive after end_tts.
if turn.user_writer is not None:
    try:
        turn.user_writer.close()
    except Exception:
        pass
    turn.user_writer = None
# tts_writer stays open; cleanup happens lazily.
```

Y agregar un cleanup periódico — en `start_turn`, antes de
crear el nuevo turn, cerrar el `tts_writer` del `_just_finished_
turn` si la grace expiró:

```python
def start_turn(self, ...):
    # ... existing logic ...
    # Cleanup: close the previous turn's tts_writer if grace expired.
    if (
        self._just_finished_turn is not None
        and time.time() - self._just_finished_at >= _GRACE_AFTER_FINISH_S
    ):
        if self._just_finished_turn.tts_writer is not None:
            try:
                self._just_finished_turn.tts_writer.close()
            except Exception:
                pass
            self._just_finished_turn.tts_writer = None
        self._just_finished_turn = None
```

Y en `shutdown`, cerrar todo:
```python
def shutdown(self) -> None:
    if self._active_turn is not None:
        self.finish_turn(reason="shutdown")
    # Close any pending just-finished tts_writer too.
    if self._just_finished_turn is not None:
        if self._just_finished_turn.tts_writer is not None:
            try:
                self._just_finished_turn.tts_writer.close()
            except Exception:
                pass
        self._just_finished_turn = None
    # ... existing thread stop logic ...
```

Esa estrategia es más simple — el `tts_writer` queda abierto y
sigue aceptando chunks por hasta GRACE_AFTER_FINISH_S segundos,
luego se cierra en el próximo `start_turn` o `shutdown`.

---

## FIX M.1.2 — Wake confidence

### M.1.2a — Pasar confidence desde WakeDetector

`gemma4_agent/voice/wake.py` ya tiene `WAKE_MIN_CONFIDENCE = 0.85`
y calcula confidence por wake event. Necesitamos que el callback
`_on_wake_detected` reciba ese valor.

Pre-flight:
```bash
grep -n "WAKE_MIN_CONFIDENCE\|on_wake\|wake_callback\|wake_confidence\|conf" gemma4_agent/voice/wake.py | head -20
```

Localizar dónde Vosk invoca el callback del controller. La
signature actual es:
```python
def _on_wake_detected(self, phrase: str, ts: float, tail_s: float = 0.0)
```

Cambiar signature a:
```python
def _on_wake_detected(
    self,
    phrase: str,
    ts: float,
    tail_s: float = 0.0,
    confidence: float = 0.0,
) -> None
```

Y en wake.py, donde dispara el callback, pasar la confidence
que ya tiene calculada (busca `WAKE_MIN_CONFIDENCE` y mira si
hay una variable `conf` cerca):

```python
# In wake.py — find where it calls the callback. Update from:
#   self._callback(phrase, ts, tail_s)
# To:
#   self._callback(phrase, ts, tail_s, confidence=conf)
```

En controller.py, dentro de `_on_wake_detected`, usar
`confidence` en lugar del `0.0` hardcoded:

```python
recorder.start_turn(
    turn_id=turn_id,
    wake_phrase=phrase,
    wake_confidence=float(confidence),  # was 0.0
    pre_wake_audio=pre,
)
```

Si por algún motivo `wake.py` no expone la confidence directamente
en el callback (e.g. está en una variable local del loop que
genera el callback), pasala explícitamente. Si requiere refactor
de >10 líneas, dejá un TODO claro y avanzá con `0.0` — los demás
fixes son más importantes.

---

## FIX M.1.3 — STT reject reason específica

### M.1.3a — Cambiar la signature de `_transcribe_buffer`

`stt.py:691` actualmente:
```python
def _transcribe_buffer(self, audio_int16: np.ndarray) -> str:
    # ... returns "" on rejection
```

Cambiar a:
```python
def _transcribe_buffer(self, audio_int16: np.ndarray) -> tuple[str, str]:
    """Returns (text, reason). text is "" on rejection; reason
    indicates WHY ('ok', 'no_speech', 'too_short', 'BoH_match',
    'low_logprob', etc)."""
```

Donde `_quality_check` rechaza, ya tenemos la `reason` —
propagarla:
```python
# Si pass-1 falla quality y Plan B no aplica, devolver (text, reason).
if not ok and verb is None:
    return "", reason

# Si VAD rechaza:
if trimmed is None:
    logger.warning(...)
    return "", "no_speech"

if trimmed.size < int(0.3 * SAMPLE_RATE):
    logger.warning(...)
    return "", "too_short"

# Si pass-1 OK:
return post_processed_text, "ok"
```

(Adaptá al control flow real del archivo — buscá todos los
`return ""` y reemplazá por tuplas.)

### M.1.3b — Caller path

Buscar quién llama a `_transcribe_buffer`:
```bash
grep -n "_transcribe_buffer\|transcribe_buffer" gemma4_agent/voice/
```

Probablemente es `transcribe_stream`. El caller necesita propagar
la reason hasta el `STTEvent` que llega al controller.

Editar `STTEvent` en `stt.py:295`:
```python
@dataclass
class STTEvent:
    kind: str  # "partial" | "final" | "timeout" | "error"
    text: str = ""
    reject_reason: str = ""  # NEW: filled when text=='' on final
```

En `transcribe_stream`, cuando emite el final event:
```python
text, reason = self._transcribe_buffer(audio_int16)
yield STTEvent(kind="final", text=text, reject_reason=reason)
```

### M.1.3c — Controller usa la reason

`controller.py:531-546` (el handler de `ev.kind == "final"`):
```python
elif ev.kind == "final":
    try:
        _rec = VoiceRecorder.get()
        if ev.text:
            _rec.annotate_turn(whisper_transcription=ev.text)
        else:
            # Use the specific reason from the STT event instead
            # of the generic placeholder. Hotfix M.1.3 2026-05-18.
            specific = getattr(ev, "reject_reason", "") or "stt_empty_or_vad_reject"
            _rec.annotate_turn(stt_reject_reason=specific)
    except Exception:
        pass
```

Después del fix, el manifest mostrará `stt_reject_reason: "BoH_match"`,
`"low_logprob"`, `"too_short"`, etc — diagnostico inmediato.

---

## FIX M.1.4 — Eager turn close on STT reject

### M.1.4a — Cerrar el turn cuando STT rechaza

En `controller.py`, en el branch `ev.kind == "final"` cuando
`not ev.text`:

```python
elif ev.kind == "final":
    try:
        _rec = VoiceRecorder.get()
        if ev.text:
            _rec.annotate_turn(whisper_transcription=ev.text)
        else:
            specific = getattr(ev, "reject_reason", "") or "stt_empty_or_vad_reject"
            _rec.annotate_turn(stt_reject_reason=specific)
            # Hotfix M.1.4 2026-05-18: STT rejected — no TTS will
            # play for this turn, so end_tts/finish_turn won't be
            # called downstream. Close the turn eagerly here so the
            # manifest entry is written immediately with the right
            # finish_reason instead of waiting for the next wake
            # to overlap-close it.
            _rec.finish_turn(reason="stt_rejected")
    except Exception:
        pass
    if not saw_speech and not ev.text:
        # ... existing logic ...
```

Verificá que esto no rompa el flow normal. El controller ya
hace `return` después de `_handle_final("")` cuando no hay
texto — así que el turn ya está terminado lógicamente cuando
salimos. Cerrar el recording acá es correcto.

---

## Tests

Crear `gemma4_agent/test_voice_recorder_m1.py`:

```python
"""Tests for recorder polish (hotfix M.1 2026-05-18):
- TTS chunks captured even if they arrive shortly after finish_turn
  (grace window for Piper async race).
- finish_turn with reason="stt_rejected" writes manifest with that
  reason instead of "overlapping_new_turn" / "tts_finished".
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np


class RecorderM1Test(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="g4m1_"))
        os.environ["GEMMA4_RECORD_AUDIO"] = "1"
        from gemma4_agent.voice import recorder as _r
        self._real_dir = _r.RECORDINGS_DIR
        _r.RECORDINGS_DIR = self.tmp_dir
        _r.VoiceRecorder._instance = None

    def tearDown(self) -> None:
        from gemma4_agent.voice import recorder as _r
        try:
            _r.VoiceRecorder.get().shutdown()
        except Exception:
            pass
        _r.VoiceRecorder._instance = None
        _r.RECORDINGS_DIR = self._real_dir
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        os.environ.pop("GEMMA4_RECORD_AUDIO", None)

    def _recorder(self):
        from gemma4_agent.voice.recorder import VoiceRecorder
        return VoiceRecorder.get()

    def test_late_tts_chunk_within_grace_is_captured(self) -> None:
        r = self._recorder()
        r.enable("sess_late")
        r.start_turn(turn_id="t1", wake_phrase="gemma", wake_confidence=0.9)
        r.capture_user_chunk(np.zeros(16000, dtype=np.int16))
        r.finish_turn(reason="tts_finished")
        # Simulate a late TTS chunk arriving 100ms after finish.
        time.sleep(0.1)
        r.capture_tts_chunk(np.full(8000, 200, dtype=np.int16))
        # Force a grace cleanup by starting a new turn AFTER grace
        # window. But first, give the writer time to process.
        time.sleep(0.5)
        # The previous turn's .tts.wav should exist with the late chunk.
        session_dir = self.tmp_dir / "sess_late"
        self.assertTrue((session_dir / "t1.tts.wav").exists(),
                        "Late TTS chunk should have been captured in grace window")

    def test_late_tts_chunk_after_grace_is_dropped(self) -> None:
        r = self._recorder()
        r.enable("sess_late2")
        r.start_turn(turn_id="t1", wake_phrase="gemma", wake_confidence=0.9)
        r.capture_user_chunk(np.zeros(1600, dtype=np.int16))
        r.finish_turn(reason="tts_finished")
        # Wait LONGER than the grace window.
        time.sleep(2.5)
        r.capture_tts_chunk(np.full(8000, 200, dtype=np.int16))
        time.sleep(0.3)
        session_dir = self.tmp_dir / "sess_late2"
        # Either no .tts.wav (preferred) or empty .tts.wav.
        tts_path = session_dir / "t1.tts.wav"
        if tts_path.exists():
            self.assertLess(tts_path.stat().st_size, 500,
                            "TTS chunk after grace should be dropped")

    def test_stt_rejected_finish_reason_in_manifest(self) -> None:
        r = self._recorder()
        r.enable("sess_rej")
        r.start_turn(turn_id="t1", wake_phrase="gemma", wake_confidence=0.9)
        r.capture_user_chunk(np.zeros(16000, dtype=np.int16))
        r.annotate_turn(stt_reject_reason="BoH_match")
        r.finish_turn(reason="stt_rejected")
        time.sleep(0.3)
        manifest = self.tmp_dir / "sess_rej" / "manifest.jsonl"
        self.assertTrue(manifest.exists())
        with open(manifest, encoding="utf-8") as fh:
            line = fh.readline()
        entry = json.loads(line)
        self.assertEqual(entry["finish_reason"], "stt_rejected")
        self.assertEqual(entry["stt_reject_reason"], "BoH_match")
        self.assertIsNone(entry["whisper_transcription"])

    def test_wake_confidence_passed_to_manifest(self) -> None:
        r = self._recorder()
        r.enable("sess_conf")
        r.start_turn(turn_id="t1", wake_phrase="gemma", wake_confidence=0.93)
        r.capture_user_chunk(np.zeros(1600, dtype=np.int16))
        r.finish_turn()
        time.sleep(0.3)
        with open(self.tmp_dir / "sess_conf" / "manifest.jsonl",
                  encoding="utf-8") as fh:
            entry = json.loads(fh.readline())
        self.assertAlmostEqual(entry["wake_confidence"], 0.93, places=2)


class STTRejectReasonTest(unittest.TestCase):
    """Pin that _transcribe_buffer returns a (text, reason) tuple
    with specific reason values."""

    def test_signature_returns_tuple(self) -> None:
        from gemma4_agent.voice.stt import StreamingSTT
        import inspect
        sig = inspect.signature(StreamingSTT._transcribe_buffer)
        # We don't enforce the typing string, but the docstring
        # should mention reason / tuple.
        doc = StreamingSTT._transcribe_buffer.__doc__ or ""
        self.assertTrue(
            "reason" in doc.lower() or "tuple" in doc.lower(),
            "M.1.3: _transcribe_buffer should return (text, reason)"
        )


if __name__ == "__main__":
    unittest.main()
```

---

## Smoke real con sesión grabada

Después del fix, re-correr una sesión de voz real (decir wake +
"pon música" 2 veces, después wake + "abre Chrome") y verificar:

```powershell
$latest = Get-ChildItem $HOME\.gemma4\recordings | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Get-Content "$($latest.FullName)\manifest.jsonl"
```

Expectativa post-fix:
- Cada turn con TTS reply genera SU `.tts.wav` (no solo el primero).
- `wake_confidence` > 0.0 en todos los turns.
- `stt_reject_reason` es específico (`BoH_match`, `low_logprob`,
  etc) cuando STT rechaza.
- `finish_reason: "stt_rejected"` cuando STT rechazó (NO
  `"overlapping_new_turn"`).

---

## ANÁLISIS DE SESIÓN DEL OPERADOR — testaudio

El operador grabó manualmente una sesión de voz **fuera** del
pipeline del agente — es un archivo de audio continuo crudo, no
hay manifest, no hay turns separados por el recorder. Vos
(el agente del sprint) tenés que tratarlo como un test estático
que valida el comportamiento esperado de Whisper + el quality
filter + el smalltalk gate.

**Ubicación exacta del archivo**:
`gemma4_agent/voice/tests/Grabación (2).m4a`

Contenido (descripción del operador): "repetí todos los comandos
dichos de diferentes formas, variando entre gemma/hey gemma y con
distintos tonos, rápidos/lentos". El repertorio que el operador
intentó cubrir incluye comandos imperativos, smalltalk, preguntas
factuales, multi-turn, triggers condicionales, comandos
cross-lingual, casos límite con disfluencias, nombres propios
complicados, y variación de tono (susurrado/apurado/enfático/con
ruido de fondo).

### Por qué este análisis importa

Este es el primer dataset multi-locutor-style real que el sistema
recibe (aunque sea un solo speaker, las variaciones de tono lo
estresan). El objetivo NO es calibrar para esta voz específica
— es **detectar dónde el pipeline universal se rompe**. Cualquier
fix derivado debe ser language-agnostic / accent-agnostic.

### Pasos de análisis

#### Paso 1 — Convertir m4a a WAV 16kHz mono int16

El recorder y todo el pipeline operan en WAV 16kHz mono int16.
`.m4a` es AAC en contenedor MP4. Conversión con `ffmpeg`
(asumido instalado; si no, instalá con `winget install ffmpeg`):

```bash
ffmpeg -y -i "gemma4_agent/voice/tests/Grabación (2).m4a" \
       -ac 1 -ar 16000 -sample_fmt s16 \
       "gemma4_agent/voice/tests/testaudio_full.wav"
```

Verificá la duración total:
```python
import wave
with wave.open("gemma4_agent/voice/tests/testaudio_full.wav", "rb") as wf:
    dur = wf.getnframes() / wf.getframerate()
print(f"Duration: {dur:.1f}s ({dur/60:.1f} min)")
```

#### Paso 2 — Detectar "wake utterances" (segments)

El archivo es continuo; no hay metadata de cuándo el operador
dijo "Hey Gemma" / "Gemma" antes de cada comando. **Detectalos
estructuralmente**:

Opción **A (recomendada)** — usar el Vosk wake detector del
proyecto en modo offline:

```python
import wave, numpy as np
from gemma4_agent.voice.wake import WakeDetector  # adapta al import real
from gemma4_agent.voice.audio_io import SAMPLE_RATE

with wave.open("gemma4_agent/voice/tests/testaudio_full.wav", "rb") as wf:
    raw = wf.readframes(wf.getnframes())
audio = np.frombuffer(raw, dtype=np.int16)

# Chunk en 32ms (mismo que el pipeline real) y feed al wake detector.
CHUNK = 512  # 32ms a 16kHz
detections = []  # list of (sample_idx, phrase, confidence)

def _on_wake(phrase, ts, tail_s=0.0, confidence=0.0):
    detections.append((ts, phrase, confidence))

detector = WakeDetector(on_wake=_on_wake)  # adapta al ctor real
detector.start()
for i in range(0, len(audio) - CHUNK, CHUNK):
    detector.feed(audio[i:i+CHUNK])
detector.stop()

print(f"Wake detections: {len(detections)}")
for ts, phrase, conf in detections:
    print(f"  t={ts:.2f}s phrase={phrase!r} conf={conf:.2f}")
```

Si el wake detector tiene una API que requiere mucho setup, **caé
a Opción B**: silero-VAD para detectar speech segments + chequeo
manual de los primeros 1-2 segundos de cada segment buscando
"gemma" / "hey gemma".

#### Paso 3 — Transcribir cada segment con Whisper

Para cada detección de wake, extraé los siguientes ~15 segundos
de audio y pasalos por el pipeline real:

```python
from gemma4_agent.voice.stt import StreamingSTT

t = StreamingSTT()
t.load()

WINDOW_S = 15
WAKE_TAIL_S = 0.5  # pre-wake margin

results = []
for ts, phrase, conf in detections:
    start = max(0, int((ts - WAKE_TAIL_S) * SAMPLE_RATE))
    end = min(len(audio), int((ts + WINDOW_S) * SAMPLE_RATE))
    segment = audio[start:end]
    # _transcribe_buffer post-M.1.3 returns (text, reason)
    text, reason = t._transcribe_buffer(segment)
    results.append({
        "wake_ts": ts,
        "wake_phrase": phrase,
        "wake_conf": conf,
        "segment_duration_s": (end - start) / SAMPLE_RATE,
        "text": text,
        "reject_reason": reason,
    })
```

#### Paso 4 — Categorizar los resultados

Clasificá cada resultado en una de estas buckets:

| Bucket | Criterio | Esperado |
|---|---|---|
| **legitimate-passed** | `text != ""` y `text` es speech coherente | mayoría de turns con comando claro |
| **legitimate-rejected** | `text == ""` Y el operador claramente dijo algo | bug — Whisper o quality_check fallando |
| **expected-rejected** | `text == ""` Y era silencio / ruido / disfluencia | OK; verificar que `reject_reason` sea específico |
| **wake-false-positive** | wake fired pero el operador NO estaba hablándole a Gemma | wake detector calibration |
| **wake-missed** | el operador dijo wake-word pero detector no lo agarró | wake detector recall problem |

#### Paso 5 — Para cada `legitimate-rejected`, root-cause

Para cada turn que el operador claramente dijo algo y Whisper
rechazó:

```python
for r in results:
    if r["text"] == "" and r["reject_reason"] in ("BoH_match", "low_logprob"):
        # Re-run with logger at DEBUG to see what Whisper actually
        # transcribed before the quality filter killed it.
        # (the pipeline already logs 'transcribe pass1: text=...' at DEBUG)
        print(f"INVESTIGATE: t={r['wake_ts']:.1f}s reason={r['reject_reason']}")
```

Si el `reject_reason` es `BoH_match`, mirá qué texto generó
Whisper antes del filter — ese texto es la phrase que está
matcheando una entry de la BoH list. Reportá esa phrase para que
el operador decida si remover la entry (como hicimos con
`"musica"` en Sprint M).

#### Paso 6 — Validar comportamiento universal

El operador grabó variaciones intencionales. Cross-checks
específicos:

**a) Variaciones de tono** — buscá pares (mismo texto, distinto
tono) y reportá si el `text` transcripto difiere significativamente:
- "abre Chrome" en tono normal vs susurrado vs apurado.
- Si transcribe los 3 igual: pipeline robusto.
- Si rechaza el susurrado o malinterpreta el rápido: bug de
  STT en condiciones realistas (no críticio para fix
  inmediato, pero anotalo).

**b) Cross-lingual** — buscá "open Chrome" / "ouvre Chrome" /
"öffne Chrome" / "abre Chrome". Whisper-small soporta esos
idiomas. Verificá que:
- Whisper devuelve el texto correctamente en cada idioma (no
  traduce a ES forzadamente).
- El quality_check NO rechaza el EN/FR/DE.
- **Si lo rechaza solo en idiomas que no son ES, es un bug
  language-specific** — reportalo prominente, contradice el
  principio "universal" del agente.

**c) Smalltalk** — buscá "hola", "gracias", "ok". Whisper los
transcribe; el smalltalk gate del router los detecta. En este
análisis offline, solo verificás que Whisper los transcribe
correctamente. El test del gate ya está cubierto por
test_smalltalk_gate_calibration.py.

**d) Casos límite del operador** — específicamente:
- Silence post-wake (decir "Hey Gemma" + nada por 8s): Whisper
  NO debe alucinar texto. Esperás `reject_reason="no_speech"`
  o `"too_short"`.
- Disfluencias ("hola Gemma... eeeh... cuánto pesa..."): Whisper
  típicamente las transcribe; el LLM tiene que parsearlas. Acá
  solo verificás que la transcripción no esté rota.
- Frases incompletas ("abrime el..."): puede pasar como rejected
  por low_logprob o transcribir parcial. Cualquiera es OK.

#### Paso 7 — Persistir el análisis

Guardá los resultados como `gemma4_agent/voice/tests/
testaudio_analysis.json`:

```python
import json
summary = {
    "source_file": "Grabación (2).m4a",
    "total_duration_s": dur,
    "wake_detections": len(detections),
    "buckets": {
        "legitimate_passed": [...],   # list of (wake_ts, text)
        "legitimate_rejected": [...], # list of (wake_ts, reject_reason)
        "expected_rejected": [...],
        "wake_false_positive": [...],
        "wake_missed_suspected": [...],  # heuristic
    },
    "issues_found": [...],  # human-readable list
}
with open("gemma4_agent/voice/tests/testaudio_analysis.json", "w",
          encoding="utf-8") as fh:
    json.dump(summary, fh, indent=2, ensure_ascii=False)
```

ESE archivo SÍ se commitea — es análisis del agente, no audio
crudo. Útil para tracking de regresiones futuras (re-correr este
análisis después de cambiar Whisper config / BoH list / VAD
threshold y comparar).

### Lo que pegás al reporte final

a. Conteo de wake detections vs turnos esperados (el operador
   intentó grabar ~50-80 comandos; si el detector agarró 20,
   tenemos un problema de recall del wake).

b. Distribución por bucket (cuántos passed / rejected / etc).

c. Para cada `legitimate_rejected`: timestamp + reject_reason +
   texto que Whisper produjo antes del filter (si aplicable).
   Esto es lo más útil — son los casos donde el pipeline rechaza
   speech real.

d. Variaciones de tono: ¿Whisper es estable across normal /
   susurrado / apurado / con ruido?

e. Cross-lingual: ¿EN/FR/DE pasan o son rechazados por reglas
   ES-centric?

f. Hallazgos no anticipados — cualquier cosa rara que merezca un
   sprint follow-up.

### .gitignore

`testaudio_full.wav` (el WAV intermedio convertido) NO se
commitea — es derivado del m4a. `testaudio_analysis.json` SÍ se
commitea. El `.m4a` original lo dejamos a discreción del operador
— si tiene voz personal sensible, va al `.gitignore`; si es
clean test data, puede ir al repo.

Por defecto, agregá al `.gitignore`:

```
# Voice analysis intermediate artifacts (regenerable from .m4a).
gemma4_agent/voice/tests/testaudio_full.wav

# Operator-provided raw audio — leave to operator decision.
# (commented out by default; uncomment if operator says so)
# gemma4_agent/voice/tests/*.m4a
```

### Si ffmpeg no está disponible

`ffmpeg` es el conversor más simple para m4a → wav. Si no está
instalado y el operador no autoriza instalarlo:

- Probá `librosa.load(path, sr=16000, mono=True)` (depende de
  audioread + ffmpeg backend; suele estar pre-instalado en
  envs con torchaudio).
- Si tampoco funciona, usá `pydub.AudioSegment.from_file(path)`
  (también necesita ffmpeg pero a veces tiene workarounds).
- Último recurso: marcá el análisis como SKIPPED con razón
  `"ffmpeg not available; m4a decode failed"` y reportalo.

### Si el archivo no está en la ruta exacta

El archivo está en `gemma4_agent/voice/tests/Grabación (2).m4a`
(con espacio + paréntesis). Cuidado con escape en bash/PowerShell.
En código Python usá `pathlib.Path(...)` que maneja eso bien:

```python
from pathlib import Path
src = Path("gemma4_agent/voice/tests/Grabación (2).m4a")
assert src.exists(), f"audio not found at {src}"
```

---

## Commit

`fix(voice): recorder polish — tts race, wake conf, stt reason, eager finish`

Mensaje:

```
fix(voice): recorder polish — tts race, wake conf, stt reason, eager finish

Sprint M.1 follow-up to Sprint L. The first real session
(20260518_120744 — 11 turns preserved) surfaced 4 gaps in the
recorder wiring:

1. tts.wav only captured for 1 of 3 turns that had TTS reply.
   Race: Piper chunks arrive async; if they land between
   finish_turn(turn N) and start_turn(turn N+1), the active_turn
   is None and the chunks were silently dropped.

2. wake_confidence: 0.0 hardcoded — Vosk's actual confidence was
   never propagated to the recorder. Loses signal for future wake
   detector calibration.

3. stt_reject_reason: "stt_empty_or_vad_reject" (generic) for all
   rejects. The Sprint M bug ("pon musica" filtered by BoH) took
   30 min to diagnose because the manifest didn't carry the
   specific reason ('BoH_match'). _quality_check already knows
   the reason; we just weren't propagating it.

4. Turn closes lazily — when STT rejects, finish_turn isn't
   called (no TTS plays); the turn stays open until the next
   wake overlap-closes it with reason="overlapping_new_turn".
   This delays the manifest write and mis-labels the finish reason.

Fixes:

M.1.1: VoiceRecorder keeps a `_just_finished_turn` reference for
2 seconds after finish_turn. Late TTS chunks (Piper async) get
appended to the just-closed turn instead of being dropped. The
tts_writer stays open during the grace window; cleanup happens
in the next start_turn or shutdown.

M.1.2: WakeDetector callback signature extended with
`confidence: float`. VoiceController forwards it to
recorder.start_turn instead of the 0.0 placeholder.

M.1.3: StreamingSTT._transcribe_buffer signature changed from
`-> str` to `-> tuple[str, str]` (text, reason). STTEvent gains a
`reject_reason` field. Controller annotates the recorder with
the specific reason ('BoH_match' / 'low_logprob' / 'no_speech' /
'too_short' / etc) instead of the generic placeholder.

M.1.4: When STT rejects (ev.text == '' on final), controller
calls finish_turn(reason='stt_rejected') eagerly. The turn
closes immediately, manifest is written, and the next wake
doesn't overlap-close with the wrong reason.

Tests pin the 4 contracts:
- Late TTS chunk in grace window is captured.
- Late TTS chunk after grace expires is dropped.
- finish_reason='stt_rejected' lands in the manifest with the
  specific stt_reject_reason field.
- wake_confidence propagates from the wake detector.

No new dependencies, no behaviour change for the voice critical
path. All recorder annotations remain try/except wrapped — a
recorder failure can never break voice.

Validation: re-run a voice session post-fix, confirm:
- 3+ turns with .tts.wav (not just the first).
- wake_confidence > 0.0 in manifest.
- BoH-rejected turns show stt_reject_reason='BoH_match' (after
  Sprint M which removes the standalone 'musica' from the BoH
  list, this combination will be rare; pre-Sprint-M it would
  have made diagnosis trivial).
- finish_reason='stt_rejected' for rejected turns.
```

---

## REPORTE FINAL

Devolveme:
1. Hash del commit.
2. Output de `python -m pytest gemma4_agent/test_voice_recorder_m1.py -v`.
3. Output de `python -m pytest gemma4_agent/ -q --tb=line`
   (debe seguir green; los tests existentes del recorder NO
   deben romperse).
4. Smoke real con sesión de voz nueva. Pegame:
   - `manifest.jsonl` completo de la nueva sesión.
   - `dir` del directorio para ver cuántos `.tts.wav` y `.user.wav`.
5. **Análisis de la sesión testaudio del operador**
   (`gemma4_agent/voice/tests/Grabación (2).m4a`):
   - Conteo de wake detections (Paso 2).
   - Distribución por bucket: legitimate_passed /
     legitimate_rejected / expected_rejected / wake_false_positive
     / wake_missed_suspected (Paso 4).
   - Para cada `legitimate_rejected`: timestamp + reject_reason +
     texto pre-filter (Paso 5).
   - Comportamiento cross-tone (normal vs susurrado vs apurado).
   - Comportamiento cross-lingual (EN/FR/DE pasan o solo ES).
   - Lista de hallazgos no anticipados.
   - `testaudio_analysis.json` committed al repo (Paso 7).
   - Si ffmpeg / decode falla: reportá SKIPPED con razón
     específica y avanzá con el resto del reporte.

## CRITERIO DE ÉXITO

- 1 commit aterrizado.
- ≥4 tests nuevos verdes.
- Suite completa verde (modulo Sprint 3a + E.5 xfail).
- Smoke real con 2+ turns que generen `.tts.wav` (no solo el
  primero).
- Manifest tiene `wake_confidence > 0` y `stt_reject_reason`
  específico (no genérico) cuando STT rechaza.
- Turn rechazado por STT tiene `finish_reason="stt_rejected"`.
- Análisis de testaudio reportado contra `Grabación (2).m4a`
  (o SKIPPED explícitamente si ffmpeg/decode falla).
- `testaudio_analysis.json` generado y commiteado.
- `.gitignore` actualizado: excluye `testaudio_full.wav` (WAV
  intermedio regenerable).
- **NINGÚN fix al pipeline derivado del análisis testaudio se
  aplica en este sprint** — los hallazgos quedan documentados
  como follow-ups en el reporte. Sprint M.1 es polish del
  recorder + análisis offline; calibration fixes son sprints
  separados con probes específicos.

## NO HACER (anti-scope)

- NO refactorices el writer thread del recorder. El grace window
  es un parche dirigido al race observado, no un rediseño.
- NO bajes el grace window a < 1s. Piper puede tardar 1-2s en
  drenar su queue interna; 2s da margen.
- NO subas grace a > 5s. La memoria de turns cerrados se acumula
  y eventualmente confunde la lógica.
- NO toques el quality_check de Whisper. El bug de "pon musica"
  se arregla en Sprint M; este sprint solo propaga la razón.
- NO inventes nuevos valores de `stt_reject_reason` — usá los
  que el `_quality_check` ya devuelve (BoH_match, low_logprob,
  no_speech_prob, compression_ratio, empty_or_too_short,
  too_many_words_for_duration, ngram_repetition, no_speech,
  too_short).
- NO toques recorder, controller o stt en partes no relacionadas
  con los 4 gaps. Si el `_transcribe_buffer` refactor toca más
  de 30 líneas, parate y reportá — algo está mal.
- Si el wake.py callback signature change requiere modificar
  más de 3 call sites, dejá el wake_confidence=0.0 hardcoded
  con TODO claro y avanzá con los otros 3 fixes.

## Follow-ups documentados (NO en este sprint)

1. Si después de M.1 todavía vemos `.tts.wav` faltantes en uso
   real, agregar telemetría: contador
   `_recorder._dropped_tts_chunks` y emitirlo en
   `router_v2_session_summary`-style line al shutdown.
2. Si el race del TTS sigue apareciendo, considerar mover
   `capture_tts_chunk` a un thread compartido con el writer
   en vez de depender del thread de Piper.
3. Re-procesar los WAVs históricos de `20260518_120744/` con el
   Sprint M aplicado para regenerar el manifest con
   `stt_reject_reason: "BoH_match"` específico — datos limpios
   para training set futuro.
