# Design — voice barge-in

> Status: **DESIGN ONLY**. Implementation deferred to Sprint 8.
> Reviewer should validate before code lands.

The external post-plan audit flagged that the voice controller drops
audio while the agent is speaking, so the user cannot interrupt a
response by talking over it. This is a real UX gap for a voice-first
assistant. This document captures the proposed design so it can be
reviewed end-to-end before any code change.

---

## 1. Current state (cited from code)

- [`gemma4_agent/voice/controller.py:338`](../../../gemma4_agent/voice/controller.py)
  — `_on_audio_chunk` routes audio per state. After the `if/elif`
  branches for `IDLE_LISTENING` and `{WAKE_DETECTED, LISTENING,
  TRANSCRIBING, FOLLOWUP}`, the comment at line 357 admits:
  > `# En THINKING / SPEAKING / IDLE_DISABLED / FAILED ignoramos audio.`

- [`gemma4_agent/voice/controller.py:261`](../../../gemma4_agent/voice/controller.py)
  — `begin_tts` docstring explicitly notes `SPEAKING descarta audio
  entrante (ver _on_audio_chunk), asi que forzar la transicion aqui
  es el anti-echo natural del controller`. The intent was anti-echo,
  not feature design — but the result is the same: no interruption.

**Consequence for UX:**
1. User says "Baxy, cuenta hasta cien" → agent enters SPEAKING.
2. User says "Baxy, parate" → ignored. The user has to wait until
   the count finishes, then say it again.

For an assistant that markets itself as Jarvis-like / voice-first,
this is the single biggest UX gap remaining.

---

## 2. Proposed design

### 2.1 New SPEAKING-state audio handler

In `_on_audio_chunk`, replace the unconditional drop in `SPEAKING`
with a parallel cheap path:

```python
elif s == S_SPEAKING:
    if self._check_barge_in(chunk):
        self._trigger_barge_in()
```

`_check_barge_in(chunk)` runs a **chunk-level VAD** (not Whisper) —
Silero VAD is already a dependency and is fast enough to run
synchronously inside the audio callback (~5 ms / 30 ms chunk).
Whisper is too heavy.

### 2.2 Sustained-speech detector

A single voiced chunk is not enough — the TTS audio leaking back
through the mic would always pass the threshold. We need *sustained*
voiced activity:

```python
# State on the controller:
self._barge_voiced_run = 0    # # of consecutive voiced chunks in SPEAKING
self._barge_threshold_chunks = 17  # ~500 ms at 30 ms chunks

def _check_barge_in(self, chunk: np.ndarray) -> bool:
    is_voiced = self._silero_vad.is_speech(chunk)  # bool
    if is_voiced:
        self._barge_voiced_run += 1
    else:
        self._barge_voiced_run = 0
    return self._barge_voiced_run >= self._barge_threshold_chunks
```

500 ms is a deliberate compromise between false-positive resilience
(TV noise, a brief cough) and responsiveness (Jarvis-like feel
implies <800 ms). The threshold should be tunable via env
(`GEMMA4_BARGE_IN_THRESHOLD_MS`).

### 2.3 Trigger action

```python
def _trigger_barge_in(self) -> None:
    # 1. Stop the ongoing TTS immediately.
    self._tts.stop()

    # 2. Drop any pending TTS chunks the LLM may still be streaming.
    self._tts.reset()  # already exists for new turns

    # 3. Reset the barge counter so the next SPEAKING starts clean.
    self._barge_voiced_run = 0

    # 4. State transition: SPEAKING → LISTENING. Skips WAKE_DETECTED
    #    because the user is already mid-sentence; treat this as a
    #    direct continuation, not a fresh wake.
    self._set_state(S_LISTENING)

    # 5. Bus event so logs + metrics see it.
    try:
        from ..events_bus import BUS
        BUS.publish({
            "kind": "barge_in",
            "voiced_chunks": self._barge_voiced_run,
            "elapsed_ms": int(self._barge_threshold_chunks * 30),
        })
    except Exception:
        pass

    # 6. Side effect: the agent_runner / GUI receive the state change
    #    and abort any remaining LLM streaming (the existing
    #    cancel_turn semantics already cover this).
```

### 2.4 What `StreamingTTS.stop()` already does

[`voice/tts.py:211`](../../../gemma4_agent/voice/tts.py) already
defines `stop()` for the FOLLOWUP-window timeout case. It:
- Tells the Piper subprocess to drop the current utterance.
- Clears the internal text-chunk buffer.
- Resets the sentence-flush state.

So **no new TTS code is needed** for the interruption itself.

---

## 3. Risks

### 3.1 TTS audio echo (self-trigger)

If Piper's output bleeds into the mic, the VAD will see voiced audio
and barge-in will trigger on the agent's own speech. The existing
`_AudioDucker` in `voice_runner.py:71` lowers system input volume
during SPEAKING, but on noisy mics or speakers placed near the mic
the leak is still measurable.

**Mitigations to apply during 2.x implementation:**
- Require the `_AudioDucker` to be active during SPEAKING (already is)
  and bump its attenuation when barge-in is enabled.
