# HOTFIX 2026-05-17 (L) — Voice session recording (continuous wake-to-reply)

> Continuá el chat post hotfix K. El operador quiere persistir
> grabaciones de cada sesión de voz para usar como training set
> futuro (Whisper fine-tuning, wake detector calibration, e2e
> latency analysis). Captura **continua** desde wake detected
> hasta TTS terminado, dos archivos por turn (user mic + tts
> output), metadata estructurada en manifest.jsonl.

---

## Contexto: lo que el operador quiere

Operator request literal: "Quiero que todas las sesiones que haga
se grabe el micrófono para usarlo como set de pruebas más tarde,
quiero que cada sesión tenga todo grabado para luego mejorar el
modelo de transcripción."

Decisiones acordadas con el operador (esta conversación):

- **Modo (b)** — captura continua wake → TTS finished (no solo
  el segmento que llega a Whisper).
- **A3** — dos archivos por turn: `<turn>.user.wav` (mic raw)
  + `<turn>.tts.wav` (synth output del agente).
- **B1** — un archivo por turn, termina cuando TTS termina.
- **C/WAV** — PCM 16-bit 16kHz mono. Sin compresión.
- **Opt-out** via `GEMMA4_RECORD_AUDIO=0`. Default ON.
- **Sin retention automática** (operator manageja a mano).
- **Background thread** — zero latency cost al critical path.
- **Solo input + TTS** — no logging de audio del agente fuera de
  los turns.

---

## Inventario del pipeline existente

Confirmado pre-flight (no tocás esto, solo lo conectás):

- `gemma4_agent/voice/audio_io.py`:
  - `SAMPLE_RATE = 16000`, mono.
  - `MicrophoneStream` ya tiene un ring buffer (`_ring`) y método
    `snapshot()` y `snapshot_tail(seconds)` que devuelven
    `np.ndarray` int16.
  - `_on_audio_chunk` callback ya existe en `VoiceController`
    para cada chunk de 32ms (línea 338).

- `gemma4_agent/voice/controller.py`:
  - `_on_wake_detected(phrase, ts, tail_s)` — línea 359, **el
    trigger del recording start**.
  - `begin_tts()` línea 261, `end_tts()` línea 304 — los markers
    de inicio/fin del TTS leg para el turn.
  - Estado `VoiceState` con transiciones — el recording se
    asocia a un turn vía estos eventos.

- `gemma4_agent/voice/tts.py`:
  - `StreamingTTS._synthesize_and_play(text, out_stream)` —
    línea 279. Piper genera chunks int16 16kHz que se escriben
    a `out_stream`. **Los mismos chunks** se pueden capturar a
    un archivo en paralelo sin tocar latencia.
  - Ya emite `tts_started` / `tts_finished` log markers (hotfix H).

- `gemma4_agent/tracing.py` (asumiendo, verificá): trace events
  ya tienen `turn_id`. Lo reusamos como recording key.

---

## OBJETIVO

Tres commits chicos:

1. `feat(voice)`: módulo nuevo `voice/recorder.py` que maneja
   el lifecycle de grabación (start/stop, write background,
   manifest append). Pure infrastructure, no wired yet.
2. `feat(voice)`: wiring en `VoiceController` (mic recording
   start on wake, stop on TTS end) + `StreamingTTS` (TTS audio
   tap).
3. `feat(voice)`: opt-out env var + tests + smoke.

---

## REGLAS GENERALES

1. PortandoLoMejor. 3 commits chicos.
2. **Zero latency cost al critical path**. La grabación corre
   en thread/queue background. Si el writer se atrasa, dropea
   chunks con un log warning — NUNCA bloquea el voice pipeline.
3. **Failure-tolerant**: si `~/.gemma4/recordings/` no se puede
   crear (disco lleno, permisos), emitir log warning y seguir
   funcionando sin grabar. No romper el agente por el recorder.
4. **NO toques** el wake detector, VAD, Whisper STT pipeline,
   router, planner, prompts. Solo agregás taps a 3 puntos
   estructurales: mic chunk callback, TTS chunk play, turn
   lifecycle.
5. **NO instales libs nuevas**. Usá `wave` (stdlib) para WAV
   write, `json` para manifest. `numpy` ya está.
6. NO `git add -A`.

---

## FIX L1 — Módulo `voice/recorder.py`

### L1.1 — API design

`gemma4_agent/voice/recorder.py` (nuevo):

