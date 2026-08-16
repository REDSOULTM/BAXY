# Índice — Investigación Carter v4 + Gemma 4 hacia 540/540

**Empezá leyendo en orden:**

1. **`RESPUESTAS_A_TUS_3_PREGUNTAS.md`** ← respuestas a las 3 preguntas que hiciste antes de arrancar (acceso archivos / granularidad Deliverable 1 / Gemma 4 real)
2. **`00_CONTEXTO_CARTER_VALORES.md`** ← los 25 valores no-negociables del proyecto Carter (Valor 3 No Mentir es central)
3. **`00b_CLAUDE_md_orientacion.md`** ← orientación general del proyecto para devs/agentes
4. **`PROMPT_INVESTIGACION.md`** ← el prompt original con los 5 deliverables, restricciones y output esperado

**Después leé los archivos según el deliverable:**

## Para Deliverable 1 (mapeo 540 casos)

- `01_BENCH_540_CASOS.md` — los 540 casos completos, una tabla por categoría C01-C18
- `02_full_matrix_runner.py` — runner del bench: cómo se evalúa cada caso (`audit_case()`, `_latency_budget_ms()`, scoring rules). Esencial para entender qué cuenta como PASS/FAIL/PARTIAL.
- `audit_qwen3/14_OPUS_DOSSIER_PATRONES_A_P.md` — análisis manual del audit qwen3:4b sobre los 540 casos. Define los 16 patrones residuales (A, B, D, E, F, J, K, L, M, N, O, P1, etc.). **Lectura obligatoria** para asignar patrón a cada caso.

## Para Deliverable 2 (CORE_PROMPT v3)

- `codigo_carter/03_models_gemma4.py` — config Gemma 4 actual con CORE_PROMPT v2.3 (12 reglas + 6 few-shots), sampling defaults, flags llama-server, turn profiles, detector destructive
- `research_dossiers/12_OPT_GEMMA4_DOSSIER.md` — research 2026-05-09 sobre cómo armar el CORE_PROMPT óptimo para Gemma 4 (sección "Axis 4 — System prompt")
- `research_dossiers/10_REPORTE_BENCH_60_CASOS.md` — bench externo 60 casos: qué prompts funcionaron y cuáles fallaron en el setup actual
- `research_dossiers/13_MULTIMODAL_GEMMA4.md` — research multimodal con sección sobre cómo el CORE_PROMPT debería instruir el uso de vision

## Para Deliverable 3 (anchors + retrieval)

- `codigo_carter/05_tool_retrieval.py` — implementación actual de `ToolRetriever` con anchors (22 tools), top-K dinámico, multilingual-e5-small embeddings
- `codigo_carter/09_tools_init.py` — qué tools están registradas en total (59 hoy)
- `codigo_carter/04_agent.py` — ver `_get_turn_catalog()` para entender cómo se construye el catálogo del turno (anchor + top-K)

## Para Deliverable 4 (ReAct loop policy)

- `codigo_carter/04_agent.py` — `Agent.run_turn()`, `_execute_tool_calls()`, ReAct loop con max_depth=3, budget 25s/turn, anti-rendición prematura, mission_pending
- `codigo_carter/06_adapter_llamacpp.py` — ver `_strip_thought_leakage()` para entender el quirk de Gemma 4 leakeando planning como content
- `codigo_carter/07_verifier_orchestrator.py` — estados `TOOL_OK_VERIFIER_INCONCLUSIVE` e `INTENT_NOT_FULFILLED` ya implementados que afectan multi-step

## Para Deliverable 5 (plan staged + ROI/categoría)

- Todos los anteriores, más:
- `codigo_carter/08_reply_checks.py` — los 3 anti-mentira post-LLM checks ya implementados (anti-eco, anti-genérico, anti-unverified-claim)
- `audit_qwen3/15_OPUS_DOSSIER_PROYECTO.md` — perspectiva de Carter como proyecto, qué define éxito vs fracaso, baseline qwen3 contra el que se compara Gemma 4

## Contexto de fondo (lectura recomendada pero no esencial)

- `research_dossiers/11_INFORME_AUDIO.md` — análisis de 4 caminos para audio (descartado para esta investigación; Whisper aparte, no scope)

## Información NO disponible en el paquete

- **Latencia real Gemma 4 IQ2_M en RTX 4060 Ti** medida sobre los 540 casos completos. Solo tenemos el bench externo de 60 casos (en `10_REPORTE_BENCH_60_CASOS.md`).
- **Resultados de Gemma 4 en el bench oficial 540** — nunca se corrió. Lo último corrido fue qwen3:4b (88.89% PASS oficial / 61% PASS REAL audit humano).
- **Trazas REPL reales** del usuario interactuando con Gemma 4. Hay sesiones reportadas en commits recientes (v21.1, v21.2, v21.3) pero sin logs estructurados.

Si en algún punto tu razonamiento depende de uno de estos datos faltantes, marcalo como "requiere medición empírica, no puedo prescribir sin correr el caso real".

---

## Comandos para auditar el repo en vivo (opcional)

Si querés validar algo del código en vivo y tenés acceso a una terminal:

```powershell
# Ver el commit actual
cd "c:/Users/usuario/Desktop/ETC/Programacion/Carter OS AI"
git log --oneline -10

# Levantar llama-server con la config Gemma 4 actual
python Run_Carterv4.py
# Esto auto-arranca llama-server con todos los flags del modulo gemma4

# Test trivial directo al server
curl http://127.0.0.1:8080/health

# Smoke test 3 probes
python Carter_v4/scripts/smoke_gemma.py

# Minimum test 10 casos del Contrato externo
python Carter_v4/scripts/minimum_test_gemma.py
```

Pero NO es necesario que corras nada. Toda la información que necesitás está en los archivos de esta carpeta.
