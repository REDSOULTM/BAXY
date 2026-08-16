# Carter Model Lab Audit (M0)

**Mission:** OPUS 4.7 — CARTER MODEL LAB. Find the best LLM/Vision/Voice stack per
hardware profile, with no hardcodes, no app hacks, no double-loading of models, no
sacrificing of quality, latency or safety. This document is the M0 audit; no code is
edited here. M1–M14 follow as separate artifacts.

---

## 1. Estado actual

| Item | Valor observado | Fuente |
|---|---|---|
| Modelo de texto activo | `qwen3:8b` (GGUF Q4_K_M, ~5.2 GB on disk) | `ollama list`, `run_carter_gpu.ps1`, `ULTRA_LATENCY_REPORT.md §1` |
| Backend principal | `llamacpp` (llama-cpp-python con CUDA) cuando se lanza `run_carter_gpu.ps1`; Ollama OpenAI-compat (`http://127.0.0.1:11434/v1`) en validación live-safe | `run_carter_gpu.ps1` líneas 11-44, `audit/runners/full_live_llm_validation.py` |
| Cuantización | `Q4_K_M` (qwen3-8b, ~5.2 GB), Carter usa `num_ctx=16384` | `.env.example`, `src/carter_v2/turn/backends.py` |
| Contexto | `CARTER_NUM_CTX=16384` (puede subir a 40960 nativo) | `.env.example` |
| VRAM usada con Carter caliente | ~6.8 GB Δ una sola vez (no doble carga) | `ULTRA_LATENCY_REPORT.md §1`, repo memory |
| RAM usada | No medida formalmente; estimada 1.5–3 GB del proceso Carter | obs. cualitativa |
| Latencia simple p95 | 1972 ms (live-safe ultra final) | `audit/results/ULTRA_LATENCY_FINAL_GATE.json`, `ULTRA_LATENCY_REPORT.md §2` |
| Latencia tools_simple p95 | 4608 ms | mismo |
| Latencia app_action p95 | 3868 ms | mismo |
| Latencia mission p95 | 31218 ms (env-bound: UIA + GUI variance) | mismo |
| Modelos de visión | `llava:7b` (semántica) + `qwen2.5vl:7b` (grounding) + `pytesseract`/omniparser fallback | `run_carter_gpu.ps1`, `src/carter_v2/capabilities/vision_router.py` |
| STT/Transcripción | **No implementado** — Carter es texto-only hoy | inspección directa de `capabilities/` |
| TTS | **No implementado** | inspección directa |
| Cámara | **No implementada** (placeholder mental, no tool) | inspección directa |
| GPU del usuario actual | RTX 4060 Ti 16 GB (driver 595.71, total 16380 MiB) | `nvidia-smi` ahora |
| Hardcode_guard críticos | 0 | repo memory, `audit/HARDCODE_*` |
| Action_failed controlables | 0 | `audit/results/PERFORMANCE_AND_HARDCODE_FINAL_GATE.json` |
| Fake-success | 0 | mismo |
| Doble carga de modelos | 0 (instance count = 1, ollama_processes 2→2 estables) | `FULL_LIVE_LLM_FINAL_GATE.json`, repo memory |

### Modelos Ollama ya instalados (inventario local, listo para tournament sin descarga)

| Familia | Tags presentes | Tamaño on-disk | Categoría |
|---|---|---:|---|
| Qwen3 | `qwen3:1.7b`, `qwen3:8b`, `qwen3:14b` (= `qwen3:14b-q4_K_M`) | 1.4 / 5.2 / 9.3 GB | LLM texto + tools |
| Qwen2.5 | `qwen2.5:32b-instruct-q4_K_M`, `qwen2.5-coder:14b-instruct-q4_K_M` | 19 / 9.0 GB | Texto / código |
| Phi-4 | `phi4:latest` (~14B) | 9.1 GB | Texto |
| Gemma 3 | `gemma3:12b` | 8.1 GB | Texto |
| Granite 3.3 | `granite3.3:8b` | 4.9 GB | Texto + tools |
| Devstral | `devstral:24b` | 14 GB | Código + tools |
| Llava | `llava:7b`, `llava-llama3:latest` | 4.7 / 5.5 GB | VLM |
| Qwen2.5-VL | `qwen2.5vl:7b` | 6.0 GB | VLM grounding |
| MiniCPM-V | `minicpm-v:latest` | 5.5 GB | VLM ligero |
| Moondream | `moondream:latest` | 1.7 GB | VLM ultra-ligero (CPU/iGPU friendly) |
| Carter custom | `carter-base`, `carter-fast` (ambos 9.3 GB) | 9.3 GB | Variantes propietarias |

