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


def _wasapi_enabled() -> bool:
    """Captura por WASAPI (default ON). Kill-switch GEMMA4_VOICE_WASAPI=0 vuelve al
    método viejo (device=None directo a 16kHz). Motivo del default ON (medido
    2026-06-07): el default de PortAudio en Windows suele ser MME, que NO soporta
    16kHz nativo y DEVUELVE CEROS (el mic 'no capta'). WASAPI respeta el default
    real del sistema y captura a su tasa nativa (48k) -> resampleamos a 16k."""
    import os
    return (os.environ.get("GEMMA4_VOICE_WASAPI", "1") or "1").strip().lower() \
        not in {"0", "false", "no", "off"}


def _resolve_wasapi_input() -> "tuple[int, int] | None":
    """(device_index, native_samplerate) del mic default vía WASAPI, o None si no
    hay WASAPI / no se puede. WASAPI = el default real del sistema (regla del user:
    SIEMPRE el default)."""
    try:
        import sounddevice as sd
        for h in sd.query_hostapis():
            if "WASAPI" in h.get("name", ""):
                di = h.get("default_input_device", -1)
                if di is not None and di >= 0:
                    sr = int(sd.query_devices(di)["default_samplerate"])
                    return di, sr
    except Exception as exc:
        logger.debug("WASAPI resolve failed: %s", exc)
    return None


