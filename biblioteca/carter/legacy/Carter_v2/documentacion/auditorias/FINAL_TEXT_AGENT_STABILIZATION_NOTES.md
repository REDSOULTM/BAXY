# Final Text Agent Stabilization Notes

## Root Causes Found

- Context overflow was caused by a real runtime mismatch: the live llama.cpp path was still using an 8192 token context window while the prompt/tool budget assumed more headroom.
- The first-pass tool catalog was still large enough that prompt growth and multi-turn history could overflow the backend without a proactive budget guard.
- Steam tool descriptions were not strong enough to stop the local model from confusing Steam Library UI navigation with `steam_run` or `steam_search`.
- `gui_do` originally treated a whole natural-language instruction like `click Library tab, type batman in the search box` as one visual target instead of decomposing it into atomic steps.
- Browser-search requests in Spanish could drift into `app_open + gui_do` because the browser-search contract was not explicit enough in compact mode.
- `app_open` could resolve UWP / AppX apps correctly but then fail to launch them because `shell:appsfolder\...` targets were being passed to `Start-Process -FilePath` directly.
- `web_open_url` could accept bogus executable-like URLs such as `https://Code.exe`; this required mechanical normalization back to `app_open`.
- The Windows key alias map was incomplete, so `windows` / `win` style requests failed at the low-level input layer.
- Refresh-rate and keyboard-layout requests had no real end-to-end capability path before this session.
- GPU / PowerShell subprocess paths were too slow and brittle under test, which surfaced as agent timeouts until the fast GPU lookup and tighter subprocess kill path were added.
- Carter had no durable live trace for tool choice / verification / context-budget debugging before this session.

## Files Changed

- `run_carter_gpu.ps1` - defaulted the runtime to `CARTER_NUM_CTX=16384` so the launch script matches the code path.
- `Carter_v2/src/carter_v2/turn/llama_backend.py` - made llama.cpp context size env-configurable and recorded the actual backend `n_ctx`.
- `Carter_v2/src/carter_v2/turn/agent.py` - added context-budget tracing, stronger routing rules, per-turn tool tracing, browser/app disambiguation, memory-save guidance, and follow-up continuity guidance.
- `Carter_v2/src/carter_v2/adapters/tools.py` - tightened long and compact tool descriptions so similar tools are explicitly disambiguated.
- `Carter_v2/src/carter_v2/adapters/tool_normalizer.py` - normalized executable-looking bogus URLs back to `app_open` and preserved other high-confidence normalizations.
- `Carter_v2/src/carter_v2/capabilities/gui_agent.py` - improved multi-step GUI decomposition and fixed search-query extraction for compound UI tasks.
- `Carter_v2/src/carter_v2/capabilities/app_resolver.py` - added localized aliases and punctuation/case normalization for app names such as `Bloc de notas`, `Calculadora`, `VS Code`, and `Opera GX`.
- `Carter_v2/src/carter_v2/capabilities/process.py` - launched AppX / `shell:appsfolder` apps through `explorer.exe` instead of the broken direct `Start-Process -FilePath` route.
- `Carter_v2/src/carter_v2/capabilities/web.py` - improved browser launch fallback and cleaned runtime web/browser messages.
- `Carter_v2/src/carter_v2/capabilities/input.py` - expanded keyboard aliases and exposed mouse move / scroll tooling.
- `Carter_v2/src/carter_v2/capabilities/system.py` - added refresh-rate / keyboard-layout tools and moved GPU lookup onto the fast path first.
- `Carter_v2/src/carter_v2/capabilities/memory.py` - cleaned remaining runtime memory messages.
- `Carter_v2/src/carter_v2/capabilities/_subprocess.py` - reduced timeout cleanup latency so killed child processes do not stall turns or tests.
- `Carter_v2/src/carter_v2/session/policy.py` - classified new GUI/input/system-setting tools for confirmation/risk handling.
- `Carter_v2/src/carter_v2/turn/verification.py` - added verification hooks for browser search, display, keyboard layout, and mouse actions.
- `Carter_v2/scripts/live_carter_llm_smoke.py` - added the real Carter + real LLM smoke harness requested for closure.
- `Carter_v2/tests/test_input_aliases.py` - covered key alias expansion.
- `Carter_v2/tests/test_system_display_keyboard.py` - covered refresh-rate and keyboard-layout capability validation.
- `Carter_v2/tests/test_web_browser_search.py` - covered browser-search helper behavior and browser fallback.
- `Carter_v2/tests/test_gui_do_planner.py` - covered GUI task decomposition and search extraction.
- `Carter_v2/tests/test_agent_turn_trace.py` - covered the new live per-turn trace format.
- `Carter_v2/tests/test_context_budget_guard.py` - covered budget trimming / guard logic.
- `Carter_v2/tests/test_tool_routing_contracts.py` - covered prompt/tool disambiguation for browser/media/system/memory routing.
- `Carter_v2/tests/test_tool_normalizer.py` - covered normalization of bogus executable URLs and other mechanical fixes.
- `Carter_v2/tests/test_app_resolver.py` - covered localized aliases and `VS Code` / `Code` resolution.
- `Carter_v2/tests/test_process_capability.py` - covered AppX launch through `explorer.exe`.
- `Carter_v2/tests/test_system_capability.py` - updated mocks to the new fast helper contract.
- `Carter_v2/live_smoke_results.json` - consolidated final live smoke JSON output.
- `Carter_v2/live_smoke_results.md` - consolidated final live smoke markdown report.

