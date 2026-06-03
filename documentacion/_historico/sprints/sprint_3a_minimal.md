# PROMPT — Sprint 3a (mínimo estructural)

> Continúa el mismo chat de Claude Code que corrió Sprints 0+1+2. El
> agente conoce el repo, los logs y el reporte de Sprint 2.

---

## Por qué este prompt es DISTINTO al `sprint_3a_recortes_confiables.md` del commit `f2dff89`

El prompt anterior planificaba eliminar 37 de las 65 compound tools
basándose en "0 calls en 5 días" del `_sprint2_usage_report.md`.
**Esa interpretación era incorrecta**: el objetivo declarado del agente
es **"uso total del PC"**, y tools como `database`, `office`, `network`,
`vision`, `uia`, `developer`, `maintenance`, etc., son capacidades
reservadas — que no aparezcan en una ventana de 5 días personales NO
es señal de deuda estructural, es señal de hábitos de uso del operador.
Borrarlas mutilaría el alcance del agente.

**Sprint 3a real solo ataca cosas estructuralmente justificadas**, que
no dependen de datos de uso:

1. Stack NLI (`capability_classifier` + `nli_service` + `_ml_import_lock`
   + lo de `grounding_gate` que dependa de NLI). Razón: cache hit
   3.2 % es métrica de **eficacia del componente**, no de uso del
   usuario. mDeBERTa pesa 280 MB en RAM, dispara worker thread, y
   en 5 días aportó 0 verdicts útiles (cache miss en el 96.8 % de
   los casos). Es ineficiente por construcción.
2. Regex multilingüe ES/EN/PT/FR/IT en `planner._suggest_tools` (y
   posiblemente `mission_goal._VERB_KIND_PATTERNS`). Razón: el
   `CORE_PROMPT` (`agent.py:47-48`) explícita "Speak Spanish to the
   user by default". Las branches PT/FR/IT son código no ejercitado
   **por diseño**, no por dataset corto. Riesgo de falso positivo en
   ES por overlap léxico.

**Tools intactas. Personas intactas. Microagents intactos. Skills
intactas.** El agente conserva 65 compound tools.

---

## Prompt completo (copy/paste al chat existente)

