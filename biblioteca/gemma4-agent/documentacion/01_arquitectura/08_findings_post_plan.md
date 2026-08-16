# 08 — Findings post-plan (deuda restante + Sprint 3b)

> **Tipo:** delta auditoría — qué quedó por hacer después de 8 sprints.
> Para los findings originales ver
> [`_baseline_audit/08_findings.md`](../_historico/baseline_audit/08_findings.md).
> Este documento es el **mapa de oportunidades futuras**, ordenado por
> ROI y riesgo.

---

## 0. Resumen ejecutivo

**El plan ejecutó 8 sprints (0-1-2-3a-4-5a-5b-6) y cerró formalmente
en `7f2eecc`.** El repo está hoy en su mejor estado estructural sin
tocar comportamiento del agente. Lo que sigue es **oportunidad
incremental**, no urgencia.

3 categorías de deuda restante, en orden de "vale la pena":

1. **Sprint 3b** (diferido a propósito) — medir uso real de personas /
   microagents / skills tras 7-10 días con instrumentación activa.
2. **Acciones MED del baseline aún no atacadas** — varias `08_findings.md
   §3` baseline que el plan operativo no incluyó.
3. **God classes conservadas conscientemente** — workers, MainWindow,
   SettingsDialog. Decisión documentada, **no es deuda accidental**.

---

## 0.1 Acciones de Sprint 7 (post-auditoría externa)

Una auditoría externa post-plan (claude.ai, 2026-05-17) identificó
7 acciones accionables, todas validadas por el operador contra datos
reales antes de ejecutar. Estado al cierre de Sprint 7:

| Acción del audit | Sprint 7 | Status |
|---|---|---|
| `state.json` TTL real (baseline §2.3) | 7.2 | ✅ implementado (`purge_stale_closed` + boot hook + 8 tests) |
| `traces.jsonl` rotation preventiva | 7.3 | ✅ implementado (50 MB / 3 archives + 6 tests) |
| Instrumentar `voice_e2e_latency_ms` + `prompt_built_tokens` | 7.1 | ✅ implementado (2 events: BUS `voice_e2e_latency` + trace `prompt_built`) |
| Fail-loud en `experience.sqlite` schema migration | 7.4 | ✅ implementado (`RuntimeError` con remediation + 3 tests) |
| Barge-in (no implementar, sólo documentar) | 7.5 | ✅ doc en `docs/architecture/design/barge_in.md` — implementación es Sprint 8 |
| Crash recovery: documentar lo que YA existe | 7.6 | ✅ §6 en `01_delta_system.md` (5 subsecciones) |
| `analyze_traces.py` con `% of turns` + recommendation | 7.7 | ✅ implementado en secciones B/C/D |

**La auditoría externa NO modificó decisiones conservadas conscientemente:**
MainWindow, SettingsDialog, workers (AgentWorker/AgentRunner) siguen
intactos por las mismas razones documentadas en `_sprint4_log.md`,
`_sprint5b_log.md` y `_sprint6_log.md`. La auditoría externa, después
de leer los logs, validó que las decisiones de conservación están bien
justificadas.

**LOC Sprint 7:** +977 (mayormente tests + dos design docs).
**Tests Sprint 7:** +17 nuevos (3 archivos), 0 regresiones.

---

## 0.2 Acciones de Sprint 8a (routing infra)

Una investigación de Claude Research (mayo 2026) sobre tool-routing
para agentes locales con catálogos grandes y multi-idioma motivó
**Sprint 8** (subdividido 8a/8b/8c). Sprint 8a, completado en este
ciclo, construye la **infraestructura** del nuevo router universal
sin regex; 8b y 8c siguen.

| Acción | Sprint 8a | Status |
|---|---|---|
| Bootstrap del modelo e5-small ONNX (113 MB, 100 langs) | 8a.1 | ✅ `scripts/bootstrap_e5_small.py` (idempotente) |
| Router v2 con pipeline de 4 layers | 8a.2 | ✅ `gemma4_agent/router_v2.py` (415 LOC, default OFF) |
| Tests de contrato del router v2 | 8a.3 | ✅ `gemma4_agent/test_router_v2.py` (22 tests) |
| Wire opt-in en `agent.py` (shadow mode + full v2) | 8a.4 | ✅ `agent.run_content` con dos env-flags |

**Hallazgos críticos de calibración (queda en docstrings del módulo):**

1. **El threshold absoluto de smalltalk no funciona** con e5-small.
   Embeddings densos → cualquier query da cosine 0.85-0.95 contra
   cualquier centroide. Cambié a **delta** (smalltalk − tools) con
   threshold +0.025. La gate ahora distingue greetings de comandos.
