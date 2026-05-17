# PROMPT — Sprint 3a (recortes con datos confiables)

> Continúa el mismo chat de Claude Code que corrió Sprints 0+1+2. El
> agente conoce el repo, los logs `_overnight_log.md` y `_sprint2_log.md`,
> y el reporte `_sprint2_usage_report.md`.
>
> **Por qué "3a" y no "3":** el reporte tiene métricas con dos
> antigüedades distintas. Las **viejas** (tools, capability classifier,
> semantic_router, mission_outcome) son confiables hoy porque su
> instrumentación lleva semanas. Las **nuevas** (personas, microagents,
> skills) recién se empezaron a loggear en Sprint 2 y muestran 0
> por instrumentation gap, no por desuso real. Sprint 3a ataca SOLO
> las viejas. Sprint 3b sale en 7-10 días con datos reales de las
> nuevas. Sprint 4 es refactor estructural sin depender de datos.

---

## Datos del reporte que justifican CADA acción de Sprint 3a

Citas literales de `docs/architecture/sprint_prompts/_sprint2_usage_report.md`:

| Hallazgo confiable | Cita | Acción |
|---|---|---|
| 45/65 compound tools sin uso | "45 of 65 compound tools have zero calls in this window" | 3a.1 |
| Capability classifier cache hit 3.2% < 20% | "Cache hit rate: 3.2% (threshold for keep/kill: 20%)" | 3a.2 |
| 45% turns con subset vacío | "tool_subset events with empty subset: 311 / 690 (45.1%)" | 3a.3 |
| 4/9 estados de MissionOutcome nunca observados | "Statuses never observed: BLOCKED_BY_POLICY, FAILED, NEEDS_PERMISSION, NEEDS_USER" | 3a.4 |
| 88% UNVERIFIED | "Top mission_outcome status: UNVERIFIED (172/195 = 88%)" | 3a.4 |

Hallazgos NO actuables todavía (esperan Sprint 3b):
- 5/6 personas nunca usadas → instrumentation `persona_active` recién
  agregada en commit 8a2ef09. Esperar.
- 0 microagent_matched → idem commit 6062cd8.
- 0 skill_loaded → idem commit 877736a.

---

## Prompt completo (copy/paste al chat existente)

