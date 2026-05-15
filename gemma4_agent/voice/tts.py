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
from pathlib import Path
from queue import Empty, Queue
from typing import Callable

import numpy as np

logger = logging.getLogger(__name__)


PIPER_MODEL_DIR = Path.home() / ".gemma4" / "models" / "piper"
DEFAULT_VOICE = "es_MX-claude-high"

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
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                done = 0
                with open(dst, "wb") as f:
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
            return True
        except Exception as exc:
            logger.error("Piper voice download failed (%s): %s", url, exc)
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
    """Sintetiza y reproduce oraciones del LLM en streaming."""

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
        """Acumula texto del LLM y encola oraciones cerradas. Devuelve cuantas encolo."""
        if not self._loaded or self._muted:
            return 0
        self._buffer += chunk
        sentences, rest = _split_sentences(self._buffer)
        self._buffer = rest
        for s in sentences:
            self._queue.put(s)
        return len(sentences)

    def flush(self) -> int:
        """Fuerza el envio del buffer pendiente como ultima oracion."""
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
                self._synthesize_and_play(item, out_stream)
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
        try:
            for chunk in self._piper.synthesize(text):
                if not self._running or self._muted:
                    return
                audio = chunk.audio_int16_array
                if audio is None or len(audio) == 0:
                    continue
                out_stream.write(audio)
        except Exception as exc:
            logger.warning("Piper synth failed: %s", exc)

    def unload(self) -> None:
        """Libera modelo de RAM."""
        self.stop()
        self._piper = None
        self._loaded = False
