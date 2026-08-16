# Carter Auto Model Stack — FINAL REPORT (Opus 4.7)

> Closes mission **CARTER AUTO-MODEL STACK FINAL** (Sesión Opus 4.7).
> Companion: [AUTO_MODEL_STACK_FINAL_AUDIT.md](AUTO_MODEL_STACK_FINAL_AUDIT.md) (the brutal audit that opened the mission).
> Gate evidence: [audit/results/AUTO_MODEL_STACK_FINAL_GATE.json](audit/results/AUTO_MODEL_STACK_FINAL_GATE.json).

## 1. Executive summary

Carter now adapts automatically to **7 hardware profiles** (`cpu_only`, `6gb`, `8gb`, `10gb`, `12gb`, `16gb`, `24gb+`) using a *measured, fair* leaderboard rather than hype or installed-only bias. The selector picks text + vision + STT + TTS + load policy + tool protocol per profile, and the CLI emits a ready-to-paste PowerShell env block, install plan, and rollback recipe.

| profile | text primary | tool protocol | vision | concurrent | rationale |
|---------|--------------|---------------|--------|-----------:|-----------|
| cpu_only | `qwen3:1.7b` | json_direct | – | 1 | only sub-2GB tools-1.00 model |
| 6gb     | `qwen3:1.7b` | json_direct | `moondream` | 1 | safelist-clamped (5.1GB budget) |
| 8gb     | `hermes3:8b` | json_direct | `minicpm-v` | 1 | fair leaderboard #1 (0.763) |
| 10gb    | `hermes3:8b` | json_direct | `qwen2.5vl:7b` | 1 | same as 8GB + larger VLM |
| 12gb    | `hermes3:8b` | json_direct | `qwen2.5vl:7b` | 1 | concurrent text+vision |
| **16gb ⭐** | `hermes3:8b` (rollback `qwen3:8b`) | json_direct | `qwen2.5vl:7b` | 1 | RTX 4060 Ti — Carter operator |
| 24gb    | `gpt-oss:20b` | openai_tools | `qwen2.5vl:7b` | 2 | concurrent voice OK |

### Why hermes3:8b became the cross-profile winner

Fair re-bench (16 × 7 protocols × 5 cases): hermes3:8b scores **fair_composite 0.763** with `tool_pass=1.00` via `json_direct`, p95 1597ms, and only 4857 MiB VRAM load. It dominates the 8/10/12/16GB band. Carter still **ships qwen3:8b as the default** (rollback target) per the rule "no cambiar config real sin confirmación"; hermes3 is exposed as opt-in via `CARTER_TEXT_MODEL=hermes3:8b` + `CARTER_TOOL_PROTOCOL=auto`.

## 2. External research (S1.1–S1.3)

The mission rejected the installed-only assumption from prior Model Lab waves. This session went further and:

- **Catalogued 30+ external candidates** across text/tools/JSON/vision/STT/TTS in [MODEL_RESEARCH_MATRIX.md](MODEL_RESEARCH_MATRIX.md) and [MODEL_CANDIDATES_BY_VRAM.md](MODEL_CANDIDATES_BY_VRAM.md).
- **Pulled new candidates** to fill gaps the local inventory missed:
  - `qwen2.5:7b-instruct` (4.7 GB) — strong multilingual tool-caller for the 8/10GB band; complements hermes3:8b.
  - `mistral-nemo:12b` (7.1 GB) — multilingual mid-tier, fits the 10/12GB band.
- **Justified skips** (size/license/duplicate): `command-r-plus`, `mixtral:8x22b`, `llama3.3:70b`, `qwen3:32b`, `internvl2-llama3-76b`, `dolphin-llama3:70b`, etc.
- **STT/TTS** are non-Ollama and were left as **executable scaffolds** (live faster-whisper CPU probe; piper install commands) because Carter has no mic/speaker capability wired into the agent loop yet.

Total disk used: 26 Ollama tags ≈ 165 GB (well under the 392 GB free on C: + 5 spare drives).

