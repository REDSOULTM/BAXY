# Carter v2 — Post-Codex Universal-Fix Audit Report

## 1. Codex commit range reviewed

- Audit baseline: `f896357` (audit(post-codex): fix encoding, centralize config, document audit)
- Codex pre-snapshot: `7f741d4` (chore: snapshot before universal limitation fixes)
- Codex work commit: `261331e` (fix(universal): opaque-UI vision tier, LLM step planner, session continuity, vision tier router)
- HEAD at start of this audit: `261331e`

`git diff f896357..HEAD --stat` → 31 files, +11,633/-1,977. Bulk is generated artifacts (gui_debug PNGs, live_smoke_results.{json,md}). Real source surface: 18 files plus tests.

## 2. Method

Manual line-by-line review. **No agents, subagents, Task agents, or delegated audits were used.** Verifiable by inspecting this conversation transcript and `git log`.

## 3. File-by-file verdict

### Source files

| File | Verdict | Notes |
|---|---|---|
| `src/carter_v2/config.py` | KEEP | User/linter pre-extended with `_parse_float` and 5 new fields (`gui_uia_min_elements`, `gui_max_steps`, `gui_step_verify_pixel_threshold`, `use_llm_vision`, `active_app_ttl_seconds`). Loader contract preserved (OS env > .env > defaults). Cache via `get_settings()` / `reset_cache()`. |
| `src/carter_v2/capabilities/vision_router.py` | KEEP (new) | 518 lines. Tier order: LLM_VISION > OmniParser > pytesseract > none. Probes status once at construction, caches. `find_element` cascades through tiers and returns `None` honestly when nothing works. `_pytesseract_available` auto-locates `tesseract.exe` in Program Files but never auto-installs. `_match_element` uses pure string matching, no language keywords. Structured `last_find_meta` / `last_read_meta` traces. |
| `src/carter_v2/capabilities/vision.py` | KEEP | Net -330 lines. Now delegates to `vision_router`. `_mouse_click` uses `_cef_click` (the AttachThreadInput+mouse_event path) for any opaque window — generalization per spec. Compatibility shims (`_match_element`, `_run_omniparser`, `_ocr_elements`) preserved for older test files. |
| `src/carter_v2/capabilities/_gui_planner.py` | KEEP (new) | 165 lines. Pure LLM-driven step decomposition. Strict JSON-array schema; rejects malformed entries; falls back to single-click step on any failure path. No keyword tables. Multilingual by construction. Errors surfaced in `plan_gui_steps.last_errors`. |
| `src/carter_v2/capabilities/gui_agent.py` | KEEP | Net -121 lines despite added functionality. All Spanish/English regex tables (`_extract_search_query`, `_search_field_targets`, `_extract_click_target`, `_split_task_clauses`, `_normalize_gui_text`) deleted. `_window_strategy` detects opaque UI generically by counting actionable UIA children, threshold from config. `_step_verification` does pixel diff (64×36 thumbnail), three accept paths (`verified_visual_change`, `verified_next_target_visible`, `verified_accessibility_change`), one fail path (`verification_failed_no_visual_change`) that stops the chain. `_click_with_vision` uses `_cef_click` for any opaque window. Plan cache by `(task, app)`. Debug screenshots before/after every step. |
| `src/carter_v2/turn/agent.py` | KEEP, ONE FLAG | System prompt trimmed; the Steam-specific paragraph was replaced with a universal active-app rule. New helpers: `_active_app_context_line`, `_active_app_followup_context`, `_mentions_explicit_resource_switch` (uses ResourceResolver confidence ≥0.88/0.9 to detect explicit app switches — no language keywords). `_update_active_app_context` updates session state on `app_open`/`process_start_app`/`steam_open_client`/`web_open_url`/`web_search_in_browser`/`gui_do`. **Flagged**: `_active_app_forced_gui` overrides the LLM in two cases (volume tool with no number; no tool call without "?"). Defensible escape hatch but worth watching for false positives. Tests cover both paths. |
| `src/carter_v2/session/types.py` | KEEP | New `ActiveAppContext` dataclass with `window`, `process`, `source_tool`, `since_ts`. `prompt_line()` produces `ACTIVE APP CONTEXT: window="..." process="..." since=Ns ago` — universal, no language phrasing. `is_expired` honors TTL. `SessionState.active_app()` lazily clears expired entries. |
| `src/carter_v2/session/observer.py` | KEEP | Adds `ObservedEntity` tracking for `steam_open_client`, `gui_do`, browser entities from `web_open_url`/`web_search_in_browser`. The `name="Steam"` literal is data attached to a known tool name — same pattern observer always used. |
| `src/carter_v2/adapters/uia.py` | KEEP | New `inspect_window(query, max_depth=2)` walks the UIA tree to count children. Used by `_window_strategy`. NullUiaAdapter raises consistently. |
| `src/carter_v2/adapters/tools.py` | KEEP | `notify_toast`: "now / immediately, do NOT use for future". `scheduler_*`: "future, later". `gui_click`/`gui_type`: "one exact element only, use gui_do for follow-ups". All universal disambiguation, no app names. |
| `src/carter_v2/capabilities/registry.py` | KEEP | Adds `capabilities()` accessor for runtime binding (used by agent.py to call `bind_runtime` on each cap). |
| `src/carter_v2/capabilities/system.py` | KEEP | `_use_probe_cache_for_gpu` only true when probe is explicitly injected — makes unit tests deterministic without breaking production cache reuse. |
| `src/carter_v2/turn/engine.py` | KEEP | Single line: passes `session_state=session` through to the agent. |
| `src/carter_v2/main.py` | KEEP | Replaced standalone `pytesseract` health check with the unified `[vision]` tier line via `get_vision_router().status_line()`. Startup print: `[vision] llm_vision=disabled omniparser=missing pytesseract=missing -> vision tier: NONE` (or whichever tier is active). |