```python
"""Per-turn voice session recorder.

Hotfix L 2026-05-17. The operator wants every voice session
persisted to disk as a future training set (Whisper fine-tuning,
wake detector calibration, e2e latency analysis).

Capture model (option B, agreed in design):
  - START: when wake-word is detected. Includes a 500ms pre-wake
    tail from the mic ring buffer (lets us audit false wakes).
  - END: when TTS playback finishes for the same turn. Captures
    user speech, VAD silence, agent reply synth.
  - Two files per turn:
      <session>/<turn>.user.wav  — raw mic, full window.
      <session>/<turn>.tts.wav   — Piper synth output (only if
                                   TTS ran; otherwise absent).
  - One manifest entry per turn appended to
    <session>/manifest.jsonl.

Format:
  - WAV PCM 16-bit, 16 kHz, mono. No compression. Whisper and
    every other STT toolchain reads it directly.

Privacy / opt-out:
  - Default ON. Disable per-process with GEMMA4_RECORD_AUDIO=0
    or =false or =off.
  - Failure-tolerant: if the recordings dir can't be created
    (disk full, permission), log a warning and disable for the
    rest of the process. NEVER raise into the voice pipeline.

Threading:
  - All disk I/O happens on a single background writer thread
    per recorder instance. The mic callback / TTS playback only
    enqueue (np.ndarray, key) tuples; the writer drains the
    queue and appends to the appropriate file.
  - If the queue saturates (writer too slow), DROP chunks and
    log a warning. The voice pipeline must never block.
"""
from __future__ import annotations

import json
import logging
import os
import queue as _queue
import threading
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .audio_io import SAMPLE_RATE

logger = logging.getLogger(__name__)

RECORDINGS_DIR = Path.home() / ".gemma4" / "recordings"

# Drop chunks if the writer queue grows past this many entries.
# At 16 kHz mono int16, 32ms chunks: ~1024 bytes/chunk. 2000
# pending = ~2 MB lag tolerance, ~64 sec of audio queued.
_MAX_QUEUE = 2000

# Pre-wake tail capture window. The mic ring buffer is short
# (audio_io.RING_BUFFER_CHUNKS) so we don't try to read more
# than it actually holds.
PRE_WAKE_TAIL_S = 0.5


@dataclass
class _ActiveTurn:
    """In-flight recording state for one turn."""
    session_id: str
    turn_id: str
    started_at: float
    wake_phrase: str
    wake_confidence: float
    user_path: Path
    tts_path: Path
    manifest_path: Path
    # Open WAV writers. Lazy-created on first chunk so we don't
    # produce 44-byte empty WAVs for turns that get cancelled.
    user_writer: Any = None
    tts_writer: Any = None
    user_samples_written: int = 0
    tts_samples_written: int = 0
    extra_metadata: dict[str, Any] = field(default_factory=dict)


def is_enabled() -> bool:
    """True iff recording is opt-in / on by default and not
    explicitly disabled."""
    raw = (os.environ.get("GEMMA4_RECORD_AUDIO") or "").strip().lower()
    return raw not in {"0", "false", "no", "off"}


class VoiceRecorder:
    """Per-process voice session recorder. Thread-safe.

    Lifecycle:
      enable()                — create recordings dir, start
                                writer thread. Idempotent.
      start_turn(...)         — open a new turn for capture.
                                Pre-wake tail is captured here.
      capture_user_chunk(...) — enqueue a mic chunk for the
                                active turn (no-op if no turn).
      capture_tts_chunk(...)  — enqueue a TTS chunk.
      finish_turn(...)        — close writers, append manifest
                                entry, drop active turn.
      shutdown()              — finish active turn (if any),
                                stop writer thread.
    """
    _instance: "VoiceRecorder | None" = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> "VoiceRecorder":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self) -> None:
        self._session_id: str | None = None
        self._active_turn: _ActiveTurn | None = None
        self._enabled = False
        self._init_failed = False
        self._writer_queue: _queue.Queue[tuple[str, np.ndarray | None]] = _queue.Queue(maxsize=_MAX_QUEUE)
        self._writer_thread: threading.Thread | None = None
        self._writer_lock = threading.Lock()
        self._dropped_chunks = 0

    def enable(self, session_id: str | None = None) -> bool:
        """Idempotent. Creates RECORDINGS_DIR if needed and starts
        the writer thread. Returns True if enabled, False if
        disabled or init failed.
        """
        if not is_enabled():
            return False
        if self._init_failed:
            return False
        try:
            RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning("voice_recorder_init_failed dir=%s error=%s",
                           RECORDINGS_DIR, exc)
            self._init_failed = True
            return False
        if session_id:
            self._session_id = session_id
        elif self._session_id is None:
            self._session_id = time.strftime("%Y%m%d_%H%M%S")
        # Per-session subdirectory.
        try:
            (RECORDINGS_DIR / self._session_id).mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning("voice_recorder_session_dir_failed error=%s", exc)
            self._init_failed = True
            return False
        # Writer thread (singleton).
        if self._writer_thread is None or not self._writer_thread.is_alive():
            self._writer_thread = threading.Thread(
                target=self._writer_loop,
                name="voice-recorder-writer",
                daemon=True,
            )
            self._writer_thread.start()
        self._enabled = True
        return True

    def start_turn(
        self,
        turn_id: str,
        wake_phrase: str = "",
        wake_confidence: float = 0.0,
        pre_wake_audio: np.ndarray | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Open a new turn for capture. Closes any in-flight turn
        first (defensive: should not normally happen)."""
        if not self._enabled:
            return
        if self._active_turn is not None:
            logger.warning("voice_recorder_turn_overlap previous=%s new=%s",
                           self._active_turn.turn_id, turn_id)
            self.finish_turn(reason="overlapping_new_turn")
        if self._session_id is None:
            return
        session_dir = RECORDINGS_DIR / self._session_id
        turn = _ActiveTurn(
            session_id=self._session_id,
            turn_id=turn_id,
            started_at=time.time(),
            wake_phrase=wake_phrase,
            wake_confidence=float(wake_confidence),
            user_path=session_dir / f"{turn_id}.user.wav",
            tts_path=session_dir / f"{turn_id}.tts.wav",
            manifest_path=session_dir / "manifest.jsonl",
            extra_metadata=dict(extra_metadata or {}),
        )
        with self._writer_lock:
            self._active_turn = turn
        # Pre-wake tail goes in as the first chunks.
        if pre_wake_audio is not None and pre_wake_audio.size > 0:
            self.capture_user_chunk(pre_wake_audio)

    def capture_user_chunk(self, chunk: np.ndarray) -> None:
        """Enqueue a mic chunk for the active turn. No-op if
        recording is off or no turn is active."""
        if not self._enabled or self._active_turn is None:
            return
        try:
            self._writer_queue.put_nowait(("user", chunk))
        except _queue.Full:
            self._dropped_chunks += 1
            if self._dropped_chunks % 100 == 1:
                logger.warning(
                    "voice_recorder_queue_full dropped_chunks=%d",
                    self._dropped_chunks,
                )

    def capture_tts_chunk(self, chunk: np.ndarray) -> None:
        """Enqueue a TTS chunk for the active turn."""
        if not self._enabled or self._active_turn is None:
            return
        try:
            self._writer_queue.put_nowait(("tts", chunk))
        except _queue.Full:
            self._dropped_chunks += 1

    def annotate_turn(self, **fields: Any) -> None:
        """Attach arbitrary key/value metadata to the active turn.
        Goes into the manifest entry on finish_turn. Caller responsible
        for using JSON-serializable values."""
        if not self._enabled or self._active_turn is None:
            return
        with self._writer_lock:
            if self._active_turn is not None:
                self._active_turn.extra_metadata.update(fields)

    def finish_turn(self, reason: str = "tts_finished") -> None:
        """Close writers and append manifest entry for the active
        turn. Safe to call when no turn is active."""
        if not self._enabled:
            return
        with self._writer_lock:
            turn = self._active_turn
            self._active_turn = None
        if turn is None:
            return
        # Drain pending chunks first. We post a sentinel "flush"
        # then wait briefly. Simpler approach: enqueue and let
        # writer process; closing writers happens here directly.
        # The writer doesn't keep file handles per turn — it
        # writes opportunistically — so we close from here.
        # Drain by waiting briefly for the queue.
        deadline = time.time() + 2.0
        while not self._writer_queue.empty() and time.time() < deadline:
            time.sleep(0.05)
        # Close writers (if any chunks made them open).
        for writer in (turn.user_writer, turn.tts_writer):
            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    pass
        # Append manifest.
        try:
            entry = {
                "session_id": turn.session_id,
                "turn_id": turn.turn_id,
                "started_at": turn.started_at,
                "finished_at": time.time(),
                "duration_s": time.time() - turn.started_at,
                "wake_phrase": turn.wake_phrase,
                "wake_confidence": turn.wake_confidence,
                "user_wav": turn.user_path.name if turn.user_samples_written > 0 else None,
                "user_samples": turn.user_samples_written,
                "tts_wav": turn.tts_path.name if turn.tts_samples_written > 0 else None,
                "tts_samples": turn.tts_samples_written,
                "finish_reason": reason,
                "whisper_transcription": turn.extra_metadata.pop(
                    "whisper_transcription", None),
                "stt_reject_reason": turn.extra_metadata.pop(
                    "stt_reject_reason", None),
                # Empty field for later manual correction in review.
                "manual_correction": "",
                "extra": turn.extra_metadata,
            }
            with open(turn.manifest_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("voice_recorder_manifest_write_failed error=%s", exc)

    def shutdown(self) -> None:
        """Stop the writer thread cleanly. Idempotent."""
        if self._active_turn is not None:
            self.finish_turn(reason="shutdown")
        if self._writer_thread is not None:
            try:
                self._writer_queue.put_nowait(("__stop__", None))
            except _queue.Full:
                pass
            self._writer_thread.join(timeout=2.0)
            self._writer_thread = None
        self._enabled = False

    def _writer_loop(self) -> None:
        """Drain the queue, opening WAV files lazily as chunks
        arrive. Runs until shutdown."""
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
            if turn is None or chunk is None:
                continue
            try:
                if kind == "user":
                    if turn.user_writer is None:
                        turn.user_writer = self._open_wav(turn.user_path)
                    if turn.user_writer is not None:
                        self._write_chunk(turn.user_writer, chunk)
                        turn.user_samples_written += int(chunk.size)
                elif kind == "tts":
                    if turn.tts_writer is None:
                        turn.tts_writer = self._open_wav(turn.tts_path)
                    if turn.tts_writer is not None:
                        self._write_chunk(turn.tts_writer, chunk)
                        turn.tts_samples_written += int(chunk.size)
            except Exception as exc:
                logger.warning(
                    "voice_recorder_write_failed kind=%s error=%s",
                    kind, exc,
                )

    @staticmethod
    def _open_wav(path: Path) -> Any:
        """Open a WAV writer at SAMPLE_RATE, mono, 16-bit PCM."""
        try:
            w = wave.open(str(path), "wb")
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            return w
        except Exception as exc:
            logger.warning("voice_recorder_open_wav_failed path=%s error=%s",
                           path, exc)
            return None

    @staticmethod
    def _write_chunk(writer: Any, chunk: np.ndarray) -> None:
        if chunk.dtype != np.int16:
            chunk = chunk.astype(np.int16, copy=False)
        writer.writeframes(chunk.tobytes())
```

