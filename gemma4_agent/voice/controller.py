"""Fase W — Voice controller: orquesta wake + STT + TTS con state machine.

Diseno:
- Estados representados como literales de string (no enum) para ser facil
  de serializar/loggear y ser tolerantes con consumers que comparen ==.
- El controller corre los componentes en threads dedicados:
    * AudioCapture: thread de PortAudio (interno).
    * WakeDetector.feed(chunk): llamado desde audio callback (sin thread propio).
    * StreamingSTT: thread propio cuando se entra a TRANSCRIBING.
    * StreamingTTS: thread propio constante (worker queue).
- Comunicacion con la GUI: Qt signals (si PyQt6 esta disponible). Si no, callbacks
  llamados directamente (modo CLI / tests).

State transitions (resumen, ver prompt para detalles completos):
    IDLE_DISABLED --(enable)--> IDLE_LISTENING
    IDLE_LISTENING --(wake)--> WAKE_DETECTED --(200ms)--> LISTENING
    LISTENING --(speech_started)--> TRANSCRIBING
    LISTENING --(5s timeout)--> IDLE_LISTENING (silent)
    TRANSCRIBING --(VAD endpoint OR 15s)--> THINKING
    THINKING --(first LLM token)--> SPEAKING
    SPEAKING --(LLM done + last sentence)--> FOLLOWUP (if window>0) OR IDLE_LISTENING
    FOLLOWUP --(speech)--> TRANSCRIBING
    FOLLOWUP --(window timeout)--> IDLE_LISTENING
    FOLLOWUP --(close phrase)--> IDLE_LISTENING
    ANY --(disable / profile LIGHT/STDBY)--> IDLE_DISABLED
    FAILED si modelo / mic falla en load
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Iterable, Iterator

import numpy as np

from .audio_io import AudioCapture, SAMPLE_RATE
from .recorder import PRE_WAKE_TAIL_S, VoiceRecorder
from .stt import StreamingSTT  # STTEvent inferred from transcribe_stream return
from .tts import StreamingTTS
from .wake import WakeDetector

logger = logging.getLogger(__name__)


# Estados como string literals
VoiceState = str
S_IDLE_DISABLED = "IDLE_DISABLED"
S_IDLE_LISTENING = "IDLE_LISTENING"
S_WAKE_DETECTED = "WAKE_DETECTED"
S_LISTENING = "LISTENING"
S_TRANSCRIBING = "TRANSCRIBING"
S_THINKING = "THINKING"
S_SPEAKING = "SPEAKING"
S_FOLLOWUP = "FOLLOWUP"
S_FAILED = "FAILED"


# Timeouts (segundos)
WAKE_FEEDBACK_MS = 200  # cyan brillante antes de LISTENING
LISTENING_TIMEOUT_S = 5.0  # 200ms gracia + ~4.8s reales para empezar a hablar
ABSOLUTE_TRANSCRIBE_S = 15.0  # ya implementado en stt.py
DEFAULT_FOLLOWUP_S = 5.0

DEFAULT_CLOSE_PHRASES = (
    "gracias", "listo", "ya esta", "ya está", "cancelar", "stop",
)

# Margen hacia atras del fin del wake-word reportado por Vosk. Vosk tiene
# jitter de ~50ms en sus word timestamps; sin margen, el snapshot puede
# comer el primer fonema del comando ("abre" -> "bre"). Informe sec. 7.4.
# Constante de modulo para que sea trivialmente ajustable y testeable.
WAKE_SAFETY_MARGIN_S = 0.05


def _normalize_phrase(text: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch)).strip()


class VoiceController:
    """Maquina de estados completa para voz.

    Callbacks (todos opcionales):
        on_state(state: VoiceState)
        on_partial(text: str)
        on_final(text: str)
        on_tts_chunk(text: str)
        on_failed(reason: str)

    Los callbacks corren en el thread del componente; el caller (GUI) debe
    marshall a su event loop (QTimer.singleShot(0, ...) o Qt signals via slot).

    Para la GUI conviene usar `VoiceControllerQt` (subclase) que emite
    pyqtSignal y maneja el marshalling automaticamente.
    """

    def __init__(
        self,
        *,
        on_state: Callable[[VoiceState], None] | None = None,
        on_partial: Callable[[str], None] | None = None,
        on_final: Callable[[str], None] | None = None,
        on_tts_chunk: Callable[[str], None] | None = None,
        on_failed: Callable[[str], None] | None = None,
        followup_seconds: float = DEFAULT_FOLLOWUP_S,
        close_phrases: Iterable[str] = DEFAULT_CLOSE_PHRASES,
        beep_on_wake: bool = True,
        device: int | str | None = None,
    ) -> None:
        self._on_state = on_state
        self._on_partial = on_partial
        self._on_final = on_final
        self._on_tts_chunk = on_tts_chunk
        self._on_failed = on_failed

        self._followup_s = float(followup_seconds)
        self._close_phrases = {_normalize_phrase(p) for p in close_phrases}
        self._beep_on_wake = bool(beep_on_wake)

        self._state: VoiceState = S_IDLE_DISABLED
        self._state_lock = threading.Lock()

        # Componentes
        self._audio = AudioCapture(on_chunk=self._on_audio_chunk, device=device)
        self._wake = WakeDetector(on_wake=self._on_wake_detected)
        self._stt = StreamingSTT()
        self._tts = StreamingTTS()

        # Para STT: queue de chunks que el thread de transcripcion drena
        self._stt_chunks: list[np.ndarray] = []
        self._stt_chunks_lock = threading.Lock()
        self._stt_thread: threading.Thread | None = None
        self._stt_stop_event = threading.Event()
        # Acoustic snapshot capturado en _on_wake_detected: el audio POST-wake
        # del ring buffer. Se pasa como prefix_audio a transcribe_stream
        # (no via _stt_chunks porque la gracia pre-speech lo descartaria).
        self._pending_snapshot: np.ndarray | None = None

        # Para timeouts (LISTENING + FOLLOWUP)
        self._timer_thread: threading.Thread | None = None
        self._timer_stop = threading.Event()

        self._failed_components: list[str] = []

        # Sprint 7.1: voice end-to-end latency instrumentation.
        # Set in _on_wake_detected; consumed (once) in begin_tts to
        # emit a BUS event with wake→first-speak elapsed_ms. Reset to
        # None after each emission so subsequent TTS chunks within the
        # same turn don't re-emit.
        self._wake_ts: float | None = None

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------

    def state(self) -> VoiceState:
        return self._state

    def _set_state(self, new: VoiceState) -> None:
        with self._state_lock:
            if self._state == new:
                return
            self._state = new
        logger.info("VoiceController -> %s", new)
        if self._on_state is not None:
            try:
                self._on_state(new)
            except Exception as exc:
                logger.warning("on_state raised: %s", exc)

    def _fail(self, reason: str) -> None:
        logger.error("VoiceController failed: %s", reason)
        self._set_state(S_FAILED)
        if self._on_failed is not None:
            try:
                self._on_failed(reason)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def enable(self) -> bool:
        """Carga modelos y arranca el audio. True si quedo en IDLE_LISTENING."""
        if self._state not in {S_IDLE_DISABLED, S_FAILED}:
            return True
        self._failed_components.clear()

        # TTS: opcional. Si falla, dejamos voice sin output pero sigue input.
        if not self._tts.load():
            logger.warning("TTS load failed: %s", self._tts.last_error)
            self._failed_components.append(f"tts: {self._tts.last_error}")
        else:
            self._tts.start()

        # STT: si falla, no podemos transcribir. Failed total.
        if not self._stt.load():
            self._fail(f"stt: {self._stt.last_error}")
            return False

        # Wake: si falla, podemos correr en "push-to-talk only" desde la GUI.
        # No es failed total -- el caller decide. Para esta fase: marcamos
        # como degradado en _failed_components.
        if not self._wake.load():
            logger.warning("Wake load failed: %s", self._wake.last_error)
            self._failed_components.append(f"wake: {self._wake.last_error}")

        # Audio: critico
        if not self._audio.start():
            self._fail(f"audio: {self._audio.last_error}")
            return False

        self._set_state(S_IDLE_LISTENING)
        return True

    def disable(self) -> None:
        """Apaga todo, libera modelos, vuelve a IDLE_DISABLED."""
        self._cancel_timer()
        self._stop_stt_thread()
        self._audio.stop()
        self._tts.unload()
        self._stt.unload()
        self._wake.unload()
        self._set_state(S_IDLE_DISABLED)

    def trigger_manual(self) -> None:
        """Atajo para el boton mic de la GUI: simula un wake (sin snapshot)."""
        if self._state == S_IDLE_LISTENING:
            # wake_end_s=0.0 -> no snapshot, gracia normal de 200ms
            self._on_wake_detected("manual", time.monotonic(), 0.0, 0.0)

    def shutdown(self) -> None:
        """Cleanup al cerrar la aplicacion."""
        self.disable()

    # ------------------------------------------------------------------
    # Setters / config
    # ------------------------------------------------------------------

    def set_tts_muted(self, muted: bool) -> None:
        self._tts.set_muted(muted)

    def is_tts_muted(self) -> bool:
        return self._tts.is_muted()

    def set_followup_seconds(self, seconds: float) -> None:
        self._followup_s = max(0.0, float(seconds))

    def set_close_phrases(self, phrases: Iterable[str]) -> None:
        self._close_phrases = {_normalize_phrase(p) for p in phrases}

    def get_failed_components(self) -> list[str]:
        return list(self._failed_components)

    # ------------------------------------------------------------------
    # TTS streaming (consumido por la GUI cuando recibe deltas del LLM)
    # ------------------------------------------------------------------

    def begin_tts(self) -> None:
        """Transicion -> SPEAKING. Llamar al primer delta del LLM.

        Originalmente solo cubria THINKING -> SPEAKING (turno disparado por voz).
        Ahora tambien acepta IDLE_LISTENING / FOLLOWUP / WAKE_DETECTED como
        origen: cuando el usuario tipea en lugar de hablar, el controller
        nunca paso por THINKING y se quedaba pegado escuchando mientras Piper
        emitia la respuesta -> Vosk capturaba su propia voz como wake.
        SPEAKING descarta audio entrante (ver `_on_audio_chunk`), asi que
        forzar la transicion aqui es el anti-echo natural del controller."""
        if self._state in {S_THINKING, S_IDLE_LISTENING, S_FOLLOWUP, S_WAKE_DETECTED}:
            self._set_state(S_SPEAKING)
        # Sprint 7.1: emit wake→first-speak elapsed_ms exactly once per turn.
        # NOTE: this approximates "first phoneme" — strictly speaking we'd
        # need to hook Piper's audio output. begin_tts fires on the first
        # LLM delta (text), so the real audio is ~50-200ms behind. Good
        # enough for p50/p95 tracking. BUS import is lazy so voice/ doesn't
        # acquire a hard dep on events_bus at module-load time.
        wake_ts = self._wake_ts
        if wake_ts is not None:
            elapsed_ms = int((time.monotonic() - wake_ts) * 1000)
            self._wake_ts = None
            try:
                from ..events_bus import BUS
                BUS.publish({
                    "kind": "voice_e2e_latency",
                    "elapsed_ms": elapsed_ms,
                    "phase": "wake_to_first_speak",
                })
            except Exception:
                pass

    def feed_tts_chunk(self, chunk: str) -> None:
        """Acumula texto del LLM stream y encola oraciones a Piper."""
        if not chunk:
            return
        flushed = self._tts.feed_text(chunk)
        if flushed > 0 and self._on_tts_chunk is not None:
            try:
                self._on_tts_chunk(chunk)
            except Exception:
                pass

    def end_tts(self) -> None:
        """LLM termino: flush ultima oracion, esperar a que Piper termine, y
        mover a FOLLOWUP o IDLE. La espera es lo que evita el eco — si
        volviéramos al estado de escucha mientras la cola TTS sigue
        reproduciendo, Vosk capturaría el final de la frase como audio del
        usuario y lo trataría como nuevo wake. La transición ocurre en un
        thread daemon para no bloquear al caller (que típicamente corre
        en el agent_runner thread)."""
        self._tts.flush()
        def _wait_and_transition() -> None:
            # cap absoluto por seguridad — una frase larga típica son 6-10s,
            # pero si algo se cuelga no queremos quedar pegados en SPEAKING.
            deadline = time.monotonic() + 30.0
            while time.monotonic() < deadline:
                if not self._tts.is_busy():
                    break
                time.sleep(0.1)
            # Hotfix L 2026-05-17: TTS finished playing — close the
            # turn's recording. Wrapped so a recorder failure doesn't
            # break the state transition.
            try:
                VoiceRecorder.get().finish_turn(reason="tts_finished")
            except Exception:
                pass
            # ya esta tranquilo — volver al estado correcto
            if self._followup_s > 0:
                self._set_state(S_FOLLOWUP)
                self._start_followup_timer()
            else:
                self._set_state(S_IDLE_LISTENING)
                self._wake.reset()
        threading.Thread(
            target=_wait_and_transition,
            name="VoiceTtsWait",
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Internals — wake + STT
    # ------------------------------------------------------------------

    def _on_audio_chunk(self, chunk: np.ndarray) -> None:
        """Audio callback. Rutea por estado.

        WAKE_DETECTED tambien encola al STT (continuacion natural del
        acoustic snapshot que se inyecta como prefix_audio en transcribe_stream).
        """
        s = self._state
        if s == S_IDLE_LISTENING:
            # Vosk wake-word
            self._wake.feed(chunk)
        elif s in {S_WAKE_DETECTED, S_LISTENING, S_TRANSCRIBING, S_FOLLOWUP}:
            # Alimentar STT (corre en thread propio)
            with self._stt_chunks_lock:
                self._stt_chunks.append(chunk)
                if len(self._stt_chunks) % 100 == 0:
                    logger.info(
                        "audio chunks flowing to STT: %d queued, state=%s",
                        len(self._stt_chunks), s,
                    )
        # En THINKING / SPEAKING / IDLE_DISABLED / FAILED ignoramos audio.

        # Hotfix L 2026-05-17: tap the mic for the recorder. No-op
        # when not recording an active turn or recording disabled.
        # Wrapped in try/except so a recorder failure can never break
        # the audio loop.
        try:
            VoiceRecorder.get().capture_user_chunk(chunk)
        except Exception:
            pass

    def _on_wake_detected(
        self,
        phrase: str,
        ts: float,
        tail_s: float = 0.0,
        confidence: float = 0.0,
    ) -> None:
        """Wake-word detectado.

        tail_s: cuanto audio del ring buffer hay DESPUES del wake-word
        (en segundos). Lo calcula wake.py con la formula robusta:
            tail_s = duracion_del_Result - posicion_del_wake_en_el_Result
        Si tail_s > 0.05, tomamos snapshot_tail(tail_s) del ring buffer
        y lo inyectamos como prefix_audio al STT (acoustic snapshot
        estilo Alexa). Asi el usuario puede decir "gemma apaga la luz"
        sin pausa.

        Si tail_s == 0 (sin word timestamp util), caemos al comportamiento
        viejo: gracia pre-speech filtra la cola del wake.
        """
        if self._state not in {S_IDLE_LISTENING, S_FOLLOWUP}:
            return
        # Sprint 7.1: timestamp the wake moment so begin_tts (called by the
        # GUI when the first LLM delta arrives) can publish the
        # wake→first-speak end-to-end latency.
        self._wake_ts = time.monotonic()
        if self._beep_on_wake:
            self._play_beep()

        # Hotfix L 2026-05-17: start recording for this turn. The
        # pre-wake tail comes from the mic ring buffer so we keep
        # ~500ms of audio before the wake-word was confirmed (useful
        # for false-wake audit). Failure-tolerant: a recorder issue
        # never breaks the voice loop.
        try:
            recorder = VoiceRecorder.get()
            if recorder.enable():
                pre = None
                try:
                    pre = self._audio.snapshot_tail(PRE_WAKE_TAIL_S)
                except Exception:
                    pre = None
                turn_id = f"turn_{int(self._wake_ts * 1000)}"
                self._current_turn_id = turn_id
                # Hotfix M.1.2 2026-05-18: wake.py now propagates
                # Vosk's confidence value through the callback;
                # pass it to the recorder for manifest annotation.
                recorder.start_turn(
                    turn_id=turn_id,
                    wake_phrase=phrase,
                    wake_confidence=float(confidence),
                    pre_wake_audio=pre,
                )
        except Exception as _rec_exc:
            logger.warning("voice_recorder_start_turn_failed error=%s", _rec_exc)

        # Ampliar el snapshot WAKE_SAFETY_MARGIN_S hacia atras del fin del
        # wake-word reportado por Vosk para no comer el principio del comando
        # (informe sec. 7.4). El strip del wake-word residual queda en
        # stt._postprocess_text como defensa en profundidad.
        snapshot_audio: np.ndarray | None = None
        if tail_s > 0.05:
            safe_tail_s = min(5.0, max(0.0, tail_s) + WAKE_SAFETY_MARGIN_S)
            try:
                snapshot_audio = self._audio.snapshot_tail(safe_tail_s)
                logger.info(
                    "snapshot tail=%.3fs (+%.3fs margin) snap_samples=%d",
                    tail_s, WAKE_SAFETY_MARGIN_S, snapshot_audio.size,
                )
            except Exception as exc:
                logger.warning("snapshot_tail failed: %s", exc)
                snapshot_audio = None

        # Guardar snapshot como prefix_audio para que transcribe_stream lo
        # use directamente (saltando la gracia pre-speech). Limpiar la queue
        # de chunks que pueda haber quedado de IDLE_LISTENING.
        self._pending_snapshot = snapshot_audio
        with self._stt_chunks_lock:
            self._stt_chunks.clear()
        self._set_state(S_WAKE_DETECTED)
        # Pausa visual breve antes de LISTENING. Durante esos 200ms los
        # chunks nuevos se acumulan (continuacion natural del snapshot).
        threading.Timer(WAKE_FEEDBACK_MS / 1000.0, self._enter_listening).start()

    def _enter_listening(self) -> None:
        if self._state != S_WAKE_DETECTED:
            return
        # NO limpiar buffer aqui: cualquier audio que llego durante los 200ms
        # de WAKE_DETECTED es valido y queremos darselo a STT.
        self._set_state(S_LISTENING)
        self._start_listening_timeout()
        self._start_stt_thread()

    def _start_listening_timeout(self) -> None:
        """Si en 5s no hay speech, volver a IDLE_LISTENING silenciosamente."""
        self._cancel_timer()
        self._timer_stop.clear()
        def _watchdog() -> None:
            if self._timer_stop.wait(LISTENING_TIMEOUT_S):
                return
            # Si seguimos en LISTENING (sin haber pasado a TRANSCRIBING) -> idle
            if self._state == S_LISTENING:
                self._stop_stt_thread()
                self._set_state(S_IDLE_LISTENING)
                self._wake.reset()
        self._timer_thread = threading.Thread(target=_watchdog, daemon=True, name="VoiceListenTimeout")
        self._timer_thread.start()

    def _start_followup_timer(self) -> None:
        self._cancel_timer()
        self._timer_stop.clear()
        seconds = self._followup_s
        def _watchdog() -> None:
            if self._timer_stop.wait(seconds):
                return
            if self._state == S_FOLLOWUP:
                self._set_state(S_IDLE_LISTENING)
                self._wake.reset()
        self._timer_thread = threading.Thread(target=_watchdog, daemon=True, name="VoiceFollowupTimer")
        self._timer_thread.start()

    def _cancel_timer(self) -> None:
        self._timer_stop.set()
        if self._timer_thread is not None and self._timer_thread.is_alive():
            self._timer_thread.join(timeout=0.1)
        self._timer_thread = None

    def _stt_chunk_iter(self) -> Iterator[np.ndarray]:
        """Generator que vacia self._stt_chunks (consumido por StreamingSTT)."""
        while not self._stt_stop_event.is_set():
            with self._stt_chunks_lock:
                if self._stt_chunks:
                    chunk = self._stt_chunks.pop(0)
                    yield chunk
                    continue
            time.sleep(0.02)  # ~20ms, mas chico que el chunk size de 30ms

    def _start_stt_thread(self) -> None:
        self._stop_stt_thread()
        self._stt_stop_event.clear()
        # Capturar snapshot pendiente (se setea en _on_wake_detected)
        prefix = self._pending_snapshot
        self._pending_snapshot = None

        def _run() -> None:
            logger.info(
                "STT thread started (prefix=%d samples)",
                prefix.size if prefix is not None else 0,
            )
            saw_speech = False
            try:
                for ev in self._stt.transcribe_stream(self._stt_chunk_iter(), prefix_audio=prefix):
                    logger.info("STT event: kind=%s text=%r", ev.kind, ev.text[:60])
                    if ev.kind == "partial":
                        saw_speech = True
                        if self._state == S_LISTENING:
                            # Primer speech detectado: pasar a TRANSCRIBING
                            self._cancel_timer()
                            self._set_state(S_TRANSCRIBING)
                        if self._on_partial is not None:
                            try:
                                self._on_partial(ev.text)
                            except Exception:
                                pass
                    elif ev.kind == "final":
                        # Hotfix L 2026-05-17: annotate the recorder
                        # with whisper transcription (or rejection
                        # reason) so the manifest carries weak ground
                        # truth alongside the WAV.
                        # Hotfix M.1.3 2026-05-18: use the specific
                        # reject_reason from the STT event (now
                        # carried on STTEvent) — 'BoH_match' /
                        # 'low_logprob' / 'no_speech' / etc — instead
                        # of the generic placeholder.
                        # Hotfix M.1.4 2026-05-18: eagerly close the
                        # turn on STT reject. No TTS will play, so
                        # end_tts -> finish_turn won't fire from the
                        # downstream path; we'd otherwise wait for
                        # the next wake to overlap-close with the
                        # wrong finish_reason.
                        try:
                            _rec = VoiceRecorder.get()
                            if ev.text:
                                _rec.annotate_turn(whisper_transcription=ev.text)
                            else:
                                _specific = (
                                    getattr(ev, "reject_reason", "")
                                    or "stt_empty_or_vad_reject"
                                )
                                _rec.annotate_turn(stt_reject_reason=_specific)
                                _rec.finish_turn(reason="stt_rejected")
                        except Exception:
                            pass
                        if not saw_speech and not ev.text:
                            # Timeout sin habla -> volver a idle limpio
                            if self._state in {S_LISTENING, S_TRANSCRIBING}:
                                self._set_state(S_IDLE_LISTENING)
                                self._wake.reset()
                            return
                        # Aseguramos transicion correcta aunque nunca hubo Partial
                        # (caso: snapshot vacio + audio nuevo sin speech audible).
                        if self._state == S_LISTENING:
                            self._cancel_timer()
                        self._handle_final(ev.text)
                        return
                    elif ev.kind == "timeout":
                        if self._state in {S_LISTENING, S_TRANSCRIBING}:
                            self._set_state(S_IDLE_LISTENING)
                            self._wake.reset()
                        return
                    elif ev.kind == "error":
                        logger.error("STT error event: %s", ev.error)
                        if self._on_failed is not None:
                            try:
                                self._on_failed(f"stt: {ev.error}")
                            except Exception:
                                pass
                        if self._state in {S_LISTENING, S_TRANSCRIBING}:
                            self._set_state(S_IDLE_LISTENING)
                            self._wake.reset()
                        return
            except Exception as exc:
                logger.exception("STT thread crashed: %s", exc)
                if self._on_failed is not None:
                    try:
                        self._on_failed(f"stt crashed: {exc}")
                    except Exception:
                        pass
                if self._state in {S_LISTENING, S_TRANSCRIBING}:
                    self._set_state(S_IDLE_LISTENING)
                    self._wake.reset()

        self._stt_thread = threading.Thread(target=_run, daemon=True, name="VoiceSTT")
        self._stt_thread.start()

    def _stop_stt_thread(self) -> None:
        """Senaliza al thread de STT que pare y espera join.

        BUG FIX (2026-05-14): la version anterior NULIFICABA self._on_partial
        y self._on_final aqui como "defensa" contra eventos straggler. Eso
        provocaba que el SIGUIENTE wake encontrara _on_final=None y se
        colgara en THINKING (porque _start_stt_thread llama esto primero).
        Solucion correcta: el thread STT ya respeta _stt_stop_event y el
        _stt_chunk_iter sale limpio; no hace falta destruir callbacks.
        """
        self._stt_stop_event.set()
        if self._stt_thread is not None:
            # 5s margin: whisper int8 on CPU typically finishes within 1-3s.
            self._stt_thread.join(timeout=5.0)
            if self._stt_thread.is_alive():
                logger.warning("STT thread did not exit after 5s; abandoning")
        self._stt_thread = None

    def _handle_final(self, text: str) -> None:
        text = (text or "").strip()
        logger.info("_handle_final called with text=%r", text)
        # Close-phrase de followup?
        if self._state == S_FOLLOWUP:
            norm = _normalize_phrase(text)
            if norm in self._close_phrases:
                logger.info("_handle_final: close phrase matched, going IDLE")
                self._set_state(S_IDLE_LISTENING)
                self._wake.reset()
                return
        # Sino, enviar al agente y pasar a THINKING
        self._set_state(S_THINKING)
        if not text:
            logger.warning("_handle_final: empty text, NOT calling on_final")
            # Volvemos a idle para no quedar pegado en THINKING
            self._set_state(S_IDLE_LISTENING)
            self._wake.reset()
            return
        if self._on_final is None:
            logger.warning("_handle_final: on_final callback is None! freeing controller")
            # Sin callback no podemos entregar el texto. Volver a IDLE para no
            # quedar pegado en THINKING (sintoma reportado: voz se cuelga
            # tras la primera transcripcion).
            self._set_state(S_IDLE_LISTENING)
            self._wake.reset()
            return
        logger.info("_handle_final: invoking on_final callback")
        try:
            self._on_final(text)
            logger.info("_handle_final: on_final returned successfully")
        except Exception as exc:
            logger.exception("on_final raised: %s", exc)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _play_beep(self) -> None:
        """Beep corto 80ms 600Hz como feedback de wake detectado.

        IMPORTANTE: lanza un thread separado porque _on_wake_detected es
        llamado desde el callback de PortAudio. Hacer sd.play() (que abre
        un nuevo stream) desde dentro del callback de otro stream puede
        bloquear PortAudio y causar drops de audio.
        """
        def _do() -> None:
            try:
                import sounddevice as sd
                duration_s = 0.08
                t = np.linspace(0, duration_s, int(SAMPLE_RATE * duration_s), False)
                tone = (np.sin(2 * np.pi * 600 * t) * 0.3 * 32768).astype(np.int16)
                sd.play(tone, samplerate=SAMPLE_RATE, blocking=False)
            except Exception as exc:
                logger.debug("beep failed: %s", exc)
        threading.Thread(target=_do, daemon=True, name="VoiceBeep").start()
