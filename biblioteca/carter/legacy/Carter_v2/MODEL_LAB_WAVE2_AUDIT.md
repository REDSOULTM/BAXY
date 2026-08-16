# MODEL_LAB_WAVE2_AUDIT.md

_Generated: 2026-05-02 — pre-Wave-2 inventory._

## Wave 1 (closed)

8 text/tool models benched live, single-load discipline, full M4+M5 suite:

| Model | composite | tool_pass | text_pass | vram MiB | verdict |
|-------|-----------|-----------|-----------|----------|---------|
| qwen3:8b      | 0.784 | 0.96 | 0.89 | 5 351 | WIN — current Carter baseline |
| granite3.3:8b | 0.745 | 0.52 | 0.83 | 5 331 | tool quality drop, not primary |
| qwen3:4b      | 0.743 | 0.88 | 0.94 | 3 059 | best 6 GB primary candidate |
| llama3.1:8b   | 0.723 | 0.56 | 0.81 | 5 105 | tool quality drop |
| llama3.2:3b   | 0.667 | 0.40 | 0.89 | 2 582 | only as fastest fallback |
| phi3.5        | 0.475 | 0.00 | 0.92 | 3 110 | NEVER primary (no tools) |
| deepseek-r1:8b| 0.430 | 0.00 | 0.89 | 5 350 | NEVER primary (no tools) |
| qwen3:1.7b    | 0.870 | 0.88 | 0.86 | 1 687 | smoke-only (subset) — re-run in Wave 2 with full suite for parity |

## Pulled-but-not-benched (Wave 2 queue)

All present in `ollama list`, sizes confirmed, ready to bench.

| Model | disk | est. VRAM | tool-capable? | Wave 2 plan |
|-------|------|-----------|---------------|-------------|
| hermes3:8b               | 4.7 GB | ~6 GB  | yes (tool-tuned) | BENCH |
| gemma3:12b               | 8.1 GB | ~8.5 GB| **no** (in `_NO_TOOLS_MODELS`) | BENCH text-only — never primary, only as VLM-style text |
| qwen2.5-coder:14b        | 9.0 GB | ~10 GB | yes | BENCH |
| qwen3:14b                | 9.3 GB | ~11 GB | yes | BENCH |
| phi4:latest              | 9.1 GB | ~10 GB | **no** (in `_NO_TOOLS_MODELS`) | BENCH text-only |
| mistral-small:24b        | 14 GB  | ~14.5 GB | yes (24B Mistral) | BENCH (borderline 16 GB; KV at ctx 4096) |
| gpt-oss:20b              | 13 GB  | ~13.5 GB | yes (OpenAI GPT-OSS) | BENCH |
| devstral:24b             | 14 GB  | ~14.5 GB | yes (code-agentic) | BENCH (borderline 16 GB) |

## Pulled-but-SKIP_WITH_REASON

| Model | disk | reason |
|-------|------|--------|
| qwen2.5:32b-instruct-q4_K_M | 19 GB | Exceeds 16 GB VRAM with any meaningful KV cache; would force CPU offload and skew latency/composite. Re-evaluate only on a 24 GB+ rig. Status: **SKIP_VRAM_OUT_OF_PROFILE** |
| carter-base / carter-fast   | 9.3 GB ×2 | Legacy fine-tunes superseded by qwen3:8b. Cleanup-candidate per `MODEL_STORAGE_CLEANUP_PLAN.md`. Status: **DO_NOT_BENCH** |
| llava-llama3                | 5.5 GB | Vision-only; will be evaluated in Wave 3 vision tournament. |

## External candidates considered but NOT pulled

| Model / family | Reason for NOT pulling |
|----------------|------------------------|
| qwen3:32b (raw)            | Already covered by qwen2.5:32b family which is local; same VRAM footprint, no clear gain. |
| llama3.3:70b, llama3.1:70b | ~40 GB VRAM at q4 — out of 16 GB profile. |
| qwen2.5:72b                | ~45 GB VRAM at q4 — out of profile. |
| command-r-plus, mixtral 8x22B | >30 GB VRAM at q4 — out of profile. |
| llava:13b, llava:34b       | Public benchmarks show qwen2.5vl:7b matches/exceeds them on grounding (M1 research); local already. |
| kokoro (TTS)               | Only useful once Carter exposes a speaker capability — defer to scaffold. |
| bark, xtts-v1              | xtts-v2 dominates per public benchmarks; pulling more TTS without a speaker integration is wasted disk. |
| vosk (STT)                 | WER worse than whisper.cpp tiny on EN/ES — no reason to add. |