```
Continuamos. Estado: rama PortandoLoMejor, 19 commits totales, working
tree limpio. El reporte de Sprint 2 está en
docs/architecture/sprint_prompts/_sprint2_usage_report.md y tiene datos
confiables para algunas decisiones de Sprint 3 — pero NO todas. Sprint
3a ataca SOLO los hallazgos con instrumentación vieja.

# REGLAS GENERALES (mismas que sprints anteriores)

1. Trabajás en PortandoLoMejor. Commits chicos por tarea, prefijo
   "sprint3a: <tarea>". NO push, NO toques main.
2. Después de cada commit: `python -c "import gemma4_agent"`. Si
   rompe: git reset --hard HEAD~1, anotá blocker en
   docs/architecture/sprint_prompts/_sprint3a_log.md, seguís.
3. NO instales deps nuevas. NO ejecutes el agente real ni llama-server.
4. NO toques data/, ~/.gemma4/, captures/, logs/, models/.
5. Si una tarea revela que el reporte está desactualizado o el código
   cambió: anotala como SKIPPED con razón, seguís.
6. NO toques: voice/, mission_goal.py, verifiers.py, verify_core.py
   (tests frágiles), capability_classifier.py NI nli_service.py (los
   borramos enteros en 3a.2 — no los toques antes).
7. NO toques personas/, microagents/, skills_registry.py (eso es 3b).
8. NO toques agent.py salvo lo MÍNIMO necesario para cada tarea
   (split de god class es Sprint 4).

# CONTEXTO

- `docs/architecture/sprint_prompts/_sprint2_usage_report.md` = los
  hallazgos. Vas a citarlo en commit messages.
- `docs/architecture/08_findings.md` §1-7 = el plan completo.
- `docs/architecture/_findings_seed.md` = detalles crudos.

# WORKFLOW

## 3a.1 — Eliminar 45 compound tools sin uso

Reporte sección A.2: 45 nombres listados textualmente. Para cada uno
hay que eliminar:
  (a) la entrada en `COMPOUND_TOOL_SCHEMAS` (tools.py, ~línea 4645+).
  (b) la entry correspondiente en `ToolRegistry._impls` (tools.py,
      `__init__`).
  (c) el método handler:
      - si está en `tools.py` (los `t_*`): borrarlo.
      - si está en `domain_tools.py` o `ops_tools.py` (los `*_tool`):
        borrarlo.
  (d) los imports de helpers que SOLO el handler usaba (cuidado:
      muchas tools comparten helpers privados de domain_tools.py).

Los 45 nombres (copia literal del reporte A.2):
  accessibility, backup_sync, browser_real, clipboard, container,
  creative_local, data_analysis, database, developer, device_settings,
  document, env, fact_check, form_filler, game_launcher, habit_tracker,
  input, job_manager, knowledge, local_calendar, local_search,
  maintenance, media_edit, memory, network, notification, office,
  package, peripheral, photo_library, printer_scanner, registry,
  reminder, safety, session, skill_load, smart_home, source_manager,
  study, subagent, system, terminal, uia, vision, watcher

⚠ ATENCIÓN — TOOLS DELICADAS DENTRO DE ESTA LISTA:

  - `safety` aparece en la lista pero es la tool que gestiona
    confirmaciones de tools peligrosas. Si la borrás, el agente pierde
    la capacidad de pedir confirmación explícita. **NO BORRES `safety`.**
    Marcala como SKIPPED en el log.
  - `session` es meta (cancel_turn). Sin ella el LLM no puede
    interrumpir un turn. **NO BORRES `session`.** SKIPPED.
  - `subagent` es el camino de delegación recursiva. Si nunca se usó
    en 5 días, eliminarla es razonable, pero verificá que ningún
    test (`test_*.py`) la importa. Si algún test la usa, SKIP.
  - `memory` es la tool de save/recall que el usuario usa explícito.
    Reporte muestra 0 calls pero el `memory.json` real tiene 3 items.
    **Eso significa que se usó antes del logging actual.** SKIP también.
  - `system` aparece en la lista pero `system_time/cpu_ram_gpu/etc`
    son la única vía para leer estado del SO. **SKIP** `system`.
  - `knowledge` con 0 calls. `knowledge.sqlite` está vacío.
    **Probablemente sí está sin uso**, pero el componente
    `KnowledgeStore` se construye en `ToolRegistry.__init__`. Borrar
    la tool + el handler está OK, pero deja `knowledge.py` y
    `KnowledgeStore` en su lugar — eso es Sprint 3b/4.
  - `skill_load` aparece en la lista pero su instrumentación recién
    salió en sprint 2 (commit 877736a). **SKIP** y revisamos en 3b.
  - `clipboard` con 0 calls. Si el user puede en algún momento decirle
    "copiá esto" o "leé el portapapeles", la pierde. **SKIP** por
    precaución.

Lista final REAL para borrar (45 menos 8 protegidas = 37):
  accessibility, backup_sync, browser_real, container, creative_local,
  data_analysis, database, developer, device_settings, document, env,
  fact_check, form_filler, game_launcher, habit_tracker, input,
  job_manager, local_calendar, local_search, maintenance, media_edit,
  network, notification, office, package, peripheral, photo_library,
  printer_scanner, registry, reminder, smart_home, source_manager,
  study, terminal, uia, vision, watcher

Estrategia de ejecución:

  Paso 1: PRE-FLIGHT — para cada nombre de los 37, ejecutá
  `grep -rn "\"<name>\"\|'<name>'" gemma4_agent/ scripts/` y guardá los
  matches en _sprint3a_log.md. Si una tool aparece en algún test
  (`test_*.py`) como un caller serio (no como string en una lista), SKIP
  esa tool. Si solo aparece en TOOL_DESCRIPTIONS o COMPOUND_TOOL_SCHEMAS
  o en docs, OK borrarla.

  Paso 2: BATCH DELETE. Para evitar 37 commits, agrupá por familia:
    - Commit batch 1: "office tools" → office, document, source_manager
    - Commit batch 2: "system mgmt" → maintenance, registry, device_settings,
      package, peripheral, env, input
    - Commit batch 3: "smart home / iot" → smart_home, container
    - Commit batch 4: "media tools" → media_edit, photo_library
    - Commit batch 5: "comm tools" → notification, reminder, local_calendar
    - Commit batch 6: "data analysis" → data_analysis, database,
      knowledge, fact_check
    - Commit batch 7: "creative" → creative_local, study, habit_tracker
    - Commit batch 8: "network/system" → network, terminal, watcher,
      job_manager, backup_sync
    - Commit batch 9: "browser stack" → browser_real, form_filler
    - Commit batch 10: "win automation" → uia, vision, accessibility,
      game_launcher, developer, local_search

  Cada batch:
    1. Eliminá el schema de COMPOUND_TOOL_SCHEMAS.
    2. Eliminá la entry de _impls.
    3. Eliminá el handler `t_<name>` en tools.py.
    4. Eliminá el `<name>_tool` en domain_tools.py o ops_tools.py.
    5. Verificá `python -c "from gemma4_agent.tools import
       COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"`.
    6. Verificá `python -m gemma4_agent.launcher status` sigue
       parseando argumentos (puede fallar por server caído).
    7. Si rompe: `git reset --hard HEAD~1`, log el blocker, seguís
       con el próximo batch.
    8. Commit message:
       "sprint3a: drop unused tools (<family>): a, b, c (zero calls
        in 5d window per _sprint2_usage_report.md)"

  Paso 3: POST-FLIGHT. Después de los 10 batches:
    - Contar COMPOUND_TOOL_SCHEMAS (debería ser 65 - 37 = 28, ± lo
      que hayas SKIPPED).
    - LOC removidas: `git diff --shortstat <base>..HEAD`.
    - Lista de helpers privados de domain_tools.py que quedaron sin
      uso (anotar en el log; borrarlos sería un Sprint propio).
    - Listar deps en requirements.txt que probablemente se pueden
      eliminar (matplotlib, pandas, mysql-connector, psycopg, pymysql,
      paho-mqtt, pdfplumber, pdf2image, pypdf, fitz, openpyxl,
      python-docx, python-pptx, PIL, bs4 — todas eran de
      domain_tools.py para tools que ahora no existen). NO los
      elimines de requirements.txt en este sprint — solo listalo.