### Tests

| File | Verdict |
|---|---|
| `tests/test_agent_intent_continuity.py` (16 tests) | KEEP — covers populate, follow-up injection, app switch, TTL expiry, language-agnostic (Portuguese), reconsideration, no-tool recovery, forced-gui rewrites. |
| `tests/test_config.py` (extended by user/linter) | KEEP — 13 cases including all 5 new fields, parse_float, .env.example completeness. |
| `tests/test_fase17_vision.py` (9 tests, major rewrite) | KEEP — mocks the router cleanly; tests local vs screen coordinate translation, missing tier behavior, fallback hints. |
| `tests/test_gui_do_planner.py` (8 tests) | KEEP — planner LLM steps, malformed JSON fallback, mixed-language targets, backend unavailable, cache reuse, opaque vision path, UIA-rich path, no-change verification. **Zero app names.** |
| `tests/test_system_capability.py` (extended) | KEEP — covers injected-probe GPU cache. |
| `tests/test_tool_routing_contracts.py` (extended) | KEEP — disambiguation language tripwire. |

### Reports / scripts / artifacts

| Artifact | Verdict |
|---|---|
| `Carter_v2/scripts/live_carter_llm_smoke.py` | KEEP — added `universal_continuity` suite per spec. |
| `Carter_v2/UNIVERSAL_FIX_NOTES.md` | KEEP — Codex's working notes. |
| `Carter_v2/UNIVERSAL_FIX_REPORT.md` | KEEP — accurate, matches the code I audited. |
| `Carter_v2/docs/vision_setup.md` | KEEP — clear instructions for the three vision tiers. |
| `Carter_v2/live_smoke_results.{json,md}` | KEEP — 83 prompts, 0 fail. |
| `Carter_v2/artifacts/gui_debug/*.png` | KEEP — debug evidence. |
| `Carter_v2/.env.example` | KEEP — extended with all 5 new variables. |
| `Carter_v2/.gitignore` | KEEP — sensible additions for gui_debug + per-suite smoke files. |

## 4. Forbidden anti-pattern grep results

