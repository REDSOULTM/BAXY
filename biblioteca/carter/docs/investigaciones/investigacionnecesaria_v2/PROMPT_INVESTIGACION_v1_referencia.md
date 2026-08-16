# Investigación: cómo lograr que Carter v4 + Gemma 4 E4B-it (UD-IQ2_M) pase los 540/540 casos del bench oficial

## El objetivo, en una frase

Diseñar la configuración EXACTA de Carter v4 (CORE_PROMPT, sampling, anchors de tool retrieval, ReAct loop policy, vision triggers, verifier orchestration) que maximice el PASS REAL en los 540 casos del bench oficial 18×30, usando Gemma 4 E4B-it-UD-IQ2_M como único modelo en llama-server CUDA.

Esto NO es una investigación arquitectónica abierta. Es un sprint de optimización: dónde está cada caso del bench, qué patrón cubre, qué tool chain debería disparar, qué falla hoy y cómo cerrarlo.

## Estado actual (concreto, no abstracto)

**Stack real al 2026-05-09:**
- llama.cpp build b9090 CUDA en `C:\llamacpp-cuda\bin\llama-server.exe`
- Modelo: `gemma-4-E4B-it-UD-IQ2_M.gguf` (3.55 GB on disk, ~5.1 GB cargado)
- mmproj: `mmproj-BF16.gguf` (945 MB, audio+vision encoder cargados)
- Flags activos: `--jinja --flash-attn on --cache-type-k/v f16 --cache-ram 0 --cache-reuse 256 --no-context-shift --reasoning off --reasoning-budget 0 --chat-template-kwargs '{"enable_thinking":false}' --image-min-tokens 280 --image-max-tokens 1120`
- Sampling default Gemma 4: T=1.0, top_p=0.95, top_k=64, repeat_penalty=1.0
- 59 tools registradas en `Carter_v4/src/carter_v4/tools/`
- 22 tools anchor (siempre incluidas en retrieval)
- ReAct loop con max_depth=3, budget 25s/turn
- Verifier estructural: frame-diff numpy + Win32 EnumWindows + GetForegroundWindow
- CORE_PROMPT actual: ~1100 tokens hybrid English/Spanish con 12 reglas + 6 few-shots contrastivos
- Stage 0-3 multimodal aplicados: vision verifier híbrido, gui_check_blockers, vision_describe_dialog, Tier-3 OCR fallback en gui_universal_action

**Validaciones empíricas hechas hasta ahora:**
- 60-test bench externo (no oficial): 55/60 = 91.7% con T=1.0 + flags optimizados
- Smoke test 10 prompts del Contrato: 10/10 ejecutados sin excepción
- Sesiones REPL reales reportadas: triviales OK, single-tool OK, pero múltiples casos donde el modelo "se rinde" cuando falta un ID (track_id, appid, video_id) en lugar de encadenar search+click+vision

**Lo que NO está validado:**
- Bench oficial 540 casos en Gemma 4 (último audit con qwen3:4b dio 88.89% PASS oficial / 61% PASS REAL audit humano)
- Cadenas multi-step de 4+ tools end-to-end con UI real (Steam, Spotify abiertos)
- Patrones residuales A/B/D/E/F/J/K/L/M/N/O/P1 con Gemma 4

## Las 18 categorías del bench oficial (540 casos = 30 × 18)

C01 Conversación simple · C02 Identidad · C03 Conocimiento · C04 Memoria · C05 Preferencias · C06 Herramientas simples · C07 Apps · C08 Web · C09 Steam · C10 Filesystem · C11 Terminal · C12 Safety · C13 GUI/visión · **C14 Misiones compuestas** · C15 Latencia · C16 Multilingüe/typos · C17 Follow-ups · C18 Regresiones reales

El archivo completo del bench está en `01_BENCH_540_CASOS.md`. Cada caso tiene: ID, severidad P0/P1/P2, prompt, resultado esperado, tools esperadas, prohibido, criterio PASS oficial.

## Lo que tenés que entregar (5 deliverables)

### Deliverable 1 — Mapeo caso-por-caso de los 540 (tabla maestra)