### L1.2 — Commit

`feat(voice): voice/recorder.py for per-turn session recording`

Mensaje:

```
feat(voice): voice/recorder.py for per-turn session recording

Operator requested persistent voice recordings to use as future
training set (Whisper fine-tuning, wake detector calibration,
e2e latency analysis). Capture model agreed in design:
  - Continuous from wake-detected to TTS-finished (option B).
  - Two files per turn: <turn>.user.wav (mic) + <turn>.tts.wav
    (synth output) (option A3).
  - One file per turn, terminates on TTS end (option B1).
  - WAV PCM 16-bit 16kHz mono. No compression.
  - Opt-out via GEMMA4_RECORD_AUDIO=0. Default ON.
  - No automatic retention.

This commit ships the module only — pure infrastructure, not
wired into the voice pipeline yet (next commit).

Design notes:
- Singleton VoiceRecorder.get() with thread-safe lifecycle.
- Single background writer thread drains a bounded queue.
- WAV files open lazily on first chunk so cancelled turns don't
  produce empty 44-byte stubs.
- Queue saturation: drop chunks + warn log, never block the
  voice critical path.
- manifest.jsonl: one line per turn with timestamps, wake info,
  whisper transcription, optional manual_correction field for
  later review.
- Init failure (disk full / permissions): log warning, set
  _init_failed sticky, recorder stays disabled for the process.
- No new dependencies (uses stdlib wave + json).
```