## Live Prompts Tested

### Observed Failures

- `PASS_HONEST_LIMITATION` - `Entra a steam y busca juegos de batman en mi biblioteca`
- `PASS_HONEST_LIMITATION` - `Entra a steam, ve a mi biblioteca y busca juegos de batman`
- `PASS_EXECUTED` - `Fall guys esta instalado?`
- `PASS_HONEST_LIMITATION` - `Puedes instalar Fall Guys en Steam?`
- `PASS_EXECUTED` - `Entra a opera y busca batman`
- `PASS_EXECUTED` - `Entra a opera gx y busca batman`
- `PASS_EXECUTED` - `Pon el volumen del pc 20`
- `PASS_EXECUTED` - `Pon una canción en Spotify`
- `PASS_EXECUTED` - `Abre youtube y pon un video`
- `PASS_EXECUTED` - `Aprieta la tecla windows`
- `PASS_ROUTED_REQUIRES_CONFIRMATION` - `Pon mi pantalla a 60hz pls`
- `PASS_ROUTED_REQUIRES_CONFIRMATION` - `Pon el idioma del teclado en ingles`
- `PASS_HONEST_LIMITATION` - `Metete a discord y metete al canal con un personaje redondo con gafas y amarillo`

### Universal Coverage

- 31 universal prompts executed.
- 28 classified `PASS_EXECUTED`.
- 3 classified `PASS_HONEST_LIMITATION`.
- 0 classified `FAIL_CONTEXT_OVERFLOW`.
- 0 classified `FAIL_NO_TOOL`.

### Acceptance Sequence

- 11 acceptance prompts executed.
- 7 classified `PASS_EXECUTED`.
- 2 classified `PASS_HONEST_LIMITATION`.
- 2 classified `PASS_ROUTED_REQUIRES_CONFIRMATION`.
- 0 wrong-tool failures remain in the acceptance sequence.

### Synthetic 10-Turn Context Run

- 10 prompts executed with the real backend at `ctx_limit=16384`.
- 0 context overflows occurred.
- 1 residual routing miss remains: after an unverified Steam Library GUI step, `Busca juegos de Batman` fell back to `steam_search` instead of `gui_do`.

## Remaining Limitations

- Steam/Discord/Spotify GUI tasks still depend on visible logged-in app state; Carter now fails honestly there instead of faking success.
- `pytesseract` is still missing on this machine, so OCR-heavy visual reads are degraded; Carter can still fall back to other vision paths when available.
- Refresh-rate and keyboard-layout changes correctly route to real tools and confirmation, but final execution still depends on the target mode/layout actually existing on the machine.
- A residual continuity edge case remains in the synthetic Steam follow-up sequence after an unverified GUI navigation step.
