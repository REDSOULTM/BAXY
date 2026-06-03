# Sprint 7 — Log (post-external-audit actions)

- **Started:** 2026-05-17
- **Finished:** 2026-05-17 (same session)
- **Operator:** Claude Code (Opus 4.7)
- **Base commit:** 6447032 `docs(sprint_prompts): add Sprint 7 …`
- **Final code commit:** 3908aff `sprint7.7: analyze_traces.py — % of turns …`
- **Net delta vs base:** 12 files changed, **+977 LOC**
- **`COMPOUND_TOOL_SCHEMAS`:** 65 → 65 (unchanged)
- **Suite total:** 759 passed, 1 pre-existing failure (same as Sprint 3a).

## Headline

All 7 actions from the external audit landed in 7 small commits. Three
add instrumentation (voice latency, prompt size, % of turns), two add
maintenance hygiene (state TTL, traces rotation), one closes a
silent-failure hazard (experience schema fail-loud), and two are docs
(barge-in design for Sprint 8, crash recovery already-existing).

## 7.1 — Instrument voice_e2e_latency + prompt_built — commit `2af6e0c` ✅

Two telemetry events added.

**(A) `voice_e2e_latency` (BUS event):**
- `voice/controller.py.__init__`: new `self._wake_ts: float | None = None`.
- `_on_wake_detected`: stamps `time.monotonic()`.
- `begin_tts`: emits the BUS event once per turn with `elapsed_ms` +
  `phase: wake_to_first_speak`, then resets `_wake_ts`. Lazy BUS
  import to avoid coupling voice/ to events_bus at module-load time.

**(B) `prompt_built` (trace event):**
- `agent.py.run_content`: emitted once per turn before the retry
  for-loop. Carries `system_chars`, `schemas_chars`, `history_chars`,
  `total_chars`, `estimated_tokens` (chars/4), `schemas_count`.
- Try/except so telemetry never breaks a turn.

**Smoke test (mock LLM):**
- `system_chars=15989`, `schemas_chars=1517`, `estimated_tokens=4377`
  — well under the 6000-token target the audit set.

## 7.2 — TTL real en `state.json` — commit `320d792` ✅ (closes baseline §2.3)

`state.py`:
- New `AgentState.purge_stale_closed(max_age_days=7)`. Drops closed
  resources older than the cutoff, drops legacy closed (no
  `closed_at`), drops malformed `closed_at`. **Never** touches open
  resources. Tz-aware comparison.
- `mark_cleaned` already wrote `closed_at` (no change there).

`agent.py.__init__`:
- After `self.trace = TraceLogger(…)`, run `purge_stale_closed(7)`
  wrapped in `try/except`. Emits `state_purge` trace event when
  anything actually got dropped.

**Tests (`test_state_purge.py`, 8 tests):** all combinations of
status/timestamp/age plus an idempotency + persists-to-disk check.

## 7.3 — Rotation in `TraceLogger` — commit `90a6447` ✅

`tracing.py`:
- Dataclass fields `max_size_mb=50`, `keep_files=3`, `_event_counter`
  (internal throttle).
- `__post_init__` rotates on startup so a previous-session oversized
  file rolls over cleanly.
- `event()` bumps the counter; every `ROTATE_CHECK_EVERY=100` events
  it re-checks file size.
- `_maybe_rotate()`: cascade scheme — active → `.1`, `.1` → `.2`, …,
  `.keep_files` → discarded. Defensive: any IO error is swallowed.
- `_rotated_path(N)` appends `.N` to the **full** filename so
  `traces.jsonl` becomes `traces.jsonl.1` (not `traces.1`),
  preserving the format hint.

**Tests (`test_tracing_rotation.py`, 6 tests):** under-limit no-op,
over-limit rotation, cascade pushes existing archives, oldest
archive discarded, IO failure path swallowed, throttle correctness.

## 7.4 — Fail-loud `experience.sqlite` schema check — commit `89f2cae` ✅

`experience.py._open`: after the `ALTER TABLE … ADD COLUMN` loop
that's wrapped in `try/except sqlite3.OperationalError: pass`,
`PRAGMA table_info(experiences)` and assert all five provenance
columns are present. If any missing → `RuntimeError` with a
remediation message mentioning antivirus / OneDrive / Dropbox sync
as the typical lock culprits and the DB path.

**Tests (`test_experience_schema_drift.py`, 3 tests):**
- Fresh DB: all 5 columns exist.
- Pre-migration DB (7 base columns only): ALTERs add the 5 missing,
  no fail.
- Simulated ALTER-swallowed bug (wrapper Connection raises on every
  ALTER): `RuntimeError` mentions "missing columns" + "antivirus" +
  the path.

Skips cleanly if `sqlite_vec` isn't installed.

## 7.5 — Barge-in design doc — commit `f2abbc5` ✅ (no production code)

New file: `docs/architecture/design/barge_in.md` (258 LOC). Captures:

1. Current state: `voice/controller.py:357` drops audio in SPEAKING
   unconditionally; user cannot interrupt.
