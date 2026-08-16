# Carter Model Download Plan (M1 extra)

Pre-flight check ejecutado el 2026-05-02:

| Recurso | Valor | Política |
|---|---|---|
| GPU | RTX 4060 Ti 16 GB (driver 595.71) | hard cap 13.6 GB |
| Disco C: libre | **64.15 GB** (97.45 GB ya en `~/.ollama/models`) | **no permitir descargas que dejen < 25 GB libres** |
| Internet | OK (registry.ollama.ai 200, huggingface.co 200) | descargas autorizadas |
| Ollama | activo en 127.0.0.1:11434, sin runner cargado en `ollama ps` | seguro para pull/test |

## Decisión maestra

Dado que ya existen **17 modelos locales (~97 GB)** y solo quedan **64 GB libres**, las
descargas se limitan a candidatos que (a) cubren un *gap* real de los perfiles
M2 y (b) no comprometen la regla de ≥ 25 GB libres en disco.

| modelo | tipo | perfil objetivo | tamaño on-disk | fuente | acción | motivo / riesgo |
|---|---|---|---:|---|---|---|
| `qwen3:4b` | LLM texto + tools | 6GB / 8GB fallback | ~2.6 GB | Ollama lib `qwen3:4b` (HF Qwen/Qwen3-4B) | **PULL** | Cubre gap entre 1.7b (débil tools) y 8b (5.2 GB). Cabe holgado. |
| `llama3.1:8b` | LLM texto + tools | 8GB / 16GB referencia | ~4.9 GB | Ollama lib `llama3.1:8b` (Meta Llama 3.1 8B Instruct) | **PULL** | Baseline alternativo con tool-calling oficial; útil para comparar contra qwen3:8b. |
| `qwen3:1.7b` | LLM texto + tools | CPU/iGPU/6GB fallback | ~1.4 GB | – | **YA INSTALADO** | Mantener. |
| `qwen3:8b` | LLM texto + tools | 10GB/12GB/16GB | ~5.2 GB | – | **YA INSTALADO** | Carter actual. Mantener. |
| `qwen3:14b` | LLM texto + tools | 16GB power / 24GB | ~9.3 GB | – | **YA INSTALADO** | Mantener. |
| `qwen2.5:32b-instruct-q4_K_M` | LLM razonamiento | 24GB+ | ~19 GB | – | **YA INSTALADO** | Mantener para perfil 24 GB. |
| `qwen2.5-coder:14b` | LLM código | 16GB on-demand | ~9.0 GB | – | **YA INSTALADO** | On-demand para tareas de código. |
| `granite3.3:8b` | LLM texto + tools | 8GB candidato | ~4.9 GB | – | **YA INSTALADO** | Probar como alternativa a qwen3:8b. |
| `devstral:24b` | LLM código + agéntico | 24GB+ on-demand | ~14 GB | – | **YA INSTALADO** | On-demand para código complejo. |
| `phi4:latest` | LLM texto puro | – | ~9.1 GB | – | **MANTENER (NO BACKEND)** | Sin tool-calling en Carter; mantener para análisis. |
| `gemma3:12b` | LLM/VLM | – | ~8.1 GB | – | **MANTENER (VLM ALT)** | Sin tools; alternativa visión. |
| `qwen2.5vl:7b` | VLM grounding | 12GB/16GB visión principal | ~6.0 GB | – | **YA INSTALADO** | Carter actual `find_element`. |
| `llava:7b` | VLM | – | ~4.7 GB | – | **MANTENER** | Carter actual `describe_image`. |
| `llava-llama3:latest` | VLM | – | ~5.5 GB | – | **CANDIDATO A BORRAR** | Reemplazado por minicpm-v en calidad OCR. |
| `minicpm-v:latest` | VLM + OCR | 8GB/12GB visión | ~5.5 GB | – | **YA INSTALADO** | Mejor OCR que llava. |
| `moondream:latest` | VLM ultra-ligero | 6GB/CPU | ~1.7 GB | – | **YA INSTALADO** | Visión perfil bajo. |
| `carter-base` / `carter-fast` | LLM custom 14B | – | 9.3 GB c/u (~18.6 GB) | – | **CANDIDATO A BORRAR** | Variantes basadas en qwen3:14b sin métrica documentada. Borrar libera ~18.6 GB. |
| `mistral-small:24b` | LLM | 24GB+ | ~14 GB | Ollama lib | **DEFER (disk pressure)** | Útil pero empuja a < 50 GB libres. Recomendar tras limpieza. |
| `gpt-oss:20b` | LLM | 16GB power | ~12 GB | Ollama lib (`gpt-oss:20b`) | **DEFER (disk + redundancia)** | Cubierto por qwen3:14b en presupuesto similar; pull tras limpieza. |
| `nemotron-nano-9b` | LLM | 8GB/10GB | ~6 GB | NVIDIA HF | **DEFER** | Sin convergencia clara; pull solo si granite/qwen3 fallan en M11. |
| `llama3.2:3b` | LLM | 6GB candidato | ~2 GB | Ollama lib | **DEFER** | Cubierto por qwen3:4b; pull si qwen3:4b falla en M11. |
| `phi3.5-mini` | LLM | CPU | ~2.5 GB | Ollama lib | **DEFER** | Pull si qwen3:1.7b/4b inviables en CPU-only. |
| `internvl2.5:8b` | VLM | 12GB | ~5 GB | HF | **DEFER** | Cubierto por qwen2.5vl:7b. |
| `whisper.cpp small` | STT | 6/8/16GB | ~466 MB GGML | ggerganov/whisper.cpp | **DEFER (out-of-Ollama)** | STT no implementado en Carter aún (M8). Plan de instalación documentado. |
| `whisper.cpp tiny/base` | STT | CPU/6GB | ~75/142 MB | mismo | **DEFER (out-of-Ollama)** | mismo |
| `faster-whisper large-v3` | STT GPU | 12GB+/16GB | ~3 GB | Systran/faster-whisper-large-v3 | **DEFER (out-of-Ollama)** | mismo |
| `Piper voices` | TTS | todos | <100 MB | rhasspy/piper | **DEFER (out-of-Ollama)** | Por idioma/voz seleccionada. |

### Comandos de descarga (autorizados, ejecutar uno a la vez)

```powershell
# Solo dos descargas autorizadas en este pase (≈ 7.5 GB combinados)
ollama pull qwen3:4b        # ~2.6 GB
ollama pull llama3.1:8b     # ~4.9 GB
```

### Política de borrado preventivo (para liberar disco antes de DEFER → PULL)

Ver `MODEL_STORAGE_CLEANUP_PLAN.md`. Limpieza recomendada libera ~24 GB sin perder
funcionalidad y permite re-evaluar `mistral-small:24b` y `gpt-oss:20b`.