- Run a **wake-word pre-check** on the suspected barge-in chunk: if
  Vosk doesn't detect "baxy" in the 500 ms post-trigger, treat as
  echo and abort the barge-in. More conservative; sacrifices the
  "just talk to interrupt" UX for "say Baxy to interrupt".
- Cancellation echo: pycaw supports AEC on some Windows audio
  devices. Out of scope for Sprint 8 first cut; flagged for Sprint 9.

### 3.2 Ambient noise (TV, dog, traffic)

500 ms sustained ≈ "someone talking near the mic, not a one-off
sound". With Silero VAD's threshold tuned conservatively
(default 0.5; consider 0.6 for SPEAKING-state), the false-positive
rate from typical room noise should be low.

**Mitigations:**
- Bus event ships `voiced_chunks` so we can tune the threshold from
  real data after a week of use.
- Optional: rate-limit barge-in to "no more than once per N seconds"
  so a chatty environment can't infinite-cycle the agent.

### 3.3 Race condition with `begin_tts` follow-up

`begin_tts` is what emits the `voice_e2e_latency` event from
Sprint 7.1. If the user barges in BEFORE the first phoneme,
`_wake_ts` is still set; we should clear it so the next turn doesn't
double-count.

**Mitigation:** `_trigger_barge_in` calls `self._wake_ts = None`
defensively.

---

## 4. Conservative variant (optional)

If false positives during early roll-out are unacceptable, add a
secondary "wake word check" gate:

```python
def _check_barge_in(self, chunk):
    is_voiced = self._silero_vad.is_speech(chunk)
    if is_voiced:
        self._barge_voiced_run += 1
        if self._barge_voiced_run >= self._barge_threshold_chunks:
            # Conservative gate: require the user say "baxy" again.
            # This costs one extra Vosk hit per detected sustained voice.
            wake_text = self._wake.check_recent(seconds=0.5)
            if "baxy" not in wake_text.lower():
                self._barge_voiced_run = 0
                return False
            return True
    else:
        self._barge_voiced_run = 0
    return False
```

This is "say Baxy to interrupt" instead of "say anything to
interrupt". Worth A/B testing in Sprint 8 once both paths are wired.

---

## 5. Plan of implementation (Sprint 8)

| Step | File | Change | LOC |
|---|---|---|---|
| 1 | `voice/controller.py` | New `_check_barge_in` + `_trigger_barge_in` | ~30 |
| 2 | `voice/controller.py` | Replace SPEAKING-drop in `_on_audio_chunk` | ~5 |
| 3 | `voice/controller.py` | `__init__`: counter + threshold config | ~5 |
| 4 | `voice/controller.py` | Reset on `_set_state` transition out of SPEAKING | ~3 |
| 5 | `voice/tts.py` | Confirm `stop()` is idempotent (likely already is) | 0 |
| 6 | `voice_runner.py` | Bump ducker attenuation while barge-in armed | ~5 |
| 7 | `test_voice_barge_in.py` | NEW. 5 tests: see §6 | ~150 |

**Estimate:** ~50 LOC production + ~150 LOC tests = Sprint 8 budget
of half a day. Risk: Medium (UX-facing, false-positive on noisy
mics).

---

## 6. Tests planned for Sprint 8

`test_voice_barge_in.py`:

1. `test_no_barge_in_when_under_threshold` — feed N-1 voiced chunks
   in SPEAKING; assert `state == SPEAKING`, TTS not stopped.
2. `test_barge_in_fires_at_threshold` — feed N voiced chunks in
   SPEAKING; assert `state == LISTENING`, `_tts.stop()` was called.
3. `test_silence_resets_counter` — interleave voiced/silent;
   counter resets, no trigger.
4. `test_does_not_fire_in_other_states` — voiced chunks in
   IDLE_LISTENING / LISTENING / etc. — no `barge_in` event.
5. `test_bus_event_shape` — when triggered, BUS gets
   `{"kind": "barge_in", "voiced_chunks": int, "elapsed_ms": int}`.

The conservative-variant tests (§4) are added if we decide to ship
both modes.

---

## 7. Acceptance criteria for Sprint 8

- All 5 tests above green.
- Manual smoke: in a quiet room, user can say "Baxy, parate" mid-TTS
  and the agent stops within 800 ms.
- No regression: `test_voice_state_machine_*` in
  `test_gx_features.py` still green (the SPEAKING transition contract
  is preserved).
- BUS event visible in `traces.jsonl` after a real barge-in.

---

## 8. Decisions deferred to Sprint 8 implementation

- Threshold env name: `GEMMA4_BARGE_IN_THRESHOLD_MS` vs
  `GEMMA4_VOICE_BARGE_MS`. Pick one.
- Default: aggressive (any sustained voice) or conservative (re-wake
  required). Recommended: aggressive default, conservative as opt-in.
- Whether to merge `_AudioDucker` attenuation bump into the same
  patch or a follow-up. Recommended: same patch, since they together
  define the practical false-positive rate.