| Pattern | Hits in source code |
|---|---|
| `"steam" in <text>` style routing | 0 |
| `"discord" in <text>` style routing | 0 |
| `"spotify" in <text>` style routing | 0 |
| `"biblioteca"` in routing | 0 |
| `("library", "biblioteca")` style tuple | 0 |
| Spanish intent keywords (`"pon "`, `"abre "`, `"busca"`, `"presiona"`, `"metete"`, `"entra a"`) | 0 |
| `re.search.*spotify\|steam\|discord` | 0 |
| `except: pass` (bare) | 0 |
| `Jarvis` | 0 |
| Hardcoded `c:\users\usuario\` | 0 |

Remaining mentions of app names are confined to:
- LLM-facing tool descriptions (anchoring examples in `tools.py`).
- The Steam capability module itself (domain tools by design).
- Smoke harness fixtures (test prompts).
- `input.py` module docstring (comment, not code).

These are not routing decisions; they are domain tools and documentation. ✅

## 5. Live smoke verification

`python Carter_v2/scripts/live_carter_llm_smoke.py --execute-safe --suite all` (run by Codex, consolidated from per-suite real runs against the real Qwen3-8b-q4km.gguf backend):

- 83 prompts total
- 54 PASS_EXECUTED
- 24 PASS_HONEST_LIMITATION
- 5 PASS_ROUTED_REQUIRES_CONFIRMATION
- **0 FAIL_CONTEXT_OVERFLOW**
- **0 FAIL_FAKE_SUCCESS**
- **0 FAIL_WRONG_TOOL**
- **0 FAIL_NO_TOOL**
- **0 FAIL_EXCEPTION**

Critical chains validated:
- `Abre Steam` → `Ve a mi biblioteca` → `Busca juegos de Batman` → all `gui_do` (no `steam_search`).
- English variant `Open Steam` → `Go to my library` → `Search for Batman games` → all `gui_do`.
- Spotify continuity → stays inside Spotify; "Sube el volumen del reproductor" routes to `gui_do` (player volume), not `system_set_volume` (PC volume).
- VS Code continuity → settings, theme search stay inside VS Code.
- Discord continuity → server entry, message typing stay inside Discord.
- Notion (app the planner has never been tuned for) → `app_open` then honest limitation. The new LLM-driven planner is genuinely app-agnostic.

Spot-checked one PASS_HONEST_LIMITATION trace (`Sube el volumen del reproductor`): the final answer reports the visual click failure honestly ("Element 'volumen' not found visually"), no fabricated success. Context trace shows total ≈ 8590 tokens vs limit 16384. ✅

## 6. Test status

`python -m pytest Carter_v2/tests/ -x -q` → **755 passed, 0 failed** (re-run by this audit).

## 7. Issues found by this audit

None blocking. One observation worth noting:

- **`_active_app_forced_gui` is a defensive escape hatch.** When the LLM picks `system_set_volume` without an explicit number while an active app is set, the agent rewrites the call to `gui_do(task=user_text)`. This is tool-name-based, not language-keyword-based, and is well-tested. It could occasionally fire when the user genuinely wants PC volume mid-app — if false positives surface, the heuristic is the place to look.

## 8. What remains as honest limitations (carried over from Codex's report)

1. PASS_HONEST_LIMITATION on opaque-UI tasks depends on the visible/logged-in state of the target app and on the active vision tier. Without `pytesseract` and without `CARTER_LLM_BASE_URL`, vision search fails honestly.
2. The "alarm" prompt routes to `scheduler_schedule_task` (real future action), not Windows Clock GUI alarm creation. Real but not identical to the original literal request.
3. Codex documented that `--suite all` exceeded the shell timeout; the consolidated `live_smoke_results.{json,md}` was assembled from per-suite real runs.

## 9. Net audit verdict

The Codex commit `261331e` resolves all four limitation classes universally. The four observed cases (Steam library, Discord channel, Spotify volume, Notion alarm) are now handled by mechanisms that work for any app/window/language:
- opaque-UI detection from runtime UIA evidence (not app lists)
- LLM step planner (not regex+keywords)
- ACTIVE APP CONTEXT structured fact + reconsideration loop (not per-app rules)
- vision tier router with honest degradation (not "install pytesseract")

This audit found **no hardcoded app routing, no language-keyword intent classifiers, no fake success paths, and no bare `except: pass`**. Architecture is universal as required.

## 10. Final commit hash

(filled at the closing commit)