## 3. Text / tools / missions ranking

Source of truth: [audit/results/model_benchmarks_fair_runtime/CONSOLIDATED.md](audit/results/model_benchmarks_fair_runtime/CONSOLIDATED.md). Ranking weights are unchanged from legacy (25% tool / 20% mission / 15% latency / 10% text / 10% multilingual / 10% VRAM / 5% stability / 5% safety). The **only** change is that the tool component is now sourced from the fair re-bench best-protocol pass, not OpenAI-native-only.

Top 10 fair composite (whole tournament, all profiles):

1. `hermes3:8b` 0.763 · json_direct · p95 1597ms · 4857 MiB
2. `granite3.3:8b` 0.748 · json_direct · 5331 MiB
3. `qwen3:1.7b` 0.732 · json_direct · 1687 MiB
4. `llama3.2:3b` 0.729 · json_direct · 915 ms (fastest tournament-wide)
5. `qwen2.5-coder:14b` 0.716 · json_direct
6. `llama3.1:8b` 0.699 · json_direct
7. `devstral:24b` 0.681 · json_direct
8. `gpt-oss:20b` 0.669 · openai_tools
9. `mistral-small:24b` 0.669 · openai_tools
10. `deepseek-r1:8b` 0.666 · json_direct (runtime probe 5/5)

`qwen3:8b` lands at #14 (0.605) — penalised by p95 31389ms thinking-mode pathology, **not** by tool failure (fair tool 1.00 + runtime probe 5/5).

## 4. Vision / screen / camera

[MODEL_VISION_TOURNAMENT_REPORT.md](MODEL_VISION_TOURNAMENT_REPORT.md) — unchanged from prior wave; per-profile picks reconciled in §1 above.

## 5. STT / transcription

[MODEL_STT_TOURNAMENT_REPORT.md](MODEL_STT_TOURNAMENT_REPORT.md) — `faster-whisper` scaffolded with live CPU probe (RTF 0.24 on `tiny`). Verdict: `STT_READY_AS_SCAFFOLD`.

## 6. TTS / voz

[MODEL_TTS_TOURNAMENT_REPORT.md](MODEL_TTS_TOURNAMENT_REPORT.md) — `piper` default for ≤16GB, `xtts-v2` at 24GB. Verdict: `TTS_READY_AS_SCAFFOLD`.

## 7. Per-VRAM stack table

See [MODEL_STACK_BY_VRAM.md](MODEL_STACK_BY_VRAM.md) — refreshed with Wave-2 + fair-leaderboard sections.

## 8. Adaptive selector

`src/carter_v2/model_selection/`:

- [hardware_probe.py](src/carter_v2/model_selection/hardware_probe.py) — VRAM/RAM/CPU/OS detection.
- [model_profiles.py](src/carter_v2/model_selection/model_profiles.py) — 7 profiles, `PROFILES_BY_NAME` mapping for `--profile` override.
- [model_registry.py](src/carter_v2/model_selection/model_registry.py) — declarative ModelEntry safelist + `tool_protocol` per model.
- [load_policy.py](src/carter_v2/model_selection/load_policy.py) — keep-alive + concurrent_voice/modal per profile.
- [selector.py](src/carter_v2/model_selection/selector.py) — fair-leaderboard reorder + `_filter_text_chain_safe` + `profile_override`.
- [data/text_leaderboard.json](src/carter_v2/model_selection/data/text_leaderboard.json) — fair-composite per-profile, regenerated by `consolidate_fair_tournament.py`.

CLI: [scripts/maintenance/recommend_carter_models.py](scripts/maintenance/recommend_carter_models.py). Validated for all 7 profiles in dry-run; produces `CARTER_MODEL_RECOMMENDATION.md` + `audit/results/MODEL_RECOMMENDATION.json` + ready-to-paste PowerShell env block + install plan + rollback recipe.

## 9. Install / cleanup

