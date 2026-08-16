# Carter Model Stack by VRAM (M9)

This is the **operative recommendation** Carter's selector consumes
(`src/carter_v2/model_selection/`). Numbers here come from M2 budgets +
research matrix M1; **definitive numbers per model arrive in M11** after
the tournament finishes.

> Hard rule: nunca residentes simultáneamente en perfiles ≤ 12 GB:
> LLM-texto + VLM grande + STT large + TTS XTTS. La columna *concurrent*
> documenta exactamente qué se permite mantener vivo a la vez.

## Tabla maestra

| VRAM | text LLM (default) | quant | ctx | text LLM alt | VLM | STT | TTS | concurrent | expected p95 simple | notes |
|---:|---|---|---:|---|---|---|---|---|---:|---|
| **0 (CPU)** | `qwen3:1.7b` | Q4_K_M | 4096 | `phi3.5:latest` | – (pytesseract) | whisper.cpp tiny | Piper low | 1 LLM (RAM) | ~6000 ms | RAM ≥ 8 GB; tools degradados |
| **6 GB** | `qwen3:4b` | Q4_K_M | 8192 | `qwen3:1.7b` | `moondream` (on-demand, unload texto) | whisper.cpp small | Piper medium | 1 LLM GPU + ligeros CPU | ~3000 ms | RAM ≥ 16 GB recom. |
| **8 GB** | `qwen3:8b` | Q4_K_M | 8192 | `granite3.3:8b` / `llama3.1:8b` / `qwen3:4b` | `minicpm-v` (on-demand) | faster-whisper distil-large | Piper | 1 LLM GPU + ligeros | ~2500 ms | sweet spot |
| **10 GB** | `qwen3:8b` | Q4_K_M | 16384 | `llama3.1:8b` | `qwen2.5vl:7b` (on-demand) | faster-whisper small | Piper | 1 LLM + 1 modal corto | ~2200 ms | |
| **12 GB** | `qwen3:8b` | Q4_K_M | 16384 | `granite3.3:8b` | `qwen2.5vl:7b` concurrente | faster-whisper medium | Piper / XTTS opt | LLM + 1 modal residente | ~2000 ms | |
| **16 GB ⭐ (RTX 4060 Ti)** | `qwen3:8b` (default seguro / rollback) | Q4_K_M | 16384 | **`mistral-small:24b`** (Wave-2 winner, composite 0.883, tool 1.00, VRAM 13 374) → `gpt-oss:20b` (0.863, tool 0.96, VRAM 12 484) → `hermes3:8b` (0.819) → `qwen3:14b` Power Mode | `qwen2.5vl:7b` concurrente (alt: `minicpm-v` para describe) | faster-whisper large-v3 (CT2 int8) | Piper + XTTS opt | LLM + visión XOR voz | ~2000 ms | mejor Carter local completo |
| **24 GB+** | **`mistral-small:24b`** (Wave-2 winner) | Q4_K_M | 32768 | `gpt-oss:20b` / `qwen2.5:32b` Q4 / `qwen3:8b` | `qwen2.5vl:7b` o `qwen2.5vl:32b` | faster-whisper large-v3 fp16 | XTTSv2 | LLM + visión + STT residentes | ~2500 ms (modelo > velocidad) | mayor contexto y razonamiento |

## Notas operativas (alimenta `src/carter_v2/model_selection/load_policy.py`)

1. **Always-loaded** = el LLM de texto. Todo lo demás se despierta sólo bajo
   demanda de la *capability* correspondiente.
2. **Unload** automático tras `KEEP_ALIVE` segundos sin uso (Ollama
   `keep_alive` parameter / faster-whisper proceso terminado).
3. **Hard cap** = 0.85 × VRAM total (16 GB → 13.6 GB). Si una carga estimada
   superaría el cap, el selector emite `[needs_user] vram_overflow` y propone
   el alt.
4. **No double load**: el selector usa `nvidia-smi` *antes* de cada
   adquisición y aborta si `used > 0.85 × total`.
5. **Quality-vs-latency tradeoff** en 16 GB: `qwen3:8b` por defecto (~2 s p95);
   `qwen3:14b` con env `CARTER_TEXT_MODEL=qwen3:14b` cuando se prefiera
   razonamiento sobre latencia (~3-4 s p95 esperado).
6. **Concurrencia 12/16 GB**: visión y voz son **mutuamente excluyentes** en
   12 GB; en 16 GB pueden coexistir si el LLM principal es 8B (no 14B).

## Rollback