## 3a.2 — Matar capability_classifier + nli_service (cache hit 3.2%)

Reporte sección D: cache hit 3.2% < 20% threshold. mDeBERTa pesa 280MB
y se carga lazy pero ocupa RAM y arranca un worker thread.

  1. Eliminá `gemma4_agent/capability_classifier.py` entero
     (303 LOC según audit).
  2. Eliminá `gemma4_agent/nli_service.py` entero (246 LOC).
  3. Eliminá `gemma4_agent/_ml_import_lock.py` (49 LOC) — solo
     existía para serializar el load de nli_service vs faster_whisper.
     Después de borrar nli_service ya no aplica.
  4. Eliminá `gemma4_agent/grounding_gate.py` SOLO si depende de
     nli_service (sin nli no funciona la mitad async). Si su parte
     inline (detect_action_claim_without_evidence) se usa
     standalone, MOVÉ esa función a `agent.py` o a un nuevo
     `agent_guards.py` y elimina el resto. Verificá:
     `grep -rn "detect_action_claim_without_evidence" gemma4_agent/`.
  5. Eliminá `gemma4_agent/intent_validator.py` SI depende de nli.
     `grep -rn "from .intent_validator" gemma4_agent/` te dice los
     callers. Si los callers usan SOLO `needs_intent_tag()` /
     `extract_intent_tag()` / `validate_call()` (que NO requieren
     NLI), entonces intent_validator se queda. Mirá el código del
     archivo para decidir.
  6. Borrá los call sites en `agent.py` y `planner.py`:
     - `from .capability_classifier import …`
     - `augment_subset(...)` calls
     - `classify_capability_async(...)` calls
     - El thread/callback de capability classifier en background.
  7. Eliminá los 3 tests:
     - `gemma4_agent/test_capability_classifier.py`
     - `gemma4_agent/test_nli_service.py`
     - `gemma4_agent/test_ml_import_lock.py`
     - `gemma4_agent/test_grounding_gate.py` SI eliminaste grounding_gate.
  8. Eliminá deps de requirements.txt:
     - `transformers` (si estaba — verificá; sino skip)
     - NO toques sentence-transformers (lo usa semantic_router).
  9. Eliminá referencias en docs/architecture/ — solo deja una nota
     en `_sprint3a_log.md` que diga "capability_classifier killed in
     Sprint 3a per cache hit rate 3.2%".

  Verificá después: `python -c "from gemma4_agent.agent import
  Gemma4Agent"` debe seguir funcionando. Si rompe: el caller en
  agent.py o planner.py tiene un import que faltó borrar.

  Commit: "sprint3a: kill capability_classifier + nli_service +
  _ml_import_lock (cache hit 3.2% < 20% kill threshold per
  _sprint2_usage_report.md §D)"