| keep        | size  | reason                              |
|-------------|------:|-------------------------------------|
| qwen3 family (1.7/4/8/14b) | ~18 GB | reference for cpu_only..16gb |
| hermes3:8b, granite3.3:8b, llama3.1:8b, llama3.2:3b | ~16 GB | top fair-composite cohort |
| qwen2.5:7b-instruct, mistral-nemo:12b | ~12 GB | new external pulls (S1.3) |
| qwen2.5-coder:14b, devstral:24b | ~23 GB | coding agentic |
| qwen2.5:32b, gpt-oss:20b, mistral-small:24b | ~46 GB | 24GB profile |
| phi4, gemma3:12b, deepseek-r1:8b, phi3.5 | ~25 GB | text-only / reasoning fallback |
| qwen2.5vl:7b, minicpm-v, llava:7b, llava-llama3, moondream | ~24 GB | vision tournament cohort |

| optional cleanup (not auto-deleted)         | size | reason |
|---------------------------------------------|-----:|--------|
| `carter-base:latest`, `carter-fast:latest`  | 18 GB | legacy fine-tunes; superseded |
| `llava-llama3:latest`                        | 5.5 GB | minicpm-v outperforms it |
| `qwen3:14b-q4_K_M` (duplicate of `qwen3:14b`)| 9.3 GB | same digest |

See [MODEL_STORAGE_CLEANUP_PLAN.md](MODEL_STORAGE_CLEANUP_PLAN.md) — operator-confirmed deletes only.

## 10. Rollback

```powershell
# revert to baseline qwen3:8b (Carter ships this default)
Remove-Item Env:CARTER_TEXT_MODEL    -ErrorAction SilentlyContinue
Remove-Item Env:CARTER_TOOL_PROTOCOL -ErrorAction SilentlyContinue
Remove-Item Env:CARTER_MODEL_PROFILE -ErrorAction SilentlyContinue
& .\run_carter_gpu.ps1
```

The selector NEVER mutates `.env` or `run_carter_gpu.ps1`. Rollback is a single env-var cleanup.

## 11. Final gates

| gate                                  | status |
|---------------------------------------|--------|
| profiles_complete                     | ✅ pass (7/7) |
| text_tournament_done (fair)           | ✅ pass (21 models) |
| external_model_research_done          | ✅ pass (30+ rows) |
| external_model_downloads_done         | ✅ pass (qwen2.5:7b-instruct, mistral-nemo:12b) |
| vision_tournament_done                | ✅ pass (5 VLMs) |
| stt_done_or_scaffolded                | ✅ pass_scaffold |
| tts_done_or_scaffolded                | ✅ pass_scaffold |
| selector_validated (per profile)      | ✅ pass |
| config_generator                      | ✅ pass |
| load_policy_per_profile               | ✅ pass |
| hardcode_guard (0/0)                  | ✅ pass |
| pytest (481 passed)                   | ✅ pass |
| no_double_load                        | ✅ pass |
| rollback_intact                       | ✅ pass |
| no_hardcodes_per_model                | ✅ pass |
| queued_models_resolved                | ✅ pass |

## 12. Verdict

**`AUTO_MODEL_STACK_READY_WITH_ENV_LIMITATIONS`**

Limitation = STT/TTS were shipped as executable scaffolds (faster-whisper live probe; piper install commands) because Carter currently has no microphone/speaker pipeline wired into the agent loop. The model layer is selector-ready end-to-end; the audio I/O layer is the next mission's work, not this one's.

Everything else closes cleanly:

1. Per-VRAM ranking complete (cpu_only..24gb).
2. Selector adaptive + validated for all 7 profiles.
3. Tool-protocol fairness baked into the leaderboard (`CARTER_TOOL_PROTOCOL=auto`).
4. Vision evaluated; STT/TTS scaffolded.
5. External research + downloads done; skips justified.
6. Pytest 481 passed; hardcode_guard 0/0.
7. Rollback intact (single env-var cleanup → qwen3:8b baseline).
8. Config generator emits PowerShell env + install plan + rollback recipe.
