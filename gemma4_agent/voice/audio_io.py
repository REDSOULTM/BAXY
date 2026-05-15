"""Fase W — captura de audio del microfono.

Reglas (post-auditoria de docs oficiales sounddevice + Silero):
- 16kHz mono int16. Chunks de **512 samples** (~32ms): es el tamano EXACTO
  que Silero VAD v5 espera (otros tamanos degradan, ver release notes).
  Vosk acepta cualquier tamano >= 100ms; 512 samples es OK.
- Ring buffer de ~5s para que wake-word pueda "rebobinar" antes del trigger.
- El callback de PortAudio NO hace trabajo pesado: solo `.copy()` del buffer
  (que es reusado por PortAudio segun docs) y push a una Queue. Un thread
  dedicado drena la queue y llama a wake/STT. Esto evita drops por
  `input_overflow` cuando Vosk/Silero tardan mas que el periodo del callback.
- Si no hay micro disponible, AudioCapture.start() retorna False y deja
  last_error con un mensaje human-readable. NO crashea.
"""
from __future__ import annotations

import logging
import queue as queue_mod
import threading
from collections import deque
from typing import Callable

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
# Silero VAD v5 requiere EXACTAMENTE 512 samples a 16 kHz. Es 32ms.
# https://github.com/snakers4/silero-vad release notes v5.
CHUNK_SAMPLES = 512
CHUNK_MS = (CHUNK_SAMPLES * 1000) // SAMPLE_RATE  # 32
RING_BUFFER_SECONDS = 5
RING_BUFFER_CHUNKS = (RING_BUFFER_SECONDS * 1000) // CHUNK_MS  # ~156


# Tipo: callback recibe un np.int16 array de CHUNK_SAMPLES samples.
ChunkCallback = Callable[[np.ndarray], None]


