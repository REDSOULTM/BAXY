# Recolección histórica de mensajes — lineage Carter OS → Baxy

> Nota de nomenclatura: el producto se llama hoy **Baxy** (antes "Gemma 4 Agent",
> brevemente "Carter"). En este documento, "Carter v1-v5" / "Carter OS AI" / los
> paths `Carter OS AI/...` y las etiquetas de dataset (`carter_*`, `project:carter`,
> `CARTER_TO_GEMMA4`) refieren al **proyecto de referencia externo** del que se
> minan mensajes históricos — NO se renombran. El **modelo** sigue siendo Gemma 4.

**Pedido del usuario (2026-06-02):** recopilar TODOS los mensajes históricos desde el
primer mensaje del lineage Carter (predecesor) hasta el último a Baxy, para curarlos como
dataset de ejemplos PERFECTOS y tunear el sistema (router + LLM 4B) sin overfitting.

Este documento registra QUÉ se recolectó, DE DÓNDE, CUÁNTOS y en QUÉ FORMATO.
Extractor reproducible: `dataset_finetune/scripts/extract_history.py`.
Salida cruda: `dataset_finetune/raw/history_raw.jsonl`.

---

## Resumen (EXTRACCIÓN EXHAUSTIVA v2 — TODO Carter v1-v5 + Gemma4)

| Métrica | Valor |
|---------|-------|
| **Mensajes ÚNICOS (dedup por texto)** | **3,691** ← universo real a curar |
| Con reply | 1,927 |
| Con tools ejecutadas | 1,374 |
| Con ground-truth (tool esperada / criterio) | 1,630 |
| Con latencia medida | 1,037 |
| Carter únicos | 1,678 |
| Gemma4 únicos | 2,013 |

**Nota:** la v1 del extractor (parcial) dio 2,502 únicos tocando solo v4/v5. La v2
EXHAUSTIVA suma ~1,200 más al cubrir Carter v2 (642), v3 (477) y los benches .md de
ground-truth (540 + 60 Gemma4). El dedup por (proyecto, prompt normalizado) hace que
v4/v5 den 0 nuevos: sus 540 prompts ya están cubiertos por el ground-truth .md y por v2/v3
(son RE-CORRIDAS de los mismos prompts, no prompts nuevos).

---

## Fuentes recolectadas

### 1. Gemma4 `traces.jsonl` — 9,006 turnos
- Ruta: `gemma4_agent/data/traces.jsonl` (153,939 eventos totales).
- Reconstrucción: por `turn_id`, uniendo `request_start` (mensaje) + `tool_call*` (tools+args) + `final` (reply).
- 9,006 turnos con mensaje del usuario.
- **CAVEAT:** el mensaje viene del campo `content.preview` del trace. Para mensajes de voz
  típicos (cortos) es el texto completo (verificado: 0 con chars>len). Mensajes muy largos
  podrían estar truncados en el log original — se marca en curación.

### 2. Carter tests 540 (`carter_v4` + `carter_v5`) — 952 casos únicos
- Rutas: `Carter OS AI/legacy/Carter_v4/audit/runs/iter*_full540.json` +
  `Carter OS AI/carter_v5/audit/runs/bench_540_*.json`.
- Estructura por caso: `{cid, category, severity, prompt, expected_tools, reply, tools, latency_ms, status}`.
- **Estos traen GROUND-TRUTH curado a mano** (expected_tools, prohibido, criterio) — la base más limpia.
- 18 categorías × 30 casos (Conversación, Identidad, Router, Apps, Steam, Filesystem,
  Seguridad, GUI, Misiones, Latencia, Multilingüe, Follow-ups, Regresiones, etc.).
- Definición oficial del bench: `Carter OS AI/docs/investigaciones/.../01_BENCH_540_CASOS.md`.

### 3. Carter v1 `runs_log.jsonl` — 0 utilizables
- Ruta: `Carter OS AI/legacy/Carter_v1/runs_log.jsonl`.
- El log viejo registra resultados por ID de test (ok/elapsed), **sin el prompt textual**.
- 0 registros con mensaje recuperable → omitido (no se inventan textos).

### 4. Gemma4 `router_corpus_real_logs.jsonl` — 1,071 mensajes COMPLETOS
- Ruta: `gemma4_agent/data/router_corpus_real_logs.jsonl`.
- Mensajes reales del usuario YA deduplicados + con `expected` + `prev`.
- **Mensajes completos, no truncados** (la mejor fuente de frases reales del usuario).

