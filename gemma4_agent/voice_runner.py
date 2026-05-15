"""Bridge between the FastAPI server and the local voice stack.

Owns a single VoiceController instance and forwards its state / partial /
final callbacks to the EventBus so the web UI sees the same signals the
PyQt6 GUI did. Once enabled, the user can say 'gemma' to wake, speak a
question, and the final transcript is fed straight into AgentRunner.submit.

The model load (Vosk + faster-whisper + Piper) takes 1-3 seconds the first
time, so enable() runs on a worker thread and emits BOOT entries while it
loads. The web UI doesn't block.
"""

from __future__ import annotations

import logging
import queue
import threading
import uuid
from typing import Any

from .boot_progress import emit_stage
from .events_bus import BUS

logger = logging.getLogger(__name__)


def _publish_activity(src: str, msg: str) -> None:
    import datetime
    n = datetime.datetime.now()
    BUS.publish({
        "type": "activity",
        "entry": {
            "id": uuid.uuid4().hex[:8],
            "src": src,
            "msg": msg,
            "ts": f"{n.hour:02d}:{n.minute:02d}:{n.second:02d}",
        },
    })


# voice → conv state mapping. the VoiceController uses richer states
# (WAKE_DETECTED, FOLLOWUP, etc.) but the UI only cares about the five
# convstate values. anything else falls back to 'idle'.
_VOICE_TO_CONV = {
    "IDLE_DISABLED": "standby",
    "IDLE_LISTENING": "idle",
    "WAKE_DETECTED": "listening",
    "LISTENING": "listening",
    "TRANSCRIBING": "listening",
    "THINKING": "thinking",
    "SPEAKING": "speaking",
    "FOLLOWUP": "listening",
    "FAILED": "standby",
}

# states during which the user is talking to gemma and the system audio
# should duck (background music / video) so the mic doesn't pick it up.
# we explicitly EXCLUDE speaking — that's gemma talking back, and the
# anti-echo in the controller already filters mic during it.
# we also EXCLUDE wake_detected: that's a 200ms window before listening
# starts, and reconfiguring the system volume during it caused windows
# audio routing to glitch and the mic to drop the first phoneme.
_DUCK_STATES = {"LISTENING", "TRANSCRIBING", "FOLLOWUP"}

# the system volume Gemma drops to while the user is talking. 15% is loud
# enough to keep music audible to the user but quiet enough that the mic
# doesn't capture it as background. constant — could be config later.
_DUCK_LEVEL = 0.15


class _AudioDucker:
    """Save the host's master volume on entry to LISTENING-like states and
    restore it when we leave them. Works via pycaw's IAudioEndpointVolume
    on Windows; on platforms where pycaw isn't available, all operations
    are no-ops so voice still works without the ducking feature.

    All pycaw / COM work runs on a dedicated worker thread. duck() and
    restore() just enqueue an intent and return immediately — this matters
    because the voice controller calls them from inside its state-change
    callback, which itself runs on the PortAudio capture thread. Blocking
    that thread on COM initialization and IAudioEndpointVolume calls would
    glitch the mic right when the user starts talking, which was the
    original 'mic stopped working' regression."""

    def __init__(self) -> None:
        self._saved_level: float | None = None
        self._intent_q: "queue.Queue[str]" = queue.Queue(maxsize=8)
        self._stop = threading.Event()
        # the worker stays daemon so it dies with the process. it gets
        # spun up lazily on first duck()/restore() so unit tests that
        # never duck don't leak a thread.
        self._worker: threading.Thread | None = None
        self._worker_lock = threading.Lock()
        # cached endpoint on the worker thread only — never touched from
        # outside. resolving it once avoids re-doing CoInitialize+Activate
        # on every state change.
        self._ep: Any = None
        self._ep_resolved = False

    def _ensure_worker(self) -> None:
        with self._worker_lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(
                target=self._run, name="AudioDucker", daemon=True,
            )
            self._worker.start()

    def _run(self) -> None:
        """Worker loop: drain intents, never block the producer."""
        # COM must be initialized on this thread before any pycaw call.
        # MTA (multi-threaded apartment) is the right model for a
        # background worker; STA would require a message pump we don't run.
        try:
            import pythoncom  # type: ignore[import-not-found]
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        except Exception as exc:
            logger.debug("audio ducker CoInitialize skipped: %s", exc)
        try:
            while not self._stop.is_set():
                try:
                    intent = self._intent_q.get(timeout=0.5)
                except queue.Empty:
                    continue
                if intent == "duck":
                    self._do_duck()
                elif intent == "restore":
                    self._do_restore()
        finally:
            try:
                import pythoncom  # type: ignore[import-not-found]
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def _endpoint(self) -> Any | None:
        """Resolve the master IAudioEndpointVolume COM pointer.
        Returns None if pycaw is missing or no device is available — the
        caller treats that as 'ducking disabled, carry on'.

        Only ever called from the worker thread."""
        if self._ep_resolved:
            return self._ep
        self._ep_resolved = True
        try:
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL  # type: ignore[import-not-found]
            from pycaw.pycaw import (  # type: ignore[import-not-found]
                AudioUtilities, IAudioEndpointVolume,
            )
        except Exception:
            self._ep = None
            return None
        try:
            device: Any = AudioUtilities.GetSpeakers()
            if device is None:
                self._ep = None
                return None
            if hasattr(device, "EndpointVolume"):
                self._ep = device.EndpointVolume
                return self._ep
            iface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self._ep = cast(iface, POINTER(IAudioEndpointVolume))
            return self._ep
        except Exception as exc:
            logger.debug("audio endpoint resolve failed: %s", exc)
            self._ep = None
            return None

    def _do_duck(self) -> None:
        if self._saved_level is not None:
            return  # already ducked
        ep = self._endpoint()
        if ep is None:
            return
        try:
            cur = float(ep.GetMasterVolumeLevelScalar())
            if cur <= _DUCK_LEVEL + 0.01:
                # user already at or below target — don't fight them.
                return
            self._saved_level = cur
            ep.SetMasterVolumeLevelScalar(_DUCK_LEVEL, None)
            logger.info("audio ducked %.2f -> %.2f", cur, _DUCK_LEVEL)
        except Exception as exc:
            logger.debug("audio duck failed: %s", exc)

    def _do_restore(self) -> None:
        if self._saved_level is None:
            return
        target = self._saved_level
        self._saved_level = None
        ep = self._endpoint()
        if ep is None:
            return
        try:
            ep.SetMasterVolumeLevelScalar(target, None)
            logger.info("audio restored to %.2f", target)
        except Exception as exc:
            logger.debug("audio restore failed: %s", exc)

    def duck(self) -> None:
        """Enqueue a duck intent. Non-blocking, safe from audio callback."""
        self._ensure_worker()
        try:
            self._intent_q.put_nowait("duck")
        except queue.Full:
            logger.debug("audio ducker queue full; dropping duck intent")

    def restore(self) -> None:
        """Enqueue a restore intent. Non-blocking, safe from audio callback."""
        self._ensure_worker()
        try:
            self._intent_q.put_nowait("restore")
        except queue.Full:
            logger.debug("audio ducker queue full; dropping restore intent")


