# REAL RUNTIME — LIVE REPRO REPORT

**Mission:** Verify the previously-claimed `CARTER_TEXT_CORE_RC_AFTER_REAL_RUNTIME_FIXES`
gate against a *real* LLM. The prior closure rested only on pytest +
hardcode_guard + dry-run repro and explicitly deferred the live run. This
report executes that pending step honestly and reports what *actually* happens
when the engine talks to a real model.

## Environment

- Repo: `C:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI\Carter_v2`
- OS: Windows
- LLM backend: Ollama on `http://localhost:11434/v1`
- Model: `qwen3:8b` (5.2 GB GGUF)
- Backend selector: `_auto_backend()` (production path) → `OpenAICompatAgentBackend`
- Env: `CARTER_BACKEND=ollama; CARTER_LLM_BASE_URL=http://localhost:11434/v1; CARTER_LLM_API_KEY=ollama; CARTER_LLM_MODEL=qwen3:8b; CARTER_DRY_RUN_DESTRUCTIVE=1; CARTER_BLOCK_INSTALL=1; CARTER_TIMING=1`

## Runner

The repro runner [audit/runners/real_runtime_transcript_repro.py](Carter_v2/audit/runners/real_runtime_transcript_repro.py)
in `--mode safe-live` was originally broken: it imported a non-existent
`build_default_registry` symbol. It now uses the *real* production factory:

```python
from carter_v2.main import _build_registry
from carter_v2.turn.agent import _auto_backend
...
registry = _build_registry(probe, memory=memory, skills=skills)
backend = _auto_backend()
if not getattr(backend, "available", False):
    return [{"id": 0, "status": "error",
             "error": "backend_unavailable: set CARTER_LLM_BASE_URL/API_KEY/MODEL"}]
engine = AssistantEngine(registry=registry, agent_backend=backend, probe=probe)
```

This is the same wiring `run.py` uses in production.

## Results — 3 / 13 PASS

Raw data: [audit/results/REAL_RUNTIME_TRANSCRIPT_REPRO.json](Carter_v2/audit/results/REAL_RUNTIME_TRANSCRIPT_REPRO.json)
Stderr trace: [audit/results/REAL_RUNTIME_LIVE_REPRO.log](Carter_v2/audit/results/REAL_RUNTIME_LIVE_REPRO.log)

| # | Input | Status | Latency | Tools called | Real failure |
|---|---|---|---|---|---|
| 1 | `a` | FAIL | 30.4s | — | Cold qwen3:8b warm-up; 1 LLM call, no tools (correct shape, latency over budget) |
| 2 | `que?` | **PASS** | 6.1s | — | — |
| 3 | `abre steam` | **PASS** | 15.2s | `app_open` | — |
| 4 | `saca un pantallazo` | FAIL | 50.5s | `gui_do`, `screen_capture_to_file` | LLM dispatched `gui_do` first (no-op) before the correct `screen_capture_to_file`; PNG was actually written (131 KB) |
| 5 | `Pon volumen 20` | FAIL | 9.6s | — | LLM responded "no tengo capacidad"; `system_set_volume` not surfaced in the focused tool catalog |
| 6 | `mutea el pc` | FAIL | 63.8s | `gui_do` | `gui_do` 30 s timeout instead of `system_mute`; window guard couldn't fire (no user nouns to match) |
| 7 | `cierra youtube` | FAIL | 61.2s | `gui_do` | `gui_do` 30 s timeout — guard didn't catch it because window_title arg did not contain "youtube" |
| 8 | `maximiza whatsapp` | FAIL | 97.2s | `gui_do` | Same — `gui_do` hangs on phantom target |
| 9 | `quien soy yo?` | FAIL | 96.9s | `gui_do`, `notify_toast` | Session contamination from prior failed mute turn; gui_do timeout |
| 10 | `a` (post-GUI) | FAIL | 92.3s | `steam_list_installed`, `gui_do`, `steam_list_installed`, `notify_toast` | After Steam-flow turns, single-letter "a" still triggered tool dispatch |
| 11 | `Estoy trabajando en intelectra en placilla` | **PASS** | 8.3s | — | Reply opens with `(memory_save) {...}`, no verbatim echo |
| 12 | `abre steam y instala fall guys` | FAIL | 38.1s | `app_open`, `steam_install` | RUNTIME-7 discriminator works (no contradiction); failure is latency only (>30 s) |
| 13 | `Por eres tan inutil` | FAIL | 27.5s | `gui_do` | **WINDOW GUARD FIRED CORRECTLY**: reply = `Refused to act on window 'Steam': the user mentioned ['eres', 'inutil'] but none of those names appear in the target window`. No GUI side effect. Counted as fail per contract because a tool call was *dispatched* before being structurally blocked. |

