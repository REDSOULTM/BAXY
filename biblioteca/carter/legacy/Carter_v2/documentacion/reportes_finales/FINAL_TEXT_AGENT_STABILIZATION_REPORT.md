# Final Text Agent Stabilization Report

## 1. Executive Summary

Carter's text-agent core was failing in four main ways before this session: it could overflow the real backend context window, confuse similar tools (especially Steam/UI/browser/media cases), fail to decompose desktop GUI tasks, and report inconsistent verification results. This session hardened the actual runtime path used by `run_carter_gpu.ps1`, added real context budgeting and turn tracing, improved tool disambiguation, expanded missing capabilities (refresh rate and keyboard layout), and added a real Carter + real LLM smoke harness.

What is now ready:

- Real 16k context runtime path with budget logging and zero live overflow across the observed, acceptance, and synthetic runs.
- Stable browser-search routing through direct URL navigation.
- Stable Windows-key / input alias handling.
- Stable refresh-rate and keyboard-layout routing to real capabilities with confirmation.
- Honest GUI/vision fallbacks for Steam/Discord/Spotify style tasks instead of fake success.
- Real live smoke artifacts plus regression coverage (`739 passed`).

Readiness verdict: Carter is ready to begin the next phase (voice, camera, transcription) with caveats. The text command kernel is now coherent and reusable, but one residual continuity edge case remains after an unverified Steam GUI step, and OCR is still degraded while `pytesseract` is missing.

## 2. Root Causes

### Context Overflow

- The live llama.cpp path still ran at `n_ctx_seq=8192` even after earlier code-side attempts to raise the limit.
- The prompt/tool budget was not enforced before sending requests.
- Focused/compact tool mode was not enough by itself; the system also needed explicit history trimming and runtime traceability.

### Wrong Tool Routing

- Similar tools were not explicitly disambiguated enough for a small local model.
- Browser search, Steam UI search, media playback, and system settings could drift into adjacent tools when the compact first pass lacked strong examples.
- Bogus executable-like URLs such as `https://Code.exe` were not normalized back to app launches.

### GUI Multi-Step Failure

- `gui_do` was originally too shallow and could treat a whole sentence as one locator.
- Multi-step app navigation needed explicit decomposition and per-step re-observation.

### CEF / Electron UI Fragility

- Steam/Discord/Spotify style apps do not expose enough reliable UIA structure.
- Carter needed to route these flows through `app_open + gui_do` with honest fallbacks, not fake success or tool substitution.

### App Resolver Gaps

- Localized names and punctuation variants were under-normalized.
- UWP / AppX launch targets resolved correctly but failed to launch because `shell:appsfolder` was being invoked incorrectly.

### Verification Problems

- Some tool paths could succeed operationally but still look failed because verification was too brittle or too slow.
- GPU and subprocess timeout handling were slow enough to break agent-loop expectations under test.

### Missing System Capabilities

- Refresh-rate and keyboard-layout changes had no end-to-end capability path.

### Input Alias Gaps

- `windows`, `win`, and related aliases were not mapped all the way down to the correct virtual key.

### Stale State / Tool Contamination

- Browser/app ambiguity and follow-up context ambiguity could still leak across turns without stronger prompt contracts and trace visibility.
- One residual continuity miss remains after an unverified Steam GUI step in the synthetic sequence.

## 3. Files Changed

