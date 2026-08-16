# MODEL CANDIDATES BY VRAM (S1.2 — Auto Model Stack)

> Generated as part of mission **CARTER AUTO-MODEL STACK FINAL** (Opus 4.7).
> Drives: `src/carter_v2/model_selection/data/text_leaderboard.json`
> (machine-readable; produced by `scripts/maintenance/consolidate_fair_tournament.py`).
>
> Tool/composite scores below come from the **fair re-bench** under
> `CARTER_TOOL_PROTOCOL=auto` (16 models × 7 protocols × 5 cases) — not the
> legacy OpenAI-native-only column. See [audit/results/model_benchmarks_fair_runtime/CONSOLIDATED.md](audit/results/model_benchmarks_fair_runtime/CONSOLIDATED.md).

## Selection rule

For each VRAM band:

1. **Primary text** = top of fair leaderboard for that profile
   (`fair_tool_pass ≥ 0.80` mandatory, `quality_tier ≥ 2` preferred).
2. **Fallback text chain** = next 2–3 entries that fit `text_budget_mb`,
   intersected with the registry safelist (`_filter_text_chain_safe`).
3. **Vision** = best VLM whose `est_vram_mb ≤ vision_budget_mb`. For
   ≤8 GB profiles vision is *on-demand only* (no co-residency).
4. **STT/TTS** = scaffold defaults from
   [MODEL_STT_TOURNAMENT_REPORT.md](MODEL_STT_TOURNAMENT_REPORT.md) /
   [MODEL_TTS_TOURNAMENT_REPORT.md](MODEL_TTS_TOURNAMENT_REPORT.md)
   (non-Ollama; pip-installable).
5. **No double load** — when concurrent_modals = 1, vision and voice
   share a slot; the load-policy unloads text before swap if needed.

## Per-profile candidates

### `cpu_only` (RAM-only, no GPU)

| role | candidate                | size  | rationale |
|------|--------------------------|-------|-----------|
| text | `qwen3:1.7b`             | 1.4GB | only fair-tool-pass=1.0 sub-2GB model in tournament |
| text alt | `phi3.5:latest`      | 2.2GB | tool 0.80 (fenced_json), CPU-friendly |
| vision   | – / pytesseract       | –     | no VLM; OCR via tesseract is enough |
| stt      | `whisper.cpp:tiny`    | 75MB  | CPU only |
| tts      | `piper:en_US-ljspeech-low` | 60MB | CPU |
| priority | high                  |       | covers laptops without GPU |

### `6gb` (RTX 3050/4050, GTX 1660)

| role | candidate                | size  | rationale |
|------|--------------------------|-------|-----------|
| text primary | `qwen3:1.7b`     | 1.4GB | leaderboard pick within registry safelist |
| text alt     | `llama3.2:3b`    | 2.0GB | fastest p95 (915ms) tournament-wide |
| text alt 2   | `qwen3:4b`       | 2.5GB | tools 1.00, but slow p95; fallback only |
| text quality | `hermes3:8b`     | 4.7GB | fair composite #1 (0.763) — opt-in via env if 5.1GB budget allows |
| vision       | `moondream`      | 1.7GB | ultra-light, on-demand |
| stt          | `whisper.cpp:small` | 466MB | |
| tts          | `piper:medium`   | 60MB  | |
| priority     | high             |       | most common consumer GPU |

### `8gb` (RTX 3060/3070/4060, GTX 1080)

| role | candidate                | size  | rationale |
|------|--------------------------|-------|-----------|
| text primary | `hermes3:8b`     | 4.7GB | fair #1, p95 1597ms, tool 1.00 |
| text alt     | `granite3.3:8b`  | 4.9GB | fair #2 (0.748), tool 1.00 |
| text alt 2   | `llama3.1:8b`    | 4.9GB | tool 1.00 (json_direct), p95 1734ms |
| text alt 3   | `qwen2.5:7b-instruct` | 4.7GB | NEW: pulled S1.3, strong tools/multilingual |
| text alt 4   | `qwen3:8b`       | 5.2GB | Carter baseline (rollback) |
| vision       | `minicpm-v`      | 5.5GB | OCR-strong; on-demand |
| stt          | `faster-whisper:distil-large-v3` | int8 1.5GB | |
| tts          | `piper:medium`   | 60MB  | |
| priority     | high             |       | gamer baseline |

### `10gb` (RTX 3080 10GB)

| role | candidate                | size  | rationale |
|------|--------------------------|-------|-----------|
| text primary | `hermes3:8b`     | 4.7GB | same as 8GB |
| text alt     | `granite3.3:8b`  | 4.9GB | |
| text alt 2   | `mistral-nemo:12b` | 7.1GB | NEW: pulled S1.3, mid-tier multilingual |
| text alt 3   | `qwen3:8b`       | 5.2GB | rollback |
| vision       | `qwen2.5vl:7b`   | 6.0GB | grounding |
| stt          | `faster-whisper:small`  | int8 0.5GB | |
| tts          | `piper:medium`   | 60MB  | |
| priority     | medium           |       | niche, Ampere step |