```
Continuamos. Estado: rama PortandoLoMejor, working tree limpio,
último commit f2dff89 (el prompt previo de Sprint 3a que vamos a
DESCARTAR). El operador re-evaluó y el plan cambió.

# REGLAS GENERALES (mismas que sprints anteriores)

1. Trabajás en PortandoLoMejor. Commits chicos por tarea, prefijo
   "sprint3a: <tarea>". NO push, NO toques main.
2. Después de cada commit: `python -c "import gemma4_agent"`. Si
   rompe: git reset --hard HEAD~1, anotá blocker en
   docs/architecture/sprint_prompts/_sprint3a_log.md, seguís.
3. NO instales deps nuevas. NO ejecutes el agente real ni
   llama-server.
4. NO toques data/, ~/.gemma4/, captures/, logs/, models/.
5. NO toques: voice/, mission_goal.py, mission_outcome.py, verifiers.py,
   verify_core.py, personas.py, microagents.py, skills_registry.py,
   ToolRegistry/COMPOUND_TOOL_SCHEMAS, domain_tools.py salvo lo
   estrictamente necesario para deshacer un import.
6. NO borres ninguna compound tool. NO toques COMPOUND_TOOL_SCHEMAS.
7. Stash @{0} restante es de antes de la auditoría — NO LO TOQUES.

# CONTEXTO

- `docs/architecture/sprint_prompts/_sprint2_usage_report.md` — datos.
- `docs/architecture/08_findings.md` §1-7 — el plan completo.
- El prompt anterior (commit f2dff89,
  docs/architecture/sprint_prompts/sprint_3a_recortes_confiables.md)
  ya fue removido del HEAD. NO lo uses como referencia para acciones,
  solo para entender qué descartamos.

# WORKFLOW

## 3a.1 — Matar el stack NLI

Justificación (cita del reporte §D):
- "capability_augment: 31 eventos"
- "Verdict source: sync 30 (96.8 %), cache 1 (3.2 %)"
- "Cache hit rate: 3.2 % (threshold for keep/kill: 20 %)"

Es decir: el componente corrió 31 veces, casi todas sync (~1.2s
primera inference) y solo 1 vez aprovechó cache. mDeBERTa 280 MB
ocupa RAM para nada útil. Mantenerlo es deuda.

### Pre-flight: mapear callers

```bash
grep -rn "capability_classifier\|nli_service\|_ml_import_lock\|grounding_gate\|intent_validator" gemma4_agent/ scripts/ docs/
```

Anotá en `_sprint3a_log.md` los call sites. Esperables:
- `agent.py` — import y llamadas a `augment_subset`, posiblemente
  `schedule_grounding_check` async post-reply, posiblemente
  `needs_intent_tag` + `validate_call` para el `<intent>` tag.
- `planner.py` — quizás import indirecto.
- Tests: `test_capability_classifier.py`, `test_nli_service.py`,
  `test_ml_import_lock.py`, `test_grounding_gate.py`,
  `test_phrase_trigger_guards.py` (quizás), `test_promise_guard.py`
  (quizás).

### Decisiones por archivo

(a) **`capability_classifier.py`** — eliminar completo.
    - LOC: ~303.
    - Importadores: agent.py (al menos).
    - Acción: `git rm`. Quitar imports + call sites en agent.py.

(b) **`nli_service.py`** — eliminar completo.
    - LOC: ~246.
    - Importadores: capability_classifier (lo borramos), grounding_gate
      (parte async).
    - Acción: `git rm` después de manejar (d) abajo.

(c) **`_ml_import_lock.py`** — eliminar completo.
    - LOC: ~49.
    - Importadores: nli_service y posiblemente capability_classifier.
    - Justificación: existía solo para serializar imports
      pesados ML (transformers + huggingface_hub) que evitaban race
      con faster_whisper. Si no hay más NLI, no hay race.
    - Acción: `git rm`.

(d) **`grounding_gate.py`** — DECISIÓN SUTIL.
    Tiene dos capas (documentado en su propio docstring):
    - **Inline (sin NLI):** `detect_action_claim_without_evidence(reply,
      tool_events)` — heurística morfológica de 1ª persona preterit.
      NO depende de nli_service. Esa pieza VALE conservar.
    - **Async (con NLI):** `schedule_grounding_check(...)` — pide
      verdict a nli_service y escribe a lesson_store. Depende de nli.
      Sin nli no aplica.

    Acción:
    1. Leé `gemma4_agent/grounding_gate.py` entero.
    2. Conservá: `detect_action_claim_without_evidence`,
       `GroundingVerdict`, `format_fallback`, `_FALLBACKS_BY_LANG`
       (reducido a `es`+`en` en 3a.2 abajo), helpers morfológicos
       (`_looks_like_first_person_preterit`, `_starts_with_action_claim`,
       `_fold`, etc.), `_HONEST_FALLBACK` si no quedó shadowed.
    3. Eliminá: `schedule_grounding_check`, cualquier
       `get_nli_service()` import, `detect_reply_language` (su único
       uso es para elegir bucket de fallback — al reducir
       `_FALLBACKS_BY_LANG` a 2 idiomas, dejá un guess simple inline
       o eliminala).
    4. Actualizá callers en agent.py.
    5. Quedaría un grounding_gate.py más corto (~130-150 LOC vs 255).
    6. Si simplificarlo no es trivial: SKIP el adelgazamiento y
       solo eliminá el call site `schedule_grounding_check` en
       agent.py. El módulo grounding_gate.py queda con código
       muerto en su mitad async — Sprint 3b o 4 limpiarán.

(e) **`intent_validator.py`** — DECISIÓN POR INSPECCIÓN.
    Tiene `needs_intent_tag()`, `INTENT_TAG_INSTRUCTION`,
    `extract_intent_tag()`, `validate_call()`, `corrective_message()`.
    NINGUNO depende de NLI: son regex + lookup de
    `CROSS_REJECT_PAIRS` (6 entries hardcoded).

    Acción: **NO TOCAR `intent_validator.py`**. Es independiente del
    stack NLI.

(f) **Tests** — eliminar SOLO los que cubrían lo borrado:
    - `test_capability_classifier.py` — eliminar.
    - `test_nli_service.py` — eliminar.
    - `test_ml_import_lock.py` — eliminar.
    - `test_grounding_gate.py` — si solo testea la parte async,
      eliminar. Si tiene assertions sobre
      `detect_action_claim_without_evidence`, conservar los relevantes
      (puede requerir tijera quirúrgica).
    - Tests NO tocados: `test_promise_guard.py`, `test_phrase_trigger_guards.py`,
      `test_intent_validator*.py` (si existe).

(g) **agent.py** — limpiar imports + call sites.
    Lo MÍNIMO posible. NO refactorices nada más. Patrón a remover:
    - `from .capability_classifier import augment_subset, …`
    - `from .grounding_gate import schedule_grounding_check`
    - Llamada(s) a `augment_subset(...)` (y la fusión de su resultado
      al subset).
    - Llamada(s) a `schedule_grounding_check(...)`.
    - Cualquier thread/callback wiring del classifier en background.

    Si una llamada estaba dentro de un try/except defensivo, dejá el
    bloque vacío con un `pass` o eliminá el try entero — usá tu juicio.

(h) **requirements.txt** — eliminar deps que solo el stack NLI usaba.
    PROBABLEMENTE: `transformers` (si estaba). Verificá:
    ```bash
    grep -rn "import transformers\|from transformers" gemma4_agent/
    ```
    Si solo nli_service.py lo importaba, sacalo de requirements.
    **NO TOQUES `sentence-transformers`** — lo usa
    `semantic_router.py` que se queda. **NO TOQUES `huggingface_hub`**
    — lo usa `voice/stt.py` para descargar modelos Whisper.

### Verificación

```bash
python -c "import gemma4_agent; from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS; print('compound:', len(COMPOUND_TOOL_SCHEMAS))"
```
- Esperado: `compound: 65` (nada cambió en tools).
- Esperado: import OK sin errores de import faltante.

```bash
python -m gemma4_agent.launcher status 2>&1 | head -5
```
- Esperado: corre sin trace fatal.

### Commit

Un solo commit grande (porque son cambios atómicos
interdependientes — eliminar 3 archivos + adelgazar 1 + actualizar
callers + tests):

```
sprint3a: kill NLI stack (capability_classifier + nli_service +
_ml_import_lock; async layer of grounding_gate)

