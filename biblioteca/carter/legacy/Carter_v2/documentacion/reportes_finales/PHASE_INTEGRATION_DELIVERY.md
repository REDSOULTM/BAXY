# Carter v2 — Master Integration Delivery Report

Stage 2 reconciliation + safe-phase implementation of the unified plan
(Auditoría 30/04 by Claude Opus 4.7 + my prior Carter v2 audit).

All work landed on this branch with **1481 tests passing** after every phase.

---

## Phase status (O0 → O11)

| Phase | Title                                  | Status            |
|------:|----------------------------------------|-------------------|
| 0     | Reconcile both audits                  | DONE              |
| 1     | TURN_TRACE timing                      | DONE              |
| 2     | A11 multilingual identity fix          | DONE              |
| 3     | Reduce extra LLM calls                 | DONE              |
| 4     | Probe cache TTL                        | DONE              |
| 5     | MEMORY.md sanitization + hardening     | DONE              |
| 6     | run_carter_gpu.ps1 vision/chat split   | DONE              |
| 7     | Tool catalog gating                    | SATISFIED by P2   |
| 8     | ES/EN hardcode reduction               | DEFERRED (risky)  |
| 9     | Honesty / prior-turn evidence          | ALREADY IN PLACE  |
| 10    | A11 + memory tests + latency           | DONE              |
| 11    | Safe debt — A3 json.loads              | DONE; A8/A9 deferred |

---

## A1–A11 mapping

| ID  | Symptom                                          | Resolution                                                                                    |
|-----|--------------------------------------------------|-----------------------------------------------------------------------------------------------|
| A1  | No `turn_trace` per-stage timing                 | Phase 1: `_timing` block, `CARTER_TIMING=1` print, `pre_stage_timings` from engine            |
| A2  | Probe snapshot rebuilt every turn                | Phase 4: `_DEFAULT_TTL=300s`, `CARTER_PROBE_TTL` env                                          |
| A3  | `json.loads` on tool args could crash turn       | Phase 11: try/except, falls back to `{"__raw__":..., "__parse_error__":True}`                 |
| A4  | Memory lock contention                           | Already shared via `RLock`; verified in Phase 5 read-through (`proactive.promote_recent`)     |
| A5  | SQLite WAL/busy_timeout                          | Confirmed `journal_mode=WAL`, `busy_timeout=3000`                                             |
| A6  | Backend re-init                                  | Singleton in `_auto_backend()`, confirmed                                                     |
| A7  | Up to 25 tool iterations / extra retry loops     | Phase 3: `MAX_TOOL_ITERATIONS=8` + `not hint_no_tools` gate on personal-memory retry          |
| A8  | Username from `Path.home().name`                 | Already centralised in `CarterSettings`; full migration to settings-only deferred             |
| A9  | Bare `except Exception: pass`                    | DEFERRED — too broad; tracked in repo memory                                                  |
| A10 | Vision models ran as chat                        | Phase 6: split env vars, removed inheritance                                                  |
| A11 | Identity questions misrouted (multilingual)      | Phase 2: extended `_GREETING_TOKENS`, removed wrong `hint_no_tools` gate, strengthened `system_get_time` |

---

## Files modified

### Source
- [Carter_v2/src/carter_v2/config.py](Carter_v2/src/carter_v2/config.py) — `timing: bool` + `CARTER_TIMING` env.
- [Carter_v2/src/carter_v2/turn/agent.py](Carter_v2/src/carter_v2/turn/agent.py) — `import time`; `pre_stage_timings` kwarg; `_timing` block; LLM/tool timing wrappers; `_emit_turn_timing`; identity guard always runs; `MAX_TOOL_ITERATIONS=8`; personal-memory retry gated by `not hint_no_tools`; `_timing.retry_reason`; A3 json.loads guard.
- [Carter_v2/src/carter_v2/turn/engine.py](Carter_v2/src/carter_v2/turn/engine.py) — measures `probe_ms` + `ctx_window_ms`, forwards `pre_stage_timings`.
- [Carter_v2/src/carter_v2/turn/brain_router.py](Carter_v2/src/carter_v2/turn/brain_router.py) — extended `_GREETING_TOKENS` cross-lingually.
- [Carter_v2/src/carter_v2/adapters/tools.py](Carter_v2/src/carter_v2/adapters/tools.py) — strengthened `system_get_time` description (full + compact).
- [Carter_v2/src/carter_v2/capabilities/probe.py](Carter_v2/src/carter_v2/capabilities/probe.py) — `_DEFAULT_TTL=300`, `CARTER_PROBE_TTL` env.
- [Carter_v2/src/carter_v2/session/memory.py](Carter_v2/src/carter_v2/session/memory.py) — `_PROMOTION_BLOCKLIST`, `_is_promotable_candidate` blocklist check, hardened `set_user_name`, defense-in-depth in `remember()`.