Tabla con una fila por cada uno de los 540 casos:

| cid | severidad | prompt (primeros 60 chars) | patrón residual (A-P) | tool chain ideal | qué falla en Gemma hoy | fix concreto |
|---|---|---|---|---|---|---|

Para llenar esto NO hace falta correr el bench. Razoná cada caso contra la config actual del CORE_PROMPT, las anchors, las tools disponibles. Si un caso requiere una tool que NO existe en Carter, marcalo y propon agregarla.

**Granularidad confirmada:** agrupar similares + expandir únicos. Ver `RESPUESTAS_A_TUS_3_PREGUNTAS.md` para detalle.

### Deliverable 2 — CORE_PROMPT v3 final

El CORE_PROMPT actual de Gemma 4 tiene 12 reglas + 6 few-shots = ~1100 tokens. Está en `codigo_carter/03_models_gemma4.py`.

Diagnosticá qué reglas:
- Sobran (no aportan vs Gemma 4 nativo)
- Faltan (los 540 casos exponen patrones que no cubre)
- Se contradicen (ej regla 9 trivial vs imperativos cortos — ya hubo 1 fix)
- Tienen wording subóptimo para Gemma 4 (research dossier dice EN para reglas, ES para few-shots; verificar si todo está en su idioma óptimo)

Entregá un CORE_PROMPT v3 drop-in. **Restricción: ≤1500 tokens totales.** Cada regla y few-shot tiene que justificarse contra ≥3 casos del bench 540.

### Deliverable 3 — Tool retrieval anchors definitivas

`codigo_carter/05_tool_retrieval.py:_ANCHOR_TOOL_NAMES` hoy tiene 22 tools. Tenés que decidir las anchors ÓPTIMAS para que los 540 casos tengan en su catálogo del turno las tools que necesitan, sin saturar el contexto.

Restricción Gemma 4 IQ2_M:
- Cada tool en el catálogo agrega ~80-150 tokens al prompt
- 22 anchors actuales = ~2500 tokens del contexto se van solo en anchors
- top_k retrieval default: 12

Devolvé:
- Lista anchors finales con justificación por tool ("X aparece en N casos del bench")
- Cambios sugeridos al algoritmo de retrieval (BM25? hybrid? scoring con verbo del prompt?)
- Casos del 540 donde la tool ideal NO está en el catálogo del turno con la config actual (problemática que cierra el cambio de retrieval)

### Deliverable 4 — ReAct loop policy + multi-step orchestration

El issue más severo en sesiones REPL reales: Gemma 4 abandona la cadena tras 1 tool call. Pide el ID en vez de encadenar search+screenshot+vision+click.

Carter tiene `max_depth=3` y `budget=25s/turn`. Para misiones compuestas (C14) eso es insuficiente.

Devolvé:
- Política de ReAct adaptada por tipo de prompt: trivial (depth=1), tool simple (depth=2), misión (depth=8-12)
- Cómo detectar **cuándo** un turn requiere multi-step (estructural, no keywords)
- Cómo el agent sabe que tras `gui_deeplink(steam, search)` debe esperar carga + screenshot + vision automáticamente, sin que el LLM lo pida
- Diseño de un "step planner" pre-LLM que descomponga "instalá X en Steam" en pasos canónicos antes de la primera llamada a Gemma. Pseudocódigo Python ≤200 LOC.
- Cómo manejar el `finish_reason=length` en el medio de una cadena multi-step (visto en bench externo)

### Deliverable 5 — Plan de validación staged contra los 540

5 stages incrementales. Cada stage activa una mejora y mide impacto.

Por cada stage:
- Cambios exactos (archivo + línea aproximada)
- Casos del 540 que esperás que cierre
- Métrica de éxito (PASS rate del subset relevante, NO pretendas validar los 540 en cada stage)
- Criterio de rollback