Per _sprint2_usage_report.md §D: capability classifier cache hit
rate is 3.2% (30 sync of 31 augments) vs 20% kill threshold from
08_findings.md §2.10. mDeBERTa carries 280MB RAM cost + worker
thread for ~0 added value over the regex planner.

Removed files:
- capability_classifier.py (303 LOC)
- nli_service.py           (246 LOC)
- _ml_import_lock.py       (49 LOC) — only existed to serialize NLI
  imports vs faster_whisper

Modified:
- agent.py: removed augment_subset call + async grounding_check call
- grounding_gate.py: kept inline morphology check, removed async
  NLI layer (or full kill if too entangled — see _sprint3a_log.md)
- requirements.txt: removed `transformers` (sentence-transformers
  stays for semantic_router; huggingface_hub stays for voice/stt.py)

Tests removed: test_capability_classifier.py, test_nli_service.py,
test_ml_import_lock.py, test_grounding_gate.py (or trimmed).

NOT touched: intent_validator.py (regex-only, no NLI dependency),
semantic_router.py (different model, different purpose), 65
compound tools intact.
```

## 3a.2 — Reducir regex multilingüe a ES+EN

Justificación (audit §2.8, ya citado en _findings_seed.md):
- `CORE_PROMPT` en `agent.py:47-48` dice "Speak Spanish to the user
  by default. You are a VOICE assistant ... reply length 1-2 sentences."
- `planner._suggest_tools` tiene ~30 buckets regex con keywords ES/EN/
  PT/FR/IT — ~250 LOC de patterns en idiomas que el agente nunca usa
  como output (y casi nunca como input, dado el target user).
- Mantenerlos aumenta riesgo de falso positivo en ES por overlap
  léxico (palabras italianas que se parecen al español).

### Archivos a tocar

(a) **`gemma4_agent/planner.py`** líneas ~212-630 (función
    `_suggest_tools` + helpers). Para cada bucket regex:
    - Identificá keywords ES y EN; conservá.
    - Eliminá keywords PT/FR/IT que NO tengan equivalente ES/EN ya
      presente.
    - Si una palabra es ambigua (e.g. "musica" se escribe igual en
      ES/IT/PT), CONSERVALA — el ahorro de borrarla es marginal y
      el riesgo de romper input multilingüe accidental es real.
    - LOC esperadas eliminadas: ~100-150.

(b) **`gemma4_agent/mission_goal.py`** — TIENE
    `_VERB_KIND_PATTERNS` también multilingüe ES/EN/PT/FR/IT (audit
    §4.7 LOW).

    PERO `mission_goal.py` está en la **lista NO-TOCAR** (regla 5
    arriba). Razón: es Carter-heredado y los tests son frágiles.

    SI te animás a tocarlo (es un cambio cosmético igual al de
    planner): hacelo en un commit aparte, con verificación adicional
    con `python -m pytest gemma4_agent/test_mission_goal.py -q` si
    el test existe.

    SI NO te animás: SKIP. Anotalo en `_sprint3a_log.md` como tarea
    para Sprint 4.

(c) **`gemma4_agent/grounding_gate.py`** — si en 3a.1(d)
    adelgazaste el módulo, `_FALLBACKS_BY_LANG` ya queda en es+en.
    Si no, hacelo ahora:
    - Eliminá entries `it`, `pt`, `fr`, `de` del dict.
    - Eliminá `_LANG_HINTS` entries de esos idiomas.
    - Si `detect_reply_language` solo se usa para elegir bucket,
      ya queda redundante — eliminala o simplificala.

### Verificación

```bash
python -c "import gemma4_agent; from gemma4_agent.planner import select_tool_names, plan_mission; plan = plan_mission('abrí Steam'); subset = select_tool_names('abrí Steam', plan); print('test ES OK:', subset)"
```
Esperado: `subset` no vacío incluyendo `steam` y posiblemente `app`.

```bash
python -c "from gemma4_agent.planner import select_tool_names, plan_mission; plan = plan_mission('open Steam'); subset = select_tool_names('open Steam', plan); print('test EN OK:', subset)"
```
Esperado: `subset` no vacío.

```bash
python -c "from gemma4_agent.planner import select_tool_names, plan_mission; plan = plan_mission('apri Steam'); subset = select_tool_names('apri Steam', plan); print('test IT:', subset)"
```
Esperado: `subset` posiblemente vacío (caería al fallback semántico).
Eso está OK — la idea es justamente NO matchear input IT.

### Commit

Por archivo afectado:

```
sprint3a: reduce planner regex to ES+EN (audit §2.8)

