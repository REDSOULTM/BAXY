# VOICE_CAMERA_HANDOFF_PLAN — Carter v2 (post-text RC)

The text core is frozen as Release Candidate. Voice, microphone, camera and
real-time vision are **future layers on top of the same core**. This document
defines the contract so future work cannot rewrite the engine.

---

## 1. Hard rules for the future layers

- **DO NOT** add hotword/wake-word detection to the core.
- **DO NOT** add an always-on microphone loop in `runtime/` or `session/`.
- **DO NOT** add an always-on camera capture loop anywhere.
- **DO NOT** add real-time vision streaming inside the turn flow.
- **DO NOT** introduce model-name string literals into voice/camera modules
  (use [src/carter_v2/models/model_registry.py](src/carter_v2/models/model_registry.py)).
- **DO NOT** bypass [src/carter_v2/session/policy.py](src/carter_v2/session/policy.py).
  Every camera frame, every transcription, every spoken reply is a *tool call*
  subject to the same risk gate.

## 2. Required interfaces (to be implemented later)

These will live in a sibling package, e.g. `src/carter_v2/io_voice/` and
`src/carter_v2/io_vision/`. They MUST expose only these functions to the core:

```python
# Speech-to-text (push-to-talk only, NOT continuous).
def transcribe(audio_bytes: bytes, *, language: str | None = None) -> str: ...

# Text-to-speech (synchronous, returns wav bytes; no autoplay in core).
def speak(text: str, *, voice: str | None = None) -> bytes: ...

# One-shot screen / camera observation (NOT a stream).
def observe_screen(*, region: tuple[int, int, int, int] | None = None) -> str: ...
def observe_camera(*, max_seconds: float = 1.0) -> str: ...
```

The core integration is exactly one line per modality:

```python
text = transcribe(audio_bytes)               # mic → text
reply = engine.submit_text_turn(text)        # SAME core entry point
audio = speak(reply)                          # text → audio
```

## 3. Lifecycle

- Mic capture starts on user action (button / keypress) and stops when the
  user releases or after a timeout. Never spontaneously.
- Camera capture is a *single frame* requested by a tool call. Never a stream.
- All audio/video buffers are discarded after the turn completes. They are
  **not** persisted in `PersistentMemory`.

## 4. Safety additions for future layers

- New risk categories in [src/carter_v2/session/policy.py](src/carter_v2/session/policy.py):
  `mic_capture`, `camera_capture`, `speak_aloud`. All default to dry-run unless
  the user explicitly enabled them.
- New telemetry counters in the gate JSON: `mic_capture_count`,
  `camera_capture_count`, `tts_count`. Must remain `0` in pure-text RC runs.

## 5. What the future test plan must include

- Voice round-trip latency budget (push-to-talk → reply → audio).
- Camera observation budget (one frame → text description).
- Re-run of the text invariants in [TEXT_CORE_INVARIANTS.md](TEXT_CORE_INVARIANTS.md)
  to prove the new layers did not regress the core.

If any of the rules above are violated, the voice/camera layer is rejected and
the text RC is restored as the rollback baseline.
