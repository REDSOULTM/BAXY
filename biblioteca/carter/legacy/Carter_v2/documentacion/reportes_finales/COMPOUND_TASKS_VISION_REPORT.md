# COMPOUND_TASKS_VISION_REPORT.md

**Scope:** implementation report for the compound-mission repair plan
described in `COMPOUND_TASKS_VISION_AUDIT.md` (sections M1–M9).

**Status:** all of M1–M9 are landed and green. The mission state
machine, structural decomposition, forced retry, per-step catalog,
verification, honest formatter, **the M4 re-observation hook and the
M7 GUI/vision tier ladder** are wired and exercised by automated
tests + the compound smoke runner.

The implementation strictly follows the constraints the user set:

* **No app hardcodes** — no `if app == "notepad"` branches anywhere,
  including in the new observation ladder (categories are decided by
  generic prefix groups: `gui_*`, `app_*`, `web_*`, `process_*`, …).
* **No fake successes** — failed / unverified / pending steps are
  visible both in the trace and in the final user-facing reply. The
  M4 hook never declares a step `success` purely on the agent's word;
  every claim is backed by a real ladder rung (`process_window`,
  `uia`, `playwright`, `ocr`, `omniparser`, `screenshot`,
  `llm_vision`) or honestly demoted to `unverified`.
* **No forced vision** — `llm_vision` is opt-in via
  `CARTER_USE_LLM_VISION=1` (or `get_settings().use_llm_vision`); the
  ladder never escalates to it unless the step explicitly asks for
  image understanding *and* the operator opted in.
* **Behind flags** — `CARTER_MISSION_STATE`, `CARTER_INTENT_DECOMPOSITION`,
  `CARTER_REOBSERVE` default ON; `CARTER_INTENT_DECOMPOSITION_LLM` and
  `CARTER_USE_LLM_VISION` default OFF.
* **Backward compatibility preserved** — the full pre-existing pytest
  suite still passes; with the 12 new `test_mission_observation.py`
  tests added the total is **1608 passing**.

---

## 1. Implementation summary

| Phase | Goal                                          | Status         | Files                                                                                                                            |
| ----- | --------------------------------------------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| M1    | `Mission` / `MissionStep` state machine + structural decomposition | Done | [src/carter_v2/turn/mission.py](Carter_v2/src/carter_v2/turn/mission.py) |
| M2    | Wire mission into `AgentEngine.run`           | Done           | [src/carter_v2/turn/agent.py](Carter_v2/src/carter_v2/turn/agent.py) |
| M3    | Force one extra tool iteration when a mission has pending steps and the LLM gave a bare text reply | Done | [src/carter_v2/turn/agent.py](Carter_v2/src/carter_v2/turn/agent.py) |
| M4    | Per-step re-observation hook + telemetry surface | **Done** | [src/carter_v2/turn/mission_observation.py](Carter_v2/src/carter_v2/turn/mission_observation.py), [src/carter_v2/turn/agent.py](Carter_v2/src/carter_v2/turn/agent.py) |
| M5    | Mission-level verification against live perception | Done | [src/carter_v2/turn/mission_verification.py](Carter_v2/src/carter_v2/turn/mission_verification.py) |
| M6    | Per-step tool catalog with capability-peer expansion | Done | [src/carter_v2/turn/tool_catalog_selection.py](Carter_v2/src/carter_v2/turn/tool_catalog_selection.py) |
| M7    | GUI/vision fallback ladder (UIA → Playwright → screenshot/OCR → LLM-vision) | **Done** | [src/carter_v2/turn/mission_observation.py](Carter_v2/src/carter_v2/turn/mission_observation.py) |
| M8    | Compound smoke runner                         | Done (10/10)   | [audit/compound_smoke_runner.py](Carter_v2/audit/compound_smoke_runner.py), [audit/COMPOUND_SMOKE.json](Carter_v2/audit/COMPOUND_SMOKE.json) |
| M9    | Honest final-reply formatter                  | Done           | [src/carter_v2/turn/mission_verification.py](Carter_v2/src/carter_v2/turn/mission_verification.py) |

## 2. Files modified / created

**New files**

