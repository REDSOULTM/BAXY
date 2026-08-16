# Universal Fix Report

## Summary
Four remaining failure classes were closed with universal mechanisms rather than prompt-specific hacks:
- opaque-window GUI fallback now uses runtime evidence instead of app lists
- GUI planning now uses the real LLM instead of regex/keyword decomposition
- session continuity now keeps an active-app fact and rescues short follow-ups inside the current window
- vision/OCR now routes through a single tiered backend with honest degradation

Regression coverage is green at `755 passed`, and the consolidated live run ended with `0 FAIL_*` across `83` real prompts.

## Root Causes And Fixes
### 1. Opaque UI fallback
UIA-only assumptions failed on Electron/CEF/opaque apps. The fix was to measure accessible actionable elements at runtime, switch to opaque-window mode when the tree is too sparse, and verify each GUI step with screenshots plus pixel-diff checks. This is not tied to Steam, Discord, Spotify, or any named app list.

### 2. Regex GUI planner
The old GUI planner embedded language-specific regexes and keyword fragments. It was replaced by `capabilities/_gui_planner.py`, which asks Carter's own backend for strict JSON UI steps and validates the returned schema. If parsing fails, the fallback is explicit and recorded.

### 3. Session continuity
The active window fact existed but was too weak in practice. The fix was:
- track `ActiveAppContext` with TTL
- inject `ACTIVE APP CONTEXT: ...` on every relevant turn
- bias short follow-ups away from low-level/suspicious tool families
- run one reconsideration pass when the model still tries to leave the active window
- detect explicit app/window/process switches from runtime resource evidence over text spans, not language keyword tables

### 4. Vision/OCR availability
Direct OCR imports caused brittle degradation when `pytesseract` was missing. The fix was a shared `vision_router.py` with a strict priority order:
`LLM_VISION > OMNIPARSER > PYTESSERACT > NONE`
Every caller now gets either a real backend result or an honest `next_step_hint`.

## Files Changed
- `.env.example` — documented the new GUI/vision/continuity settings
- `.gitignore` — ignored GUI debug artifacts and intermediate suite outputs
- `scripts/live_carter_llm_smoke.py` — added continuity suite, robust backend restart-on-load-failure, and consolidated live reporting support
- `src/carter_v2/config.py` — added typed settings for opaque-window, vision, and active-app continuity
- `src/carter_v2/main.py` — replaced ad-hoc OCR startup warning with unified vision-tier status
- `src/carter_v2/adapters/tools.py` — clarified GUI, notification, and scheduler tool contracts
- `src/carter_v2/adapters/uia.py` — added shallow window inspection for opaque-window detection
- `src/carter_v2/capabilities/_gui_planner.py` — new LLM-backed GUI step planner
- `src/carter_v2/capabilities/gui_agent.py` — removed regex planner path and added verified multi-step execution
- `src/carter_v2/capabilities/registry.py` — exposed registry capability iteration for runtime binding
- `src/carter_v2/capabilities/system.py` — made GPU info retrieval deterministic when no explicit probe is injected
- `src/carter_v2/capabilities/vision.py` — switched to router-backed implementation and kept legacy helper compatibility
- `src/carter_v2/capabilities/vision_router.py` — new shared tiered vision backend router
- `src/carter_v2/session/observer.py` — updated app/window observations for active-context continuity
- `src/carter_v2/session/types.py` — added `ActiveAppContext` and TTL handling
- `src/carter_v2/turn/agent.py` — added active-app continuity routing, reconsideration, and prompt updates
- `src/carter_v2/turn/engine.py` — passed `session_state` into the agent runtime
- `docs/vision_setup.md` — documented LLM vision, Tesseract, and OmniParser setup
- `tests/test_agent_intent_continuity.py` — added continuity, reconsideration, and fallback tests
- `tests/test_config.py` — covered the new settings
- `tests/test_fase17_vision.py` — covered the router tier behavior
- `tests/test_gui_do_planner.py` — covered opaque-window branching and step verification
- `tests/test_system_capability.py` — covered injected-probe GPU cache behavior
- `tests/test_tool_routing_contracts.py` — covered updated prompt/tool disambiguation

## Live Validation
Real live runs were executed against Carter's actual runtime path and local LLM backend. The final consolidated files are:
- `Carter_v2/live_smoke_results.json`
- `Carter_v2/live_smoke_results.md`

Final aggregate:
- `PASS_EXECUTED: 54`
- `PASS_HONEST_LIMITATION: 24`
- `PASS_ROUTED_REQUIRES_CONFIRMATION: 5`
- `FAIL_*: 0`

Important prompt families that now behave correctly:
- Steam library continuity no longer falls back to `steam_search` on the follow-up chain
- Spotify follow-ups stay inside the active app and no longer jump to system volume for player-volume prompts
- VS Code follow-ups stay inside VS Code instead of falling out to browser search
- Discord follow-ups keep `gui_do` continuity with honest limitations
- Immediate toast notifications are no longer used to fake a future alarm

## Anti-pattern Grep
Checked runtime logic for:
- hardcoded language routing fragments
- app-name keyword classifiers
- regex routing tied to Steam/Spotify/Discord

Result:
- no keyword-based intent routing was introduced in runtime logic
- remaining hits are confined to:
  prompt/tool examples
  smoke prompt fixtures
  tests
  pre-existing interface/doc strings

## Honest Limits
- The single-command `--suite all` run exceeded the shell timeout budget, so the final `live_smoke_results.*` files were composed from suite-by-suite real runs and then merged.
- `PASS_HONEST_LIMITATION` remains expected for opaque UI tasks when the app is open but the visible state, login state, or installed vision tier prevents proof of completion.
- The alarm prompt now routes to a real future action (`scheduler_schedule_task`) instead of a fake immediate toast. That is a real scheduled action, but it is not the same as proving Windows Clock GUI alarm creation.