> **Observación crítica para no doble-carga:** Ollama mantiene un único proceso runner por modelo y hace unload por `keep_alive`. El runner `model_benchmark.py` debe forzar unload entre modelos via `keep_alive=0` o `ollama stop <model>`.

---

## 2. Dónde el modelo limita a Carter (análisis conceptual)

### 2.1 Tool calling y JSON

- Carter expone ~60 capabilities a través de un *tool catalog* compactado (`tool_catalog_selection.py`). El modelo necesita:
  1. seleccionar la herramienta correcta;
  2. emitir argumentos JSON válidos;
  3. respetar enums (`risk_level`, `app_open.target`, etc.);
  4. saber cuándo NO llamar herramienta (`_NO_TOOL_NEEDED_PREFIX`);
  5. encadenar herramientas en misiones (M1 mission state).
- Modelos sin entrenamiento explícito de tool-calling (`phi4`, `gemma3:12b`, `llava`, `moondream`, `minicpm-v`) están **excluidos** del catálogo de tool-calling por `OpenAICompatAgentBackend._NO_TOOLS_MODELS`. Solo cumplen rol "texto puro" o "vision puro".
- **Limitación observada:** Qwen3-8B emite tool-calls correctos en ~95% de los casos scripted; en live-safe el único fallo recurrente es ambigüedad deíctica ("abre eso") donde dispara `app_open` en lugar de pedir aclaración (memo: `full_live_llm_matrix.md` §"4 fails").

### 2.2 Misiones compuestas

- El planner (`mission.py` + `agent.py`) depende de que el LLM:
  - mantenga contexto multi-step (ya gestionado, pero prompt > 4k tokens degrada modelos pequeños);
  - emita observación post-step (`mission_observation`);
  - reconozca verificación pendiente (`mission_verification`).
- Modelos < 7B suelen perder cohesión a partir de 3 pasos (riesgo de loop, ya mitigado por `_repeat_failure_break`).

### 2.3 Visión

- VLM se invoca on-demand a través de `vision_router`. Hoy hay **doble VLM** (llava + qwen2.5vl). Esto es seguro porque **no son grandes (5–6 GB cada uno) y se cargan on-demand**, pero en perfiles ≤ 12 GB ya no caben con texto residente.
- OCR fallback: `pytesseract` (CPU). Sin GPU, sin cuota. Es el mínimo común denominador.

### 2.4 Latencia de salida

- Tokens/s de qwen3:8b en RTX 4060 Ti ~ 50–60 tok/s (medido implícitamente por p95 simple ≈ 2 s para ~120-token replies).
- Cualquier modelo más grande (qwen3:14b, qwen2.5:32b, devstral:24b) reduce throughput proporcionalmente. Para mantener `simple p95 < 8 s` un perfil 24 GB **debería** quedarse en 14B Q4 o 8B Q5.

### 2.5 Alucinación e idioma

- qwen3:8b responde en el idioma del usuario sin fallback; modelos como `phi4` tienden a responder en inglés aunque se les hable en español (riesgo MOM idioma).
- Familias `granite3.3`, `gemma3` mezclan idiomas en >2 turnos sin reforzar el system prompt.

### 2.6 Memoria y contexto largo

- Carter ya tiene resolución de identidad con confianza (L1) + memoria SQLite. El LLM no necesita ventana > 32k para conversación normal; pero misiones con observaciones GUI llegan a 8–12k tokens.
- Qwen3 nativo soporta 128k (RoPE); en GGUF Q4_K_M con `num_ctx=16384` consume ~6.8 GB. Subir a 32k añade ~2 GB más → cuidado en perfiles 8 GB.

---

## 3. Qué debe medir el laboratorio

Por cada **(modelo, perfil, modo)** registrar:

| Dimensión | Métrica | Umbral aceptable Carter |
|---|---|---|
| **Calidad texto** | rúbrica 1-5 + contains-must / contains-must-not | ≥ 4.0 promedio |
| **Velocidad** | first_token_ms, tokens/s, total_ms p50/p95 | simple p95 ≤ perfil-target |
| **Estabilidad** | runs sin crash, sin OOM, sin timeout | 100% |
| **VRAM** | before / after / peak (MiB), Δ | ≤ 0.85 × VRAM perfil |
| **RAM** | before / after del proceso Python + Ollama | ≤ 4 GB en perfiles ≤ 8 GB |
| **Tool accuracy** | tool_selection, json_validity, wrong_tool_rate, unnecessary_tool_rate | tool_selection ≥ 0.90, json_validity = 1.0 |
| **Mission success** | completed / verified / partial | ≥ 0.80 |
| **Safety** | dangerous_bypass, prompt_injection_bypass, fake_success | 0 |
| **Visión** | OCR_acc, find_element_acc, hallucination_rate | OCR ≥ 0.85 sobre fixtures |
| **STT** | WER, command_intent_acc, latency first_partial | WER ≤ 0.15 ES/EN |
| **TTS** | first_audio_ms, MOS auto-est, naturalidad | first_audio ≤ 800 ms |
| **Cámara** | reuso del pipeline VLM | identidad de fixture |
| **Uso prolongado** | p95 después de N=200 turnos vs N=10 | drift < 25% |

Todas las mediciones se persisten en `audit/results/model_benchmarks/<model_id>/<timestamp>.json`.

---

## 4. Plan M1 → M14 (no implementar hasta cerrar M0 ✓)

| Fase | Entregable principal | Estado |
|---|---|---|
| M1 | `MODEL_RESEARCH_MATRIX.md` | pendiente |
| M2 | `MODEL_HARDWARE_PROFILES.md` | pendiente |
| M3 | `audit/runners/model_benchmark.py` | pendiente |
| M4 | `audit/runners/model_text_eval_cases.py` | pendiente |
| M5 | `audit/runners/model_tool_eval_cases.py` | pendiente |
| M6 | reuse `compound_smoke_runner.py` + extender (`mission_eval_cases`) | pendiente |
| M7 | `audit/runners/model_vision_eval.py` | pendiente |
| M8 | `VOICE_MODEL_RESEARCH.md` + `audit/runners/model_voice_eval.py` (offline) | pendiente |
| M9 | `MODEL_STACK_BY_VRAM.md` | pendiente |
| M10 | `src/carter_v2/model_selection/*` + `scripts/maintenance/recommend_carter_models.py` | pendiente |
| M11 | `MODEL_TOURNAMENT_REPORT.md` (real partial coverage) | pendiente |
| M12 | `.env.example` + `run_carter_gpu.ps1` (env-driven, rollback preservado) | pendiente |
| M13 | re-correr gates con stack ganador | pendiente |
| M14 | `CARTER_MODEL_LAB_REPORT.md` | pendiente |

### Reglas operativas que se aplicarán durante M1–M14

1. **Un modelo a la vez.** El runner emite `keep_alive=0s` y/o `ollama stop <model>` antes de cargar el siguiente. Verifica con `ollama ps` que la lista quede vacía.
2. **Sin paralelismo.** El benchmark se ejecuta serial; ningún `asyncio.gather` sobre modelos distintos.
3. **VRAM watchdog.** Antes de cada modelo, `nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits` y se aborta si `used > 0.85 × total` ya antes de cargar.
4. **Fallback documentado, no inventado.** Si internet no está disponible para investigación de M1, se usan SOLO los 17 modelos ya instalados y se marca el resto como `UNKNOWN_NOT_TESTED`.
5. **Rollback intocable.** `run_carter_gpu.ps1` actual queda como `run_carter_gpu.ps1.baseline` antes de cualquier edición; el nuevo runner es env-driven y revierte a Qwen3:8b por defecto si las nuevas variables no están definidas.
6. **No tocar el motor del agent.** Todas las decisiones de modelo van por config; cero ramas if-model en `agent.py`, `_system_prompt.py`, `tool_catalog_selection.py`.

---

**Veredicto M0:** `AUDIT_READY` — luz verde para ejecutar M1.
