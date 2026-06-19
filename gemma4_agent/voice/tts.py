"""Fase W — TTS streaming con Piper.

Diseno:
- speak_stream(text_iter) acumula chunks del LLM en un buffer.
- Cada vez que ve un fin de oracion (`.!?;¡¿\\n\\n`), corta y manda esa oracion
  a Piper en una cola FIFO. El productor (LLM) no espera al TTS.
- Worker thread separado consume la cola, sintetiza con Piper, reproduce con
  sounddevice.OutputStream.
- stop() corta playback inmediato y vacia la cola.
- Si la dep o el modelo no estan, queda en FAILED con last_error explicativo.

Voz default: es_MX-claude-high. URLs hardcoded a HuggingFace rhasspy/piper-voices.
Si el archivo de la voz no existe, se descarga al primer uso con consentimiento.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from pathlib import Path
from queue import Empty, Queue
from typing import Callable


logger = logging.getLogger(__name__)


PIPER_MODEL_DIR = Path.home() / ".gemma4" / "models" / "piper"
DEFAULT_VOICE = "es_MX-claude-high"

# After the last audio chunk finishes playing, is_busy() stays True for this
# grace window. Without it the controller flips to IDLE_LISTENING the instant
# the queue drains, and the spoken sentence's tail (still coming out of the
# speakers) leaks back into the mic as a fake "command" (self-hearing). The
# grace keeps the mic muted until the room is actually quiet again.
TTS_TAIL_GRACE_S = float(os.environ.get("GEMMA4_TTS_TAIL_GRACE_S", "0.6"))

# While the agent is STREAMING a reply (between the first feed_text and flush),
# is_busy() stays True even if the synth queue momentarily drains between
# sentences. Without this, when default-on streaming TTS makes Piper speak
# sentence-by-sentence and the LLM stalls >TAIL_GRACE between them, the wake
# detector un-pauses in the gap and the NEXT spoken sentence leaks into the mic
# as a phantom command (self-hearing → garbage STT). Bounded by STREAM_STALE_S
# so a stalled/aborted reply can never mute the mic forever.
STREAM_STALE_S = float(os.environ.get("GEMMA4_TTS_STREAM_STALE_S", "8.0"))

# URLs hardcoded de huggingface.co/rhasspy/piper-voices, main branch.
# Si rompe en el futuro, el usuario ve el error y puede bajar manualmente.
PIPER_VOICE_URLS = {
    "es_MX-claude-high": (
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/es_MX-claude-high.onnx",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/es_MX-claude-high.onnx.json",
    ),
    "es_MX-ald-medium": (
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/ald/medium/es_MX-ald-medium.onnx",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/ald/medium/es_MX-ald-medium.onnx.json",
    ),
    "es_ES-sharvard-medium": (
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/sharvard/medium/es_ES-sharvard-medium.onnx",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/sharvard/medium/es_ES-sharvard-medium.onnx.json",
    ),
}

# Regex de fin de oracion (incluye signos invertidos del espanol)
SENTENCE_END_RE = re.compile(r"[.!?;¡¿]\s|\n\n")
# Opening-clause boundary for the first-chunk fast path: the first comma or
# sentence-ending punctuation. Used once per utterance to flush the opening
# words to Piper early (e.g. "Listo," before the rest of the sentence arrives).
_OPENING_CLAUSE_RE = re.compile(r"[,.!?;…]")


def voice_files_exist(voice: str) -> bool:
    """True si .onnx y .onnx.json estan en disco."""
    onnx = PIPER_MODEL_DIR / f"{voice}.onnx"
    cfg = PIPER_MODEL_DIR / f"{voice}.onnx.json"
    return onnx.is_file() and cfg.is_file()


def download_voice(
    voice: str,
    progress_cb: Callable[[int, int], None] | None = None,
) -> bool:
    """Descarga .onnx + .onnx.json a PIPER_MODEL_DIR."""
    if voice not in PIPER_VOICE_URLS:
        logger.error("Unknown Piper voice: %s", voice)
        return False
    onnx_url, cfg_url = PIPER_VOICE_URLS[voice]
    PIPER_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    import urllib.request

    def _dl(url: str, dst: Path) -> bool:
        # Download to a .part temp and atomically rename on success. A network
        # drop mid-stream otherwise leaves a TRUNCATED .onnx at the final path;
        # voice_files_exist() then reports it present, load() fails on the
        # corrupt model, and TTS is bricked until the user manually deletes the
        # partial file. Same atomic-write discipline as state.py / experience.py.
        tmp = dst.with_suffix(dst.suffix + ".part")
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                done = 0
                with open(tmp, "wb") as f:
                    while True:
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        if progress_cb is not None:
                            try:
                                progress_cb(done, total)
                            except Exception:
                                pass
            os.replace(tmp, dst)  # atomic: dst is never a partial file
            return True
        except Exception as exc:
            logger.error("Piper voice download failed (%s): %s", url, exc)
            try:
                tmp.unlink()
            except OSError:
                pass
            return False

    return _dl(onnx_url, PIPER_MODEL_DIR / f"{voice}.onnx") and \
           _dl(cfg_url, PIPER_MODEL_DIR / f"{voice}.onnx.json")


def installed_voices() -> list[str]:
    """Lista de nombres de voces presentes en disco (sin extension)."""
    if not PIPER_MODEL_DIR.is_dir():
        return []
    out: set[str] = set()
    for p in PIPER_MODEL_DIR.glob("*.onnx"):
        name = p.name[:-5]  # quita ".onnx"
        if (PIPER_MODEL_DIR / f"{name}.onnx.json").is_file():
            out.add(name)
    return sorted(out)


def _split_sentences(text: str) -> tuple[list[str], str]:
    """Devuelve (oraciones_cerradas, resto_pendiente).

    Cierra en `.!?;` seguidos de espacio o EOL, o en doble salto de linea.
    """
    sentences: list[str] = []
    pending = text
    while True:
        match = SENTENCE_END_RE.search(pending)
        if not match:
            return sentences, pending
        end = match.end()
        sentence = pending[:end].strip()
        if sentence:
            sentences.append(sentence)
        pending = pending[end:]


class StreamingTTS:
    """Sintetiza y reproduce oraciones del LLM en streaming.

    ============================================================
    DEFERRED — item 2.4 del optimization_roadmap.md:
    Kokoro-82M-es como backend TTS alternativo.
    Pros: Apache 2.0 (licencia friendly), calidad subjetiva superior
    a Piper, 82M params manageable en CPU.
    Cons:
      - Latencia primer chunk CPU 600-1200 ms vs Piper <300 ms,
        VIOLA el SLA "≤1 s primer fonema" del brief.
      - Requiere dep nueva (kokoro-onnx o equivalente).
      - Voces es-MX/es-AR no son oficiales (parche comunitario).
    Decision: DEFERRED indefinido. Re-evaluar SOLO si llega
    feedback explicito de usuarios pidiendo voz mas natural. Por
    ahora Piper VITS+ONNX es la opcion correcta por latencia.
    ============================================================
    """

    def __init__(self, voice: str | None = None) -> None:
        env_voice = (os.environ.get("GEMMA4_VOICE_TTS_VOICE") or "").strip()
        self.voice = voice or env_voice or DEFAULT_VOICE
        self._piper = None  # type: ignore[assignment]
        self._sample_rate: int = 22050
        self._queue: "Queue[str | None]" = Queue()  # None = stop sentinel
        self._worker: threading.Thread | None = None
        self._running: bool = False
        self._muted: bool = False
        self._buffer: str = ""
        self._loaded: bool = False
        self.last_error: str | None = None
        # Busy-state tracking (tail-grace + synthesizing) so is_busy() stays
        # True through synth+play and a short tail, preventing self-hearing.
        self._synthesizing: bool = False
        self._last_audio_ts: float = 0.0
        # Streaming-utterance bridge (anti self-hearing across inter-sentence
        # gaps): True from the first feed_text of a reply until flush().
        self._streaming: bool = False
        self._last_feed_ts: float = 0.0
        # First-chunk fast path: flush the opening clause of an utterance early
        # so Piper starts speaking ~1-2s sooner; re-armed on each flush().
        self._first_chunk_done: bool = False

    def load(self) -> bool:
        try:
            from piper import PiperVoice  # type: ignore[import-not-found]
        except ImportError as exc:
            self.last_error = f"piper-tts not installed: {exc}"
            return False
        if not voice_files_exist(self.voice):
            self.last_error = (
                f"piper voice files for {self.voice!r} not found in {PIPER_MODEL_DIR}"
            )
            return False
        onnx = PIPER_MODEL_DIR / f"{self.voice}.onnx"
        try:
            self._piper = PiperVoice.load(str(onnx))
            cfg = getattr(self._piper, "config", None)
            self._sample_rate = int(getattr(cfg, "sample_rate", 22050) or 22050)
            self._loaded = True
            self.last_error = None
            logger.info("StreamingTTS loaded (voice=%s, rate=%d)", self.voice, self._sample_rate)
            return True
        except Exception as exc:
            self.last_error = f"piper load failed: {type(exc).__name__}: {exc}"
            logger.error(self.last_error)
            return False

    def is_loaded(self) -> bool:
        return self._loaded

    def is_busy(self) -> bool:
        """True while TTS is occupied: queued text pending, actively
        synthesising, or within the tail-grace window after the last audio.

        Used by the controller to keep SPEAKING (and the mic muted) until Piper
        is fully done AND the speakers are quiet — without this the controller
        goes back to IDLE_LISTENING the instant the queue drains and the tail
        of the spoken sentence leaks into the mic as echo (self-hearing)."""
        if not self._running:
            return False
        if self._synthesizing:
            return True
        # Streaming bridge: stay busy across inter-sentence gaps while a reply is
        # actively being fed (see STREAM_STALE_S). Closes the self-hearing gap.
        if self._streaming and (time.monotonic() - self._last_feed_ts) < STREAM_STALE_S:
            return True
        if not self._queue.empty():
            return True
        # Tail grace: stay busy briefly after the last audio finished.
        if self._last_audio_ts and (
            time.monotonic() - self._last_audio_ts < TTS_TAIL_GRACE_S
        ):
            return True
        return False

    def set_muted(self, muted: bool) -> None:
        self._muted = bool(muted)

    def is_muted(self) -> bool:
        return self._muted

    def start(self) -> None:
        """Arranca el worker thread que consume la cola y reproduce."""
        if self._running:
            return
        self._running = True
        self._worker = threading.Thread(target=self._run_worker, name="PiperTTS", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        """Detiene playback inmediato y vacia la cola."""
        self._running = False
        self._streaming = False
        # Drenar cola
        try:
            while True:
                self._queue.get_nowait()
        except Empty:
            pass
        self._queue.put(None)  # sentinel
        if self._worker is not None:
            self._worker.join(timeout=1.0)
        self._worker = None
        self._buffer = ""

    def feed_text(self, chunk: str) -> int:
        """Acumula texto del LLM y encola oraciones cerradas. Devuelve cuantas encolo.

        FIRST-CHUNK FAST PATH (latency): for the FIRST emission of an utterance,
        flush the opening clause (up to the first comma or sentence end) as soon
        as it closes, so Piper starts speaking ~1-2s before the full sentence is
        ready. After that first flush, normal full-sentence chunking resumes
        (so later commas don't fragment the audio). Re-armed by flush()."""
        if not self._loaded or self._muted:
            return 0
        # Mark the streaming utterance live so is_busy() bridges inter-sentence
        # gaps (mic stays muted across the whole reply, not just per sentence).
        self._streaming = True
        self._last_feed_ts = time.monotonic()
        self._buffer += chunk
        queued = 0

        # First-chunk: emit the opening clause early (boundary = first comma or
        # sentence end). Only once per utterance.
        if not self._first_chunk_done:
            m = _OPENING_CLAUSE_RE.search(self._buffer)
            if m:
                clause = self._buffer[: m.end()].strip()
                self._buffer = self._buffer[m.end():]
                if clause:
                    self._queue.put(clause)
                    queued += 1
                self._first_chunk_done = True

        # Normal sentence chunking for the remainder.
        sentences, rest = _split_sentences(self._buffer)
        self._buffer = rest
        for s in sentences:
            self._queue.put(s)
            queued += 1
        return queued

    def flush(self) -> int:
        """Fuerza el envio del buffer pendiente como ultima oracion.

        Also re-arms the first-chunk fast path for the NEXT utterance."""
        self._first_chunk_done = False
        # Agent done feeding this utterance: the tail (queued sentences still
        # playing + TAIL_GRACE) keeps the mic muted from here; clear the bridge.
        self._streaming = False
        if not self._loaded or self._muted:
            self._buffer = ""
            return 0
        text = self._buffer.strip()
        self._buffer = ""
        if text:
            self._queue.put(text)
            return 1
        return 0

    def _run_worker(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            logger.error("sounddevice not available: %s", exc)
            return
        out_stream = None
        try:
            out_stream = sd.OutputStream(
                samplerate=self._sample_rate, channels=1, dtype="int16",
            )
            out_stream.start()
            while self._running:
                try:
                    item = self._queue.get(timeout=0.2)
                except Empty:
                    continue
                if item is None:
                    break
                if self._muted:
                    continue
                # Mark busy across synth+play; stamp the finish time so is_busy()
                # keeps the mic muted through the tail-grace window afterwards.
                self._synthesizing = True
                try:
                    self._synthesize_and_play(item, out_stream)
                finally:
                    self._synthesizing = False
                    self._last_audio_ts = time.monotonic()
        finally:
            if out_stream is not None:
                try:
                    out_stream.stop()
                    out_stream.close()
                except Exception:
                    pass

    def _synthesize_and_play(self, text: str, out_stream) -> None:  # noqa: ANN001
        """Sintetiza una oracion y la escribe al output stream.

        API piper-tts 1.4.x: .synthesize(text) -> Iterable[AudioChunk].
        AudioChunk.audio_int16_array es un np.ndarray int16 listo para tocar.
        """
        if self._piper is None:
            return
        # Hotfix H 2026-05-17: greppable tts_started / tts_finished
        # markers around playback so 'Gemma está lento' reports can
        # be localized to the TTS leg. We log only structural signals
        # (text_len, duration_s) — never the synthesized phrase text,
        # since that crosses the privacy boundary for audio content.
        import time as _time
        _t0 = _time.monotonic()
        logger.warning("tts_started text_len=%d", len(text))
        # Privacidad: NO se graba ni persiste el audio del usuario ni el sintetizado.
        # El audio se reproduce en streaming y se descarta; nada toca el disco.
        try:
            for chunk in self._piper.synthesize(text):
                if not self._running or self._muted:
                    logger.warning(
                        "tts_finished duration_s=%.3f reason=interrupted",
                        _time.monotonic() - _t0,
                    )
                    return
                audio = chunk.audio_int16_array
                if audio is None or len(audio) == 0:
                    continue
                out_stream.write(audio)
            logger.warning(
                "tts_finished duration_s=%.3f reason=ok",
                _time.monotonic() - _t0,
            )
        except Exception as exc:
            logger.warning(
                "tts_finished duration_s=%.3f reason=error error=%s",
                _time.monotonic() - _t0, exc,
            )
            logger.warning("Piper synth failed: %s", exc)

    def unload(self) -> None:
        """Libera modelo de RAM."""
        self.stop()
        self._piper = None
        self._loaded = False