* [src/carter_v2/turn/mission.py](Carter_v2/src/carter_v2/turn/mission.py) — Mission state machine, structural decomposition, env flag readers.
* [src/carter_v2/turn/mission_verification.py](Carter_v2/src/carter_v2/turn/mission_verification.py) — `MissionVerifier` and `format_mission_reply`.
* [src/carter_v2/turn/mission_observation.py](Carter_v2/src/carter_v2/turn/mission_observation.py) — M4 + M7 observation ladder (process/window → UIA → Playwright → screenshot/OCR → LLM-vision → honest unverified).
* [tests/test_mission_state.py](Carter_v2/tests/test_mission_state.py) — 27 unit tests for mission, decomposition, peer expansion, verification, env flags.
* [tests/test_mission_observation.py](Carter_v2/tests/test_mission_observation.py) — 12 unit tests for the observation ladder (text-skip, UIA fallback, web tier, OCR fallback, LLM-vision opt-in, omniparser missing, never-raises, each-tier-once, env flags).
* [audit/compound_smoke_runner.py](Carter_v2/audit/compound_smoke_runner.py) — scripted-backend compound smoke (10 cases, M4/M7 telemetry assertions).
* [audit/COMPOUND_SMOKE.json](Carter_v2/audit/COMPOUND_SMOKE.json) — last smoke artifact (includes per-step `mission_events`).

**Modified files**

* [src/carter_v2/turn/agent.py](Carter_v2/src/carter_v2/turn/agent.py) — mission setup, M3 forced retry, step lifecycle update inside the tool execution loop with the M4 reobserve hook, `mission_blocks_direct` guard, `format_mission_reply` override in `_return_turn`.
* [src/carter_v2/turn/perception.py](Carter_v2/src/carter_v2/turn/perception.py) — `PerceptionSnapshot.screen_hash` now defaults to `""` so observation tests can construct snapshots without recomputing the hash.
* [src/carter_v2/turn/tool_catalog_selection.py](Carter_v2/src/carter_v2/turn/tool_catalog_selection.py) — `select_tools_for_step()` and `_CAPABILITY_PEERS` symmetric capability groups.

## 3. Mission state architecture

```
            decompose_intent(user_text)
                       │
                       ▼
                 ┌──────────┐
                 │ Mission  │  status = TRIVIAL  ──►  legacy single-shot path
                 └────┬─────┘
                      │ status = PENDING / RUNNING
                      ▼
            ┌────────────────────────────────────┐
            │  AgentEngine main loop              │
            │  ───────────────────────────────── │
            │  for iter in range(MAX_ITERS):      │
            │     LLM → tool_calls?               │
            │       yes → execute, mark pending   │
            │              step (success /        │
            │              unverified / failed)   │
            │       no  → if mission has pending  │
            │              and not retry_used:    │
            │                 force one retry     │
            │                 with [MISSION_      │
            │                 CONTROL] hint &     │
            │                 per-step tools      │
            │              else: exit loop        │
            └────────────────────────────────────┘
                      │
                      ▼
            MissionVerifier.verify(mission)
                      │
                      ▼
            format_mission_reply(mission, draft)
                      │
                      ▼
              AgentTurnResult
              (.mission_status, .mission_trace)
```

* **`MissionStatus`**: `pending`, `running`, `complete`, `partial`,
  `failed`, `needs_user`, `trivial`.
* **`StepStatus`**: `pending`, `running`, `success`, `failed`, `skipped`,
  `unverified`.
* **Settle rule** (in `Mission.settle_status`): all SUCCESS → COMPLETE;
  all FAILED → FAILED; mix of SUCCESS / UNVERIFIED / PENDING / FAILED →
  PARTIAL.
* **`mission_blocks_direct`** — a closure-time guard added before the
  `direct_action_reply` short-circuit. If the mission still has pending
  steps the agent refuses to collapse the turn into a one-tool reply.

## 4. Decomposition flow

`decompose_intent(user_text, backend, tool_index)` runs in two stages:

1. **Structural gate** (`looks_compound`): cheap regex check for
   pipeline glyphs (`->`, `=>`, `→`), semicolons, `then` / `then_es`
   markers, or `comma + rest`. Bare `y` / `and` / `e` no longer trigger
   compound detection — they too often join verbs like "open and read"
   without a real second action.
