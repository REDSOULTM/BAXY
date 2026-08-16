# CARTER MODEL TOURNAMENT REPORT (M11)

_Generated: 2026-05-02T14:01:13Z_

Methodology: each candidate is loaded ALONE in Ollama (keep_alive=0 between
models, no double GPU residency), benchmarked with the M4 text suite (33
cases, 13 categories) plus the M5 tool suite (23 cases, 7 categories incl.
safety_rmrf / safety_inject / ambiguous_open). Composite score weights:
25% tool, 20% mission, 15% latency, 10% text, 10% multilingual, 10% VRAM
efficiency, 5% stability, 5% safety. Sources:
`audit/results/model_benchmarks/<model>/*.json`.

**Models with at least one full result:** 16

## Profile **cpu_only** — VRAM 0-1 MiB, text budget ≤ 0 MiB

_No candidate fits this profile yet — pending tournament wave._

## Profile **6gb** — VRAM 1-7000 MiB, text budget ≤ 4096 MiB

| # | model | composite | text_pass | tool_pass | p95_ms | vram_load_mb | duration_s |
|---|-------|-----------|-----------|-----------|--------|--------------|------------|
| 1 | `qwen3:1.7b` | 0.870 | 0.86 | 0.88 | 3428 | 1687 | 103.0 |
| 2 | `qwen3:4b` | 0.743 | 0.94 | 0.88 | 47435 | 3059 | 771.1 |
| 3 | `llama3.2:3b` | 0.667 | 0.89 | 0.40 | 915 | 2582 | 32.9 |
| 4 | `phi3.5:latest` | 0.475 | 0.92 | 0.00 | 2079 | 3110 | 83.9 |

## Profile **8gb** — VRAM 7000-9216 MiB, text budget ≤ 5632 MiB

| # | model | composite | text_pass | tool_pass | p95_ms | vram_load_mb | duration_s |
|---|-------|-----------|-----------|-----------|--------|--------------|------------|
| 1 | `qwen3:1.7b` | 0.870 | 0.86 | 0.88 | 3428 | 1687 | 103.0 |
| 2 | `hermes3:8b` | 0.819 | 0.92 | 0.76 | 1597 | 4857 | 58.2 |
| 3 | `qwen3:8b` | 0.784 | 0.89 | 0.96 | 31389 | 5351 | 508.1 |
| 4 | `granite3.3:8b` | 0.745 | 0.83 | 0.52 | 3393 | 5331 | 87.3 |
| 5 | `qwen3:4b` | 0.743 | 0.94 | 0.88 | 47435 | 3059 | 771.1 |
| 6 | `llama3.1:8b` | 0.723 | 0.81 | 0.56 | 1734 | 5105 | 61.4 |
| 7 | `llama3.2:3b` | 0.667 | 0.89 | 0.40 | 915 | 2582 | 32.9 |
| 8 | `phi3.5:latest` | 0.475 | 0.92 | 0.00 | 2079 | 3110 | 83.9 |
| 9 | `deepseek-r1:8b` | 0.430 | 0.89 | 0.00 | 9380 | 5350 | 257.0 |

## Profile **10gb** — VRAM 9216-11264 MiB, text budget ≤ 7168 MiB

| # | model | composite | text_pass | tool_pass | p95_ms | vram_load_mb | duration_s |
|---|-------|-----------|-----------|-----------|--------|--------------|------------|
| 1 | `qwen3:1.7b` | 0.870 | 0.86 | 0.88 | 3428 | 1687 | 103.0 |
| 2 | `hermes3:8b` | 0.819 | 0.92 | 0.76 | 1597 | 4857 | 58.2 |
| 3 | `qwen3:8b` | 0.784 | 0.89 | 0.96 | 31389 | 5351 | 508.1 |
| 4 | `granite3.3:8b` | 0.745 | 0.83 | 0.52 | 3393 | 5331 | 87.3 |
| 5 | `qwen3:4b` | 0.743 | 0.94 | 0.88 | 47435 | 3059 | 771.1 |
| 6 | `llama3.1:8b` | 0.723 | 0.81 | 0.56 | 1734 | 5105 | 61.4 |
| 7 | `llama3.2:3b` | 0.667 | 0.89 | 0.40 | 915 | 2582 | 32.9 |
| 8 | `phi3.5:latest` | 0.475 | 0.92 | 0.00 | 2079 | 3110 | 83.9 |
| 9 | `deepseek-r1:8b` | 0.430 | 0.89 | 0.00 | 9380 | 5350 | 257.0 |