2. **`FALLBACK_THETA` con RRF k=60** debe vivir en banda 0.01-0.05
   (no 0.30). Con k=60 sobre 65 docs, el top-1 teórico máximo es
   ~0.033. Threshold final: 0.025.
3. **ONNX e5-small necesita `token_type_ids`** (BERT-style), siempre
   zeros. La doc de huggingface no lo dice — el `session.run()`
   falla si no se pasa.

**Por qué default OFF:** las 65 tool descriptions actuales son
cortas (legado de `semantic_router.py`). BM25 tiene poco material
para queries con marcas/intents específicos ("Netflix", "Daredevil",
"investiga"). Esto se resuelve en 8b con `purpose + example_queries`.
Activar v2 ahora produciría peores resultados que v1.

**Estado de uso:**

- Default: v1 (planner + semantic_router) activo. No hay cambio
  visible.
- Para probar v2 en producción con datos reales (recomendado para
  preparar 8c):
  ```pwsh
  python scripts/bootstrap_e5_small.py  # una vez
  $env:GEMMA4_ROUTER_V2_SHADOW = "1"     # log v2 vs v1, no cambia v1
  ```

**LOC Sprint 8a:** +776 (router_v2 + tests + bootstrap + agent hook).
**Tests Sprint 8a:** +22 nuevos, 0 regresiones (790 total verde).

---

## 1. PENDIENTE: Sprint 3b (diferido por diseño)

### 1.1 Por qué se difirió

Sprint 2 agregó eventos de instrumentación nuevos al BUS:
- `persona_active` (commit `8a2ef09`)
- `microagent_matched` (commit `6062cd8`)
- `skill_loaded` (commit `877736a`)

Estos eventos **empezaron a loggearse desde Sprint 2 en adelante**.
En Sprint 3a, los conteos eran 0 — pero ese 0 era por **instrumentation
gap**, no por desuso real.

Esperar 7-10 días de uso normal del agente permite acumular datos
**confiables** sobre:
- Cuál de las 6 personas hardcoded (`default, coder, researcher,
  creative, planner, casual`) se usa en producción.
- Cuál de los 5 microagents (`microagents/*.md`) matchea inputs reales.
- Cuál de los 10 skills (`skills/*/SKILL.md`) se invoca vía `skill_load`.

### 1.2 Cómo ejecutar Sprint 3b

**Cuando hayan pasado 7-10 días de uso real:**

```bash
python scripts/analyze_traces.py > /tmp/post_use_report.md
```

El script lee `gemma4_agent/data/traces.jsonl` y reporta secciones
B (personas), C (microagents+skills), etc.

**Criterios de decisión:**
- Personas con `count == 0`: candidatas a eliminar (audit baseline
  §3.5 LOW las marcó).
- Microagents con `count == 0`: candidatos a eliminar (~70-300 LOC
  de markdown + parser entries).
- Skills con `count == 0`: candidatas a eliminar (~50-200 LOC de
  markdown).

**Si después de 7-10 días un componente sigue `count == 0`**: eliminar
es seguro con relativamente alto nivel de confianza. **NO antes.**

### 1.3 Estimación de LOC ahorrables (si Sprint 3b se ejecuta)

Conservative (suponiendo que ~50 % de cada categoría sea borrable):

| Categoría | Si todo se borra | Si 50 % se borra |
|---|--:|--:|
| 5 de 6 personas | ~80 LOC | ~40 LOC |
| 4 de 5 microagents | ~100 LOC + 4 .md | ~50 LOC + 2 .md |
| 5 de 10 skills | ~250 LOC en markdown | ~125 LOC en markdown |
| **Total estimado** | **~430 LOC + 9 .md** | **~215 LOC + 5 .md** |

No es enorme pero es **trabajo limpio** (no rompe nada, datos
confiables, decisión binaria).

### 1.4 Prompt de Sprint 3b (cuando lo necesites)

Cuando llegue el momento, decime y te armo el prompt específico para
el agente. Tendría estas tareas:

1. Re-correr `scripts/analyze_traces.py` y guardar `_sprint3b_usage_report.md`.
2. Para cada componente con `count == 0`: confirmar removal + eliminar.
3. Para componentes con `count > 0`: documentar y dejarlos.
4. Tests preexistentes deben seguir verde.
5. Log final + cierre definitivo del plan.

---

## 2. Acciones MED del baseline aún NO atacadas

Lo que el baseline `08_findings.md` marcó como severidad **MED** pero
el plan operativo no incluyó. Cada una es una mini-tarea independiente
si en algún momento te molesta.

### 2.1 `state.json` no purga `closed` resources (audit baseline §2.3 HIGH)