- `run_carter_gpu.ps1` - aligned the launcher with the real 16k runtime context configuration.
- `Carter_v2/src/carter_v2/turn/llama_backend.py` - made the backend honor `CARTER_NUM_CTX` and capture the real context window used by llama.cpp.
- `Carter_v2/src/carter_v2/turn/agent.py` - added prompt routing fixes, context budgeting/tracing, memory guidance, browser/app disambiguation, and per-turn tool traces.
- `Carter_v2/src/carter_v2/adapters/tools.py` - strengthened tool contracts and compact descriptions so similar tools stay separable under local-model pressure.
- `Carter_v2/src/carter_v2/adapters/tool_normalizer.py` - normalized obvious mechanical misfires like executable-like fake URLs.
- `Carter_v2/src/carter_v2/capabilities/_subprocess.py` - reduced timeout cleanup latency and made timeout behavior predictable.
- `Carter_v2/src/carter_v2/capabilities/app_resolver.py` - added localized aliases and punctuation-insensitive app matching.
- `Carter_v2/src/carter_v2/capabilities/gui_agent.py` - improved multi-step GUI planning and query extraction.
- `Carter_v2/src/carter_v2/capabilities/input.py` - expanded keyboard alias handling and mouse-action coverage.
- `Carter_v2/src/carter_v2/capabilities/memory.py` - removed remaining Spanish runtime messages in the active memory path.
- `Carter_v2/src/carter_v2/capabilities/process.py` - fixed AppX/UWP launching by using `explorer.exe` for `shell:appsfolder` targets.
- `Carter_v2/src/carter_v2/capabilities/system.py` - added refresh-rate / keyboard-layout tools and moved GPU lookup to a fast first path.
- `Carter_v2/src/carter_v2/capabilities/web.py` - hardened browser launch fallback and web runtime messaging.
- `Carter_v2/src/carter_v2/session/policy.py` - added policy/risk coverage for new tools.
- `Carter_v2/src/carter_v2/turn/verification.py` - added verifiers for the new browser/input/system-setting tools.
- `Carter_v2/scripts/live_carter_llm_smoke.py` - added the required live Carter + real LLM smoke harness.
- `Carter_v2/tests/test_agent_turn_trace.py` - covered the new turn-trace contract.
- `Carter_v2/tests/test_app_resolver.py` - covered localized alias and VS Code resolution.
- `Carter_v2/tests/test_context_budget_guard.py` - covered context trimming/budget logic.
- `Carter_v2/tests/test_gui_do_planner.py` - covered GUI decomposition and search extraction.
- `Carter_v2/tests/test_input_aliases.py` - covered expanded keyboard alias handling.
- `Carter_v2/tests/test_process_capability.py` - covered AppX/UWP launch behavior.
- `Carter_v2/tests/test_system_capability.py` - aligned system mocks with the new fast helper path.
- `Carter_v2/tests/test_system_display_keyboard.py` - covered refresh-rate and keyboard-layout behavior.
- `Carter_v2/tests/test_tool_normalizer.py` - covered normalization of bogus executable URLs and related cases.
- `Carter_v2/tests/test_tool_routing_contracts.py` - covered the updated prompt/tool disambiguation rules.
- `Carter_v2/tests/test_web_browser_search.py` - covered direct browser search routing and fallback.
- `Carter_v2/live_smoke_results.json` - consolidated the final live smoke JSON.
- `Carter_v2/live_smoke_results.md` - consolidated the final live smoke markdown summary.
- `Carter_v2/FINAL_TEXT_AGENT_STABILIZATION_NOTES.md` - working notes with root causes, changes, live prompts, and limitations.
- `Carter_v2/FINAL_TEXT_AGENT_STABILIZATION_REPORT.md` - this closure report.

## 4. Live Smoke Results

The consolidated results are in `Carter_v2/live_smoke_results.md`.

High-level outcome:

- Observed failures: 13 prompts, 0 `FAIL_CONTEXT_OVERFLOW`, 0 `FAIL_WRONG_TOOL`, 0 `FAIL_NO_TOOL`.
- Universal suite: 31 prompts, 28 `PASS_EXECUTED`, 3 `PASS_HONEST_LIMITATION`, 0 `FAIL_NO_TOOL`.
- Acceptance sequence: 11 prompts, 0 wrong-tool failures remaining.
- Synthetic 10-turn run: 0 context overflows, 1 residual continuity misroute after an unverified Steam GUI step.

## 5. Remaining Limitations

- Discord visual channel selection still depends on visible UI state and a logged-in session; Carter now reports that honestly instead of hallucinating completion.
- Steam Library and Spotify GUI flows can still downgrade to `PASS_HONEST_LIMITATION` when the visible state is not confirmable or the app is not ready.
- OCR is degraded while `pytesseract` is missing on this machine.
- Changing refresh rate requires a supported mode and confirmation.
- Changing keyboard layout requires the requested layout to exist in the current session.
- Installing Steam games still requires Steam account state and confirmation.
- Residual continuity limitation: after an unverified Steam Library navigation step, a short follow-up search can still fall back to `steam_search` in the synthetic sequence.

## 6. Next Phase Readiness

### Voice

- Text command engine is stable enough to reuse.
- Non-blocking turn orchestration and interruption handling should be added before TTS/STT are layered on.
- TTS should consume the final answer boundary only, not intermediate trace/tool messages.
- STT partials should feed the same text core once a stable intent chunk is available.

### Camera

- Reuse the same GUI/vision decision layer, but add a camera-specific observation API separate from screen perception.
- Add explicit consent/activation controls and frame-source separation.
- Do not mix live camera context with screen UI context in the same implicit state channel.

### Transcription

- Add the audio capture/STT pipeline as another front-end into the same stabilized text core.
- Define speaker/event segmentation and memory-ingestion policy before durable storage of transcribed content.

### Real-Time Autonomy

- The text kernel is now strong enough to serve as the core loop, but long-running autonomy still needs interruption/cancel semantics, stronger progress reporting, and recovery after app-state drift.
- The residual synthetic continuity miss should be addressed before fully autonomous multi-step GUI workflows are trusted for long sessions.