## Vision (Wave 3 queue)

None benched yet by `audit/runners/model_vision_eval.py`. Available locally:

| Model | est. VRAM | role | plan |
|-------|-----------|------|------|
| moondream:latest    | ~1.9 GB | ultra-light describe          | BENCH (6 GB tier) |
| llava:7b            | ~5.2 GB | describe                      | BENCH (8 GB tier) |
| llava-llama3:latest | ~5.8 GB | describe + reasoning          | BENCH (8 GB tier) |
| minicpm-v:latest    | ~5.8 GB | OCR + describe                | BENCH (8 GB tier) |
| qwen2.5vl:7b        | ~6.3 GB | grounding (Carter find_element) | BENCH (12+ GB tier) |
| gemma3:12b          | ~8.4 GB | VLM (no tools)                | BENCH (16 GB tier) |

## Voice (Wave 4 status)

Carter today exposes **no microphone or speaker capability** (no entries in
`tool_catalog.py` for `record_audio`, `speak`, `play_audio`, `mic_capture`).
Therefore live STT/TTS *integration* cannot be benchmarked end-to-end.

What WILL be done in W2-4:
- Verify `audit/runners/model_voice_eval.py` runs offline-probe mode.
- Generate audio fixtures (silence + tone) using stdlib `wave` so the
  scaffold has deterministic input.
- Document the exact `pip install` / runtime commands per profile in
  `VOICE_MODEL_RESEARCH.md` (already done — re-verify).
- Ship `MODEL_VOICE_TOURNAMENT_REPORT.md` with **NOT_EXECUTED_ENV_LIMITATION**
  status and per-profile recommendations from public model cards
  (faster-whisper distil-large-v3, whisper.cpp tiny/base, Piper, XTTS-v2).

## Profiles still missing a live winner

| Profile  | wave 1 fits | gap                                       |
|----------|------------|--------------------------------------------|
| cpu_only | (none — backend would be llama-cpp CPU) | Unverified empirically; qwen3:1.7b on CPU is reasonable per public cards, but skip live bench (slow, mainly proves nothing new). |
| 6 GB     | qwen3:4b 0.743 | Confirmed. |
| 8 GB     | qwen3:8b 0.784 | Confirmed; need to also try hermes3:8b in W2 to be sure. |
| 10 GB    | qwen3:8b (only candidate in band) | Need wave-2 14B class to confirm 8b still wins. |
| 12 GB    | qwen3:8b (only candidate in band) | Wave-2 qwen3:14b / qwen2.5-coder:14b candidates. |
| 16 GB    | qwen3:8b (only candidate in band) | Wave-2 mistral-small / gpt-oss / devstral candidates. |
| 24 GB    | none yet — out of hardware | Document recommended stack from registry, no live bench. |

## Plan for Wave 2 (text/tool)

Sequential (no parallel), keep_alive=0 between models, max one model in
GPU at a time. Order chosen so that bigger/longer runs come last and the
process can be interrupted without losing the cheap wins:

1. hermes3:8b  (8 GB tier completion)
2. qwen3:1.7b  (full suite, replace smoke)
3. qwen3:14b   (12 GB tier)
4. qwen2.5-coder:14b (12 GB tier)
5. gemma3:12b  (text-only no-tools sanity)
6. phi4        (text-only no-tools sanity)
7. gpt-oss:20b (16 GB borderline)
8. mistral-small:24b (16 GB borderline)
9. devstral:24b (16 GB borderline)

Each writes to `audit/results/model_benchmarks/<model>/<ts>.json`. Final
consolidator regenerates `MODEL_TOURNAMENT_REPORT.md`.

## Acceptance criteria carried over

- tool_pass < 0.70 → cannot be primary (mark "secondary/text-only").
- VRAM > profile budget → not eligible.
- Slower AND lower composite than qwen3:8b → not a replacement.
- composite must beat qwen3:8b by ≥ 0.03 AND tool_pass ≥ qwen3:8b for
  any new "default" recommendation. Otherwise rollback wins.