**Estado actual:** sigue pendiente. 84 % de los `resources` eran
zombies en la muestra original.

**Acción:** modificar `state.AgentState.mark_cleaned()` para
`del data["resources"][rid]` en lugar de cambiar status.

**Riesgo:** romper consumers que asumen que las closed siguen en
disco. Verificación con `grep -rn "status.*closed" gemma4_agent/`
antes de tocar.

**Esfuerzo:** S (1h con verificación).

**Recomendación:** **hacelo manualmente** con el script en
`05_delta_data.md §2`. No vale la pena un sprint propio.

### 2.2 `traces.jsonl` sin rotación (baseline §2.4)

**Estado actual:** 1.7 MB en la muestra original, crece monótonamente.
Telemetry tiene `rotate(keep_days=30)`, este sink no.

**Acción:** agregar rotación por tamaño o por días a `TraceLogger`.

**Riesgo:** bajo (solo escritura).

**Esfuerzo:** S (~40 líneas).

**Recomendación:** hacelo si en algún momento ves que el archivo
crece a >50 MB. Hoy no es urgente.

### 2.3 Migrar TraceLogger callers a BUS → LogRecorder (baseline §2.5)

**Estado actual:** TraceLogger sigue activo con 50+ call sites en
`agent.py`. Sprint 4.4 lo evaluó como alto riesgo y diferió.

**Riesgo:** alto (mecánico pero muchos sitios; bug silencioso si se
salta alguno).

**Esfuerzo:** M (medio día).

**Recomendación:** **NO lo hagas** salvo que tengas un motivo concreto.
La duplicación es funcional pero contenida.

### 2.4 Lazy-load TOOL_RULES + CORE_PROMPT a `prompts/*.md` (baseline §2.11)

**Estado actual:** sigue siendo string literal de 560 LOC en
`agent_prompt.py`.

**Acción:** mover `CORE_PROMPT` y `TOOL_RULES["X"]` a archivos
markdown lazy-loaded.

**Riesgo:** medio (cambiar el prompt sin querer es bug catastrófico
en el agente).

**Esfuerzo:** M.

**Recomendación:** **opcional**. Útil solo si vas a iterar sobre el
prompt frecuentemente.

### 2.5 Eliminar `_FALLBACKS_BY_LANG` para idiomas no ES/EN (parcial)

**Estado actual:** Sprint 3a redujo de 6 idiomas a 2 (es+en). Hecho.

### 2.6 Reducir AppResolver de 9 fuentes a 3-4 (baseline §2.14)

**Estado actual:** sigue con 9 fuentes en `app_resolver.py`. El
módulo está bien aislado ahora pero internamente sigue siendo god
class (16 métodos).

**Acción:** medir cuál fuente aporta qué % de candidatos únicos.
Eliminar las que aportan <5 %.

**Riesgo:** bajo (sub-sistema aislado).

**Esfuerzo:** M (necesita instrumentar + medir).

**Recomendación:** hazlo si en algún momento `AppResolver.find()`
está lento (>500ms).

### 2.7 SDK oficial MCP (baseline §2.13)

**Estado actual:** `mcp_server.py` sigue implementando JSON-RPC desde
cero (332 LOC).

**Acción:** reescribir con el paquete oficial `mcp`.

**Riesgo:** medio (compatibilidad con Claude Desktop / Cursor / goose).

**Esfuerzo:** M.

**Recomendación:** **opcional**. Solo si querés que el código sea
futuro-compatible automáticamente con cambios de spec MCP.

---

## 3. God classes conservadas a propósito (NO son deuda)

### 3.1 `ui/main_window.py` (1 430 LOC, 53 métodos)

**Razón documentada:** "55 métodos comparten 15+ state attrs
compartidos" (Sprint 5b log). Es **acoplamiento real del dominio**,
no accidente. Una MainWindow PyQt típicamente coordina N widgets +
N signals + M dialogs + persistencia de layout. Splitear requeriría
inventar protocolos artificiales entre subwidgets.

**Acción recomendada:** **conservar.** Si un bug específico te molesta,
atacalo localmente.

### 3.2 `ui/settings.py` (1 148 LOC, 22 métodos)

**Razón documentada:** "tabs comparten refs vía `self._gather()`"
(Sprint 5b log). Cada tab lee/escribe al mismo dict de configuración.
Splitear por tab requiere rediseñar la persistencia.

**Acción recomendada:** **conservar.** Lo que sí podés hacer en cualquier
momento: extraer constantes (orden de tabs, defaults) a `ui/settings_defaults.py`.

### 3.3 `agent_runner.py` (552 LOC) + `ui/agent_thread.py` (220 LOC)

