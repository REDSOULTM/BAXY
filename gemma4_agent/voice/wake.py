"""Fase W — wake-word detector con Vosk small es-0.42.

Activadores: "gemma" y "hey gemma". Engine: Vosk con vocabulario restringido
para acotar falsos positivos.

Modelo: ~/.gemma4/models/vosk-model-small-es-0.42/. Si no existe, primera
invocacion devuelve estado MISSING y el caller (controller) muestra dialogo
de consentimiento + dispara descarga.

URL oficial: https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip
Tamano descomprimido ~40 MB.
"""
from __future__ import annotations

import json
import logging
import os
import time
import zipfile
from pathlib import Path
from typing import Callable

import numpy as np

from .audio_io import SAMPLE_RATE

logger = logging.getLogger(__name__)


VOSK_MODEL_NAME = "vosk-model-small-es-0.42"
VOSK_MODEL_URL = f"https://alphacephei.com/vosk/models/{VOSK_MODEL_NAME}.zip"
VOSK_MODEL_DIR = Path.home() / ".gemma4" / "models" / VOSK_MODEL_NAME

WAKE_VOCAB = '["gemma", "hey gemma", "[unk]"]'
WAKE_PHRASES = {"gemma", "hey gemma"}
WAKE_DEBOUNCE_S = 2.0

# Confidence minimo por word para aceptar un wake.
# Vosk reporta conf ∈ [0,1] cuando SetWords(True). Un wake real suele
# salir >0.9; los falsos positivos (palabras foneticamente parecidas
# como "tema", "venga", "vengo") salen tipicamente <0.7.
# Subir => menos falsos positivos pero mas misses. Bajar => al reves.
WAKE_MIN_CONFIDENCE = 0.85


WakeCallback = Callable[[str, float, float], None]
# Signature: on_wake(matched_phrase, wall_clock_ts, tail_s)
#
# - matched_phrase: "gemma" o "hey gemma"
# - wall_clock_ts: time.monotonic() en el momento del wake (para debounce/UX)
# - tail_s: cuanto audio del ring buffer hay DESPUES del wake-word (en seg).
#   Lo calcula este modulo restando wake_end vs duracion del Result actual.
#   El caller usa snapshot_tail(tail_s) para sembrar el STT con el comando
#   continuo "gemma apaga la luz" sin perder la cola.


def model_exists() -> bool:
    """True si el modelo Vosk ya esta bajado y descomprimido en disco."""
    # Vosk model dirs contienen al menos `am/final.mdl` o `graph/HCLr.fst`.
    if not VOSK_MODEL_DIR.is_dir():
        return False
    try:
        # Heuristica: cualquier archivo .mdl o subcarpeta `am` indica modelo valido
        for sub in VOSK_MODEL_DIR.iterdir():
            if sub.is_dir() and sub.name in {"am", "graph", "ivector"}:
                return True
        return False
    except OSError:
        return False