class VoiceRunner:
    """Long-lived owner of a single VoiceController.

    The controller stays None until `enable()` is called for the first time —
    that way the import of pyaudio/numpy/onnxruntime only happens if voice
    is actually requested. Disabling unloads the models too.
    """

    def __init__(self) -> None:
        self._controller: Any = None
        self._lock = threading.Lock()
        # the AgentRunner instance that should receive each final transcript.
        # set lazily on the first enable() call so we don't import circularly.
        self._agent_submit: Any = None
        # ducks system audio while the user is talking to gemma.
        self._ducker = _AudioDucker()
        # tracks whether the in-flight turn was triggered by voice. when the
        # user types in the chat, gemma still streams TTS through the voice
        # controller (so wake-word echo protection works), but we don't want
        # to lower the system volume — the user isn't speaking, there's no
        # mic capture to protect. set to True on `_on_final` (mic path) and
        # cleared once the controller returns to IDLE_LISTENING.
        self._voice_originated = False

    def is_running(self) -> bool:
        c = self._controller
        if c is None:
            return False
        try:
            st = c.state()
        except Exception:
            return False
        return st not in {"IDLE_DISABLED", "FAILED"}

    def status(self) -> dict[str, Any]:
        c = self._controller
        if c is None:
            return {"running": False, "state": "IDLE_DISABLED", "failed": []}
        try:
            st = c.state()
            failed = list(c.get_failed_components())
        except Exception as exc:
            return {"running": False, "state": "FAILED", "failed": [str(exc)]}
        return {
            "running": st not in {"IDLE_DISABLED", "FAILED"},
            "state": st,
            "failed": failed,
        }

    def feed_tts(self, content: str) -> None:
        """Called by AgentRunner when a turn produces a reply. Speaks it
        if voice is active. No-op when voice is off."""
        c = self._controller
        if c is None or not content:
            return
        try:
            c.begin_tts()
            c.feed_tts_chunk(content)
            c.end_tts()
        except Exception as exc:
            logger.warning("voice TTS dispatch failed: %s", exc)

    def enable(self) -> bool:
        """Load models + start audio. Blocking 1-3s on first call.
        Returns True if the controller is in IDLE_LISTENING after."""
        with self._lock:
            if self._controller is not None and self.is_running():
                return True

            _publish_activity("SYSTEM", "voice · levantándose (vosk + whisper + piper)…")
            emit_stage(BUS.publish, "voice_loading",
                       "loading voice stack · vosk + whisper + piper")

            try:
                from .voice.controller import VoiceController
            except Exception as exc:
                _publish_activity("SYSTEM", f"voice unavailable · {exc}")
                emit_stage(BUS.publish, "voice_loading",
                           f"voice import failed: {exc}", error=str(exc))
                return False

            # bind on_final to the agent runner so transcribed speech enters
            # the normal turn pipeline (same as if you typed it).
            if self._agent_submit is None:
                from .agent_runner import RUNNER
                self._agent_submit = RUNNER.submit

            def _on_state(s: str) -> None:
                conv = _VOICE_TO_CONV.get(s, "idle")
                BUS.publish({"type": "state", "value": conv})
                # the duck-flag only applies when the active turn was kicked
                # off by the mic. text-chat turns reuse the same controller
                # for TTS echo protection, but lowering the system volume
                # for them would surprise the user — there's no mic capture
                # to protect.
                if s == "IDLE_LISTENING":
                    # turn cycle ended — clear the flag so the next turn
                    # starts fresh and an explicit voice path can re-arm it.
                    self._voice_originated = False
                elif s in {"WAKE_DETECTED", "LISTENING"}:
                    # mic capture is active → this is definitively a voice
                    # turn. set the flag so the duck kicks in immediately.
                    # text-chat turns never pass through these states (they
                    # jump straight from IDLE_LISTENING to SPEAKING via
                    # begin_tts), so this branch can't false-positive.
                    self._voice_originated = True
                # "call mode" — duck system audio while the user is talking
                # to gemma so the mic doesn't capture music/video as input.
                # we ALSO duck during THINKING because the user might still
                # have audio playing while the agent processes. SPEAKING is
                # intentionally excluded — that's gemma talking back, the
                # user wants to hear it at normal volume.
                if self._voice_originated and (s in _DUCK_STATES or s == "THINKING"):
                    self._ducker.duck()
                else:
                    self._ducker.restore()

            def _on_partial(text: str) -> None:
                # partials change fast; we don't spam the activity log. the
                # state already reflects 'listening'. nothing else to do.
                _ = text

            def _on_final(text: str) -> None:
                text = (text or "").strip()
                if not text:
                    return
                # this turn was triggered by the mic — keep the audio ducked
                # until the controller returns to IDLE_LISTENING so the user
                # isn't blasted by background music while gemma replies.
                self._voice_originated = True
                # the AgentRunner will push its own YOU entry, so we skip it here.
                try:
                    self._agent_submit(text)
                except Exception as exc:
                    _publish_activity("SYSTEM", f"voice → agent dispatch failed: {exc}")

            def _on_failed(reason: str) -> None:
                _publish_activity("SYSTEM", f"voice failed · {reason}")

            try:
                self._controller = VoiceController(
                    on_state=_on_state,
                    on_partial=_on_partial,
                    on_final=_on_final,
                    on_tts_chunk=None,
                    on_failed=_on_failed,
                )
            except Exception as exc:
                _publish_activity("SYSTEM", f"voice create failed · {exc}")
                self._controller = None
                return False

            try:
                ok = self._controller.enable()
            except Exception as exc:
                _publish_activity("SYSTEM", f"voice enable crashed · {exc}")
                return False

            if ok:
                _publish_activity("SYSTEM", "voice · levantado · decí 'gemma' o 'hey gemma'")
                emit_stage(BUS.publish, "voice_ready",
                           "voice ready · vosk + whisper + piper loaded",
                           progress=100.0)
                return True

            failed = self._controller.get_failed_components()
            if failed:
                _publish_activity("SYSTEM", f"voice partial · {', '.join(failed)}")
                emit_stage(BUS.publish, "voice_loading",
                           f"voice partial · {', '.join(failed)}",
                           error=", ".join(failed))
            else:
                _publish_activity("SYSTEM", "voice enable failed")
                emit_stage(BUS.publish, "voice_loading",
                           "voice enable failed",
                           error="enable returned False")
            return False

    def disable(self) -> None:
        with self._lock:
            if self._controller is None:
                return
            try:
                self._controller.disable()
            except Exception as exc:
                logger.warning("voice disable error: %s", exc)
            # if we ducked the system audio and the user shuts voice down
            # mid-listening, leaving it ducked would frustrate them. restore.
            self._ducker.restore()
            _publish_activity("SYSTEM", "voice · apagado")

    def trigger_manual(self) -> None:
        """Push-to-talk: simulate a wake event without saying the wake word.
        No-op if voice isn't loaded."""
        c = self._controller
        if c is None:
            return
        # mark the turn as voice-originated up front so the ducker activates
        # as soon as LISTENING begins — without this we'd only flip the flag
        # at `_on_final` and miss the duck during the user's actual speech.
        self._voice_originated = True
        try:
            c.trigger_manual()
        except Exception as exc:
            logger.warning("voice trigger_manual error: %s", exc)


VOICE = VoiceRunner()