## Profile **12gb** — VRAM 11264-14336 MiB, text budget ≤ 7680 MiB

| # | model | composite | text_pass | tool_pass | p95_ms | vram_load_mb | duration_s |
|---|-------|-----------|-----------|-----------|--------|--------------|------------|
| 1 | `qwen3:1.7b` | 0.870 | 0.86 | 0.88 | 3428 | 1687 | 103.0 |
| 2 | `hermes3:8b` | 0.819 | 0.92 | 0.76 | 1597 | 4857 | 58.2 |
| 3 | `qwen3:8b` | 0.784 | 0.89 | 0.96 | 31389 | 5351 | 508.1 |
| 4 | `granite3.3:8b` | 0.745 | 0.83 | 0.52 | 3393 | 5331 | 87.3 |
| 5 | `qwen3:4b` | 0.743 | 0.94 | 0.88 | 47435 | 3059 | 771.1 |
| 6 | `llama3.1:8b` | 0.723 | 0.81 | 0.56 | 1734 | 5105 | 61.4 |
| 7 | `llama3.2:3b` | 0.667 | 0.89 | 0.40 | 915 | 2582 | 32.9 |
| 8 | `phi3.5:latest` | 0.475 | 0.92 | 0.00 | 2079 | 3110 | 83.9 |
| 9 | `deepseek-r1:8b` | 0.430 | 0.89 | 0.00 | 9380 | 5350 | 257.0 |

## Profile **16gb** — VRAM 14336-20480 MiB, text budget ≤ 8192 MiB

| # | model | composite | text_pass | tool_pass | p95_ms | vram_load_mb | duration_s |
|---|-------|-----------|-----------|-----------|--------|--------------|------------|
| 1 | `qwen3:1.7b` | 0.870 | 0.86 | 0.88 | 3428 | 1687 | 103.0 |
| 2 | `hermes3:8b` | 0.819 | 0.92 | 0.76 | 1597 | 4857 | 58.2 |
| 3 | `qwen3:8b` | 0.784 | 0.89 | 0.96 | 31389 | 5351 | 508.1 |
| 4 | `granite3.3:8b` | 0.745 | 0.83 | 0.52 | 3393 | 5331 | 87.3 |
| 5 | `qwen3:4b` | 0.743 | 0.94 | 0.88 | 47435 | 3059 | 771.1 |
| 6 | `llama3.1:8b` | 0.723 | 0.81 | 0.56 | 1734 | 5105 | 61.4 |
| 7 | `llama3.2:3b` | 0.667 | 0.89 | 0.40 | 915 | 2582 | 32.9 |
| 8 | `phi3.5:latest` | 0.475 | 0.92 | 0.00 | 2079 | 3110 | 83.9 |
| 9 | `deepseek-r1:8b` | 0.430 | 0.89 | 0.00 | 9380 | 5350 | 257.0 |

## Profile **24gb** — VRAM 20480-1000000000 MiB, text budget ≤ 12288 MiB