def download_model(progress_cb: Callable[[int, int], None] | None = None) -> bool:
    """Descarga + descomprime el modelo Vosk a VOSK_MODEL_DIR.

    progress_cb(bytes_done, total) opcional para GUI.
    Devuelve True si quedo listo. False si fallo.
    """
    import urllib.request
    VOSK_MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
    zip_path = VOSK_MODEL_DIR.parent / f"{VOSK_MODEL_NAME}.zip"
    try:
        logger.info("Downloading Vosk model from %s", VOSK_MODEL_URL)
        with urllib.request.urlopen(VOSK_MODEL_URL, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            with open(zip_path, "wb") as f:
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
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(VOSK_MODEL_DIR.parent)
        # El zip extrae a una carpeta `vosk-model-small-es-0.42`. Listo.
        try:
            zip_path.unlink()
        except OSError:
            pass
        logger.info("Vosk model ready at %s", VOSK_MODEL_DIR)
        return True
    except Exception as exc:
        logger.error("Vosk download failed: %s", exc)
        return False


class WakeDetector:
    """Detector continuo de wake-words sobre stream de audio.

    Uso:
        det = WakeDetector(on_wake=lambda phrase, ts: ...)
        if det.load():
            det.feed(chunk)  # llamar desde audio callback
    """

    def __init__(self, on_wake: WakeCallback) -> None:
        self._on_wake = on_wake
        self._rec = None  # type: ignore[assignment]
        self._loaded: bool = False
        self.last_error: str | None = None
        self._last_fire_at: float = 0.0
        # AUDIT POST-BUG ALEXA:
        # La premisa anterior ("ambos contadores son cumulativos desde la
        # creacion del recognizer, por eso se mantienen alineados") es FALSA.
        # Vosk re-zerea internamente samples_round_start_/frame_offset_ cuando
        # frame_offset_ > 20000 (~10 min de audio) en CleanUp(), pero NUESTRO
        # _total_samples_fed sigue creciendo. Eso causa wake_end_s muy chico
        # y tail_s = total_fed_s - wake_end_s ≈ total_fed_s → clampea a 5s
        # → snapshot de 5s contaminado (incluye TTS previo, eco, etc).
        # Sintoma: "abre Steam" se transcribe como "abre este" o cosas raras.
        #
        # FIX: medir samples DENTRO del Result actual. Vosk emite el Result
        # cuando detecta endpoint; todo lo que recibimos via AcceptWaveform
        # desde el ULTIMO Result final es el span de este Result. Los word
        # timestamps "start"/"end" en el Result son acumulativos pero la
        # RESTA contra otros words del MISMO Result es consistente. Mejor
        # aun: mantener un offset_at_last_result que captura el valor
        # acumulativo de Vosk justo antes de este Result. Asi:
        #   tail_in_buffer_s = (samples_received_this_result/SR) -
        #                       (wake_end_s - vosk_offset_at_last_result)
        # Donde vosk_offset_at_last_result viene del PROPIO Vosk leyendo
        # words[0].start del Result actual. start - end_of_word - now da
        # un calculo estable sin contadores globales.
        #
        # Simplificacion final: medir todo en SAMPLES y dentro del Result.
        # _samples_since_last_result = audio fed desde el ultimo AcceptWaveform=True.
        # Cuando llega el wake, audio en este Result = samples_since_last_result.
        # Position relativa del fin del wake dentro del Result =
        #   wake_end_s - (start del primer word del Result).
        # tail_samples = samples_since_last_result -
        #                (wake_relative_end_s * SAMPLE_RATE)
        self._samples_since_last_result: int = 0

    def load(self) -> bool:
        """Carga el modelo Vosk. Devuelve True/False. last_error si falla."""
        if not model_exists():
            self.last_error = f"vosk model not found at {VOSK_MODEL_DIR}"
            return False
        try:
            import vosk  # lazy import
        except ImportError as exc:
            self.last_error = f"vosk not installed: {exc}"
            return False
        try:
            # Silenciar el log verbose de Vosk
            try:
                vosk.SetLogLevel(-1)
            except Exception:
                pass
            model = vosk.Model(str(VOSK_MODEL_DIR))
            self._rec = vosk.KaldiRecognizer(model, SAMPLE_RATE, WAKE_VOCAB)
            # Activar word timestamps para acoustic snapshot (igual a Alexa):
            # result["result"] = [{word, start, end, conf}]. Lo usamos para
            # saber donde termina "gemma" en el audio y empalmar el comando
            # inmediato sin perder la cola.
            try:
                self._rec.SetWords(True)
            except Exception as exc:
                logger.warning("Vosk SetWords(True) failed: %s", exc)
            self._samples_since_last_result = 0
            self._last_fire_at = 0.0
            self._loaded = True
            self.last_error = None
            logger.info("WakeDetector loaded (%s)", VOSK_MODEL_NAME)
            return True
        except Exception as exc:
            self.last_error = f"vosk init failed: {type(exc).__name__}: {exc}"
            logger.error(self.last_error)
            return False

    def is_loaded(self) -> bool:
        return self._loaded

    def feed(self, chunk: np.ndarray) -> None:
        """Procesa un chunk de audio (int16, 16kHz, mono).

        Llama on_wake si detecta una frase wake. Aplica debounce 2s.
        Solo dispara en results FINALES, no partials (evita falsos positivos).
        """
        if not self._loaded or self._rec is None:
            return
        try:
            data = chunk.tobytes() if hasattr(chunk, "tobytes") else bytes(chunk)
            self._samples_since_last_result += int(chunk.size)
            is_final = self._rec.AcceptWaveform(data)
        except Exception as exc:
            logger.warning("WakeDetector.feed error: %s", exc)
            return
        if not is_final:
            return
        # AcceptWaveform=True => Vosk va a emitir Result. Capturamos el size
        # del span ANTES de resetearlo, asi el snapshot puede usarlo.
        samples_in_this_result = self._samples_since_last_result
        self._samples_since_last_result = 0
        # Result final disponible
        try:
            raw = self._rec.Result()
            result = json.loads(raw)
        except (ValueError, TypeError):
            return
        text = (result.get("text") or "").strip().lower()
        if not text:
            return
        # Debounce: ignorar wakes muy seguidos
        now = time.monotonic()
        if now - self._last_fire_at < WAKE_DEBOUNCE_S:
            return
        # Match exacto sobre las dos frases conocidas (criterio textual previo)
        matched: str | None = None
        if text == "hey gemma":
            matched = "hey gemma"
        elif text == "gemma":
            matched = "gemma"
        elif "hey gemma" in text:
            matched = "hey gemma"
        elif "gemma" in text.split():
            matched = "gemma"
        if matched is None:
            return

        # Validacion por confidence: Vosk reporta conf por word cuando
        # SetWords(True). Necesitamos encontrar la palabra "gemma" con
        # conf >= WAKE_MIN_CONFIDENCE. Si no la hay, descartar este result
        # como falso positivo (palabra foneticamente similar tipo "tema",
        # "venga", "pega" mapeada al vocab restringido).
        #
        # Al mismo tiempo calculamos el TAIL_S (cuanto audio en el ring
        # buffer hay DESPUES del wake). Esto es lo que el caller corta como
        # acoustic snapshot estilo Alexa.
        #
        # CALCULO ROBUSTO (post bug "abre Steam → abre este"):
        # Los words[].start/end de Vosk son acumulativos desde la creacion
        # del recognizer, PERO Vosk re-zerea internamente cada ~10 minutos.
        # Por eso usar contadores globales no funciona. En su lugar:
        #
        #   1. samples_in_this_result = audio fed desde el ULTIMO Result final.
        #   2. result_start_s = words[0].start (timestamp del primer word
        #      del Result actual, en escala acumulativa de Vosk).
        #   3. wake_end_s = end del ultimo word "gemma" en este Result.
        #   4. wake_end_relative_s = wake_end_s - result_start_s
        #      (cuanto desde el principio del Result actual termino el wake).
        #   5. result_duration_s = samples_in_this_result / SAMPLE_RATE.
        #   6. tail_s = result_duration_s - wake_end_relative_s
        #      (cuanto audio del Result quedo DESPUES del wake-word).
        #
        # Como ambos endpoints (start y end) salen del MISMO Result, su
        # resta es consistente sin importar el "wrap" interno de Vosk.
        wake_end_s = 0.0
        best_conf = 0.0
        result_start_s = 0.0
        words = result.get("result") or []
        if isinstance(words, list) and words:
            # result_start_s = primer word del Result (orden temporal)
            for w in words:
                if isinstance(w, dict):
                    try:
                        result_start_s = float(w.get("start") or 0.0)
                    except (TypeError, ValueError):
                        result_start_s = 0.0
                    break
            # wake_end_s = ultimo "gemma" con conf alta
            for w in reversed(words):
                if not isinstance(w, dict):
                    continue
                wtxt = str(w.get("word") or "").strip().lower()
                if wtxt != "gemma":
                    continue
                try:
                    wconf = float(w.get("conf") or 0.0)
                except (TypeError, ValueError):
                    wconf = 0.0
                if wconf < WAKE_MIN_CONFIDENCE:
                    continue
                try:
                    wake_end_s = float(w.get("end") or 0.0)
                except (TypeError, ValueError):
                    wake_end_s = 0.0
                best_conf = wconf
                break

        if best_conf < WAKE_MIN_CONFIDENCE:
            logger.debug(
                "wake descartado por conf (%.2f < %.2f): text=%r words=%r",
                best_conf, WAKE_MIN_CONFIDENCE, text, words,
            )
            return

        # Calcular tail_s con la formula robusta
        result_duration_s = samples_in_this_result / float(SAMPLE_RATE)
        wake_end_relative_s = max(0.0, wake_end_s - result_start_s)
        tail_s = max(0.0, result_duration_s - wake_end_relative_s)
        logger.info(
            "wake detect: result_dur=%.2fs wake_rel_end=%.2fs tail=%.2fs (conf=%.2f, text=%r)",
            result_duration_s, wake_end_relative_s, tail_s, best_conf, text,
        )

        self._last_fire_at = now
        try:
            self._on_wake(matched, now, tail_s)
        except Exception as exc:
            logger.warning("on_wake callback raised: %s", exc)

    def reset(self) -> None:
        """Limpia el buffer interno de Vosk para el proximo wake.

        Tambien resetea _samples_since_last_result porque Reset() en Vosk
        descarta cualquier audio parcial que estuviera buffereado. La
        proxima palabra arranca un Result nuevo desde 0 samples.
        """
        if self._rec is not None:
            try:
                self._rec.Reset()
            except Exception:
                pass
        self._samples_since_last_result = 0
        self._last_fire_at = 0.0

    def unload(self) -> None:
        """Libera el modelo de RAM. Llamado al pasar a LIGHT/STANDBY."""
        self._rec = None
        self._loaded = False
        self._samples_since_last_result = 0
        self._last_fire_at = 0.0