---

## FIX L2 — Wire the recorder into `VoiceController` + `StreamingTTS`

### L2.1 — `voice/controller.py`

Pre-flight grep:
```bash
grep -n "_on_wake_detected\|_on_audio_chunk\|begin_tts\|end_tts" gemma4_agent/voice/controller.py
```

Three integration points:

**a) On wake detect (line ~359)** — start the recording with pre-wake tail:

```python
# At the top of controller.py:
from .recorder import VoiceRecorder, PRE_WAKE_TAIL_S

# In _on_wake_detected, after the existing state transition logic:
try:
    recorder = VoiceRecorder.get()
    if recorder.enable(session_id=getattr(self, "_session_id", None)):
        # Pull the pre-wake tail from the mic ring buffer.
        pre = None
        try:
            if self._mic is not None:
                pre = self._mic.snapshot_tail(PRE_WAKE_TAIL_S)
        except Exception:
            pre = None
        turn_id = getattr(self, "_current_turn_id", None) or f"turn_{int(ts*1000)}"
        recorder.start_turn(
            turn_id=turn_id,
            wake_phrase=phrase,
            wake_confidence=float(getattr(self, "_last_wake_confidence", 0.0)),
            pre_wake_audio=pre,
        )
except Exception as _rec_exc:
    logger.warning("voice_recorder_start_turn_failed error=%s", _rec_exc)
```