## 3a.3 — Reducir el 45% de turns con subset vacío

Reporte sección E: 311 de 690 `tool_subset` events vinieron vacíos.
El planner regex (`planner._suggest_tools`) no detectó nada y todo
cayó al semantic_router fallback.

NO arregles el planner regex (eso es estructural — Sprint 4 lo haría
unificando con capability_classifier que ya matamos en 3a.2).

PERO:

  3a.3.a — `planner._suggest_tools` tiene regex multilingüe ES/EN/PT/
  FR/IT (audit §2.8 HIGH, ~250 LOC). El sistema responde solo en ES.
  Eliminá las branches PT/FR/IT.

  - Leé `gemma4_agent/planner.py` líneas 212-630 (aprox).
  - Para cada bucket regex que tenga patterns "playlist|musica|cancao|
    musique|canzone|...", reducí a ES + EN.
  - Si encontrás keywords que aparecen SOLO en PT/FR/IT (sin
    equivalente ES o EN), eliminálas.
  - Después: `python -m gemma4_agent.launcher status` debe seguir
    levantando.
  - Tests: `grep -l "_suggest_tools\|planner\." gemma4_agent/test_*.py`
    y leé los que matchean. Si alguno tiene un input PT/FR/IT
    explícito, anotalo en log + skippealo (lo arreglamos en 3b).
  - LOC esperadas eliminadas: ~150.
  - Commit: "sprint3a: reduce planner regex to ES+EN (PT/FR/IT
    unused per audit §2.8, system prompt is Spanish-only)"

  3a.3.b — `grounding_gate._FALLBACKS_BY_LANG` tiene 6 idiomas × 4
  templates = 24 strings (audit §2.9). System default es ES. Si en
  3a.2 ya borraste grounding_gate.py entero, esto YA está hecho.
  Si grounding_gate sobrevivió, reducí a 2 idiomas (es + en).

  - Si grounding_gate.py existe: eliminá entries de
    `_FALLBACKS_BY_LANG` salvo `es` y `en`. Eliminá
    `detect_reply_language` (solo se usaba para elegir bucket de
    fallback que ya no existe).
  - Commit: "sprint3a: reduce grounding_gate fallbacks to es+en
    (audit §2.9)"

## 3a.4 — Colapsar MissionOutcome estados sin uso

Reporte sección F: 4 de 9 estados nunca observados:
  - BLOCKED_BY_POLICY
  - FAILED
  - NEEDS_PERMISSION
  - NEEDS_USER

DECIDÍ con cuidado:

  - `FAILED` es semánticamente útil incluso si no aparece. **NO
    BORRAR.** El sistema lo emite cuando un verifier explícito dice
    "esto NO ocurrió". Si no aparece es porque los verifiers son
    lenientes — no porque el estado sea redundante. SKIP.
  - `NEEDS_PERMISSION` es para futuro UAC / admin scenarios.
    Probablemente nunca se usó porque las tools peligrosas piden
    confirmación vía `safety`, no vía permission. SKIP por ahora;
    cuando se elimine `safety` (no es este sprint) re-evaluar.
  - `NEEDS_USER` se emite cuando el agente pide clarification al
    user. Reporte no lo registra pero el agente PREGUNTA. Verificá:
    grep en agent.py `OutcomeStatus.NEEDS_USER`. Si lo emite y el
    reporte no lo cuenta, hay bug de instrumentación, NO eliminar.
    SKIP.
  - `BLOCKED_BY_POLICY` es ambiguo. `grep -rn "BLOCKED_BY_POLICY"
    gemma4_agent/` — si solo aparece en mission_goal.py (enum
    definition) y nada lo emite, ESE SÍ es candidato a borrar.
    Pero `mission_goal.py` está en la lista NO-TOCAR de las reglas
    arriba (es Carter-heredado). **SKIP.**

  Resultado esperado de 3a.4: 0 ejecuciones, todo SKIP, anotás en
  el log "los 4 estados sin uso son: semánticamente necesarios (FAILED),
  futuro (NEEDS_PERMISSION), bug de instrumentación (NEEDS_USER),
  en módulo no-tocar (BLOCKED_BY_POLICY)". No es un fracaso del
  sprint — es haber chequeado y decidido no actuar.

