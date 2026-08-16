# Auto Model Stack Final Audit

> Pre-implementation audit for Opus-4.7 mission **CARTER AUTO-MODEL STACK FINAL**.
> Purpose: close the original Model Lab mission with a *truly adaptive* selector
> that picks the best Carter stack for any user PC (CPU-only / 6 / 8 / 10 / 12 / 16 / 24 GB),
> using the **fair-protocol** evidence (CARTER_TOOL_PROTOCOL=auto), not the
> OpenAI-native-only harness that previously biased the ranking.
>
> No code is edited in this document. This is the brutal honest map of where we
> are *before* S1–S11.

---

## 1. Veredicto brutal

Carter is **READY for the 16 GB rig the user actually owns** and **READY in
research/scaffold form** for every other VRAM profile, but **the auto-adaptive
loop is not closed end-to-end**. Specifically:

### What is already done (do not redo)

- ✅ **Runtime tool protocol wiring shipped.** `CARTER_TOOL_PROTOCOL=auto` routes per-model;
  HTTP-400 `"does not support tools"` auto-falls-back to the compat router (R5 done in
  prior mission). Verdict `RUNTIME_TOOL_PROTOCOL_READY`. See
  [RUNTIME_TOOL_PROTOCOL_FINAL_GATE.json](audit/results/RUNTIME_TOOL_PROTOCOL_FINAL_GATE.json).
- ✅ **Fair re-bench done for 16 text models × 7 protocols × 5 universal tool cases.**
  See [fair_rebench_summary.json](audit/results/model_tool_compatibility/fair_rebench_summary.json).
  4 families recovered from `0.00 native → ≥0.80` once their native channel was used.
- ✅ **Runtime probe done for 5 representative models** through real Carter backend
  (`OpenAICompatAgentBackend`). 24/25 cases pass, **0 fake_success**.
  See [RUNTIME_TOOL_PROTOCOL_PROBE.json](audit/results/RUNTIME_TOOL_PROTOCOL_PROBE.json).
- ✅ **Vision tournament smoke done** for 6 VLMs (5/6 perfect smoke).
  See [MODEL_VISION_TOURNAMENT_REPORT.md](MODEL_VISION_TOURNAMENT_REPORT.md).
- ✅ **Voice runner exists, smoke executed**: `faster-whisper:tiny` loads 398 ms,
  RTF 0.24 on CPU. See [voice_smoke_20260502-100029.json](audit/results/voice_smoke_20260502-100029.json).
- ✅ **Selector exists** in [src/carter_v2/model_selection/](src/carter_v2/model_selection/)
  with `probe_hardware`, `choose_profile` (7 buckets), `recommend()`, `LoadPolicy`,
  and a `_filter_text_chain_safe` that drops models with `supports_tools=False`.
- ✅ **Registry has `tool_protocol` per ModelEntry** (declarative — no per-model `if` in core).
- ✅ **Gates green:** pytest 481 passed, hardcode_guard 0/0.

### What is genuinely missing for "auto-adapt to any PC"

