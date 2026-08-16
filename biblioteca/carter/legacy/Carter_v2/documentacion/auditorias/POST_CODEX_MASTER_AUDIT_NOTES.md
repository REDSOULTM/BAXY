# Carter v2 — Post-Codex Master Audit Notes

## Codex commit range
- Snapshot before Codex: `051e014` (chore: snapshot before final universal text-agent stabilization)
- Codex commits:
  - `c6ffa9a` fix(runtime): harden Carter routing, app launch, context guard, and live smoke harness
  - `6ebfef6` fix(universal): stabilize Carter text-agent core with live LLM verification
- HEAD: `6ebfef6`

## Files Codex changed
67 files, +14357/-533. The bulk is generated artifacts (gui_debug PNGs, live_smoke_*.json/md). Real source changes:

### Source files
- `Carter_v2/src/carter_v2/turn/llama_backend.py` — num_ctx wiring
- `Carter_v2/src/carter_v2/turn/agent.py` — context budget guard, system prompt, traces
- `Carter_v2/src/carter_v2/turn/verification.py`
- `Carter_v2/src/carter_v2/adapters/tools.py` — tool descriptions
- `Carter_v2/src/carter_v2/adapters/tool_normalizer.py` — bogus URL → app_open rewrite
- `Carter_v2/src/carter_v2/capabilities/gui_agent.py` — major rewrite (multi-step planner, CEF)
- `Carter_v2/src/carter_v2/capabilities/input.py` — key aliases
- `Carter_v2/src/carter_v2/capabilities/system.py` — display + keyboard layout
- `Carter_v2/src/carter_v2/capabilities/web.py` — browser search helper
- `Carter_v2/src/carter_v2/capabilities/app_resolver.py` — Opera GX, browser aliases
- `Carter_v2/src/carter_v2/capabilities/process.py` — small fix
- `Carter_v2/src/carter_v2/capabilities/memory.py` — small fix
- `Carter_v2/src/carter_v2/capabilities/_subprocess.py` — small fix
- `Carter_v2/src/carter_v2/session/policy.py`
- `run_carter_gpu.ps1`

### Tests added by Codex
- `tests/test_agent_turn_trace.py`
- `tests/test_app_resolver.py` (extended)
- `tests/test_context_budget_guard.py`
- `tests/test_gui_do_planner.py`
- `tests/test_input_aliases.py`
- `tests/test_system_display_keyboard.py`
- `tests/test_tool_routing_contracts.py`
- `tests/test_web_browser_search.py`
- `tests/test_tool_normalizer.py` (extended)
- `tests/test_process_capability.py` (extended)
- `tests/test_system_capability.py` (extended)

### Reports/scripts
- `Carter_v2/scripts/live_carter_llm_smoke.py`
- `Carter_v2/FINAL_TEXT_AGENT_STABILIZATION_NOTES.md`
- `Carter_v2/FINAL_TEXT_AGENT_STABILIZATION_REPORT.md`
- `Carter_v2/live_smoke_results.{json,md}`
- `Carter_v2/artifacts/live_smoke_*.{json,md}`
- `Carter_v2/artifacts/gui_debug/*.png` (~30 screenshots)

## Manual review log
(filled below as the audit proceeds)

