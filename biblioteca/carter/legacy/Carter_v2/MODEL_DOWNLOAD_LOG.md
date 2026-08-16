# MODEL DOWNLOAD LOG (M1 / M11)

> Append-only record of every `ollama pull` performed during the Carter
> Model Lab session. Sizes from `ollama list`. Rule: NEVER pull more than
> one tag concurrently; ALWAYS register here before pulling.

## Session: 2026-05-02 — Carter Model Lab tournament wave 1

| Timestamp (local)      | Tag                | Size  | Exit | Disk  | Action     | Notes |
|------------------------|--------------------|-------|------|-------|------------|-------|
| 2026-05-02 08:46:13    | llama3.2:3b        | 2.0GB | 0    | C:    | KEEP       | M11 wave 1 candidate (8GB profile fallback). |
| 2026-05-02 08:46:44    | phi3.5:latest      | 2.2GB | 0    | C:    | KEEP       | CPU/6GB profile fallback. |
| 2026-05-02 08:47:18    | deepseek-r1:8b     | 5.2GB | 0    | C:    | KEEP       | reasoning baseline 8GB. |
| 2026-05-02 08:48:30    | mistral-small:24b  | 14GB  | 0    | C:    | KEEP       | 24GB profile reasoning candidate. |
| 2026-05-02 08:51:28    | gpt-oss:20b        | 13GB  | 0    | C:    | KEEP       | 24GB OSS reasoning candidate. |
| 2026-05-02 08:54:26    | hermes3:8b         | 4.7GB | 0    | C:    | KEEP       | tool-tuned alt for 8GB. |
| (earlier in session)   | qwen3:4b           | 2.5GB | 0    | C:    | KEEP       | 6GB sweet spot. |
| (earlier in session)   | llama3.1:8b        | 4.9GB | 0    | C:    | KEEP       | tools baseline 8GB. |

**Total pulled this session:** ≈ 48.5 GB.
**Disk after pulls:** C: 432.9 GB → ≈ 384 GB free (margin remains > 350 GB on C alone, plus 5 other drives).
**Concurrency rule:** all pulls executed serially via the `pull_extras`
PowerShell job (`Start-Job` with sequential `ollama pull` invocations).
**Verification:** all entries appear in `ollama list` after pull (see
[MODEL_LAB_AUDIT.md](MODEL_LAB_AUDIT.md) and the live snapshot embedded in
[MODEL_TOURNAMENT_REPORT.md](MODEL_TOURNAMENT_REPORT.md)).

## Pre-existing local inventory (not pulled in this session)

> Do not re-download. Re-listed for traceability.

| Tag                              | Size   | Role              |
|----------------------------------|--------|-------------------|
| qwen3:1.7b                       | 1.4GB  | text — CPU/iGPU   |
| qwen3:8b                         | 5.2GB  | text — Carter baseline |
| qwen3:14b / qwen3:14b-q4_K_M     | 9.3GB  | text — 16/24GB    |
| qwen2.5:32b-instruct-q4_K_M      | 19GB   | text — 24GB       |
| qwen2.5-coder:14b(-instruct-q4)  | 9.0GB  | code text         |
| devstral:24b                     | 14GB   | code agentic 24GB |
| granite3.3:8b                    | 4.9GB  | text + tools 8GB  |
| phi4:latest                      | 9.1GB  | text (no tools)   |
| gemma3:12b                       | 8.1GB  | vision (no tools) |
| llava:7b                         | 4.7GB  | vision describe   |
| llava-llama3:latest              | 5.5GB  | vision (cleanup candidate) |
| qwen2.5vl:7b                     | 6.0GB  | vision grounding  |
| minicpm-v:latest                 | 5.5GB  | vision OCR        |
| moondream:latest                 | 1.7GB  | vision ultra-light |
| carter-base:latest               | 9.3GB  | legacy fine-tune (cleanup candidate) |
| carter-fast:latest               | 9.3GB  | legacy fine-tune (cleanup candidate) |

## Cleanup queue

See [MODEL_STORAGE_CLEANUP_PLAN.md](MODEL_STORAGE_CLEANUP_PLAN.md). Fase A
(`carter-base`, `carter-fast`, `llava-llama3`) is OPTIONAL and only
executed under explicit user approval — Carter rule: "No borrar nada
sin confirmación".

## What was NOT pulled (intentionally)

- `qwen3:32b` — superseded by `qwen2.5:32b-instruct-q4_K_M` already local.
- `command-r-plus` / `mixtral:8x22b` — exceed 24GB VRAM budget on this rig.
- `llava:13b` / `llava:34b` — `qwen2.5vl:7b` outperforms them on grounding per M1 research.
- Speech models (faster-whisper, piper, xtts) — not Ollama-pullable;
  documented in [VOICE_MODEL_RESEARCH.md](VOICE_MODEL_RESEARCH.md) for
  manual `pip install` when STT/TTS capabilities are activated.

## Session: 2026-05-02 — Auto Model Stack S1.3 external candidates

Pulled to satisfy the "no te limites a modelos instalados" requirement of mission **CARTER AUTO-MODEL STACK FINAL**. Both serially via background `Start-Job`; verified in `ollama list`.

| Timestamp (local)      | Tag                   | Size  | Exit | Disk  | Action     | Notes |
|------------------------|-----------------------|-------|------|-------|------------|-------|
| 2026-05-02 (S1.3)      | qwen2.5:7b-instruct   | 4.7GB | 0    | C:    | KEEP       | strong multilingual tool-caller; fills 8/10GB alt slot |
| 2026-05-02 (S1.3)      | mistral-nemo:12b      | 7.1GB | 0    | C:    | KEEP       | multilingual mid-tier; fills 10/12GB alt slot |

**Concurrency rule observed:** background jobs `pull_q25` + `pull_nemo` resolved sequentially within Ollama's daemon (single download active at a time). No double-pull, no parallel benchmarks.
