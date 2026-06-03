# Sprint 5b — Log (splits with Sprint 5a safety net)

- **Started:** 2026-05-17
- **Finished:** 2026-05-17 (same session)
- **Operator:** Claude Code (Opus 4.7)
- **Base commit:** 124bd4e `sprint5a: write log`
- **Final code commit:** 8fbf30e `sprint5b: extract CORE_PROMPT + TOOL_RULES + build_system_prompt`
- **`COMPOUND_TOOL_SCHEMAS`:** 65 → 65 (unchanged)

## Headline

Four extractions landed; six tasks deliberately SKIPPED with reasons.
**No regressions:** every test that was green before Sprint 5b is
still green; every test that was red was red before Sprint 5b for
reasons unrelated to this sprint's edits.

## Tasks completed

### 5b.1.a — Extract `AppResolver` + `AppCandidate` — commit 4637c3f ✅

383 LOC (`tools.py:621-998`) moved to new module
`gemma4_agent/app_resolver.py`. `tools.py` re-exports both names. The
ranking / parsing helpers (`_fold`, `_score`, `_acf_value`,
`_nearest_steam_appid`, `_pretty_exe_name`,
`_looks_like_uninstaller`) stay in `tools.py` because they are also
consumed by code outside `AppResolver`; the new module imports them
lazily inside each method to avoid a top-level cycle.

- `tools.py`: 4764 → 4388 (−376)
- `app_resolver.py`: 418 new
- 45/45 ToolRegistry tests green.

### 5b.1.b — Extract SSRF guard — commit 23181c3 ✅

`_is_private_host` (31 LOC) + `_SSRFGuardRedirectHandler` (12 LOC)
moved to `gemma4_agent/ssrf_guard.py`. Pure stdlib (`ipaddress`,
`socket`, `urllib.request`). `tools.py` re-exports both. Audit §4.20
`[1-USER]` resolved.

- `tools.py`: 4388 → 4348 (−40)
- `ssrf_guard.py`: 64 new
- Smoke test green: `_is_private_host("localhost")=True`,
  `_is_private_host("google.com")=False`.

### 5b.1.d — Extract `COMPOUND_TOOL_SCHEMAS` literal — commit 63efd1d ✅

The 65-entry list literal (67 LOC inline) moved to
`gemma4_agent/tool_schemas.py`. `tools.py` imports it; the
subsequent `_apply_action_enums(COMPOUND_TOOL_SCHEMAS)` call
operates on the same shared object (identity verified).

- `tools.py`: 4348 → 4282 (−66)
- `tool_schemas.py`: 79 new
- `COMPOUND_TOOL_SCHEMAS` is the SAME object from both
  `gemma4_agent.tools` and `gemma4_agent.tool_schemas` (identity check).

### 5b.2.c — Extract prompt builder — commit 8fbf30e ✅

`CORE_PROMPT` (150 LOC) + `TOOL_RULES` dict (35 entries) +
`build_system_prompt()` + the eager `SYSTEM_PROMPT` singleton (~549
LOC total, agent.py:41-590) moved to `gemma4_agent/agent_prompt.py`.
`agent.py` re-exports all four names so the
`/agent/system_prompt` endpoint, MCP server, tests, and UI all keep
working unchanged.

**Behaviour-invariance proof** (byte-level hash on the eager
singleton):

| Metric | Before | After |
|---|---|---|
| `len(SYSTEM_PROMPT)` | 25 626 | 25 626 |
| `sha256(SYSTEM_PROMPT)[:16]` | b23565023496fbcc | b23565023496fbcc |
| `len(CORE_PROMPT)` | 8 682 | 8 682 |
| `len(TOOL_RULES)` | 35 | 35 |
| `SYSTEM_PROMPT is sp2` | — | True |

- `agent.py`: 3019 → 2470 (−549)
- `agent_prompt.py`: 561 new

**Commit hygiene note (BUG FOUND in my own workflow):** my
`git add -A` on this commit picked up three pre-existing WIP files
that were in the working tree but were not part of this sprint:
`gemma4_agent/voice/app_inventory.py` (new, 639 LOC),
`gemma4_agent/voice/stt.py` (+156 LOC diff),
`gemma4_agent/test_gx_features.py` (+109 LOC diff). They are
legitimate code (not scratch), so the commit is still safe, but it
muddies the diff-stat. The next prompt should remind the agent to
use selective `git add <path>` instead of `-A` when committing a
refactor. Logged here so Sprint 6 doesn't repeat the mistake.

## Tasks SKIPPED

### 5b.1.c — Extract dispatch pipeline helpers ⏭

