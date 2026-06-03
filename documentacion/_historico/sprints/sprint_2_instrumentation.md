# PROMPT — Sprint 2 (instrumentación de telemetría)

> Continúa el mismo chat de Claude Code que corrió Sprint 0+1. El
> agente conoce el repo, los commits y el log
> `docs/architecture/sprint_prompts/_overnight_log.md`. Copy/paste el
> bloque de abajo cuando estés listo para lanzar.

---

## Contexto rápido (para el agente, ya commiteado)

Desde el último prompt el repo cambió: se hicieron 5 commits más
después de tu `_overnight_log.md`. El working tree ahora arranca limpio.

- `bc764cf docs(architecture): restore full audit tree to docs/architecture root`
- `ad6911b feat(routing): restore NLI-based routing & validation modules`
- `c54f032 test: restore 22 new tests + 8 modified for routing & WIP coverage`
- `8a48f89 scripts: restore streaming probes (Playwright/CDP) + their JSON outputs`
- `0ccebdd chore: gather external docs + gitignore trace dumps`

Estos commits recuperaron código que estaba en stash@{0} (que el operador
hizo para que tus commits del sprint anterior quedaran limpios). En
particular:

1. **`gemma4_agent/capability_classifier.py`, `grounding_gate.py`,
   `intent_validator.py`, `nli_service.py`, `_ml_import_lock.py`** —
   los 5 módulos de routing/validation que la auditoría describe en
   `docs/architecture/02_components/routing.md` y
   `03_classes/routing.md`. Ahora **existen** en HEAD (no estaban
   cuando saltaste Sprint 1.4 y 1.5).
2. **`gemma4_agent/experience.py`** — ahora tiene los métodos
   `flag_grounding` + `flag_grounding_by_turn` que en tu sprint
   anterior reportaste como inexistentes. Sigue válido el plan de
   colapsarlos (era Sprint 1.4), pero **no es prioridad para
   Sprint 2**; lo dejamos para Sprint 3.
3. **`docs/architecture/`** — toda la auditoría ahora vive ahí (no
   en `gemma4_agent/docs/architecture/`). El `08_findings.md` es la
   fuente del plan; el `_findings_seed.md` tiene los detalles crudos.

Sprint 2 NO toca código de producción. Es **observabilidad pura** para
preparar las decisiones de Sprint 3 con datos reales.

---

## Prompt completo (copy/paste al chat existente)