**Razón documentada:** divergen genuinamente en threading model
(Thread vs QThread), output channel (BUS vs pyqtSignal), build
sequence (5 pasos vs 2 pasos), presencia de health_loop.

Los tests de paridad de Sprint 5a.3 confirmaron paridad de **API**
(ambos tienen `submit`, `stop`, etc.) pero NO de **flujo interno**.

**Acción recomendada:** **conservar.** Colapsar sin tests de flujo
interno = bug silencioso garantizado.

### 3.4 `tracing.py` (67 LOC) + `telemetry.py` (443 LOC)

**Razón:** ambos sinks tienen 50+ callers (TraceLogger) o son opt-in
(Telemetry). Migrar a BUS canonical es alto riesgo por marginal beneficio.

---

## 4. Lo que NO se va a poder mejorar más sin cambios mayores

Tres categorías de cosas que **no son deuda** sino **diseño asumido**:

### 4.1 `domain_tools.py` 10 489 LOC

Es un archivo gigante pero **conservado a propósito**. Sprint 4 verificó
que sus top-level imports ya son livianos (lazy dentro de cada
`<name>_tool`). El archivo concentra 33 funciones tool con ~290
helpers privados. Splitear arbitrariamente no aporta nada — los
splits naturales serían "tools de Windows" / "tools de docs" / "tools
de comm" / etc., pero cada caller actual sería `from
.domain_tools_<sub> import X` igualmente.

**Veredicto:** **no es god module, es módulo grande con razón**.

### 4.2 `ToolRegistry` (`tools.py:1486+`, ~3 000 LOC dentro de clase)

Después de extraer `app_resolver`, `ssrf_guard`, `tool_schemas`,
`_shared`, sigue siendo grande. La auditoría baseline lo marcó
CRITICAL pero ejecutar el split completo requiere:
- Tests de cada `t_*` handler (no existen aún).
- Cycle resolution de 5 helpers privados (Sprint 6.6 SKIP).

**Veredicto:** la red de tests de Sprint 6.5 quedó escrita por si
alguien retoma. **Hoy no es urgente.**

### 4.3 `Gemma4Agent.run_content` (~600 LOC en HEAD vs 892 baseline)

Bajó de 892 a ~600 al extraer guards + compaction + dispatch. **No
puede bajar más sin sacrificar legibilidad** — lo que queda es el
turn loop honesto (planner → tools → guards → reply) que es la
secuencia lineal del comportamiento del agente.

---

## 5. Resumen de oportunidades

| Acción | ROI | Riesgo | Esfuerzo | Recomendación |
|---|---|---|---|---|
| **Sprint 3b** (datos personas/microagents/skills) | alto | bajo | S | **HACER cuando pase 1 semana de uso** |
| Purgar `state.json` closed | medio | bajo | S | hacer a mano, no sprint |
| Rotación de `traces.jsonl` | bajo | bajo | S | solo si crece >50MB |
| Migrar TraceLogger → BUS | bajo | alto | M | **NO hacer** |
| Lazy-load prompts a `.md` | medio | medio | M | opcional |
| Reducir AppResolver fuentes | bajo | bajo | M | solo si está lento |
| SDK oficial MCP | bajo | medio | M | opcional |
| Splitear MainWindow / SettingsDialog | negativo | alto | L | **NO hacer** (god class intencional) |
| Colapsar AgentRunner ≡ AgentWorker | negativo | alto | L | **NO hacer** (divergen genuinamente) |
| Splitear ToolRegistry dispatch pipeline | bajo | medio | M | red de tests escrita por si querés |
| Splitear `domain_tools.py` | negativo | bajo | M | no aporta nada |

---

## 6. Estado final del plan

| Aspecto | Score |
|---|---|
| god classes >1 000 LOC | 2 (UI, conservadas) — era 4 |
| Ciclos de import | 0 — preservado |
| Código muerto real | 0 — confirmado en Sprint 6 |
| Duplicaciones auto-confesadas | 0 — eliminadas en Sprint 4 |
| Tests de contrato | 107 — protegen las APIs públicas |
| Tools del LLM | 65 — intactas, decisión consciente |
| Carter residual | 0 funcional, 0 visible — cleanup Sprint 1 |
| Estabilidad runtime | igual a baseline — 0 regresiones |
| Reproducibilidad | sí, ahora con `requirements.txt` + `pyproject.toml` |
| Documentación de arquitectura | **completa** — baseline + delta |

**Veredicto:** el plan logró lo que prometió. Lo que queda es
**uso real** + **decisiones puntuales** cuando algo concreto te
moleste, no más sprints de optimización masiva.