`_normalize_tool_result` + `_coerce_and_validate_tool_args` +
`_PRE_VALIDATORS` + `_parameters_for_tool` + their helpers
(`_prevalidate_notification`, `_prevalidate_backup_sync`,
`_coerce_json_value`, `_json_type_ok`) carry hard dependencies on
8+ private tools.py helpers (`_dt`, `_err`, `_P`,
`_DISPATCH_OK_COMPLETIONS`, `_has_unverified_signal`,
`_redact_sensitive`, `_result_evidence`, `_RX_HHMM_LOCAL`). A clean
extraction would require either moving all of them too or threading
lazy-import patterns through the critical `execute()` pipeline.
The risk of subtle regression in tool dispatch is higher than the
cosmetic win of moving 330 LOC. **Deferred to Sprint 6** where it
can be done together with a `tools.py` reorganization that lifts
the helpers first.

### 5b.1.e — Extract `t_*` wrappers ⏭

The prompt itself suggested SKIP: "es un refactor cosmético que no
agrega valor inmediato. Sugerencia: SKIP en este sprint." Done.

### 5b.2.a — Extract `_guard_*` methods ⏭

PRE-FLIGHT revealed **17 pre-existing test failures** in
`test_promise_guard.py`:

```
AttributeError: 'Stub' object has no attribute '_build_user_facing_fallback'
```

The test file's `Stub` class is missing a method that the agent
acquired since the test was written. Per Sprint 5b's rule #1
("Si NO están todos en verde antes del refactor: abortar") and
rule #9 ("NO arregles bugs encontrados — sólo anotarlos"), I
cannot safely extract `_guard_*` methods without distinguishing
my regressions from these pre-existing failures. **The bug is in
the test stub, not in agent.py.**

Repro mínimo:

```
$ python -m pytest gemma4_agent/test_promise_guard.py -q
17 failed, 8 passed in 0.87s
# Each failure is identical: Stub object has no attribute '_build_user_facing_fallback'
```

The fix is a one-line addition to the test stub class. **NOT done
in this sprint** per rule #9.

### 5b.2.b, 5b.2.d — Extract compaction + agent dispatch ⏭

The plan sequenced these after 5b.2.a; with that one skipped, the
shape of `agent.py` and the data flow into `_compact_completed_history`
/ `_execute_calls_*` becomes harder to mock for verification without
the `_guard_*` extraction red still resolved. Lower the risk and
defer both to Sprint 6, which can also fix the test stub problem
first.

### 5b.3 — Workers collapse (AgentSerial) ⏭

Sprint 4's pre-flight analysis (see `_sprint4_log.md` §4.3) showed
that AgentRunner (threading.Thread, BUS-publish output) and
AgentWorker (PyQt QThread, pyqtSignal output) diverge in every
dimension that matters for unification: threading model, output
channel, build sequence, presence of a health-loop. The Sprint 5a
parity tests only pin the **public surface** (`submit` + `stop`),
not the internal flow. With that limited net, a shared base class
risks subtle output-ordering regressions in WS clients / UI.

The Sprint 4 reasoning still applies and the parity test coverage
hasn't grown enough to make this safer. Defer to Sprint 6+ when a
richer suite of behavioural tests for the worker loop is in place.

### 5b.4 — MainWindow split (55 methods, 1616 LOC) ⏭

The Sprint 5a contract tests only verify attribute existence and
`closeEvent` non-raising. The 55 methods share 15+ state attributes
(`self.worker`, `self._bus_bridge`, `self.hud`, `self.log`,
`self._metrics`, `self._metrics_timer`, `self._llama_manager`,
`self._profile_watcher`, `self._server_boot_thread`,
`self._voice_bridge`, `self._voice_controller`,
`self._voice_loader`, `self._sessions_panel`, `self._session_store`,
`self._current_session`, the four panel-handle dicts). A clean
sub-widget extraction would require either threading those attrs
through every signature or introducing a shared state container —
both are real refactors, not "splits".

Per Sprint 5b rule #10 ("Si dudás entre splitear o dejar: dejá"),
**deferred to Sprint 6** where a richer test net + a deliberate
state-container design can land first.

### 5b.5 — SettingsDialog split (22 methods, 11 tabs, 1247 LOC) ⏭

The 11 `_tab_*` methods each construct a self-contained QWidget,
but they store widget references on `self` (`self.<…>_widget`,
`self._tab_widgets`) which the `_gather()` method (line 1137) reads
to coordinate the `apply_clicked` payload. Splitting each tab into
`ui/settings_<tab>.py` would require either redesigning the
`gather()` flow (each sub-widget exposes its own data) or proxying
widget refs through `self`. The first is a real refactor; the
second leaks `self`-state into sibling modules.

The Sprint 5a contract test pins the tab list order + the public
helpers (`apply_to_env`, `load_persisted`, `apply_persisted_on_startup`)
but does not cover the per-tab `gather` flow. With that gap, a
mechanical split risks breaking the settings-apply path silently.
**Deferred to Sprint 6** under the same conditions as 5b.4.