Stages propuestos (ajustables):
- **Stage A**: CORE_PROMPT v3 + anchors definitivas — ¿cuántos casos cierra solo con esto?
- **Stage B**: ReAct depth dinámico + step planner pre-LLM — afecta C14 + multi-step en otras categorías
- **Stage C**: Vision triggers automáticos post-deeplink — afecta C09 (Steam), C08 (web), C14 (misiones compuestas)
- **Stage D**: Verifier orchestration con TOOL_OK_VERIFIER_INCONCLUSIVE — afecta C09, C13
- **Stage E**: Anti-mentira post-LLM checks aplicados al reply final — afecta todos

El último stage debe rendir un **número defendible** del PASS rate esperado al 540, con margen de error.

## Restricciones (innegociables)

1. **Modelo fijo**: gemma-4-E4B-it-UD-IQ2_M. NO proponer cambio de quant ni modelo.
2. **Hardware fijo**: RTX 4060 Ti 16 GB CUDA. Sin offload CPU.
3. **Stack fijo**: llama.cpp b9090, llama-server, Carter v4 con sus 59 tools.
4. **VRAM target**: ≤8 GB pico (modelo + KV f16 16K + mmproj). Margen para Whisper futuro.
5. **Latencia Alexa-tier**:
   - Trivial p99 <5s
   - Tool simple p99 <8s
   - App open p99 <15s
   - Misión compuesta p99 <30s
6. **Sin per-app hardcodes**: NO `if Steam` en el cerebro. Resolución por intención + recursos del sistema.
7. **Audio nativo**: omitido por ahora (Whisper aparte).
8. **NO romper qwen3 fallback**: el módulo `carter_v4/models/qwen3.py` debe seguir funcionando bit-perfect para `--no-gemma`.

## Honestidad por construcción

Si algún caso del 540 simplemente NO se puede cerrar con E4B-IQ2 (techo capability del modelo), decílo:
- "C14-22 (corregir bug + agregar test que falle antes) requiere razonamiento de programador, E4B-IQ2 no llega"
- "C03-XX (conocimiento atemporal específico) puede alucinar; recomendar marcar UNVERIFIED en lugar de forzar PASS"

Estimar honestamente el techo:
- ¿Qué % de los 540 es realmente alcanzable con esta config?
- ¿Cuántos son cuello de botella del modelo vs cuello del agente?

Si tu conclusión es "no llegamos a 540/540 con IQ2_M, máximo realista es 510/540 = 94%", quiero ese número con desglose por categoría, no un upsell.

## Lo que NO entra en esta investigación

- Comparación con qwen3 / mistral / llama4 (ya validamos Gemma 4 como ganador)
- Reescritura de Carter en otro framework
- Audio multimodal (otra investigación)
- Migración a vLLM / WSL2
- Bench rewrite (los 540 casos son el contrato, no se cambian)

## Archivos a leer

Ver `INDICE.md` para mapeo completo. En resumen:

- `01_BENCH_540_CASOS.md` — los 540 casos
- `02_full_matrix_runner.py` — cómo se evalúa cada caso
- `codigo_carter/03_models_gemma4.py` a `codigo_carter/09_tools_init.py` — código actual de Carter
- `research_dossiers/10_REPORTE_BENCH_60_CASOS.md` a `research_dossiers/13_MULTIMODAL_GEMMA4.md` — research dossiers verificados sobre Gemma 4
- `audit_qwen3/14_OPUS_DOSSIER_PATRONES_A_P.md` y `audit_qwen3/15_OPUS_DOSSIER_PROYECTO.md` — análisis del audit qwen3 sobre los 540 casos con los 16 patrones residuales

## Tiempo y profundidad

Esta investigación NO es exploratoria. Es de cierre. Estimar 6-10 horas de pensamiento + lectura de los archivos. El output debe ser implementable directamente: cada cambio propuesto con archivo + línea + diff conceptual.

Si en algún punto detectás que los archivos del repo y el research no alcanzan para responder con precisión un caso específico, decílo: "C14-XX requiere correr el caso real para validar, no puedo prescribir el fix sin medirlo". No inventes números.

## Output esperado

Un único documento markdown con las 5 secciones (Deliverable 1-5) + las restricciones + el techo realista estimado.

Sin sección de teoría general. Sin "considerations". Solo: qué cambia, dónde, por qué cierra X casos del bench, cómo se valida.

Adelante.