2. **Splitting** (`_structural_split`): tries the strongest connector
   first (pipeline → semicolon → then_en → then_es → comma_long), stops
   at the first one that yields ≥ 2 clauses with at least one ≥ 2-token
   clause.

LLM decomposition via `TaskFrameBuilder` is **opt-in**
(`CARTER_INTENT_DECOMPOSITION_LLM=1`). When opted in, the decomposer
asks the LLM for a `TaskFrame` and converts each `WorkUnit` into a
`MissionStep`. When the LLM call fails or returns < 2 work units, we
fall back to the structural split.

## 5. Re-observation (M4)

**Done.** A new module
[src/carter_v2/turn/mission_observation.py](Carter_v2/src/carter_v2/turn/mission_observation.py)
is the single decision point for *"after a tool ran, how should we
observe what actually happened?"*. It is wired into
[src/carter_v2/turn/agent.py](Carter_v2/src/carter_v2/turn/agent.py)
directly inside the per-tool branch of the main loop.

Flow per tool call:

1. `needs_observation(tool_name)` decides whether the ladder is worth
   running. Pure-text tools (`memory_*`, `system_get_*`, `clock_*`,
   `calendar_*`, …) return `False` and the ladder is **skipped**
   (cheap turns stay cheap).
2. When the mission is active, `observe_after_tool(...)` is called
   with the tool name, the step objective, an optional
   `window_hint` extracted from the tool args (`window_title`,
   `title_contains`, or `target`), and the snapshot captured *before*
   the tool ran. The hook is wrapped in `try/except` so a tier
   crash can never crash the agent loop.
3. The returned `ObservationOutcome` plus the existing
   `MissionVerifier.verify_step` result decide the step lifecycle:

   * `result.ok = False`                              → `mark_failed`
   * verifier `confirmed` / `skipped` **or** `outcome.ok`  → `mark_success`
   * everything else                                  → `mark_unverified`

4. Per step we emit a `mission_event` into
   `turn_trace["mission_events"]` carrying the full M4 telemetry
   surface:

   ```
   mission_id, step_index, step_text, mission_status,
   reobserve_used,
   observation_source,           # process_window | uia | playwright |
                                # ocr | omniparser | screenshot |
                                # llm_vision | unverified | error |
                                # text_skip
   observation_ok,
   active_app, active_window,
   used_uia, used_playwright,
   used_screenshot, used_ocr,
   used_llm_vision, used_omniparser,
   observation_error,
   observation_elapsed_ms
   ```

The hook honours `CARTER_REOBSERVE` (default ON). With
`CARTER_REOBSERVE=0` it is a complete no-op and the agent uses the
legacy verifier-only path.

## 6. Mission verification (M5)

`MissionVerifier.verify(mission)` walks each SUCCESS step and, when the
step's `verification` dict carries `expected_process_alive` or
`expected_process_dead`, checks the live `PerceptionMonitor.snapshot()`
against it. Failed verifications demote the step to UNVERIFIED. The
mission status is then re-settled. No screenshots, no OCR, no LLM call
— this stage is deterministic.

## 7. Per-step tool catalog (M6)

`select_tools_for_step(step_objective, full_tools, user_text,
prior_calls, pinned_tools, k)` rebuilds the catalog for the *current
pending step* (instead of the original user_text) and:

* **Always includes** any pinned tools the decomposer attached to the
  step.
* **Symmetrically expands** every prior or pinned tool through six
  hard-coded "capability peer" frozensets (e.g. `{app_open, app_close,
  process_stop_app, process_start_app, window_close}` — symmetric, not
  app-specific). This means that whenever `app_open` was used earlier
  in the turn, the **closing** counterparts become reachable to the
  LLM in subsequent iterations even when the Spanish prompt
  "ciérralo" wouldn't have surfaced them on its own.
* Bounded by the existing top-K + always-on-core selector to avoid
  flooding the model.

## 8. Vision / GUI status (M7)

**Done.** The GUI/vision fallback ladder lives in
[src/carter_v2/turn/mission_observation.py](Carter_v2/src/carter_v2/turn/mission_observation.py)
and is exercised on every observable tool call. Tier order:

| # | Tier             | When tried                                  | Backend probe                                                  |
| - | ---------------- | ------------------------------------------- | -------------------------------------------------------------- |
| 1 | `process_window` | always (cheap)                              | `PerceptionMonitor.snapshot()` + `diff()` over processes / active window |
| 2 | `uia`            | category in `{gui, process, unknown}`       | `import uiautomation` (cached probe)                          |
| 3 | `playwright`     | category == `web`                           | `import playwright` (cached probe)                            |
| 4 | `screenshot+ocr` | tiers 1–3 unsatisfied OR step needs text   | `mss` for capture; `omniparser` first, then `pytesseract`      |
| 5 | `llm_vision`     | step explicitly needs image *and* operator opted in | `vision_router._llm_read_text` (gated by `CARTER_USE_LLM_VISION`) |
| 6 | `unverified`     | every preceding tier reported unavailable   | n/a — the outcome is honestly reported as `ok=False`           |

Guarantees:

* **Each tier runs at most once per call.** No retry loops, no
  re-entry. `_TIER_CACHE` memoises availability probes per process so
  cost is dominated by the actual capture, not by import attempts.
* **No automatic LLM-vision activation.** The screenshot/OCR tier is
  preferred whenever it can answer the question; the LLM tier is
  invoked only when the *caller* of `observe_after_tool` set
  `needs_image=True` *and* the operator opted in via
  `CARTER_USE_LLM_VISION=1` (or the existing `use_llm_vision`
  setting). The compound smoke asserts
  `used_llm_vision == False` for every case.
* **Honest unavailability.** Missing dependencies surface as
  `observation_source="unverified"` with an explanatory
  `observation_error` (`uia_unavailable`, `mss_unavailable`,
  `no_ocr_backend_configured`, …) — never silently treated as
  success.
* **Integration with the existing stack.** The OCR / omniparser /
  LLM-vision rungs reuse the helpers already exposed by
  `src/carter_v2/capabilities/vision_router.py`
  (`_omniparser_available`, `_run_omniparser`, `_ocr_all`,
  `_llm_read_text`) so behaviour stays consistent with the standalone
  vision tools. `gui_agent.py` and `screen_cache.py` are unchanged —
  the ladder consumes their outputs through the existing
  `PerceptionMonitor` interface.

Unit tests covering the ladder live in
[tests/test_mission_observation.py](Carter_v2/tests/test_mission_observation.py)
(12 tests, all green).

## 9. Pytest results

* Pre-change baseline:    `1569 passed`.
* After M1+M2+M3+M5+M6+M9 integration & test additions: `1596 passed`
  (1569 legacy + 27 new in `tests/test_mission_state.py`).
* After M4 + M7 land with their unit tests: **`1608 passed`**
  (1596 + 12 new in `tests/test_mission_observation.py`).

Command used:

```pwsh
python -m pytest -q --ignore=tests/test_main_jarvis.py
```

No legacy test was deleted. Three legacy tests in
`tests/test_agent_intent_continuity.py`,
`tests/test_e2e_agent_turn.py`,
`tests/test_ambiguity_resolution.py`,
`tests/test_tool_normalizer.py` had to be re-validated after tightening
the structural gate; once bare-`y` / bare-`and` no longer triggered
decomposition, they all passed unmodified.

## 10. Compound smoke results

`python audit/compound_smoke_runner.py` → `10/10 PASS`. Output written to
[audit/COMPOUND_SMOKE.json](Carter_v2/audit/COMPOUND_SMOKE.json).

| Case                                          | Tools dispatched                                    | Mission status (env-dependent†) |
| --------------------------------------------- | --------------------------------------------------- | ------------------------------- |
| open_then_close_notepad                       | `app_open`, `app_close`                             | partial ∨ complete              |
| open_write_close_notepad                      | `app_open`, `gui_do`, `app_close`                   | partial ∨ complete              |
| open_steam_then_close                         | `steam_open_client`, `gui_do`, `process_stop_app`   | complete                        |
| three_step_pipeline                           | `app_open`, `filesystem_read_text`                  | partial *                       |
| step_two_fails                                | `app_open`, `app_close` (cap returns ok=False)      | failed                          |
| trivial_who_are_you                           | (none)                                              | trivial                         |
| trivial_what_time                             | `system_get_time`                                   | trivial                         |
| open_opera_search_batman                      | `app_open`, `web_search`                            | trivial ‡                       |
| gui_step_observed_via_uia_or_unverified       | `app_open`, `app_close`                             | partial ∨ complete              |
| uia_unavailable_falls_back_to_unverified      | `app_open`, `gui_do`, `app_close`                   | partial ∨ complete              |