| # | Gap | Severity |
|---|---|---|
| G1 | No **per-VRAM-profile fair-protocol leaderboard**. The current `MODEL_TOURNAMENT_REPORT.md` ranks globally, not per profile. The selector implicitly relies on chains, but there is no auditable "for 6 GB the fair winner is X with composite Y" table. | high |
| G2 | Wave-1 + Wave-2 benchmarks were captured **before** the runtime fair path was wired. They used `model_benchmark.py` with native protocol, so legacy native-pass numbers leak into composite scores for phi/gemma/deepseek/phi3.5 and depress them unfairly. The fair re-bench (`tool_call_compatibility.py`) was tools-only, no text/mission. So we still lack a **fair composite** per model. | high |
| G3 | Vision tournament was a 6-case **smoke**, not a per-profile quality bench. No OCR WER, no UI grounding accuracy, no per-profile recommended VLM justified by numbers (only by VRAM fit). | medium |
| G4 | STT tournament is **research + 1-shot smoke** (`faster-whisper:tiny` CPU). Multiple engines (whisper.cpp, distil-whisper, openai-whisper) are not benched on the same fixture. No `MODEL_STT_TOURNAMENT_REPORT.md` exists. | medium |
| G5 | TTS tournament is **research only**. No `MODEL_TTS_TOURNAMENT_REPORT.md`. No live first-audio-ms bench for piper / xtts / kokoro on the rig. | medium |
| G6 | `LoadPolicy` lacks STT/TTS keep-alive fields and per-modal swap rules. `concurrent_modals` covers vision but not voice. | medium |
| G7 | `recommend_carter_models.py` has only `--quality` and `--json`. No `--profile <X>` override, no `--include-vision/voice`, no `--dry-run`, no install-plan / rollback / env-block emit. | medium |
| G8 | No `AUTO_MODEL_STACK_FINAL_GATE.json` artifact yet (this mission's closure JSON). | mission |
| G9 | `MODEL_STACK_BY_VRAM.md` predates the fair re-bench; the per-profile picks need to be reconciled against the fair leaderboard (which they are *consistent with*, but the report does not cite the fair-protocol evidence row-by-row). | low |

**No new model downloads are needed.** The 16 text models + 6 VLMs + voice runtimes
already on disk are sufficient evidence; the missing work is *consolidation,
selector wiring, and config-generator UX* — not more raw runs (with two optional
exceptions: a vision OCR fixture bench and a voice fixture bench, both feasible
on the rig in minutes).

---

## 2. Estado por perfil VRAM

Reconstructed from existing evidence: [MODEL_STACK_BY_VRAM.md](MODEL_STACK_BY_VRAM.md),
[MODEL_TOURNAMENT_REPORT.md](MODEL_TOURNAMENT_REPORT.md), [fair_rebench_summary.json](audit/results/model_tool_compatibility/fair_rebench_summary.json),
[RUNTIME_TOOL_PROTOCOL_PROBE.json](audit/results/RUNTIME_TOOL_PROTOCOL_PROBE.json).

| Perfil | Text actual (registry) | Vision | STT | TTS | Evidence | Faltante |
|---|---|---|---|---|---|---|
| cpu_only | `qwen3:1.7b` | — | `whisper.cpp:tiny` | `piper:default` | M9 + voice research | live STT bench on CPU; selector emits no-GPU policy |
| 6gb | `qwen3:4b` (fair: 1.00 with `openai_tools`) | `moondream` (smoke 1.00, 2.1 GB) | `whisper.cpp:base` | `piper:default` | M11 wave1 + vision wave3 + voice research | per-profile fair leaderboard; voice live |
| 8gb | `qwen3:8b` (1.00) | `minicpm-v` (smoke 1.00, 5.6 GB) | `faster-whisper:distil` | `piper:default` | wave1 + wave3 + research | per-profile fair leaderboard; STT engine bench |
| 10gb | `qwen3:8b` | `qwen2.5vl:7b` if VRAM permits, else `minicpm-v` | `faster-whisper:small` | `piper:default` | wave1 + wave3 + research | LoadPolicy decision rule documented |
| 12gb | `qwen3:8b` (could opt-in `gpt-oss:20b` 12.5 GB) | `qwen2.5vl:7b` | `faster-whisper:medium` | `piper:default` | wave1+2 + wave3 + research | opt-in chain in selector |
| 16gb | `qwen3:8b` (Carter actual) — opt-in `mistral-small:24b` (fair 1.00, +0.099 composite) | `qwen2.5vl:7b` (grounding) | `faster-whisper:large-v3` | `piper:default` (xtts opt-in) | wave1+2 fair + wave3 + voice smoke | MODEL_STT/TTS reports; selector "quality vs safe" toggle |
| 24gb+ | `mistral-small:24b` primary, `gpt-oss:20b` fallback | `qwen2.5vl:7b` | `faster-whisper:large-v3` | `xtts-v2` | wave2 fair + wave3 + research | live xtts bench |

**Tool protocol per profile** (from registry, post-fair-rebench):
- `qwen*` → `openai_tools` (native).
- `gpt-oss:20b`, `mistral-small:24b`, `hermes3:8b`, `llama3.1:8b` → `openai_tools` works (fair 1.00) but `json_direct` is also 1.00 fallback.
- `phi4`, `gemma3:12b`, `deepseek-r1:8b`, `granite3.3:8b`, `llama3.2:3b`, `qwen2.5-coder:14b`, `devstral:24b` → `json_direct` (their native channel — 1.00 fair).
- `phi3.5:latest` → `fenced_json` (best 0.80, still text-fallback only).

**Default behaviour:** `CARTER_TOOL_PROTOCOL=openai_native` (bit-exact legacy);
`auto` enables registry routing; `off` is the kill-switch. HTTP-400 fallback is
always on unless `off` (so even default benefits from the safety net).

---

## 3. Plan S1–S12

### S1 — Consolidated fair-protocol leaderboard (no new live runs needed)

**Inputs already on disk:**
- [audit/results/model_benchmarks/](audit/results/model_benchmarks/) — wave1+2 per-model JSONs (text/tool/mission/latency/VRAM)
- [audit/results/model_tool_compatibility/fair_rebench_summary.json](audit/results/model_tool_compatibility/fair_rebench_summary.json) — 16×7×5 fair tools matrix
- [audit/results/RUNTIME_TOOL_PROTOCOL_PROBE.json](audit/results/RUNTIME_TOOL_PROTOCOL_PROBE.json) — runtime evidence

**Output:** `audit/results/model_benchmarks_fair_runtime/CONSOLIDATED.json`
+ updated `MODEL_TOURNAMENT_REPORT.md` with a **fair composite** column where:
  ```
  fair_composite = 0.25 * fair_tool_pass + 0.30 * text_pass + 0.20 * mission_pass
                 + 0.15 * latency_score    + 0.10 * vram_score
  ```
  (Same weights as M11 composite, but tool component sourced from
  fair_rebench best-protocol pass instead of legacy native pass.)

**No new live LLM runs required for S1.** All inputs already live on disk.
*(Optional: if a model is missing a `mission` JSON, run the mission subset
for that one model only — single-load discipline preserved.)*

### S2 — Per-VRAM ranking tables

For each profile, produce a table:

| Profile | Primary | Fair composite | Tool pass | Mission pass | p95 ms | VRAM MiB | Fallback chain |
|---|---|---:|---:|---:|---:|---:|---|

Filter rule: `vram_load_mb ≤ profile.vram_budget_mb × 0.85`.
Then sort descending by `fair_composite`. Pick top-1 as primary, top-3 as chain.
Output → `MODEL_STACK_BY_VRAM.md` (refresh) + new section in `MODEL_TOURNAMENT_REPORT.md`.

### S3 — Vision per-profile (consolidate, optionally extend)

Use existing 6-VLM smoke. **Optional add:** small fixture (3–5 PNG screenshots
in `audit/fixtures/vision/`) for OCR / button-target / Spanish-text. If skipped,
state explicitly in report. Output → `MODEL_VISION_TOURNAMENT_REPORT.md` (refresh
with per-profile section).

### S4 — STT scaffold tournament

Run `audit/runners/model_voice_eval.py` against the existing fixture
([_voice_smoke_fixture.wav](audit/results/_voice_smoke_fixture.wav)) for each engine
that loads. Document WER as N/A if no reference text. Output →
`MODEL_STT_TOURNAMENT_REPORT.md` with per-profile picks + install commands +
`stt_chain` for selector.

### S5 — TTS scaffold tournament

Same shape: run piper smoke, document xtts/kokoro requirements, per-profile picks
in `MODEL_TTS_TOURNAMENT_REPORT.md`. No live audio playback; capture
`first_audio_ms` + `total_generation_ms` only.

### S6 — LoadPolicy extension

Add `stt_keep_alive_s`, `tts_keep_alive_s`, `concurrent_voice` fields to
[load_policy.py](src/carter_v2/model_selection/load_policy.py). Per-profile
defaults documented. Refresh `MODEL_STACK_BY_VRAM.md` "load policy" column.

### S7 — Selector consumes fair-protocol leaderboard

Update [selector.py](src/carter_v2/model_selection/selector.py) so the text chain
ordering is sourced from a *declarative* leaderboard (CSV/JSON in
`src/carter_v2/model_selection/data/text_leaderboard.json`) rather than hardcoded
per profile. Same for vision/stt/tts chains. **Zero per-model conditionals.**

### S8 — Config generator UX

Add to [scripts/maintenance/recommend_carter_models.py](scripts/maintenance/recommend_carter_models.py):
- `--profile {auto,cpu_only,6gb,8gb,10gb,12gb,16gb,24gb}`
- `--include-vision`, `--include-voice`
- `--dry-run` (don't write files)
- `--generate-env` (PowerShell `$env:CARTER_*=...` block)
- `--generate-install-plan` (`ollama pull` + `pip install` for missing)
- `--generate-rollback` (Copy-Item launcher.baseline → launcher)

### S9 — `MODEL_STACK_BY_VRAM.md` refresh

Single source of truth table with columns:
`VRAM | text primary | tool protocol | text fallback | vision | STT | TTS | load policy | install size | expected p95 latency | notes`.

### S10 — Final gates

Run:
```
python -m pytest -q --ignore=tests/test_main_jarvis.py -k "not live"
python audit/hardcode_guard.py
python scripts/maintenance/recommend_carter_models.py --profile auto --dry-run
python scripts/maintenance/recommend_carter_models.py --profile 6gb  --dry-run
python scripts/maintenance/recommend_carter_models.py --profile 8gb  --dry-run
python scripts/maintenance/recommend_carter_models.py --profile 12gb --dry-run
python scripts/maintenance/recommend_carter_models.py --profile 16gb --dry-run
python scripts/maintenance/recommend_carter_models.py --profile 24gb --dry-run
python scripts/maintenance/consolidate_tournament.py
```
Skip `full_live_llm_validation.py` because the 16GB primary (qwen3:8b) does not
change. Output → `audit/results/AUTO_MODEL_STACK_FINAL_GATE.json` (15 conditions).

### S11 — `AUTO_MODEL_STACK_FINAL_REPORT.md`

Final mission report with the structure mandated in the user prompt.

### S12 — Memory + cleanup

Update `/memories/repo/model_compatibility_mission.md` with the new closure
verdict + paths. Do **not** delete any models from disk; cleanup plan stays as
a *recommendation* in [MODEL_STORAGE_CLEANUP_PLAN.md](MODEL_STORAGE_CLEANUP_PLAN.md).

---

## 4. Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | Fair composite formula could disagree with legacy composite for some models, causing a "ranking churn" | Document both columns in the consolidated table; only the *fair* ranking drives the selector |
| R2 | Selector picking phi4/gemma3 (now tool-capable via `json_direct`) for 12 GB and breaking the user's qwen-trained workflows | Keep qwen3:8b as default for 8/10/12/16 GB profiles; expose recovered models only as **opt-in fallback** chain (operator must `$env:CARTER_TEXT_MODEL=...`) |
| R3 | STT/TTS bench requires fixtures | Use existing `_voice_smoke_fixture.wav`; for TTS, generate a 1-line "Hola Carter" via piper/xtts and record duration only |
| R4 | Selector regression breaking the 481-test suite | Add tests *before* refactor: `test_selector_uses_fair_leaderboard`, `test_recommend_emits_env_block`, etc. |
| R5 | Hardcode_guard catches a per-model `if` in new code | Keep all model-specific logic in `data/*.json` consumed by registry; assertions in `tests/test_hardcoded_models.py` |
| R6 | `recommend_carter_models.py --dry-run` accidentally still writes files | Test: assert files unchanged after `--dry-run` invocation |
| R7 | User on a 6 GB GPU running the recommend script gets a stack we never live-validated | Be explicit in the report: numbers are *projected from fair-protocol matrix*; only 16 GB is rig-validated end-to-end |

---

## 5. Closure conditions for this mission (preview)

`AUTO_MODEL_STACK_READY` requires (all 15 must be true in `AUTO_MODEL_STACK_FINAL_GATE.json`):

1. `AUTO_MODEL_STACK_FINAL_AUDIT.md` exists ← *this file*
2. `AUTO_MODEL_STACK_FINAL_REPORT.md` exists
3. `AUTO_MODEL_STACK_FINAL_GATE.json` exists with all 15 conditions
4. `MODEL_STACK_BY_VRAM.md` updated and cites fair evidence
5. `MODEL_TOURNAMENT_REPORT.md` includes fair composite column + per-profile section
6. `MODEL_VISION_TOURNAMENT_REPORT.md` has per-profile recommendations
7. `MODEL_STT_TOURNAMENT_REPORT.md` exists (scaffold + smoke acceptable)
8. `MODEL_TTS_TOURNAMENT_REPORT.md` exists (scaffold + smoke acceptable)
9. Selector has been validated for 6/8/10/12/16/24 + cpu_only via `--profile` flag
10. `recommend_carter_models.py` supports the new flags and emits env/install/rollback
11. `python audit/hardcode_guard.py` → 0 findings, 0 critical
12. `pytest -k "not live"` → all green
13. No per-model `if` in `agent.py` / `backends.py` / `mission.py` / selector core
14. No double load: LoadPolicy enforced; tournament runner unloads between models
15. Rollback path intact: `run_carter_gpu.ps1.baseline` exists; one-line restore documented

If conditions 7 or 8 cannot be met live (Carter has no mic/speaker capability),
verdict downgrades to `AUTO_MODEL_STACK_READY_WITH_ENV_LIMITATIONS` with explicit
list of what's blocked and how to unblock it.

---

## 6. Concrete go-ahead

This audit closes S0. Next: implement S1–S11 in order, **without further user
prompts**, gated by the user's instruction "Empieza con AUTO_MODEL_STACK_FINAL_AUDIT.md.
Después implementa S1–S11 automáticamente."

Estimated artifacts to be created or refreshed:
- 6 new/updated Markdown reports
- 1 new selector data file (`text_leaderboard.json`)
- 4–6 new selector tests
- 1 updated `recommend_carter_models.py` with ~7 new CLI flags
- 1 new final gate JSON
- 1 memory update

No new model downloads. No new live LLM training. No mutation of `.env` or
`run_carter_gpu.ps1`. Rollback baseline untouched.

End of S0.