```
Continuamos desde donde quedaste. Estado actual: rama PortandoLoMejor,
13 commits en total (los 8 tuyos del sprint anterior + 5 de recovery
del stash). Working tree limpio. La auditoría completa vive en
docs/architecture/ (no gemma4_agent/docs/architecture/).

Importante: ahora SÍ existen `capability_classifier.py`,
`grounding_gate.py`, `intent_validator.py`, `nli_service.py`,
`_ml_import_lock.py` y `experience.flag_grounding_by_turn` — vinieron
en los commits ad6911b/c54f032. Cuando consultes 02_components/routing.md
o 03_classes/routing.md ya describen código que existe en HEAD.

# OBJETIVO DE SPRINT 2

Preparar la instrumentación que va a permitir decidir, con datos reales
de uso, qué se queda y qué se elimina en Sprint 3+. NO se borra nada.
NO se refactoriza nada. Solo se agregan contadores y se genera un
reporte agregado de uso histórico.

# REGLAS GENERALES (mismas que sprint anterior)

1. Trabajás en PortandoLoMejor. Commits chicos por tarea, prefijo
   "sprint2: <tarea>". NO push, NO toques main, NO toques branches.
2. Después de cada commit: verificá `python -c "import gemma4_agent"`.
3. Si una tarea revela que el plan asume algo que no se cumple en el
   código actual: anotala como SKIPPED con razón explícita en
   docs/architecture/sprint_prompts/_sprint2_log.md y seguís.
4. NO instales deps nuevas. NO ejecutes el agente real ni llama-server.
5. NO toques archivos en data/, ~/.gemma4/, captures/, logs/, models/.
6. SÍ podés leer data/traces.jsonl (existe, ~1.7 MB) para el script
   de análisis. NO lo modifiques.
7. Stash @{0} restante ("pre-night-audit-WIP-2026-05-16") es de antes
   de la auditoría, NO lo toques.

# WORKFLOW

## 2.1 — Análisis estático de traces.jsonl actual (sin instrumentar nada nuevo)

Antes de agregar instrumentación nueva, exprimí lo que ya hay en disco.

Creá un script standalone (no parte del paquete): `scripts/analyze_traces.py`
(carpeta `scripts/` en la raíz del repo, NO `gemma4_agent/scripts/` que
es para streaming probes).

El script lee `gemma4_agent/data/traces.jsonl` y reporta, en consola
y como `docs/architecture/sprint_prompts/_sprint2_usage_report.md`:

  Sección A — Tools usadas
  - Conteo de tool_call por nombre (los 65 compound + cualquier otro
    que aparezca). Tabla descendente por uso.
  - Top N tools sin uso (count == 0). Son las candidatas a borrar.
  - Distribución por status: ok / failed / needs_confirmation / unverified.

  Sección B — Personas activas
  - grep en el .jsonl de eventos kind == "persona" o de líneas que
    referencien "persona": <nombre>. Conteo por persona.
  - Lista de personas hardcoded en gemma4_agent/personas.py
    (default, coder, researcher, creative, planner, casual). Cuántas
    aparecen en logs?

  Sección C — Microagents y skills
  - kind == "microagent_match" / "skill_load" o equivalente. Conteo
    por nombre. La auditoría (07_tools.md) sospecha que muchos no se
    usan; cuantifiquemos.

  Sección D — Capability classifier (Bug 1 de la auditoría)
  - Eventos relacionados a augment_subset / classify_capability.
    Cache hits vs misses (si el evento incluye source: cache|sync|
    async_pending). Verdict adoptado vs descartado.
  - Si NO hay eventos relacionados, anotalo. Significa que el
    classifier corre pero no se loguea — Sprint 2.2 va a arreglarlo.

  Sección E — Routing / fallback semántico
  - Cuántas veces el planner devolvió subset=[] y cayó al
    semantic_router.
  - Cuántas veces el continuation hint disparó (last_assistant_text
    + perfil + plataforma streaming).

  Sección F — Estados de MissionOutcome
  - Distribución de los 9 estados (COMPLETED, PARTIAL, FAILED,
    UNVERIFIED, NEEDS_USER, NEEDS_PERMISSION, BLOCKED_BY_POLICY,
    TOOL_OK_VERIFIER_INCONCLUSIVE, INTENT_NOT_FULFILLED).
  - Cuáles nunca aparecen → candidatas a colapsar.

  Sección G — Hallazgos
  - Lista breve "esto se usa N veces, esto cero".

El script:
- es self-contained (solo stdlib: json, collections, pathlib, sys).
- soporta `--limit N` para procesar solo las últimas N líneas
  (default: todas).
- soporta `--since YYYY-MM-DD`.
- imprime también el path absoluto del jsonl que está leyendo.
- maneja líneas corruptas con try/except y cuenta cuántas saltó.

Commit: "sprint2: add scripts/analyze_traces.py + first usage report
from existing traces.jsonl".

Importante: corré el script una vez al final de esta tarea y commiteá
también el `_sprint2_usage_report.md` generado.

## 2.2 — Agregar contadores faltantes que el análisis de 2.1 detectó

Después de 2.1 vas a saber qué información FALTA en traces.jsonl para
tomar decisiones. Probables candidatos:

a) capability_classifier no loguea verdict ni cache_source.
b) microagents no loguea cuál matcheó (solo el efecto en system_prompt).
c) skills_registry no loguea qué skill cargó vía skill_load tool.
d) personas no loguea cuál se aplicó al turno.

Para CADA información faltante:
- Identificá el punto exacto en el código donde ocurre el evento.
- Agregá UN `self.trace.event(turn_id, "<kind>", **payload)` mínimo.
  Reusá el TraceLogger existente (no instales TelemetryStore — eso es
  Sprint 3+ donde se decida si vale).
- `<kind>` debe ser claro: `capability_verdict`, `microagent_matched`,
  `skill_loaded`, `persona_active`.
- El payload debe ser flat y serializable (strings/ints/bools/listas
  de strings). NO objetos custom.

Una pequeña constraint: el TraceLogger queda como está. La auditoría
recomienda eliminarlo (08_findings.md §2.5), pero esa es decisión de
Sprint 3 — no la tomes acá.

Commit por kind agregado: "sprint2: log <kind> via TraceLogger".
Máximo 4 commits si los 4 candidatos aplican.

## 2.3 — Documentar cómo correr el reporte semanalmente

Editá `docs/architecture/sprint_prompts/_sprint2_log.md` con:

- Comando para regenerar el reporte:
  `python scripts/analyze_traces.py --since YYYY-MM-DD > /tmp/report.md`
- Frecuencia sugerida: semanal, después de uso normal.
- Cuándo conviene volver a correrlo:
  - antes de Sprint 3 (decisiones de qué eliminar/refactorizar).
  - después de cualquier cambio mayor en personas/microagents/skills.
- Qué buscar en el reporte (referenciá las secciones A-G):
  - Sección A: tools con count == 0 → candidatas a borrar.
  - Sección B-C: personas/microagents/skills con count == 0 → candidatas.
  - Sección D: capability classifier cache_hit_rate < 20% → eliminar.
  - Sección F: estados de MissionOutcome sin uso → colapsar.

## 2.4 — Reporting

Al terminar (o cuando te bloquees), creá
`docs/architecture/sprint_prompts/_sprint2_log.md` con la misma estructura
que el log del sprint anterior:

- Timestamp de inicio y fin.
- Tareas hechas con SHA del commit.
- Tareas saltadas con razón explícita.
- Hallazgos del reporte (top 3-5 cosas que sorprenden).
- Recomendación: cuánto tiempo dejar correr el agente antes de re-medir
  (sugerencia: 7 días con uso real; ajustá si tu intuición dice otra cosa
  basada en el volumen actual de traces.jsonl).
- Estado final: `git log --oneline -10` + `git status`.

# QUÉ NO HAGAS

- NO refactorizar capability_classifier ni nli_service ni grounding_gate
  ni intent_validator. Esos son Sprint 3.
- NO eliminar personas, microagents, skills o tools — eso depende del
  reporte que vas a producir.
- NO crear TelemetryStore nuevo. Reusá TraceLogger.
- NO instales nada.
- NO toques `data/` ni `~/.gemma4/`.
- NO modifiques traces.jsonl.

Arrancá.
```

---

## Notas para vos al despertar

1. **El primer artifact concreto del Sprint 2 es `_sprint2_usage_report.md`**:
   te dice exactamente qué se usa y qué no en tu agente. Esa info la
   necesitamos antes de Sprint 3.

2. **Si el reporte muestra que `traces.jsonl` tiene poco volumen** (por
   ejemplo <500 turns), la recomendación va a ser "dejá correr el
   agente N días más antes de Sprint 3". El agente va a calcularlo y
   anotarlo. Vos decidís.

3. **Sprint 3** va a usar el reporte como input. Cuando lances Sprint 3
   te paso un prompt nuevo que cita los hallazgos del reporte real (no
   estimados como ahora).