## 3a.5 — Limpieza final + reporting

  1. Re-correr el analyzer con el estado nuevo:
     `python scripts/analyze_traces.py > /tmp/post_sprint3a.md`
     Comparar `len(distinct_tools_in_compound_schemas)` antes (65) vs
     después (esperado ~28). Anotar en log.

  2. Re-correr el import-test:
     `python -c "import gemma4_agent; from gemma4_agent.tools import
     COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"`.

  3. Re-correr launcher status.

  4. Total LOC delta:
     `git diff --shortstat 5457632..HEAD`.

  5. Escribir `docs/architecture/sprint_prompts/_sprint3a_log.md`
     con la misma estructura que sprints anteriores:
     - Timestamp inicio/fin.
     - Tareas hechas con SHA + cuántos tools eliminados por batch.
     - Tareas SKIPPED con razón.
     - LOC removidas, breakdown por commit.
     - Estado final: git log --oneline -25 + git status.
     - Recomendación para Sprint 3b: "esperar 7-10 días para que
       persona_active / microagent_matched / skill_loaded acumulen
       datos reales".

  6. Commit del log: "sprint3a: write log".

# QUÉ NO HAGAS (recap)

- NO toques personas/, microagents/, skills_registry.py.
- NO toques `safety`, `session`, `subagent`, `memory`, `system`,
  `skill_load`, `clipboard` tools aunque estén en la lista de
  "0 calls".
- NO toques mission_goal.py, verifiers.py, verify_core.py, voice/.
- NO modifiques traces.jsonl.
- NO instales nada.
- NO toques requirements.txt todavía (los deps a eliminar van en
  Sprint 4 después de medir lo que queda).
- NO refactorices ToolRegistry ni Gemma4Agent (god class split es
  Sprint 4 con tests primero).

Arrancá.
```

---

## Notas para vos al despertar (mañana)

1. **El número clave a verificar:** `len(COMPOUND_TOOL_SCHEMAS)` debe
   bajar de 65 a ~28. Si bajó menos, el agente SKIPPÓ con razón válida
   (mirá `_sprint3a_log.md` sección "tareas saltadas").

2. **LOC esperadas eliminadas:** ~3 000-5 000 LOC entre los 37 tools
   borrados (handlers + schemas + entries) + 600+ LOC de
   capability_classifier/nli_service/_ml_import_lock + grounding_gate +
   ~150 LOC del planner regex multilingüe. Total esperado: **~4 000-6 000
   LOC removidas**.

3. **Si vas a producción mañana:** confirmá que las 8 tools protegidas
   (`safety`, `session`, `subagent`, `memory`, `system`, `skill_load`,
   `clipboard`, `knowledge` parcial) siguen vivas. Son las que probable-
   mente uses sin que aparezcan en logs frecuentes.

4. **Sprint 3b** lo armamos cuando hayas usado el agente 7-10 días con
   la instrumentación nueva del Sprint 2 (`persona_active`,
   `microagent_matched`, `skill_loaded`). Recorrés Sprint 2.1 de nuevo
   (mismo comando) y me pasás el reporte actualizado.

5. **Sprint 4** (refactor estructural — workers, sinks, lazy imports,
   split de god classes) NO depende de datos. Se puede hacer en
   paralelo con Sprint 3b si te alcanza la energía. Te armo prompt
   separado cuando llegues.