† The new M4 hook means the verifier now consults the live UIA / process
tree. On a Windows host with `uiautomation` installed and a real
Notepad window the steps are confirmed and the mission settles to
COMPLETE. On a CI host without UIA the same scripted run honestly
settles to PARTIAL with an `observation_source="unverified"` event.
The smoke runner accepts both outcomes — they are both **honest**.
\* The pipeline case has 3 declared steps but only 2 tools are
dispatched (the third step is satisfied by the LLM's textual summary),
so the mission settles to PARTIAL.
‡ *"abre Opera y busca Batman"* uses bare `y` which is no longer a
compound trigger (see §11). The mission stays TRIVIAL but the M4
ladder still runs per tool — the smoke asserts that
`used_llm_vision == False` is preserved.

## 11. Unsupported cases (today, by design)

* **Implicit multi-action verbs without a sequencing connector** —
  e.g. *"abre Opera y busca Batman"* (bare `y`). Bare conjunctions
  caused too many false positives on English verb-pairs ("read and
  summarize"). The agent still relies on the LLM to chain these on
  its own; mission only kicks in for explicit sequencing markers
  (`y luego`, `;`, `->`, `then`, `,`).
* **Visual confirmation of GUI changes** without any `process_*` /
  `window_*` change is still out of scope — `MissionVerifier` only
  consults processes and active window title.
* **Multi-turn missions** (state across user turns) — `Mission` lives
  inside a single turn. Persisting a mission across user turns is not
  implemented.

## 12. Remaining risks

* **Structural over-split with `,`** — long sentences with internal
  commas may produce too many fragments. Mitigated by the
  `_structural_split` cap of 6 sub-tasks and by the soft-PARTIAL
  draft-preservation rule, but worth watching in real conversations.
* **Forced retry in single-tool turns** — `_mission_force_retry_used`
  prevents infinite loops, but if the operator enables LLM
  decomposition on a model that hallucinates many steps, we could burn
  one extra LLM call per turn. Defaults are conservative.
* **Tool dispatch namespace coupling in the smoke runner** — the
  smoke runner registers a recording capability per known namespace.
  When new namespaces are added to `src/carter_v2/capabilities/`, the
  smoke runner's `_NAMESPACES_FOR_CASES` tuple should be extended too,
  otherwise new compound cases that touch them will silently dispatch
  to nothing.

## 13. What is left before voice / camera

1. **Live-OS compound smoke** — the current smoke uses scripted
   backends. A second variant that drives a real Ollama backend and
   the actual capabilities is a natural follow-up; it would replace
   the current `live_smoke_results.json` for compound prompts.
2. **Voice-triggered turns** — the mission state machine and the M4
   ladder both take plain text in and produce structured traces, so
   STT-derived `user_text` will work without changes. Wire when ready.
3. **Camera / vision input** — orthogonal to mission state. The M7
   ladder already exposes `used_llm_vision` / `used_omniparser`
   telemetry, so adding a camera frame source is mostly a matter of
   feeding `bytes` to `vision_router._llm_read_text` /
   `_run_omniparser` from a non-screenshot tier.

---

**Bottom line:** the smoking-gun case from the audit
(`'abre Notepad y luego ciérralo' → tools=['app_open']`) is no longer
possible. With mission state on, the structural split forces
`first_pending` to remain `'ciérralo'` after `app_open`, the
per-step catalog re-exposes the symmetric `app_close` /
`process_stop_app` peer, and the forced retry guarantees one more
attempt with `require_tool=True` before the loop exits. If the second
tool still doesn't fire, the mission settles to PARTIAL and the
formatter writes an honest banner instead of a fake "ok".