### `12gb` (RTX 3060 12GB / 4070)

| role | candidate                | size  | rationale |
|------|--------------------------|-------|-----------|
| text primary | `hermes3:8b`     | 4.7GB | same |
| text alt     | `granite3.3:8b`  | 4.9GB | |
| text alt 2   | `qwen2.5-coder:14b` | 9.0GB | fair 0.716, coding-strong |
| text alt 3   | `phi4:latest`    | 9.1GB | tool 1.00 via json_direct (runtime probe 5/5) |
| text alt 4   | `qwen3:14b`      | 9.3GB | text quality (slow p95) |
| vision       | `qwen2.5vl:7b`   | 6.0GB | concurrent with 8B text |
| stt          | `faster-whisper:medium` | int8 1.5GB | |
| tts          | `piper:medium`   | 60MB  | |
| priority     | high             |       | popular sweet-spot |

### `16gb` (RTX 4060 Ti 16GB ⭐ — Carter operator's rig)

| role | candidate                | size  | rationale |
|------|--------------------------|-------|-----------|
| text primary | `hermes3:8b`     | 4.7GB | fair #1 + leaves headroom for vision concurrent |
| text alt     | `gpt-oss:20b`    | 13GB  | fair 0.669, openai_tools, 16GB-only |
| text alt 2   | `mistral-small:24b` | 14GB | fair 0.669, openai_tools, near-budget |
| text alt 3   | `devstral:24b`   | 14GB  | coding agentic |
| text rollback| `qwen3:8b`       | 5.2GB | Carter ships default — revert via rollback recipe |
| vision       | `qwen2.5vl:7b`   | 6.0GB | concurrent with 8B text |
| vision alt   | `minicpm-v`      | 5.5GB | OCR fallback |
| stt          | `faster-whisper:large-v3` | int8 1.5GB | |
| tts          | `piper:medium` + opt `xtts-v2` | 1.8GB | optional XTTS |
| priority     | **CRITICAL**     |       | Carter's actual rig |

### `24gb` (RTX 3090 / 4090 / A6000)

| role | candidate                | size  | rationale |
|------|--------------------------|-------|-----------|
| text primary | `gpt-oss:20b`    | 13GB  | top fair-composite that fits with margin |
| text alt     | `mistral-small:24b` | 14GB | tool 1.00 native |
| text alt 2   | `qwen2.5:32b-instruct-q4_K_M` | 19GB | text quality |
| text alt 3   | `qwen3:8b`       | 5.2GB | rollback |
| vision       | `qwen2.5vl:7b`   | 6.0GB | concurrent w/ 24B |
| stt          | `faster-whisper:large-v3 fp16` | 3GB | |
| tts          | `xtts-v2`        | 1.8GB | concurrent voice |
| priority     | medium           |       | enthusiast/server |

## Externally-pulled candidates (S1.3 — this session)

| tag                  | size  | profile target | source         | decision         | notes |
|----------------------|------:|----------------|----------------|------------------|-------|
| `qwen2.5:7b-instruct`| 4.7GB | 6/8/10gb       | ollama library | INSTALLED + KEPT | strong multilingual tools, complements hermes3:8b |
| `mistral-nemo:12b`   | 7.1GB | 10/12gb        | ollama library | INSTALLED + KEPT | fills gap between 8B and 14B; multilingual |

Both pulled serially via background `ollama pull` jobs; verified in
`ollama list`. No double-load (sequential). See updated
[MODEL_DOWNLOAD_LOG.md](MODEL_DOWNLOAD_LOG.md).

## Skipped externally (justified)

| candidate                     | reason |
|-------------------------------|--------|
| `command-r-plus`              | exceeds 24GB VRAM budget on this rig |
| `mixtral:8x22b`               | exceeds 24GB |
| `llama3.3:70b`                | exceeds 24GB by far |
| `qwen3:32b`                   | superseded by `qwen2.5:32b-instruct-q4_K_M` already local |
| `internvl2-llama3-76b`        | size + license ambiguity |
| `xtts-v2` runtime dl          | non-Ollama; scaffolded in MODEL_TTS_TOURNAMENT_REPORT.md |
| `whisper-large-v3` HF weights | non-Ollama; scaffolded in MODEL_STT_TOURNAMENT_REPORT.md |
| `nemotron-mini:4b`            | NVIDIA license requires acceptance interactively; needs operator confirmation |
| `dolphin-llama3:70b`          | exceeds budget |

These are catalogued in [MODEL_RESEARCH_MATRIX.md](MODEL_RESEARCH_MATRIX.md)
with full justification per row.
