# Documentación — Gemma 4 Agent

Índice de toda la documentación del proyecto, ordenada por temática.
Movida y consolidada el 2026-05-22 desde múltiples carpetas sueltas
(`docs/`, `audit/`, `bench/`, `Investigaciones Router/`, raíz del repo).

> **No funcional:** estos son documentos de lectura. El código operativo
> vive aparte y **no** se movió: `prompts/tool_rules/`, `skills/`,
> `microagents/`, y `documentacion/` (índice numerado) siguen en su lugar
> porque el runtime los carga por ruta. Igual `harness_carter540/`,
> `audit/*.py`, `bench/*.py` y `evidencia pruebas gemma4/` (harness +
> resultados + samples), que son artefactos ejecutables, no docs.

---

## `research/` — Investigaciones, por temática

El corazón del archivo: informes de investigación y prompts de research
agrupados por tema. (Los archivos crípticos `compass_artifact_wf-…` y
`deep-research-report` fueron renombrados a títulos descriptivos según
su contenido el 2026-05-22.)

- **`research/router/`** — Router de tools:
  - `router_unificado_selectivo_investigacion.md` — investigación del
    router unificado y selectivo (deep-research).
  - `router_audit_arquitectura_y_migracion.md` — audit + plan de migración.
  - `router_plan_migracion_hacia_100.md` — plan técnico para llevar el
    router a ~100%.
  - `router_arquitectura_retriever_hibrido_rrf.md` — retriever híbrido
    BM25+dense con RRF para 65 compound tools.
  - `router_calibracion_tight_cluster_band.md` — recomendación de la banda
    TIGHT_CLUSTER.
  - `PROMPT_FOR_ROUTING_RESEARCH.md`, logbooks de rebuild, y el PDF
    "Optimizing Voice Assistant Tool Router".
- **`research/voice_stt/`** — STT y pipeline de voz:
  - `whisper_small_cpu_spanglish_accuracy.md` — maximizar precisión de
    Whisper-small en CPU para asistente Spanglish.
  - `stt_precision_local_analisis.md` — análisis de precisión local de STT.
  - prompt de research de STT, rediseño del pipeline de voz (prompt +
    clarifications), camino de training del wake-word custom.
- **`research/streaming/`** — Reproducción de títulos en plataformas:
  `streaming_playback_field_guide_2026.md` (Netflix/Disney+/HBO Max/Prime).
  ⚠️ Referenciado por `domain_tools.py` (selectores/URLs).
- **`research/latency/`** — Presupuesto de latencia: prompt de research +
  "golden eras" de latencia.
- **`research/audio_vision/`** — Audio multimodal: informe de estado de
  audio para Carter.

## `architecture/` — Arquitectura y diseño

- Documento maestro `ARCHITECTURE.md`, `INFORME_ARQUITECTURA_6GB.md`
  (origen de los números de VRAM de `profiles.py`), `PLAN_CERRADO.md`,
  el prompt de auditoría externa, y los deltas (`00_..08_`).
- **`architecture/_baseline_audit/`** — Auditoría baseline completa
  (inventory, system, components, classes, sequences, data, deps, tools,
  findings).
- **`architecture/design/`** — Notas de diseño puntual (barge-in).

## `audits/` — Auditorías y logs de fixes

Reportes de auditoría (`AUDITORIA_2026_05_14`, `NIGHT_AUDIT_2026_05_16`,
`audit_report`), checklists de merge/consolidación, logs de fixes,
optimización, smoke, tradeoffs, y las auditorías externas
(`review_arquitectonico_3_bugs_voz.md` + AUDIT_REPORT externo + informe
de optimización externa).

## `reports/` — Reportes de sesión

`INFORME_NOCTURNO`, `MORNING_REPORT`, y los reportes de sesión
(continuation / overnight 2026-05-21).

## `benchmarks/` — Mediciones

Baselines y reportes de latencia, validación E2E del LLM, hunt de
flakiness, shakedown final, validación overnight.
(Los `.json`/`.py` de `bench/` quedaron en `bench/` — son el harness.)

## `sprints/` — Prompts y logs de sprints

Los 49 documentos de `sprint_prompts`: cada sprint (0..8c), los hotfixes
del 2026-05-17 (a..t), y sus logs (`_sprintN_log.md`).

## `carter/` — Integración con Carter

`REPORTE_GEMMA4_PARA_CARTER`, `PARA_AGENTE_CARTER_PROMPTS_SEPARADOS`.
La evidencia de validación completa (Contrato, REPORTE, VALIDACION,
INFORME_AUDIO + harness + samples) sigue en `../../evidencia pruebas gemma4/`
porque es un bundle ejecutable con su harness; no se duplicó.

## `product/` — Producto y proceso

`PRODUCTION_READY` (gate de aceptación), `PORTING_PLAN`, `MCP`,
`BRANCHING` (modelo de ramas).

## `prompts_externos/` — Prompts para agentes externos

Prompts de misión para otros modelos/sesiones: research de router para
ChatGPT/Gemini, misión nocturna del router.

## `_archive/` — Volcados de contexto

Dumps accidentales de contexto de sesión (`contextoclaude.md`,
`ContextoClaude_gemma4_agent.md`). Sin valor documental; archivados por
si acaso.