`CARTER_TEXT_MODEL=qwen3:8b` (default) garantiza que cualquier perfil cae al
modelo verificado actual. Fallbacks por perfil son determinísticos en
`model_registry.py` (`TEXT_FALLBACK_BY_PROFILE`).

## Wave-2 update (2026-05-02)

Wave 2 benched 9 nuevos candidatos texto+tool sobre el mismo harness
(single-load, 5 cases tool + 13 text). Resumen mediciones:

| Model               | Composite | text | tool  | p95 ms | VRAM MiB |
|---------------------|----------:|-----:|------:|-------:|---------:|
| **mistral-small:24b** | **0.883** | 0.92 | **1.00** | 6 234 | 13 374 |
| qwen3:1.7b          | 0.870 | 0.86 | 0.88 | 2 520 |  1 687 |
| gpt-oss:20b         | 0.863 | 0.86 | 0.96 | 6 120 | 12 484 |
| devstral:24b        | 0.842 | 0.89 | 0.88 | 3 472 | 13 375 |
| hermes3:8b          | 0.819 | 0.92 | 0.76 | 1 597 |  4 857 |
| qwen3:14b           | 0.680 | 0.89 | 0.88 | 21 073 | 9 223 |
| qwen2.5-coder:14b   | 0.729 | 0.92 | 0.52 |  —    |  9 079 |
| phi4:latest         | 0.442 | 0.89 | 0.00 |  —    |  9 193 |
| gemma3:12b          | 0.439 | 0.86 | 0.00 |  —    |  8 587 |

**Decisión integración:** mistral-small:24b *supera el gate* +0.099
composite y tool 1.00 ≥ qwen3:8b 0.96 → **califica como nuevo default
en 16 GB** según las reglas duras. Sin embargo Carter actualmente corre
`qwen3:8b` vía **llama-cpp-python (GGUF)**, no Ollama, para chat. Cambiar
el primary requeriría un GGUF nuevo + integración llama-cpp + revalidar
Carter completo. Para preservar rollback y la regla "no cambiar config
real sin confirmación", el selector mantiene `qwen3:8b` como primary y
expone `mistral-small:24b` / `gpt-oss:20b` como **fallbacks/opt-in**:

```powershell
# Opt-in al ganador Wave-2 (Ollama backend):
$env:CARTER_TEXT_MODEL = "mistral-small:24b"
& .\run_carter_gpu.ps1
```

`phi4`, `gemma3:12b`, `phi3.5`, `deepseek-r1:8b` están marcados
`supports_tools=False` en `model_registry.py` y un filtro
(`_filter_text_chain_safe`) en `selector.py` los excluye del rol texto
para impedir regresiones.

## Auto Model Stack S9 update (fair-leaderboard)

The operative selector is now driven by [audit/results/model_benchmarks_fair_runtime/CONSOLIDATED.md](audit/results/model_benchmarks_fair_runtime/CONSOLIDATED.md) (fair re-bench best-protocol per model under `CARTER_TOOL_PROTOCOL=auto`). Per-profile primaries:

| profile | text primary (fair) | tool protocol | vision (on-demand if <=8GB) | concurrent_voice |
|---|---|---|---|---:|
| cpu_only | qwen3:1.7b | json_direct | - | 1 |
| 6gb | qwen3:1.7b | json_direct | moondream | 0 |
| 8gb | hermes3:8b | json_direct | minicpm-v | 0 |
| 10gb | hermes3:8b | json_direct | qwen2.5vl:7b | 1 |
| 12gb | hermes3:8b | json_direct | qwen2.5vl:7b | 1 |
| 16gb | hermes3:8b (rollback qwen3:8b) | json_direct | qwen2.5vl:7b | 1 |
| 24gb | gpt-oss:20b | openai_tools | qwen2.5vl:7b | 2 |

New externally-pulled candidates (S1.3): `qwen2.5:7b-instruct` (4.7GB) and `mistral-nemo:12b` (7.1GB) � see [MODEL_DOWNLOAD_LOG.md](MODEL_DOWNLOAD_LOG.md) and [MODEL_CANDIDATES_BY_VRAM.md](MODEL_CANDIDATES_BY_VRAM.md). Final closure: [AUTO_MODEL_STACK_FINAL_REPORT.md](AUTO_MODEL_STACK_FINAL_REPORT.md), gates: [audit/results/AUTO_MODEL_STACK_FINAL_GATE.json](audit/results/AUTO_MODEL_STACK_FINAL_GATE.json).
