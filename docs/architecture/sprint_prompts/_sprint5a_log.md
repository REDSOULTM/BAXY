# Sprint 5a — Log (tests-first for the 4 god classes)

- **Started:** 2026-05-17
- **Finished:** 2026-05-17 (same session)
- **Operator:** Claude Code (Opus 4.7)
- **Base commit:** d2b2ffe `docs(sprint_prompts): add Sprint 5a (tests-first) + 5b (splits)`
- **Final code commit:** 51d40a3 `sprint5a: add SettingsDialog contract tests`
- **Net delta vs base:** 7 files changed, **+1993 LOC, 0 deletions** (pure-add sprint)
- **`COMPOUND_TOOL_SCHEMAS`:** 65 → 65 (unchanged)
- **Total new tests:** **83** (19 + 25 + 14 + 11 + 14) — all green

## Headline

Five contract test files committed, one per god class plus the worker
pair. Every Sprint 5b reorganization will land against this net. All
tests pass with `QT_QPA_PLATFORM=offscreen`; nothing was skipped due
to environment.

## Pre-flight: Qt headless confirmed

```
$ python -c "import os; os.environ['QT_QPA_PLATFORM']='offscreen';
            from PyQt6.QtWidgets import QApplication; QApplication([])"
Qt OK (offscreen)
```

So the Qt-bound suites (5a.3 AgentWorker, 5a.4 MainWindow, 5a.5
SettingsDialog) were able to run end-to-end. Sprint 5b can rely on
all 83 tests being executable from the same environment.

## 5a.1 — `test_tool_registry_contract.py` — commit 012fff1 ✅ (19 tests)

Extends `test_tool_dispatch_contract.py` (which already pins `execute()`).
5 test classes cover the rest:

- **TestSchemasAPI**: `schemas` / `schema_names` / `schemas_for_names`
  return shape and types. 65-entry length pinned, OpenAI function
  shape asserted, list/tuple/set inputs all work, unknown names
  silently ignored, empty input returns `[]`.
- **TestImplsIntegrity**: `_impls` has exactly 65 entries, keys equal
  compound schema names, every value is callable. Anti-regression if
  Sprint 5b accidentally drops a wrapper.
- **TestRoutineStep**: `execute_routine_step` injects
  `routine_context=True` + `confirmed_at_create` kwarg; strips any
  LLM-injected duplicates; normalizes unknown tools.
- **TestSafetyGate**: `safety_enabled=False` is bypass;
  `safety_enabled=True` blocks risky tools (`app.close`) with
  `status="needs_confirmation"`; `confirmed=True` passes; the `safety`
  tool itself is never gated.
- **TestParentAgentBackref**: `getattr(reg, "parent_agent", None)`
  is the contract; assignment works.

## 5a.2 — `test_gemma4agent_contract.py` — commit dee0d03 ✅ (25 tests)

7 test classes pinning everything the 4 surfaces (CLI / UI Desktop /
UI Field / MCP) consume:

- **TestConstructor**: core attributes exist (memory, state, client,
  tools, experience, trace, history, _persona); history starts empty;
  `tools.parent_agent` backref wired; default persona is `"default"`.
- **TestClear**: `clear()` resets history, `_turn_counter`,
  `_recent_recalls`, `_cached_microagents`, `_cached_skills_*`,
  `_last_turn_ts`.
- **TestPersona**: `get_persona` shape;
  `set_persona("coder")` changes; `set_persona("nonexistent")`
  returns `ok=False` with `available`, persona unchanged.
- **TestRunTextSmoke**: `run_text("hola")` returns `AgentReply` with
  `content/tool_events/error/mission`; history grows by ≥2; turn
  counter increments.
- **TestRunTextToolCallFlow**: two-call sequence (tool_call → reply)
  with `LLMClient.chat` and `ToolRegistry.execute` mocked;
  `tool_events` captures the tool; post-compaction history has user +
  assistant only (the `role="tool"` row inserted during the turn is
  stripped by `_compact_completed_history`'s cheap pass — pinned as
  observed behaviour).
- **TestGuardsSpy**: `_guard_promise_without_action` invoked at least
  once per turn (the canary for the 6 inline guards).
- **TestContextBudget**: `_compute_context_budget` has the 7
  documented keys, values scale with `context_size`, floor of 1024.

## 5a.3 — `test_agent_workers_parity.py` — commit 50036d9 ✅ (14 tests)

The most important file of this sprint. 6 classes pin both workers
before Sprint 5b collapses them onto a shared `AgentSerialWorker`
base:

- **TestAgentRunnerSubmit**: `submit()` enqueues exactly one item;
  returns in <100 ms; propagates `images` + `audios` into the
  `_TurnRequest`.
- **TestAgentRunnerStop**: `stop()` sets `_running=False`,
  `_stop_event`; injects the `"__stop__"` sentinel that unblocks
  `queue.get()`.
- **TestAgentRunnerRestart**: `restart()` clears `_agent` and
  `_warmed_up` (with `_build_agent` patched to a no-op).
- **TestRunnerSingleton**: module-level `RUNNER` is the same object
  across two imports.
- **TestAPIParity**: `submit` + `stop` present on both classes;
  `submit` signatures both accept `(text, *, images, audios)`.
- **TestAgentWorkerHeadless**: AgentWorker instantiates under
  `QT_QPA_PLATFORM=offscreen`; all 7 pyqtSignals expose
  `.emit`/`.connect`; `submit` enqueues; `stop` sets the flag.