def _resample_to_16k(audio: np.ndarray, src_sr: int) -> np.ndarray:
    """int16 mono src_sr -> 16000. scipy (anti-alias) si está, si no interp lineal.
    Probado 2026-06-07: 48k->16k preserva el nivel."""
    if src_sr == SAMPLE_RATE or audio.size == 0:
        return audio.astype(np.int16, copy=False)
    try:
        from math import gcd
        from scipy.signal import resample_poly
        g = gcd(int(src_sr), SAMPLE_RATE)
        return resample_poly(audio.astype(np.float64),
                             SAMPLE_RATE // g, int(src_sr) // g).astype(np.int16)
    except Exception:
        n_out = int(round(audio.size * SAMPLE_RATE / src_sr))
        idx = np.linspace(0, audio.size - 1, max(1, n_out))
        return np.interp(idx, np.arange(audio.size), audio).astype(np.int16)


def _aec_enabled() -> bool:
    """AEC con referencia loopback (P1, 2026-06-12). Default ON tras la
    validación EN VIVO (hardware real, deriva de reloj real):
      - ERLE convergió a 10.9 dB con música real (igual que la simulación);
        las voces del cantante desaparecen del mic (STT: texto→vacío).
      - CERO daño a la voz local: conversación transcribe idéntica con/sin
        AEC (double-talk), y 4/4 wakes detectados sobre música fuerte.
      - Ganancia en la zona dura (sim, 30 casos): SIR 0 dB recall
        0.433→0.733. Costo: ~18% de un core SOLO mientras hay reproducción.
    Kill-switch: GEMMA4_VOICE_AEC=0. Sin loopback disponible → bypass solo."""
    import os
    return (os.environ.get("GEMMA4_VOICE_AEC", "1") or "1").strip().lower() \
        in {"1", "true", "yes", "on"}


class LoopbackReference:
    """Captura lo que el PC REPRODUCE (loopback WASAPI del output default)
    como señal de referencia para el AEC. Requiere pyaudiowpatch (el
    PortAudio de sounddevice no expone loopback — verificado 2026-06-12).

    Mantiene un ring de samples a 16 kHz; `latest(n)` devuelve los últimos n
    (el DelayEstimator del AEC absorbe el desfase mic↔loopback). Si no hay
    loopback disponible, `start()` devuelve False y el AEC queda en bypass
    (nunca rompe la captura del mic)."""

    def __init__(self) -> None:
        self._pa = None
        self._stream = None
        self._sr = 48000
        self._ring = np.zeros(SAMPLE_RATE * 2, dtype=np.int16)  # 2 s @16k
        self._lock = threading.Lock()
        self.last_error: str | None = None

    def start(self) -> bool:
        try:
            import pyaudiowpatch as pa
        except ImportError as exc:
            self.last_error = f"pyaudiowpatch no instalado: {exc}"
            logger.warning(self.last_error)
            return False
        try:
            self._pa = pa.PyAudio()
            wasapi = self._pa.get_host_api_info_by_type(pa.paWASAPI)
            out = self._pa.get_device_info_by_index(
                int(wasapi["defaultOutputDevice"]))
            # buscar el dispositivo loopback del output default por nombre
            lb = None
            for i in range(self._pa.get_device_count()):
                d = self._pa.get_device_info_by_index(i)
                if d.get("isLoopbackDevice") and \
                        str(out["name"]) in str(d["name"]):
                    lb = d
                    break
            if lb is None:
                self.last_error = "sin dispositivo loopback para el output default"
                logger.warning(self.last_error)
                return False
            self._sr = int(lb["defaultSampleRate"])

            def _cb(in_data, frame_count, time_info, status):
                try:
                    x = np.frombuffer(in_data, dtype=np.int16)
                    ch = max(1, int(lb["maxInputChannels"]))
                    if ch > 1:
                        x = x.reshape(-1, ch).mean(axis=1).astype(np.int16)
                    x16 = _resample_to_16k(x, self._sr)
                    with self._lock:
                        n = x16.size
                        self._ring = np.concatenate([self._ring[n:], x16])
                except Exception:
                    pass
                return (None, pa.paContinue)

            self._stream = self._pa.open(
                format=pa.paInt16, channels=int(lb["maxInputChannels"]),
                rate=self._sr, input=True,
                input_device_index=int(lb["index"]),
                frames_per_buffer=int(self._sr * 0.032),
                stream_callback=_cb)
            self._stream.start_stream()
            logger.info("LoopbackReference activo: %s @%dHz", lb["name"], self._sr)
            return True
        except Exception as exc:
            self.last_error = f"loopback start falló: {exc}"
            logger.warning(self.last_error)
            return False

    def latest(self, n: int) -> np.ndarray:
        with self._lock:
            return self._ring[-n:].copy()

    def stop(self) -> None:
        try:
            if self._stream is not None:
                self._stream.stop_stream()
                self._stream.close()
            if self._pa is not None:
                self._pa.terminate()
        except Exception:
            pass


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
        # WASAPI: capturar del default real del sistema a su tasa nativa y
        # resamplear a 16k. Solo si el caller no fijó un device explícito y el
        # kill-switch está ON. Si no se resuelve -> método viejo (device, 16k).
        self._native_sr = SAMPLE_RATE          # tasa de captura real
        self._needs_resample = False
        if device is None and _wasapi_enabled():
            _w = _resolve_wasapi_input()
            if _w is not None:
                self._device, self._native_sr = _w
                self._needs_resample = (self._native_sr != SAMPLE_RATE)
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
        # AEC opcional (GEMMA4_VOICE_AEC=1): referencia loopback + cancelador.
        # Se arman en start(); si el loopback no está, quedan None (bypass).
        self._aec = None
        self._loopback: LoopbackReference | None = None
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
        # AEC opcional: referencia loopback + cancelador NLMS. Best-effort:
        # si el loopback no arranca, el mic sigue limpio sin AEC.
        if _aec_enabled() and self._loopback is None:
            try:
                from .aec import EchoCanceller
                lb = LoopbackReference()
                if lb.start():
                    self._loopback = lb
                    self._aec = EchoCanceller()
                    logger.info("AEC activo (referencia loopback)")
            except Exception as exc:
                logger.warning("AEC no disponible: %s", exc)
        # Arrancar el pump thread ANTES del stream para que la queue no
        # se llene si el primer chunk llega rapido.
        self._pump_stop.clear()
        self._pump_thread = threading.Thread(
            target=self._pump_loop, daemon=True, name="AudioPump",
        )
        self._pump_thread.start()
        # blocksize a la tasa NATIVA: capturamos CHUNK_SAMPLES "equivalentes a 16k"
        # (1536 a 48k = 512 a 16k tras resamplear) -> downstream sigue viendo 512@16k
        # exactos, que es lo que Silero VAD v5 exige.
        cap_sr = self._native_sr
        cap_block = int(round(CHUNK_SAMPLES * cap_sr / SAMPLE_RATE))
        try:
            self._stream = sd.InputStream(
                samplerate=cap_sr,
                blocksize=cap_block,
                dtype="int16",
                channels=1,
                device=self._device,
                callback=self._sd_callback,
            )
            self._stream.start()
            self.running = True
            self.last_error = None
            logger.info(
                "AudioCapture started (device=%s, capture=%dHz block=%d -> 16kHz "
                "chunk=%d/%dms, resample=%s)",
                self._device, cap_sr, cap_block, CHUNK_SAMPLES, CHUNK_MS,
                self._needs_resample,
            )
            return True
        except Exception as exc:
            # FALLBACK: si WASAPI/tasa nativa falla, reintentar el método viejo
            # (device default a 16k). Nunca dejar la voz rota por el cambio.
            logger.warning("WASAPI capture failed (%s); fallback a 16k directo", exc)
            if self._needs_resample or self._device is not None:
                try:
                    self._device = None
                    self._native_sr = SAMPLE_RATE
                    self._needs_resample = False
                    self._stream = sd.InputStream(
                        samplerate=SAMPLE_RATE, blocksize=CHUNK_SAMPLES,
                        dtype="int16", channels=1, device=None,
                        callback=self._sd_callback)
                    self._stream.start()
                    self.running = True
                    self.last_error = None
                    logger.info("AudioCapture started (fallback 16k directo)")
                    return True
                except Exception as exc2:
                    exc = exc2
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
            # RESAMPLE a 16k (off-callback, acá sí se puede): el chunk crudo viene a
            # la tasa nativa del mic (48k). Resamplear a 16k da los 512 samples que
            # Silero VAD v5 + el resto del pipeline esperan.
            if self._needs_resample:
                try:
                    chunk = _resample_to_16k(chunk, self._native_sr)
                except Exception as exc:
                    logger.debug("resample failed, passing raw: %s", exc)
            # AEC: restar lo que el PC reproduce (referencia loopback). El
            # DelayEstimator interno absorbe el desfase entre streams. Si el
            # chunk no es del tamaño esperado, bypass (nunca romper captura).
            if self._aec is not None and self._loopback is not None \
                    and chunk.size == CHUNK_SAMPLES:
                try:
                    ref = self._loopback.latest(CHUNK_SAMPLES)
                    chunk = self._aec.process(chunk, ref)
                except Exception as exc:
                    logger.debug("aec process falló (bypass): %s", exc)
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
