# Text Core Model Decision (RC1)

> Closes the model question for **CARTER_TEXT_CORE_RELEASE_CANDIDATE**.

## Decision

| role                          | model              | tool protocol | rationale |
|-------------------------------|--------------------|---------------|-----------|
| **DEFAULT_TEXT_STACK_RC**      | `qwen3:8b`         | `auto` → `openai_tools` (with content-channel fallback) | Carter's historically-validated baseline. Used by every prior closure (TEXT_FINAL_CLOSURE, ULTRA_LATENCY, FULL_LIVE_LLM, RUNTIME_TOOL_PROTOCOL). Runtime probe 5/5. |
| **RECOMMENDED_TEXT_STACK_16GB**| `hermes3:8b`       | `json_direct` | Fair leaderboard #1 (composite 0.763, tool 1.00, p95 1597ms, 4857 MiB). Selector emits this; **opt-in only**. |
| **ROLLBACK_TEXT_STACK**        | `qwen3:8b`         | `auto`        | Same as default. `Remove-Item Env:CARTER_TEXT_MODEL` reverts. |
| **FAST_TEXT_STACK_16GB**       | `llama3.2:3b`      | `json_direct` | 915 ms p95 (fastest), tool 1.00. Use when latency matters more than reasoning. |
| **QUALITY_TEXT_STACK_24GB+**   | `gpt-oss:20b`      | `openai_tools` | Top-tier composite for ≥24GB. |

## Why qwen3:8b stays as the real default

The mission rule is *"No cambiar config real sin confirmación"*. `hermes3:8b` is a **measured fair-leaderboard winner**, not a runtime-validated Carter default — it has not been live-safe-validated end-to-end as the active text model in `agent.py`. Until that validation runs, it remains a *recommended candidate*, not the default.

`qwen3:8b` has been the default through:
- TEXT_FINAL_CLOSURE (action_failed elimination).
- ULTRA_LATENCY (p95 budgets).
- FULL_LIVE_LLM_VALIDATION (scripted + live-safe + ULTRA_CAT12).
- SKIPPED_LIVE_VALIDATION (web/steam/gui-vision/compound).
- RUNTIME_TOOL_PROTOCOL_PROBE (5/5 cases).

Switching the default would require re-running all of the above with `hermes3:8b`. That's the next mission's scope, not this one.

## How to test both

```powershell
# Run with the default (qwen3:8b) — no change required:
.\run_carter_gpu.ps1

# Try the recommended candidate (hermes3:8b):
$env:CARTER_TEXT_MODEL    = 'hermes3:8b'
$env:CARTER_TOOL_PROTOCOL = 'json_direct'
.\run_carter_gpu.ps1

# Try the fast candidate (llama3.2:3b):
$env:CARTER_TEXT_MODEL    = 'llama3.2:3b'
$env:CARTER_TOOL_PROTOCOL = 'json_direct'
.\run_carter_gpu.ps1
```

## How to change without breaking

1. Set `CARTER_TEXT_MODEL` and `CARTER_TOOL_PROTOCOL` env vars.
2. Run `.\run_carter_gpu.ps1` — Carter picks up the env automatically (no code change).
3. To rollback: `Remove-Item Env:CARTER_TEXT_MODEL,Env:CARTER_TOOL_PROTOCOL -ErrorAction SilentlyContinue`.
4. The selector ([scripts/maintenance/recommend_carter_models.py](scripts/maintenance/recommend_carter_models.py)) emits the exact PowerShell block per VRAM profile.

## Load policy

| field                 | value (16GB) |
|-----------------------|--------------|
| text_keep_alive_s     | 600          |
| modal_keep_alive_s    | 0 (unload between modal calls) |
| max_vram_ratio        | 0.85         |
| concurrent_modals     | 1            |
| concurrent_voice      | 1 (text + voice OK; vision XOR voice when ≤12GB) |
| unload_text_before_modal | True      |

Source: [src/carter_v2/model_selection/load_policy.py](src/carter_v2/model_selection/load_policy.py).

## Verdict

**`DEFAULT = qwen3:8b`** stays.
**`RECOMMENDED = hermes3:8b`** documented + selector-exposed.
No real-config change shipped this RC.
