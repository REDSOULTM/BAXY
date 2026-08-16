# Carter v2 — Post-Codex Universal-Fix Audit Notes

## Codex commit range
- Audit baseline: `f896357` (audit(post-codex): fix encoding, centralize config, document audit)
- Codex pre-snapshot: `7f741d4` (chore: snapshot before universal limitation fixes)
- Codex work commit: `261331e` (fix(universal): opaque-UI vision tier, LLM step planner, session continuity, vision tier router)
- HEAD: `261331e`

## Files Codex changed (real source)
- `src/carter_v2/turn/agent.py` — system prompt, active-app continuity, focused tool routing
- `src/carter_v2/capabilities/gui_agent.py` — gui_do mini-agent rewrite
- `src/carter_v2/capabilities/_gui_planner.py` — NEW: LLM step planner
- `src/carter_v2/capabilities/vision_router.py` — NEW: vision tier router (LLM_VISION > OmniParser > pytesseract > none)
- `src/carter_v2/capabilities/vision.py` — major rewrite to use router
- `src/carter_v2/capabilities/system.py` — likely changes
- `src/carter_v2/session/observer.py` — likely active-app tracking
- `src/carter_v2/session/types.py` — SessionState extended
- `src/carter_v2/adapters/uia.py` — likely added introspection helpers
- `src/carter_v2/adapters/tools.py` — possible tool description tweaks
- `src/carter_v2/main.py` — startup hook for vision router
- `src/carter_v2/turn/engine.py` — small wiring
- `src/carter_v2/capabilities/registry.py` — small wiring
- `src/carter_v2/config.py` — additional fields (already user-modified)

## Tests
- `tests/test_agent_intent_continuity.py` (extended)
- `tests/test_config.py` (extended; user-modified)
- `tests/test_fase17_vision.py` (372 line change — major)
- `tests/test_gui_do_planner.py` (extended)
- `tests/test_system_capability.py` (extended)
- `tests/test_tool_routing_contracts.py` (extended)

## Reports
- `Carter_v2/UNIVERSAL_FIX_NOTES.md`
- `Carter_v2/UNIVERSAL_FIX_REPORT.md`
- `Carter_v2/docs/vision_setup.md` (new)
- `Carter_v2/live_smoke_results.{json,md}` (regenerated)
- `Carter_v2/.env.example` (extended; user-modified)
- `Carter_v2/.gitignore` (extended)

## Manual review log
(filled below)