2. Proposed design: chunk-level Silero VAD inside SPEAKING with a
   500 ms sustained-voice threshold; on trigger, `_tts.stop()` +
   `_set_state(LISTENING)` + BUS event.
3. Risks: self-trigger from TTS echo (mitigated by existing
   `_AudioDucker`), ambient noise (mitigated by 500 ms sustained
   threshold), race with `begin_tts` (defensive `_wake_ts = None`).
4. Conservative variant: re-require wake word during the trigger
   window — "say gemma to interrupt" instead of "say anything".
5. Implementation plan: ~50 LOC production + ~150 LOC tests, Sprint
   8 estimate half a day.
6. Test plan: 5 tests covering threshold, silence-resets-counter,
   other-states-don't-fire, BUS event shape, etc.

No production code touched in Sprint 7.

## 7.6 — Crash recovery doc — commit `535cdbb` ✅ (no production code)

`docs/architecture/01_delta_system.md`: appended §6 with five
subsections documenting what the audit thought was missing but
already exists:

- 6.1 `detect_crash_signature()` (CUDA / OOM pattern matching in
  `err.log`).
- 6.2 `recycle_for_vision_leak()` (auto-restart after
  `IMAGE_RELAUNCH_THRESHOLD` images; wired in
  `agent_runner._build_agent`).
- 6.3 `restart(profile)` (used by `profile_watcher` on VRAM-aware
  profile changes).
- 6.4 What does NOT exist: auto-restart **mid-turn** (current turn
  is lost; next turn autostart recovers); no periodic health probe
  during long turns.
- 6.5 Gaps for Sprint 8+: mid-turn auto-restart, periodic health
  probe, crash metrics.

## 7.7 — `analyze_traces.py` % of turns + recommendation — commit `3908aff` ✅

`scripts/analyze_traces.py`:
- New helpers `_pct_of_turns()` and `_usage_recommendation()`.
  Thresholds: `<1%` candidate to delete, `1-5%` review, `≥5%` keep.
- `total_turns` lifted to the section-shared scope (was inline).
- Section B (Personas): added "% of turns" + "recommendation"
  columns; zero-usage personas explicitly flagged.
- Section C.1/C.2 (Microagents + Skills): same treatment.
- Section D.2 (Tools suggested by classifier): "% of turns" column.

Re-running the analyzer regenerates `_sprint2_usage_report.md` —
included in the commit so the canonical report shows the new shape.

## Final verifications

```
$ python -c "import gemma4_agent": OK
$ python -c "from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"
65

$ python -m gemma4_agent.launcher status   # runs cleanly

$ python -m pytest test_state_purge.py test_tracing_rotation.py \
                   test_experience_schema_drift.py -q
17 passed in 0.41s

$ python -m pytest gemma4_agent/ -q --tb=no
759 passed, 1 failed in 48.08s
```

The 1 remaining failure is the same pre-existing
`test_planner_continuation.test_without_hint_short_reply_subset_empty`
that's been documented since Sprint 3a. Not introduced by this sprint.

## Recap of commits

```
2af6e0c sprint7.1: instrument voice_e2e_latency + prompt_built_tokens
320d792 sprint7.2: TTL real en state.json (purge_stale_closed + boot hook)
90a6447 sprint7.3: TraceLogger size-based rotation (50MB / 3 archives)
89f2cae sprint7.4: fail-loud schema check in experience.sqlite
f2abbc5 sprint7.5: barge-in design doc (Sprint 8 will implement)
535cdbb sprint7.6: document existing crash recovery in 01_delta_system.md
3908aff sprint7.7: analyze_traces.py — % of turns + recommendation columns
<this commit>
```

## LOC delta

| Change | LOC |
|---|--:|
| 7.1 controller + agent instrumentation | +65 |
| 7.2 state.py + agent hook + tests | +201 |
| 7.3 tracing.py + tests | +184 |
| 7.4 experience.py + tests | +164 |
| 7.5 barge_in.md (docs) | +258 |
| 7.6 01_delta_system.md (docs) | +65 |
| 7.7 analyze_traces.py + regenerated report | +41 net (113 ins, 72 del) |
| **Total** | **+977 LOC** |

## What's next

- **Sprint 3b** is the natural next step: now that the
  `% of turns` + `recommendation` columns are wired (7.7), one week
  of use will produce data to act on. The instrumentation from 7.1
  also lights up p50/p95 of voice latency and prompt tokens, which
  the audit flagged as the missing voice-first KPIs.

- **Sprint 8** (optional, when energy allows):
  - Implement barge-in per the design doc (7.5).
  - Mid-turn auto-restart of llama-server (7.6 §6.5).
  - Periodic health probe during long turns (7.6 §6.5).
  - The remaining hard refactor: extracting the dispatch pipeline
    from tools.py (the cycle complexity Sprint 6.6 deferred).

- **No new SKIPs** to track from Sprint 7: all 7 audit items are
  either implemented or have a concrete deferred-with-plan exit
  (barge-in → Sprint 8, crash recovery gaps → Sprint 8).