### 5. Carter v2 runs — 642 únicos
- Ruta: `Carter OS AI/legacy/Carter_v2/audit/results/*.json` (45 archivos).
- Formato: `{cid, category, prompt, mode, status, total_ms, llm_calls, tool_calls, reply_excerpt, ...}`.
- Trae prompt + reply_excerpt + tool_calls + latencia (total_ms).

### 6. Carter v3 runs — 477 únicos
- Ruta: `Carter OS AI/legacy/Carter_v3/audit/runs/*.json` (176 archivos, incl. iteraciones "v6"=sufijo).
- Formato: `{cid, category, prompt, status, total_ms, tool_calls, tool_families, reply_excerpt, ...}`.

### 7. Carter v4/v5 runs — 0 nuevos (ya cubiertos)
- Rutas: `legacy/Carter_v4/audit/runs/*.json` (211) + `carter_v5/audit/runs/*.json` (15).
- 0 prompts nuevos: son RE-CORRIDAS de los mismos 540 que ya están en el ground-truth .md y v2/v3.

### 8. Benches .md con ground-truth — 559 únicos
- `01_BENCH_540_CASOS.md` (v1, oficial): 518 casos con prompt + tool esperada + prohibida + criterio.
- `10_REPORTE_BENCH_60_CASOS.md`: 41 casos exclusivos de Gemma4 (NO de los 540).
- v2/v3 .md: idénticos a v1 (dedup → 0 nuevos).

---

## EXCLUIDO a propósito (con justificación)

- **memory.db (161 SQLite)**: NO son conversaciones — son la memoria de HECHOS del asistente
  (tabla `memory` con key/value/confidence/source_turn_id). No hay mensajes user→reply ahí.
- **Competidores** (openclaw, OS-Copilot, Hermes3): datos de OTROS productos —
  openclaw=caché i18n (traducciones gpt-5.5), OS-Copilot=tareas Excel, hermes=tareas browser
  en inglés. Entrenar con ellos SESGARÍA hacia otro producto/idioma/estilo = el overfitting que
  el usuario quiere evitar. Revisados 2026-06-02, EXCLUIDOS del training (sirven solo como
  referencia de diseño, ya analizada en `documentacion/BACKLOG_competidores.md`).
- **venv/.runtime/site-packages**: dependencias (sympy/torch benchmarks), no mensajes.

---

## Esquema unificado (cada registro en `history_raw.jsonl`)

```json
{
  "id": "<source>_<n>",
  "source": "gemma4_traces|carter_v4_540|carter_v5_540|gemma4_corpus",
  "project": "carter|gemma4",
  "user_text": "<mensaje del usuario>",
  "prev_text": "<turno anterior o ''>",
  "tools_called": ["app", ...],          // lo que REALMENTE pasó (puede estar MAL — se re-cura)
  "tool_args": [{...}, ...],
  "reply": "<respuesta del asistente>",
  "latency_ms": <int|null>,
  "status_original": "PASS|FAIL|null",   // juicio original — NO confiable, se re-evalúa en curación
  "expected_tools": [...],               // ground-truth si la fuente lo trae (Carter 540 / corpus)
  "expected_note": "<criterio esperado en NL si existe>",
  "ts": "<timestamp|null>"
}
```

---

## Principio anti-error (regla del usuario)

`tools_called`, `reply` y `status_original` reflejan lo que el sistema HIZO — que puede estar
MAL. **NUNCA se entrena con eso directamente.** La FASE 2 (curación) revisa mensaje por mensaje,
determina la tool/respuesta CORRECTA, y produce un dataset separado de ejemplos PERFECTOS
(`curated/`). Solo lo curado-correcto alimenta el router-FT (FASE 4) y el QLoRA (FASE 6).

## Mapeo de tools Carter → Gemma4 (FASE 1, pendiente)

Carter usó ~60 tools individuales (`system_time`, `filesystem_write`, `gui_deeplink`...).
Gemma4 usa 16 compuestas (`system`, `filesystem`, `gui`, `app`, `media`...). La curación de
ejemplos de Carter requiere traducir cada tool individual → la compuesta de Gemma4 (ej.
`system_time`→`system`, `media_play`→`media`). Tabla de mapeo en FASE 1.

---

*Generado en FASE 0. Próximo: FASE 1 (esquema curado + mapeo de tools), FASE 2 (curación
mensaje-por-mensaje con agentes).*