Crucially we never call `.start()` / `.run()` — that would trigger
`_build_agent` against a non-existent llama-server.

## 5a.4 — `test_main_window_contract.py` — commit 8c61787 ✅ (11 tests)

4 classes:

- **TestMainWindowImport**: module loads, MainWindow inherits
  `QMainWindow`.
- **TestMainWindowInstantiation**: `MainWindow()` does not raise;
  pins the post-init attribute names Sprint 5b will move to sub-widgets:
  - `self.worker` → `AgentWorker`
  - `self._bus_bridge` → `EventBusBridge` (underscore prefix —
    documenting the real name)
  - `self.hud` → `HudCanvas`
  - `self.log` → `LogWidget` (attribute is `log`, not `log_widget`)
  - `self._header_h` / `_left_h` / `_right_h` / `_footer_h` → dicts
- **TestMainWindowSignalWiring**: emitting `worker.state_changed` and
  `worker.log` from outside doesn't raise (canary that __init__'s
  connect calls survived).
- **TestMainWindowCloseEvent**: `closeEvent(QCloseEvent())` runs
  cleanly. (Used a real `QCloseEvent` — PyQt6 rejects `MagicMock` at
  the C++ boundary with "argument 1 has unexpected type".)

## 5a.5 — `test_settings_dialog_contract.py` — commit 51d40a3 ✅ (14 tests)

4 classes:

- **TestApplyToEnv** (no Qt): `apply_to_env({...})` pushes env keys
  as strings; `None`/`""` values remove the key; toggles serialize
  as `"true"`/`"false"` lowercase; empty input is no-op.
- **TestLoadPersisted**: `load_persisted` reads `SETTINGS_PATH` via
  `unittest.mock.patch` (so the user's real `~/.gemma4/gui.json`
  is never touched); missing → `{}`; valid JSON → dict;
  malformed → `{}`; non-dict root → `{}`.
- **TestApplyPersistedOnStartup**: no file → no-op; with file → env
  applied.
- **TestSettingsDialogShell** (Qt offscreen): constructor doesn't
  raise; `apply_clicked` + `restart_clicked` pyqtSignals exposed;
  **exactly 11 tabs in this order**: CONNECTION, AGENT, SAMPLING,
  BEHAVIOUR, VOICE, PROFILES, OPTIM, TOGGLES, PATHS, PROMPT, ABOUT.

The tab-title tuple is the part Sprint 5b will need most: any drift
flags a rename or accidental removal during the per-tab split.

## Tests SKIPPED — none

Initial plan accounted for skipping the Qt-bound suites if headless
init failed. It didn't — `QT_QPA_PLATFORM=offscreen` worked
end-to-end. **All 83 tests run unconditionally.**

## BUGS FOUND while writing the tests — none reported (one anomaly noted)

While writing `TestClear` (5a.2) I observed that `Gemma4Agent.clear()`
does **not** reset `self._phrase_fires` — but the field is itself
populated per-turn at the start of `run_content` (agent.py:904
`self._phrase_fires = []`). So clear's omission is harmless: any new
turn will overwrite it anyway. I did NOT add a regression test
asserting the omission; that would freeze a non-essential behaviour.
Documenting here for Sprint 5b in case the split path changes this
invariant.

No real bugs found.

## Final verifications

```
$ python -c "import gemma4_agent"
(no output, exit 0)

$ python -c "from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"
65

$ python -m pytest test_tool_dispatch_contract test_session847_fixes \
                   test_log_audit_fixes test_inherit_tools_safety -q
69 passed, 3 subtests passed in 4.63s

$ python -m pytest test_tool_registry_contract test_gemma4agent_contract \
                   test_agent_workers_parity test_main_window_contract \
                   test_settings_dialog_contract -q
83 passed in 27.71s
```

## Recap of commits

```
012fff1 sprint5a: add ToolRegistry contract tests (schemas API, routine, safety, _impls)
dee0d03 sprint5a: add Gemma4Agent contract tests (init, clear, persona, run_text, guards spy)
50036d9 sprint5a: add AgentWorker/AgentRunner parity contract tests
8c61787 sprint5a: add MainWindow contract tests (importable, widgets, signal wiring, closeEvent)
51d40a3 sprint5a: add SettingsDialog contract tests (env application, persisted startup, tab structure)
<this commit>
```

## Ready for Sprint 5b

Sprint 5a's contract net is in place. Sprint 5b can:

1. Run **all 152 tests** (69 preexisting + 83 new) before any change
   to establish baseline green.
2. Make a refactor change.
3. Re-run the 83 new contract tests in ~28 seconds; any red is a
   regression.

Headlines that Sprint 5b must preserve, encoded as test invariants:

- ToolRegistry: 65 schemas, 65 `_impls` entries, each callable;
  parent_agent backref pattern; routine_step injection.
- Gemma4Agent: history+memory+state+tools+experience+trace+_persona
  attributes; default persona "default"; AgentReply shape; guards
  fire post-reply; context_budget keys.
- Workers: `submit` + `stop` on both; `submit(text, *, images,
  audios)` signature; RUNNER singleton identity; AgentWorker has all
  7 pyqtSignals.
- MainWindow: `worker`, `_bus_bridge`, `hud`, `log`, panel-handle
  dicts; closeEvent never raises.
- SettingsDialog: 11 tabs in order; `apply_clicked` +
  `restart_clicked` signals; `apply_to_env` / `load_persisted` /
  `apply_persisted_on_startup` behaviour.