**b) On every mic chunk (line ~338 `_on_audio_chunk`)** — tap the chunk:

```python
def _on_audio_chunk(self, chunk: np.ndarray) -> None:
    # ... existing wake-word feed / VAD feed logic ...
    # Hotfix L 2026-05-17: tap the mic for the recorder. No-op
    # when not recording an active turn.
    try:
        VoiceRecorder.get().capture_user_chunk(chunk)
    except Exception:
        pass  # never break audio loop on recorder failure
```

**c) On `end_tts()` (line ~304)** — finalize the turn:

```python
def end_tts(self) -> None:
    # ... existing end_tts logic ...
    try:
        VoiceRecorder.get().finish_turn(reason="tts_finished")
    except Exception:
        pass
```

**d) Annotate Whisper transcription (find where STT returns)**:

In whatever path receives the empty `""` or the transcribed text
from `stt.transcribe()`, before passing it onward:

```python
try:
    recorder = VoiceRecorder.get()
    if transcribed:
        recorder.annotate_turn(whisper_transcription=transcribed)
    else:
        # Existing voice_silent_reject event (hotfix E) — annotate
        # the recorder too so the manifest captures rejected turns.
        recorder.annotate_turn(stt_reject_reason="stt_empty_or_vad_reject")
except Exception:
    pass
```

Pre-flight to find the STT call site:
```bash
grep -n "transcribe\|stt\." gemma4_agent/voice/controller.py | head
```

### L2.2 — `voice/tts.py`

In `_synthesize_and_play` (line ~279), after each chunk is
written to the output stream, also capture it:

```python
def _synthesize_and_play(self, text: str, out_stream) -> None:
    if self._piper is None:
        return
    import time as _time
    _t0 = _time.monotonic()
    logger.warning("tts_started text_len=%d", len(text))
    try:
        # Hotfix L 2026-05-17: lazy import so the recorder
        # module is optional for environments that don't have
        # the voice package set up fully.
        try:
            from .recorder import VoiceRecorder
            _recorder = VoiceRecorder.get()
        except Exception:
            _recorder = None
        for chunk in self._piper.synthesize(text):
            if not self._running or self._muted:
                logger.warning(
                    "tts_finished duration_s=%.3f reason=interrupted",
                    _time.monotonic() - _t0,
                )
                return
            audio = chunk.audio_int16_array
            out_stream.write(audio)
            # Tap for recording (no-op if no active turn / disabled).
            if _recorder is not None:
                try:
                    _recorder.capture_tts_chunk(audio)
                except Exception:
                    pass
    except Exception as exc:
        logger.warning("tts_synth_error error=%s", exc)
    logger.warning("tts_finished duration_s=%.3f", _time.monotonic() - _t0)
```

### L2.3 — Shutdown hook in launcher

`gemma4_agent/launcher.py` already has the hotfix H atexit hook
for `router_v2_session_summary`. Add a sibling:

```python
def _shutdown_voice_recorder() -> None:
    """Flush any in-flight recording on shutdown."""
    try:
        from .voice.recorder import VoiceRecorder
        VoiceRecorder.get().shutdown()
    except Exception:
        pass

atexit.register(_shutdown_voice_recorder)
```

### L2.4 — Commit

`feat(voice): wire recorder into controller (wake -> tts end)`

Mensaje:

```
feat(voice): wire recorder into controller (wake -> tts end)

Plug the recorder from the previous commit into the voice
pipeline at three structural points:

  1. VoiceController._on_wake_detected — start_turn with the
     pre-wake tail pulled from the mic ring buffer (so we
     capture ~500ms before wake confirmed).
  2. VoiceController._on_audio_chunk — capture every mic chunk
     (32ms, int16, 16kHz) for the active turn.
  3. VoiceController.end_tts — finish_turn writes manifest and
     closes WAV files.
  4. StreamingTTS._synthesize_and_play — capture each Piper
     synth chunk to <turn>.tts.wav.

Whisper transcription is annotated via recorder.annotate_turn
right after stt.transcribe() returns, so the manifest entry
includes the auto-transcription as weak ground truth.

Launcher atexit hook flushes any in-flight recording on shutdown
(sibling to the existing router_v2_session_summary hook from
hotfix H).

All taps are wrapped in try/except so a recorder failure can
never break the voice loop. The recorder itself drops chunks
when its queue saturates (logged) rather than blocking.

No new dependencies, no behaviour change when
GEMMA4_RECORD_AUDIO=0.
```

---

## FIX L3 — Tests + smoke

### L3.1 — Tests

Crear `gemma4_agent/test_voice_recorder.py`:

```python
"""VoiceRecorder lifecycle tests (hotfix L 2026-05-17).

These exercise the module in isolation with synthetic numpy
chunks. They do NOT depend on a live microphone or Piper voice
files — pure unit tests against the recorder's public API.
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


class VoiceRecorderTest(unittest.TestCase):
    def setUp(self) -> None:
        # Force an isolated recordings dir for each test so we
        # never touch the real ~/.gemma4/recordings.
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="g4rec_"))
        os.environ["GEMMA4_RECORD_AUDIO"] = "1"
        # Monkey-patch RECORDINGS_DIR.
        from gemma4_agent.voice import recorder as _rec_mod
        self._real_dir = _rec_mod.RECORDINGS_DIR
        _rec_mod.RECORDINGS_DIR = self.tmp_dir
        # Force fresh singleton.
        _rec_mod.VoiceRecorder._instance = None

    def tearDown(self) -> None:
        from gemma4_agent.voice import recorder as _rec_mod
        try:
            _rec_mod.VoiceRecorder.get().shutdown()
        except Exception:
            pass
        _rec_mod.VoiceRecorder._instance = None
        _rec_mod.RECORDINGS_DIR = self._real_dir
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        os.environ.pop("GEMMA4_RECORD_AUDIO", None)

    def _recorder(self):
        from gemma4_agent.voice.recorder import VoiceRecorder
        return VoiceRecorder.get()

    def test_disabled_via_env(self) -> None:
        os.environ["GEMMA4_RECORD_AUDIO"] = "0"
        r = self._recorder()
        self.assertFalse(r.enable("sess_x"))

    def test_enable_creates_session_dir(self) -> None:
        r = self._recorder()
        self.assertTrue(r.enable("sess_1"))
        self.assertTrue((self.tmp_dir / "sess_1").is_dir())

    def test_turn_lifecycle_produces_wav_and_manifest(self) -> None:
        r = self._recorder()
        r.enable("sess_2")
        r.start_turn(
            turn_id="t1",
            wake_phrase="gemma",
            wake_confidence=0.92,
        )
        # Fake 1 second of mic audio (16000 samples int16).
        mic = np.zeros(16000, dtype=np.int16)
        mic[::100] = 5000  # any non-silence
        r.capture_user_chunk(mic)
        # Fake 0.5s of TTS audio.
        tts = np.zeros(8000, dtype=np.int16)
        r.capture_tts_chunk(tts)
        r.annotate_turn(whisper_transcription="hola")
        r.finish_turn(reason="tts_finished")
        # Wait for writer to drain.
        time.sleep(0.3)

        session_dir = self.tmp_dir / "sess_2"
        self.assertTrue((session_dir / "t1.user.wav").exists())
        self.assertTrue((session_dir / "t1.tts.wav").exists())
        self.assertTrue((session_dir / "manifest.jsonl").exists())

        with open(session_dir / "manifest.jsonl", encoding="utf-8") as fh:
            line = fh.readline()
        entry = json.loads(line)
        self.assertEqual(entry["turn_id"], "t1")
        self.assertEqual(entry["wake_phrase"], "gemma")
        self.assertAlmostEqual(entry["wake_confidence"], 0.92, places=2)
        self.assertEqual(entry["whisper_transcription"], "hola")
        self.assertEqual(entry["manual_correction"], "")
        self.assertEqual(entry["user_samples"], 16000)
        self.assertEqual(entry["tts_samples"], 8000)
        self.assertEqual(entry["finish_reason"], "tts_finished")

    def test_capture_with_no_turn_active_is_noop(self) -> None:
        r = self._recorder()
        r.enable("sess_3")
        # No start_turn — capture should be silent.
        r.capture_user_chunk(np.zeros(1600, dtype=np.int16))
        r.capture_tts_chunk(np.zeros(1600, dtype=np.int16))
        time.sleep(0.1)
        # No WAV files should exist.
        session_dir = self.tmp_dir / "sess_3"
        if session_dir.exists():
            wavs = list(session_dir.glob("*.wav"))
            self.assertEqual(wavs, [])

    def test_tts_only_turn_omits_user_wav(self) -> None:
        # A turn with TTS chunks but no mic chunks should produce
        # only the .tts.wav (no empty .user.wav stub).
        r = self._recorder()
        r.enable("sess_4")
        r.start_turn(turn_id="t1", wake_phrase="", wake_confidence=0.0)
        r.capture_tts_chunk(np.zeros(8000, dtype=np.int16))
        r.finish_turn()
        time.sleep(0.3)
        session_dir = self.tmp_dir / "sess_4"
        self.assertTrue((session_dir / "t1.tts.wav").exists())
        self.assertFalse((session_dir / "t1.user.wav").exists())

    def test_pre_wake_tail_included(self) -> None:
        r = self._recorder()
        r.enable("sess_5")
        tail = np.full(8000, 100, dtype=np.int16)  # 0.5s pre-wake
        r.start_turn(
            turn_id="t1",
            pre_wake_audio=tail,
            wake_phrase="gemma",
            wake_confidence=0.9,
        )
        r.capture_user_chunk(np.full(16000, 200, dtype=np.int16))
        r.finish_turn()
        time.sleep(0.3)
        # The user wav should be ~24000 samples = 1.5s (tail + 1s).
        import wave
        with wave.open(str(self.tmp_dir / "sess_5" / "t1.user.wav"), "rb") as wf:
            self.assertEqual(wf.getnchannels(), 1)
            self.assertEqual(wf.getframerate(), 16000)
            self.assertGreaterEqual(wf.getnframes(), 23000)

    def test_manifest_appends_multiple_turns(self) -> None:
        r = self._recorder()
        r.enable("sess_6")
        for i in range(3):
            r.start_turn(turn_id=f"t{i}", wake_phrase="gemma", wake_confidence=0.9)
            r.capture_user_chunk(np.zeros(1600, dtype=np.int16))
            r.finish_turn()
            time.sleep(0.1)
        with open(self.tmp_dir / "sess_6" / "manifest.jsonl", encoding="utf-8") as fh:
            lines = fh.readlines()
        self.assertEqual(len(lines), 3)

    def test_overlapping_start_closes_previous(self) -> None:
        r = self._recorder()
        r.enable("sess_7")
        r.start_turn(turn_id="t1", wake_phrase="gemma", wake_confidence=0.9)
        r.capture_user_chunk(np.zeros(1600, dtype=np.int16))
        # No finish_turn — start a new one. Should auto-close t1.
        r.start_turn(turn_id="t2", wake_phrase="gemma", wake_confidence=0.9)
        r.capture_user_chunk(np.zeros(1600, dtype=np.int16))
        r.finish_turn()
        time.sleep(0.3)
        with open(self.tmp_dir / "sess_7" / "manifest.jsonl", encoding="utf-8") as fh:
            lines = fh.readlines()
        # Both turns should be in the manifest.
        self.assertEqual(len(lines), 2)
        t1 = json.loads(lines[0])
        self.assertEqual(t1["turn_id"], "t1")
        self.assertEqual(t1["finish_reason"], "overlapping_new_turn")


if __name__ == "__main__":
    unittest.main()
```

### L3.2 — Smoke manual (post-deploy)

Documentá en el commit message — el operador corre:

```bash
# Set up.
$env:GEMMA4_RECORD_AUDIO = "1"   # default ON but explicit for clarity
python -m gemma4_agent.launcher start

# Talk to the agent: say wake-word, ask "qué hora es", listen
# to the reply.

# After session.
dir $HOME\.gemma4\recordings
# Expected: directory like 20260517_213045\ with N WAV pairs + manifest.

Get-Content $HOME\.gemma4\recordings\20260517_213045\manifest.jsonl
# Expected: 1 JSON line per turn with whisper_transcription,
# user_samples, tts_samples, wake_confidence.
```

### L3.3 — Commit

`feat(voice): tests + manual smoke for voice recorder`

Mensaje:

```
feat(voice): tests + manual smoke for voice recorder

Tests (8 cases, all unit-level — no live mic or Piper voice
required):
- disabled via env var
- enable() creates the session dir
- full turn lifecycle: start_turn -> capture -> finish_turn
  produces .user.wav, .tts.wav, manifest.jsonl entry with
  correct fields including whisper_transcription weak label
- capture with no active turn is a silent no-op
- tts-only turn (no mic chunks) omits the user.wav
- pre-wake tail audio is included in the user.wav
- manifest.jsonl appends correctly across multiple turns
- overlapping start_turn auto-closes the previous turn

Manual smoke documented for the operator: set
GEMMA4_RECORD_AUDIO=1, run a voice session, inspect
~/.gemma4/recordings/<session>/manifest.jsonl.

No new dependencies. Tests run in isolation against a tmpdir
RECORDINGS_DIR monkey-patch so they never touch the operator's
real recordings.
```

---

## REPORTE FINAL

Devolveme:
1. Hashes de los 3 commits.
2. Output de `python -m pytest gemma4_agent/test_voice_recorder.py -v`.
3. Output de `python -m pytest gemma4_agent/ -q --tb=line` (debe
   subir de 1048 a ~1056 con los 8 nuevos).
4. Smoke manual post-deploy: 1 sesión de voz real, output de:
   ```powershell
   dir $HOME\.gemma4\recordings
   Get-Content $HOME\.gemma4\recordings\<latest>\manifest.jsonl
   ```
5. Confirmación de que el agent.launcher start sigue arrancando
   sin errores nuevos.

## CRITERIO DE ÉXITO

- 3 commits aterrizados.
- ≥6 tests nuevos verdes en test_voice_recorder.py.
- Suite completa verde (modulo Sprint 3a + E.5 xfail).
- Smoke manual produce 1 sesión con ≥1 WAV pair + manifest entry.
- launcher status OK.
- Disabling via `GEMMA4_RECORD_AUDIO=0` no crashea y no escribe
  archivos.

## NO HACER (anti-scope)

- NO toques el wake detector, VAD, Whisper STT pipeline,
  router_v2, planner, prompts, modes, las 65 tools.
- NO inventes retention automática. El sprint dice explícitamente
  sin retention; el operador maneja a mano.
- NO compresiones audio. WAV PCM 16-bit directo.
- NO migres a config / YAML. Constantes hardcoded en
  `voice/recorder.py` con comment.
- NO logues el contenido del Whisper transcription en log
  estructural — va al manifest (que es lo que el operador pidió),
  no a trace events broadcast.
- Si el operador tiene una pre-existing carpeta `~/.gemma4/
  recordings/` con otros files, NO la borres ni la sobreescribas.
  El recorder solo crea subdirectorios por session_id.
- NO añadas un transcription "ground truth" cross-check (correr
  Whisper otra vez sobre el WAV). Innecesario en este sprint —
  el `manual_correction` field es el path correcto para ground
  truth, hecho por el operador en revisión, no automático.
- NO instales libs nuevas. `wave` (stdlib) + `numpy` (ya está)
  alcanzan.
- Si el wiring de TTS (L2.2) requiere refactor pesado del worker
  thread de Piper, escala a tap solo en mic (L2.1) y dejá un TODO
  claro para tts capture en sprint follow-up. La captura de mic
  es lo crítico para Whisper training; tts es bonus.

## Follow-ups documentados (NO en este sprint)

1. **Compresión FLAC** si el storage se vuelve problema (~1 mes
   de uso → ~1.5GB). Sprint M opcional.
2. **Review UI**: una página simple en el ui_field para listar
   sessions, reproducir audio, escribir manual_correction en el
   manifest. Sprint futuro cuando haya data suficiente para
   revisar.
3. **Auto-transcript pipeline**: correr Whisper-large o similar
   offline sobre los WAVs y comparar con whisper_transcription
   del manifest. Solo después de tener data.
4. **Retention policy** si el operador la pide explícitamente
   después de uso real.