class AudioCapture:
    """Wraper de sounddevice.InputStream con ring buffer integrado.

    Arquitectura post-fix de docs oficiales:
    - El callback de PortAudio SOLO hace `.copy()` y push a `_pending_queue`.
      Sin locks, sin trabajo pesado. Docs sounddevice prohiben I/O en callback.
    - Un thread `_pump_loop` drena la queue y llama `on_chunk` (que a su vez
      puede ejecutar Vosk costoso sin bloquear PortAudio).
    - El ring buffer tambien se actualiza desde el pump thread, no desde el
      callback.

    Uso:
        cap = AudioCapture(on_chunk=lambda c: ...)
        if cap.start():
            ...
            cap.stop()
        else:
            print(cap.last_error)
    """

    def __init__(
        self,
        on_chunk: ChunkCallback,
        device: int | str | None = None,
    ) -> None:
        self._on_chunk = on_chunk
        self._device = device
        self._stream = None  # type: ignore[assignment]
        self._ring: deque[np.ndarray] = deque(maxlen=RING_BUFFER_CHUNKS)
        self._lock = threading.Lock()
        # Queue entre el callback de PortAudio (productor) y el pump thread
        # (consumidor). maxsize>0 evita memory blowup si on_chunk se cuelga.
        # 250 chunks = 8s de audio buffereado antes de dropear.
        self._pending: "queue_mod.Queue[np.ndarray]" = queue_mod.Queue(maxsize=250)
        self._pump_stop = threading.Event()
        self._pump_thread: threading.Thread | None = None
        self._drop_count: int = 0
        self.last_error: str | None = None
        self.running: bool = False

    def start(self) -> bool:
        """Arranca el stream. Devuelve True si OK, False si fallo (con last_error)."""
        try:
            import sounddevice as sd  # lazy import
        except ImportError as exc:
            self.last_error = f"sounddevice not installed: {exc}"
            logger.error(self.last_error)
            return False
        # Arrancar el pump thread ANTES del stream para que la queue no
        # se llene si el primer chunk llega rapido.
        self._pump_stop.clear()
        self._pump_thread = threading.Thread(
            target=self._pump_loop, daemon=True, name="AudioPump",
        )
        self._pump_thread.start()
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                blocksize=CHUNK_SAMPLES,
                dtype="int16",
                channels=1,
                device=self._device,
                callback=self._sd_callback,
            )
            self._stream.start()
            self.running = True
            self.last_error = None
            logger.info(
                "AudioCapture started (device=%s, chunk=%d samples / %dms)",
                self._device, CHUNK_SAMPLES, CHUNK_MS,
            )
            return True
        except Exception as exc:
            self.last_error = f"audio stream failed: {type(exc).__name__}: {exc}"
            logger.error(self.last_error)
            self._stream = None
            self._pump_stop.set()
            return False

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._pump_stop.set()
        if self._pump_thread is not None:
            self._pump_thread.join(timeout=1.0)
            self._pump_thread = None
        self.running = False
        if self._drop_count > 0:
            logger.info("AudioCapture closed (total drops=%d)", self._drop_count)

    def snapshot(self) -> np.ndarray:
        """Devuelve copia concatenada del ring buffer (audio ultimos 5s)."""
        with self._lock:
            if not self._ring:
                return np.zeros(0, dtype=np.int16)
            return np.concatenate(list(self._ring))

    def snapshot_tail(self, seconds: float) -> np.ndarray:
        """Devuelve los ultimos `seconds` segundos del ring buffer.

        Usado por el acoustic-snapshot: tras detectar wake-word, el caller
        toma el tail del audio que sigue al wake (para empalmar el comando
        inmediato 'gemma apaga la luz' sin perder la cola).

        Si el ring tiene menos audio que `seconds`, devuelve lo que haya.
        """
        if seconds <= 0:
            return np.zeros(0, dtype=np.int16)
        with self._lock:
            if not self._ring:
                return np.zeros(0, dtype=np.int16)
            total = sum(c.size for c in self._ring)
            needed = int(SAMPLE_RATE * seconds)
            if total <= needed:
                return np.concatenate(list(self._ring))
            # Tomar tail: iterar desde atras
            out: list[np.ndarray] = []
            acc = 0
            for chunk in reversed(self._ring):
                out.append(chunk)
                acc += chunk.size
                if acc >= needed:
                    break
            out.reverse()
            arr = np.concatenate(out)
            # Recortar exacto al numero de samples pedido
            if arr.size > needed:
                arr = arr[-needed:]
            return arr

    def _sd_callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        """Callback de PortAudio. Critico: NO bloquear, NO hacer I/O.

        Docs oficiales sounddevice (Stream callback guidance):
          "Do not allocate memory, access the file system, call library
          functions or call other functions from the stream callback that
          may block."
        Por eso aca solo: 1 copy (para evitar buffer reuse), 1 put_nowait.
        """
        if status:
            # input_overflow = CPU lento aguas abajo. Loggeamos a INFO porque
            # nos importa diagnosticarlo.
            if status.input_overflow:
                logger.info("AudioCapture overflow: %s", status)
            else:
                logger.debug("AudioCapture status: %s", status)
        # indata es 2D (frames, 1) con channels=1. Aplanamos + copy() (docs
        # oficiales: el buffer se reusa entre callbacks).
        try:
            chunk = indata[:, 0].copy()
        except Exception:
            return
        try:
            self._pending.put_nowait(chunk)
        except queue_mod.Full:
            self._drop_count += 1
            # No loggeamos en el callback (I/O), incrementamos y seguimos.

    def _pump_loop(self) -> None:
        """Drena la queue y llama on_chunk + actualiza ring buffer.

        Corre off-PortAudio. Si on_chunk se cuelga, la queue se llena y
        se dropean chunks (con _drop_count incrementado) -- el stream
        de PortAudio sigue saludable.
        """
        while not self._pump_stop.is_set():
            try:
                chunk = self._pending.get(timeout=0.1)
            except queue_mod.Empty:
                continue
            # Update ring buffer (off-callback)
            with self._lock:
                self._ring.append(chunk)
            # Llamar al user callback (Vosk feed, etc)
            try:
                self._on_chunk(chunk)
            except Exception as exc:
                logger.warning("on_chunk raised: %s", exc)


def list_input_devices() -> list[dict[str, object]]:
    """Devuelve la lista de dispositivos de entrada para el Settings dropdown.

    Cada entry: {"index": int, "name": str, "default": bool}.
    """
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        default_in = sd.default.device[0] if sd.default.device else -1
    except Exception as exc:
        logger.warning("list_input_devices failed: %s", exc)
        return []
    out: list[dict[str, object]] = []
    for i, d in enumerate(devices):
        if d.get("max_input_channels", 0) > 0:
            out.append({
                "index": i,
                "name": str(d.get("name", f"device {i}")),
                "default": (i == default_in),
            })
    return out