### Scripts
- [run_carter_gpu.ps1](run_carter_gpu.ps1) — vision/chat env split; explicit `Remove-Item Env:CARTER_LLM_*`.

### Tests added
- [Carter_v2/tests/test_a11_multilang_identity.py](Carter_v2/tests/test_a11_multilang_identity.py) — 37 cases.
- [Carter_v2/tests/test_phase5_memory_hardening.py](Carter_v2/tests/test_phase5_memory_hardening.py) — 18 cases.
- [Carter_v2/tests/test_agent_turn_trace.py](Carter_v2/tests/test_agent_turn_trace.py) — added `test_agent_turn_trace_records_timing`.
- [Carter_v2/tests/test_brain_router_fase7.py](Carter_v2/tests/test_brain_router_fase7.py) — `TestBrainRouterIdentity` updated to encode A11 fix.

### Data sanitised
- [Carter_v2/MEMORY.md](Carter_v2/MEMORY.md) — only legitimate user facts kept (`favorite_color: azul`, `name: Emmanuel`).
- `Carter_v2/MEMORY.md.bak.20260430-190222` — full backup of original 13-entry contaminated file.

---

## Before / after — performance signals

(Pre-existing audit numbers vs structural changes here. Real wall-clock will land
once `CARTER_TIMING=1` runs against the live model; structurally, the savings are:)

| Metric                          | Before                            | After                                              |
|---------------------------------|-----------------------------------|----------------------------------------------------|
| Probe rebuild per turn          | every call (~50 ms each)          | cached 300 s / `CARTER_PROBE_TTL`                  |
| Tool iteration cap              | 25                                | 8                                                  |
| Identity question LLM calls     | 1 LLM + N tool retries (drift)    | 1 LLM, 0 tools (`hint_no_tools=True` first pass)   |
| Per-turn timing visibility      | none                              | `turn_trace["_timing"]` always populated           |
| Vision-model-as-chat risk       | latent (active if api_key set)    | impossible (vars removed + isolated)               |

---

## Residual risks

1. **Phase 8 not done** — `_LIVE_QUERY_MARKERS`, `_PERSONAL_MEMORY_PHRASES`,
   `_PERSONAL_MEMORY_QUERY_MARKERS`, `_ACTION_QUESTION_PREFIXES` in
   [agent.py](Carter_v2/src/carter_v2/turn/agent.py#L885) and `_CALENDAR_INTENTS`
   in `invariants.py` still hold ES/EN keyword lists that bypass routing logic.
   Removing them risks regressing dozens of contract tests; needs a dedicated session.
2. **A8 username** — already centralised in `CarterSettings`, but a full sweep for
   any leftover `os.getlogin()` / `Path.home().name` usage was not performed.
3. **A9 bare excepts** — broad cleanup deferred; current ones swallow recoverable
   errors silently.
4. **Prompt diet + `cache_prompt`** (Claude's Phase 4 extra) — deferred.
5. **`set_user_name` "qué hora es" edge** — bare interrogative without `?` cannot
   be rejected purely structurally; documented in the test file.

---

## Smoke list — run with `run_carter_gpu.ps1`

After launching, verify:

1. **A11 identity** — type `quien eres`, `who are you`, `qui es-tu`, `wer bist du`,
   `chi sei`. Expected: each → 1 LLM call, 0 tools, no time/calendar tool drift.
   With `CARTER_TIMING=1`, `[turn_trace]` should show `tool_calls_made=[]`.
2. **Time path** — `que hora es`. Expected: `system_get_time` called exactly once,
   answered without follow-up LLM call (it's in `DIRECT_ACTION_TOOL_NAMES`).
3. **Probe cache** — three turns in a row without restart: second/third should show
   `probe_ms ≈ 0`.
4. **Memory hygiene** — open [Carter_v2/MEMORY.md](Carter_v2/MEMORY.md). After a
   probe-only session, no `carter_probe_*` / `probe-event-*` lines should appear.
5. **Vision split** — `Get-ChildItem Env:CARTER_LLM_*` after running the script
   should return nothing; `CARTER_VISION_LLM_*` should be set.
6. **Iteration cap** — ask Carter to run an unproductive long tool chain;
   it should bail out at iteration 8 (was 25).
7. **Set/get name** — `mi nombre es Emmanuel` → `MEMORY.md` gets exactly one
   `name: Emmanuel` line; `como me llamo` answers from memory in 1 LLM call.
8. **No vision-as-chat regression** — Carter should never reply with llava
   describing its own prompt; only screenshot tools route to vision.
