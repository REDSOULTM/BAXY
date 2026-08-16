# Session 21 - Universal Core Closure Notes

## Executive Result

The post-S20 universal core closure is complete for the requested scope.

Voice and camera remain out of scope and were not touched.

## Breaches Found And Closed

| Breach | Initial State | Final State | Evidence |
| --- | --- | --- | --- |
| Auto universal routing did not pass task workspace/resource bases into the runner | `AgentEngine` created `PlanGraphRunner` without `resource_base_dirs` | `AgentEngine` now derives base dirs from `CARTER_UNIVERSAL_RESOURCE_BASE_DIRS`, `CARTER_WORKSPACE_DIR`, and run workspace when a run id exists | `tests/test_universal_agent_kernel.py::test_agent_engine_auto_universal_persists_resource_base_evidence` |
| Forced universal runner did not pass resource context either | Forced path used the same runner construction gap | Forced path now uses the same resolver/base-dir integration | `tests/test_universal_agent_kernel.py::test_agent_engine_forced_universal_uses_resource_base_dirs` |
| `/tasks` did not expose resource evidence | Checkpoint listing showed artifacts only | Checkpoint rows now include resource count and concise resource summary | `tests/test_universal_agent_kernel.py::test_cli_formats_task_rows_with_resource_summary` |
| S21 had no LLM probe proving artifact + later use + checkpoint + resume + resource evidence | No S21 probe existed | Added `S21-RESOURCE-1` and `S21-RESOURCE-2`; generated `probe_session21_results.json` | `probe_session21_results.json`: 2 PASS, 0 FAIL, 0 ERROR, 0 SKIP |

## Reviewed And Left Untouched

| Area | Reason |
| --- | --- |
| Memory/skills policy | Existing S16 implementation and tests are valid; no S21 breach found. |
| Tool/capability public interfaces | No interface changes were required. |
| Tool normalizer app-hack cleanup | Already handled; tests still pass. |
| Brain router structural risk checks | Already handled; tests still pass. |
| Product capabilities | Existing tools remain the execution surface. |
| Voice/camera | Explicitly excluded from scope. |

## Files Changed For Core Closure

| File | Change |
| --- | --- |
| `src/carter_v2/turn/agent.py` | Passes resource resolver/base dirs into universal runner for forced and auto routes. |
| `src/carter_v2/main.py` | Creates stable universal task workspace env for `/task` and `/resume`; formats `/tasks` with resource summary. |
| `src/carter_v2/universal/checkpoint.py` | Adds resource count and readable resource summaries to checkpoint list rows. |
| `src/carter_v2/universal/runner.py` | Preserves prior artifact resolution even when a system snapshot resolver is supplied. |
| `tests/test_universal_agent_kernel.py` | Adds coverage for auto/forced resource bases and `/tasks` resource summaries. |
| `probe_all_tools.py` | Adds S21 LLM probes for artifact creation, artifact reuse, checkpoint schema 3, resume, and persisted resource evidence. |
| `probe_session21_results.json` | Stored S21 probe result. |
| `session21_full_closure_audit.md` | Audit and breach matrix. |

## Validation Evidence

Focused tests:

- `python -m pytest Carter_v2/tests/test_universal_agent_kernel.py -q` -> `33 passed`
- `python -m pytest Carter_v2/tests/test_resource_resolver.py -q` -> `6 passed`
- `python -m pytest Carter_v2/tests/test_assistant_engine.py -q` -> `15 passed`
- `python -m pytest Carter_v2/tests/test_tool_normalizer.py -q` -> `22 passed`
- `python -m pytest Carter_v2/tests/test_brain_router_fase7.py -q` -> `32 passed`
- `python -m pytest Carter_v2/tests/test_registry_errors.py -q` -> `4 passed`

Full suite:

- `python -m pytest Carter_v2/tests -q` -> `1216 passed`, `3 warnings`

Probe:

- `python probe_all_tools.py --only S21-RESOURCE-1,S21-RESOURCE-2 --output probe_session21_results.json`
- Result: `PASS 2`, `FAIL 0`, `ERROR 0`, `SKIP 0`

## Probe Evidence

`S21-RESOURCE-1`:

- Created `probe_assets_runtime/s21_workspace/artifact.txt`.
- Read the artifact in a later node.
- Checkpoint saved with `schema_version: 3`.
- `resolved_resources` includes the artifact path with file evidence.

`S21-RESOURCE-2`:

- Resumed `s21-resource-flow`.
- Did not re-run completed tools.
- Preserved checkpoint resource evidence.

## Non-Core Files Left Outside The Commit

Generated or unrelated files present in the worktree before/during S21 remain outside the core closure unless explicitly part of S21 output:

- Existing generated probe outputs unrelated to S21.
- Existing dirty binary fixture `probe_assets/sample.docx`.
- Personal/session notes and prompt files.
- External config/archive/research artifacts.
- Untracked historical tests not required by S21.

## Remaining Real Core Pending

None in the requested S15-S20/S21 core scope.

Out of scope by instruction:

- Voice.
- Camera.