## Final verifications

```
$ python -c "import gemma4_agent"
(no output, exit 0)

$ python -c "from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"
65

$ python -m gemma4_agent.launcher status   # runs cleanly

# Sprint 5a contract tests (the safety net)
$ python -m pytest test_tool_registry_contract test_gemma4agent_contract \
                   test_agent_workers_parity test_main_window_contract \
                   test_settings_dialog_contract -q
83 passed in 29.76s

# Pre-existing regression suite (rule #4)
$ python -m pytest test_tool_dispatch_contract test_session847_fixes \
                   test_log_audit_fixes test_inherit_tools_safety \
                   test_loop_detection -q
88 passed, 3 subtests passed in 4.72s
```

The 17 `test_promise_guard.py` failures present before Sprint 5b are
**unchanged after Sprint 5b** — exact same identity.

## LOC table

| File | Before | After | Δ |
|---|--:|--:|---|
| `agent.py` | 3019 | 2478 | −541 |
| `tools.py` | 4764 | 4282 | −482 |
| `ui/main_window.py` | 1616 | 1616 | 0 (skipped) |
| `ui/settings.py` | 1247 | 1247 | 0 (skipped) |
| **New** | | | |
| `agent_prompt.py` | — | 560 | +560 |
| `app_resolver.py` | — | 418 | +418 |
| `tool_schemas.py` | — | 79 | +79 |
| `ssrf_guard.py` | — | 64 | +64 |
| Pre-existing WIP swept up in 8fbf30e | | | |
| `voice/app_inventory.py` | — | 639 | +639 (not from this sprint) |
| `voice/stt.py` | various | various | +156 diff (not from this sprint) |
| `test_gx_features.py` | various | various | +109 diff (not from this sprint) |

Sprint-5b-attributable LOC (excluding the WIP commit-hygiene
incident): tools.py + agent.py shed 1023 LOC; new files added 1121
LOC; **net +98 LOC**. The win is locality, not LOC reduction:
SYSTEM_PROMPT changes no longer require scrolling past 2500 lines
of agent loop, and the 65-schema list lives in its own file.

## What's preserved

- 65 compound tool schemas — same object identity through both
  `gemma4_agent.tools` and `gemma4_agent.tool_schemas`.
- All public API names re-exported from their original modules:
  `tools.AppResolver`, `tools.AppCandidate`,
  `tools._is_private_host`, `tools._SSRFGuardRedirectHandler`,
  `tools.COMPOUND_TOOL_SCHEMAS`, `agent.CORE_PROMPT`,
  `agent.TOOL_RULES`, `agent.SYSTEM_PROMPT`,
  `agent.build_system_prompt`.
- `SYSTEM_PROMPT` byte-identical (sha256 unchanged).
- All Sprint 5a contract tests (83/83) still green.
- All pre-existing test suites unchanged in pass/fail breakdown.

## Recap of commits

```
4637c3f sprint5b: extract AppResolver + AppCandidate to app_resolver.py
23181c3 sprint5b: extract _is_private_host + _SSRFGuardRedirectHandler to ssrf_guard.py
63efd1d sprint5b: extract COMPOUND_TOOL_SCHEMAS literal to tool_schemas.py
8fbf30e sprint5b: extract CORE_PROMPT + TOOL_RULES + build_system_prompt to agent_prompt.py
<this commit>
```

## For Sprint 6

Pre-conditions to revisit the SKIPs:

1. **Fix the `test_promise_guard.py` Stub class** — add
   `_build_user_facing_fallback` to the stub so all 17 pre-existing
   failures clear. With that net green, 5b.2.a (`_guard_*`
   extraction) becomes safe.
2. **Write behavioural tests for the worker loops** beyond the
   parity surface — slot-fill flow, build-sequence ordering, output
   channel determinism. With that net, 5b.3 (workers collapse) is
   safer.
3. **Settings-apply flow tests** — round-trip from a widget value
   through `_gather` to `apply_clicked.emit` payload. With that
   net, 5b.5 is safer.
4. **MainWindow lifecycle tests** — `start → submit → speaking →
   idle → closeEvent` simulated. With that net, 5b.4 is safer.
5. **`tools.py` helper unification** — lift the 8 dispatch-pipeline
   helpers (`_dt`, `_err`, `_P`, `_DISPATCH_OK_COMPLETIONS`, etc.)
   into a small `tool_internals.py` module first, then 5b.1.c
   (`tool_dispatch.py` extraction) becomes mechanical.

The agent_prompt extraction (5b.2.c) is a working template for the
rest: extract a self-contained block, re-export from the original
home, verify byte-level invariance.
