# Universal Limitation Fix Notes

## Scope
- Session goal: close the four remaining universal limitations from `POST_CODEX_MASTER_AUDIT_REPORT.md`.
- No agents/subagents used.
- Safety snapshot commit: `7f741d4 chore: snapshot before universal limitation fixes`

## Limitation 1: Opaque UI fallback
- Root cause:
  `gui_do` still depended on brittle UIA-first behavior and legacy single-target visual fallbacks.
- Universal fix:
  Added runtime opaque-window detection from UIA element count, step-by-step screenshot verification, pixel-diff validation, and shared vision routing through `vision_router.py`.
- Key files:
  `src/carter_v2/capabilities/gui_agent.py`
  `src/carter_v2/capabilities/vision_router.py`
  `src/carter_v2/capabilities/vision.py`
  `src/carter_v2/adapters/uia.py`
  `src/carter_v2/main.py`
- Live evidence:
  Steam, Discord, Spotify, and VS Code follow-up prompts now produce per-step GUI traces and honest limitations instead of fake completion.

## Limitation 2: Regex GUI planner
- Root cause:
  `_plan_gui_task` was pattern/keyword based and language-bound.
- Universal fix:
  Replaced planner logic with `_gui_planner.py`, which asks Carter's own backend for strict JSON UI steps and validates them.
- Key files:
  `src/carter_v2/capabilities/_gui_planner.py`
  `src/carter_v2/capabilities/gui_agent.py`
  `tests/test_gui_do_planner.py`
- Live evidence:
  Compound GUI prompts route through `gui_do` with LLM-produced step lists; no legacy regex planner remains.

## Limitation 3: Session continuity
- Root cause:
  ACTIVE APP CONTEXT was injected but not strong enough to survive short follow-ups, and app-switch detection from raw full-text matching was too weak.
- Universal fix:
  Added `ActiveAppContext` with TTL, active-app injection into turn context, short follow-up tool bias, one-shot active-app reconsideration, runtime span-based explicit switch detection, and a bounded GUI fallback only before the first tool executes.
- Key files:
  `src/carter_v2/session/types.py`
  `src/carter_v2/turn/agent.py`
  `src/carter_v2/turn/engine.py`
  `src/carter_v2/session/observer.py`
  `tests/test_agent_intent_continuity.py`
- Live evidence:
  `universal_continuity` finished with 0 failures after the final fix set.

## Limitation 4: Vision tier / OCR availability
- Root cause:
  Vision code imported OCR backends directly and degraded badly when `pytesseract` was absent.
- Universal fix:
  Centralized backend probing and routing in `vision_router.py` with tier order:
  `LLM_VISION > OMNIPARSER > PYTESSERACT > NONE`
  plus honest `next_step_hint` failures.
- Key files:
  `src/carter_v2/capabilities/vision_router.py`
  `src/carter_v2/capabilities/vision.py`
  `docs/vision_setup.md`
  `tests/test_fase17_vision.py`
- Live evidence:
  `Lee lo que hay en pantalla` now fails honestly when no vision tier is available, instead of crashing or fabricating OCR.

## Additional fixes made during closure
- Restored compatibility helpers in `vision.py` so legacy tests/imports still pass.
- Stabilized `SystemCapability.get_gpu_info()` so default shared probe cache does not contaminate unit tests.
- Hardened smoke harness restart behavior when `llama.cpp` fails to load on a fresh run.
- Clarified tool contracts for `gui_click`, `gui_type`, `notify_toast`, and scheduler tools.

## Validation summary
- `python -m pytest Carter_v2/tests/ -x -q`
  Result: `755 passed`
- Live suites executed with real Carter + real local LLM:
  `observed`
  `universal` (split into main block + tail block)
  `synthetic`
  `acceptance` (split into main block + tail block)
  `universal_continuity`
- Consolidated final smoke:
  `Carter_v2/live_smoke_results.json`
  `Carter_v2/live_smoke_results.md`
- Final aggregate:
  `54 PASS_EXECUTED`
  `24 PASS_HONEST_LIMITATION`
  `5 PASS_ROUTED_REQUIRES_CONFIRMATION`
  `0 FAIL_*`

## Anti-pattern grep result
- Runtime logic files checked:
  `turn/agent.py`
  `capabilities/gui_agent.py`
  `capabilities/_gui_planner.py`
  `capabilities/vision_router.py`
  `session/types.py`
- No natural-language keyword routing tables were introduced.
- Remaining grep hits are in:
  system-prompt/tool-description examples
  smoke harness prompt fixtures
  tests
  pre-existing non-routing interface/doc strings

## Honest limits
- `--suite all` as one shell command exceeded the shell timeout budget, so the final live report was composed from suite-by-suite real runs and then merged.
- Some GUI tasks still end as `PASS_HONEST_LIMITATION` because Steam/Discord/Spotify/Notion depend on current window state, login state, and lack of OCR/vision backends.
- Alarm creation is now routed away from fake immediate toast notifications; in the live tail run it used `scheduler_schedule_task` as a real scheduled action instead of fabricating a Clock-app alarm.