### What the live run actually proves

Working in production:

- RUNTIME-5 — `screen_capture_to_file` writes a real PNG file (#4 evidence).
- RUNTIME-6 — `_validate_window_target_or_block` blocks mismatched targets (#13 evidence; exact guard message in the reply).
- RUNTIME-7 — Steam install discriminator no longer contradicts itself (#12 message is internally consistent).
- RUNTIME-8 — declarative facts are routed to `memory_save` instead of being echoed verbatim (#11 evidence).
- Trivial conversational turns succeed (#2, #3 evidence).

Still broken (root causes identified, NOT yet fixed):

1. **`gui_do` hangs 30 s on phantom targets** (#6, #7, #8, #9, #10, #13). Root cause: `gui_do` never short-circuits when the target window doesn't exist; it spins through the full UIA timeout. The window guard only fires when the LLM passes a window_title containing user-named nouns; when it passes `""` or the active window, the guard skips and `gui_do` is dispatched.
2. **`system_mute` / `system_set_volume` not surfaced** (#5, #6). The focused tool catalog produced by `select_tools_for_turn` does not rank these tools high enough for "mutea el pc" / "pon volumen 20", so the LLM either claims it lacks the capability or falls back to `gui_do`.
3. **Trivial-input session contamination** (#10). After several Steam-flow turns the LLM is primed to invent `steam_list_installed` / `gui_do` calls on the next single-letter prompt. The trivial-input `hint_no_tools = True` override is in place inside `AgentEngine.run()` (agent.py L987) but a tool-bearing path still reaches dispatch — likely an earlier intent shortcut in `AssistantEngine` runs before the override can suppress tools.
4. **Cold qwen3:8b warm-up ~18-30 s** (#1, #10). Not a Carter bug — model first-token cost on a cold Ollama process. The 8 s contract budget is unrealistic without a pre-warm.
5. **Steam install latency** (#12). Functionally correct; takes 38 s end-to-end versus the 30 s contract.

## Next exact fixes

| # | File | Fix |
|---|---|---|
| 1 | `src/carter_v2/capabilities/gui.py` | At the start of `gui_do`, when `window_title` is provided and `find_window_by_title(window_title)` returns `None`, return `CapabilityResult(ok=False, message=f"Window '{window_title}' is not currently open.", errors=["window_not_open"], next_step_hint="Open the app first via app_open / process_start_app.")` immediately. Caps the 30 s timeout to <100 ms honest failure. |
| 2 | `src/carter_v2/adapters/tools.py` (descriptions) and/or `select_tools_for_turn` | Ensure `system_mute` / `system_set_volume` descriptions contain Spanish keywords ("mutear", "silenciar", "volumen", "subir", "bajar") so semantic ranking promotes them on Spanish prompts. Or expand the focused pool when the prompt contains volume/mute keywords. |
| 3 | `src/carter_v2/turn/engine.py` (`AssistantEngine.run` / shortcut paths) | Apply the same `_is_trivially_short_input(user_text)` guard *before* any Steam/intent shortcut so single-letter inputs cannot reach tool dispatch via a non-`AgentEngine.run` path. |
| 4 | env / runtime | Pre-warm the model: `ollama run qwen3:8b ""` once at startup, OR raise the per-turn budget for the first turn after cold start. |
| 5 | `src/carter_v2/capabilities/steam.py` (`_install_game`) | Fast-path: if Steam process was just launched by this turn, skip the second 8 s settle-and-poll wait when the install dialog already disappeared. |

## Regression gates (still green)

- `python -m pytest -q --ignore=tests/test_main_jarvis.py -k "not live"` → **481 passed, 1 deselected**.
- `python audit/hardcode_guard.py` → **0 findings, 0 critical**.
- `python audit/runners/real_runtime_transcript_repro.py --mode dry-run` → **REAL_RUNTIME_REPRO_OK 13/13** (dry-run, structural only).

## Honest verdict

**`PARTIAL_WITH_NEXT_STEP`** — the live run was actually executed; some of the
RUNTIME-* fixes work in production (proven by #11, #12, #13 evidence above);
the remaining failures map to specific structural bugs with named next fixes.
The previous `CARTER_TEXT_CORE_RC_AFTER_REAL_RUNTIME_FIXES` verdict was
inflated and is hereby revoked.