| # | model | composite | text_pass | tool_pass | p95_ms | vram_load_mb | duration_s |
|---|-------|-----------|-----------|-----------|--------|--------------|------------|
| 1 | `qwen3:1.7b` | 0.870 | 0.86 | 0.88 | 3428 | 1687 | 103.0 |
| 2 | `hermes3:8b` | 0.819 | 0.92 | 0.76 | 1597 | 4857 | 58.2 |
| 3 | `qwen3:8b` | 0.784 | 0.89 | 0.96 | 31389 | 5351 | 508.1 |
| 4 | `granite3.3:8b` | 0.745 | 0.83 | 0.52 | 3393 | 5331 | 87.3 |
| 5 | `qwen3:4b` | 0.743 | 0.94 | 0.88 | 47435 | 3059 | 771.1 |
| 6 | `qwen2.5-coder:14b` | 0.729 | 0.92 | 0.52 | 3743 | 9079 | 90.2 |
| 7 | `llama3.1:8b` | 0.723 | 0.81 | 0.56 | 1734 | 5105 | 61.4 |
| 8 | `qwen3:14b` | 0.680 | 0.89 | 0.88 | 28447 | 9223 | 720.1 |
| 9 | `llama3.2:3b` | 0.667 | 0.89 | 0.40 | 915 | 2582 | 32.9 |
| 10 | `phi3.5:latest` | 0.475 | 0.92 | 0.00 | 2079 | 3110 | 83.9 |
| 11 | `phi4:latest` | 0.442 | 0.89 | 0.00 | 4074 | 9193 | 68.7 |
| 12 | `gemma3:12b` | 0.439 | 0.81 | 0.00 | 1824 | 8587 | 69.6 |
| 13 | `deepseek-r1:8b` | 0.430 | 0.89 | 0.00 | 9380 | 5350 | 257.0 |

## Notes & open items

- Vision tournament pending (`audit/runners/model_vision_eval.py --tournament`).
- Voice models (STT/TTS) probed only — no live tournament; see [VOICE_MODEL_RESEARCH.md](VOICE_MODEL_RESEARCH.md).
- Re-run this consolidator after each `_tournament_*.json` snapshot.

## Fair-protocol re-bench addendum (Opus 4.7)

The single-protocol composite above only tests OpenAI native tools and
therefore systematically penalises models whose native tool channel is
silently dropped by the Ollama backend (`phi4`, `phi3.5`, `gemma3`,
`deepseek-r1` — all scored 0.00 in column `tool` above). The fair
re-bench (16 models × 7 protocols × 5 cases) and the runtime probe (5
models × 5 cases through Carter's actual backend) reach a different
verdict for those models:

| model            | tool (legacy) | tool (fair best) | best protocol | runtime probe |
|------------------|--------------:|-----------------:|---------------|--------------:|
| qwen3:8b         | 0.96          | 1.00             | openai_tools  | **5/5**       |
| phi4:latest      | 0.00          | 1.00             | json_direct   | **5/5**       |
| gemma3:12b       | 0.00          | 1.00             | json_direct   | **5/5**       |
| deepseek-r1:8b   | 0.00          | 1.00             | json_direct   | **5/5**       |
| hermes3:8b       | 0.76          | 1.00             | openai_tools  | 4/5           |

The runtime probe used Carter's real
[`OpenAICompatAgentBackend`](src/carter_v2/turn/backends.py) with
`CARTER_TOOL_PROTOCOL=auto`. Output:
[audit/results/RUNTIME_TOOL_PROTOCOL_PROBE.json](audit/results/RUNTIME_TOOL_PROTOCOL_PROBE.json).
Full audit: [RUNTIME_TOOL_PROTOCOL_WIRING_AUDIT.md](RUNTIME_TOOL_PROTOCOL_WIRING_AUDIT.md).

## Auto Model Stack S2 � fair-composite per profile (Opus 4.7)

Generated by `scripts/maintenance/consolidate_fair_tournament.py` from the same single-load benchmark JSONs but with the **tool pass column replaced by the fair-rebench best-protocol pass** (16 models x 7 protocols x 5 cases). Latency penalties for thinking-mode pathologies (Qwen3 family) carry over from text-suite p95.  See [audit/results/model_benchmarks_fair_runtime/CONSOLIDATED.md](audit/results/model_benchmarks_fair_runtime/CONSOLIDATED.md) for the full per-profile tables and [audit/results/model_benchmarks_fair_runtime/CONSOLIDATED.json](audit/results/model_benchmarks_fair_runtime/CONSOLIDATED.json) for the machine-readable source of truth that the selector now consumes.

Carter still defaults to `qwen3:8b` per the rule 'no cambiar config real sin confirmacion'.  The fair leaderboard exposes higher-composite alternatives as **opt-in** via `CARTER_TEXT_MODEL` + `CARTER_TOOL_PROTOCOL=auto`; the selector emits the exact PowerShell block in `CARTER_MODEL_RECOMMENDATION.md`.