CORE_PROMPT (agent.py:47-48) commits the agent to Spanish-by-default
output. The 30+ multilingual buckets in planner._suggest_tools
included PT/FR/IT keywords that the agent never produces and that
introduce false-positive risk in ES via lexical overlap.

Conservado: ES, EN, palabras universales (steam, youtube, opera,
chrome, etc).
Eliminado: PT-only / FR-only / IT-only que no compartían forma con
ES o EN. Keywords ambiguas (musica, video) quedaron.

LOC removed: ~XXX (anotar el delta real).
```

## 3a.3 — Reporting

Escribí `docs/architecture/sprint_prompts/_sprint3a_log.md`:

- Timestamp inicio/fin.
- Tareas hechas con SHA del commit.
- Tareas SKIPPED con razón (probable: mission_goal._VERB_KIND_PATTERNS,
  o adelgazamiento de grounding_gate si fue muy entangled).
- LOC delta total: `git diff --shortstat f2dff89..HEAD`.
- Resultado de las 3 verificaciones ES/EN/IT del 3a.2.
- Estado: `git log --oneline -10` + `git status`.
- Headline: "Sprint 3a: NLI stack killed (~600 LOC), planner regex
  trimmed to ES+EN (~150 LOC). Tools intact (65). Personas
  intact (6). Microagents/Skills intact. Total: ~XXX LOC removed."

Commit final: "sprint3a: write log".

# QUÉ NO HAGAS (recap importante)

- NO borres compound tools.
- NO toques personas.py, microagents.py, skills_registry.py.
- NO refactorices ToolRegistry ni Gemma4Agent (Sprint 4).
- NO instales deps.
- NO toques mission_outcome.py, verifiers.py, verify_core.py, voice/.
- NO toques traces.jsonl.
- NO toques sentence-transformers ni huggingface_hub en
  requirements.txt — son de OTROS módulos vivos (semantic_router,
  voice/stt.py).
- Si dudás entre "borrar" y "dejar": dejá. Anotá en log para Sprint 4.

Arrancá.
```

---

## Notas para vos cuando despiertes

1. **El número clave a verificar:** `len(COMPOUND_TOOL_SCHEMAS) == 65`
   (intacto). Si bajó, algo se rompió.
2. **LOC esperadas removidas:** ~750-850
   (300 + 246 + 49 = 595 por capability/nli/import_lock + ~100 de
   grounding_gate async + ~150 de planner regex).
3. **Sprint 3b** queda para 7-10 días, con datos reales de
   `persona_active`, `microagent_matched`, `skill_loaded`.
4. **Sprint 4** (refactor estructural — workers, sinks, lazy imports,
   split de god classes) puede salir en paralelo con la ventana de
   medición de 3b. Te armo cuando me digas.

## Notas sobre el commit anterior (`f2dff89`)

El commit del prompt v1 se queda en historial — no lo revierto. Sirve
para que en un futuro audit alguien vea "acá pensaron borrar 37 tools
basándose en 5 días de datos, después se dieron cuenta del error y
splitearon Sprint 3a a algo conservador". Es información valiosa.
