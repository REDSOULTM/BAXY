# Compound Tasks & Vision Audit — Carter v2

Auditoría READ-ONLY. No se modificó código. Se leyeron los artefactos de
F-SMOKE, agent loop, intent_resolution, tool_catalog_selection,
verification, perception, universal/{task_frame, plan_graph, runner,
task_frame_builder} y vision_router/gui_agent.

Fecha: 2026-04-30.
Modelo de smoke: `qwen3:8b` (Ollama local).

---

## 1. Veredicto brutal

- **Texto simple**: estable. Conversación, identidad, hora, IP, memoria,
  capability discovery, single-tool actions: funcionan.
- **Tareas compuestas**: **NO LISTO**. Carter declara éxito tras la primera
  herramienta. No hay descomposición real, no hay máquina de estados de
  misión, no hay verificación a nivel de objetivo final, y el catálogo de
  tools no se recalcula entre pasos.
- **GUI/Visión**: **parcial y opaco**. UIA existe; OCR (`pytesseract`) y LLM
  vision existen pero gateados por env; **Omniparser está como dependencia
  opcional** y no hay Playwright para el escritorio. La perception monitor
  es deterministic (procesos + título de ventana) pero `capture_screen=False`
  por defecto, por lo que no hay observación visual entre pasos.
- **Smoke 18/18 OK es engañoso**: el runner sólo cuenta como `failure` los
  casos que lanzan excepción Python. No hay aserciones semánticas, ni
  validación de estado final del sistema, ni assert de que un compuesto
  cierre lo que abrió. Ver §7.

Carter hoy es un **agente single-shot disfrazado de loop**. El loop existe
pero las condiciones de salida lo colapsan a un único tool + texto.

---

## 2. Evidencia principal

Caso 15 de [F-SMOKE_smoke.json](audit/F-SMOKE_smoke.json#L195-L208):

```json
{
  "n": 15,
  "prompt": "abre Notepad y luego ciérralo",
  "tool_calls": ["app_open"],
  "reply": "Notepad está abierto. Ahora lo cerraré."
}
```

Caso 14 (también marcado OK):

```json
{
  "n": 14,
  "prompt": "cierra Notepad",
  "tool_calls": ["app_open"],
  "reply": "No, the request is not fully satisfied. I need to close Notepad."
}
```

**Lo que pasó (caso 15):**

1. El usuario pidió 2 acciones (abrir + cerrar).
2. El selector de catálogo ([tool_catalog_selection.py#L113](src/carter_v2/turn/tool_catalog_selection.py#L113-L184)) puntúa por overlap de tokens entre `user_text` y `tool_name+desc`. El input contiene `{abre, notepad, luego, cierralo}`. `app_open` matchea por "open" en su descripción/nombre. `app_close` / `process_stop_app` **no matchean** "ciérralo" porque el matcher es token-bag inglés. **Resultado: el LLM nunca recibe una herramienta de cierre.**
3. Iteración 0: LLM llama `app_open(target="notepad")`. Verifier confirma proceso. Como `app_open ∈ DIRECT_ACTION_TOOL_NAMES` y `role=PREPARATORY_ACTION`, `evaluate_direct_action_closure` ([intent_resolution.py#L137-L155](src/carter_v2/turn/intent_resolution.py#L137-L155)) devuelve `can_close_turn=False` y agrega un *continuation_prompt* en inglés: "Is the request fully satisfied? If yes reply concisely; if no call the next required tool immediately without explaining."
4. Iteración 1: el agent loop hace nueva llamada al LLM. **No fuerza `require_tool=True`**, **no recalcula catálogo con `prior_calls`** (ver [agent.py#L820-L831](src/carter_v2/turn/agent.py#L820-L831): `tools = select_tools_for_turn(user_text, full_tools=full_tools)` se computa una sola vez, antes del loop, sin `prior_calls`).
5. El LLM responde texto: "Notepad está abierto. Ahora lo cerraré." Sin tool_call.
6. Rama `if not response.has_tool_calls:` ([agent.py#L1167-L1217](src/carter_v2/turn/agent.py#L1167-L1217)) acepta ese texto como respuesta final del turno y retorna `ok=True`.

**Lo que debería haber ocurrido:** `process_stop_app(target="notepad.exe")` o `app_close` como segundo paso, seguido de verificación a nivel de misión (¿el proceso ya no existe?).

**Por qué el smoke lo marcó OK:** `smoke_runner_fsmoke.py` ([smoke_runner_fsmoke.py#L57-L62](audit/smoke_runner_fsmoke.py#L57-L62)) sólo trata como falla `result.get("error")` (excepción Python). No lee `tool_calls`, no compara con expected, no verifica estado del sistema. Igual mecánica para el caso 14: el reply en inglés "No, the request is not fully satisfied" delata la falla, pero como no hubo excepción, cuenta como OK.

Caso 9 (`qué color me gusta` → reply literal `"NO_TOOL_NEEDED"`) y caso 16 (`what is the capital of France?` → mismo `"NO_TOOL_NEEDED"`) son fallas adicionales que el smoke no detecta: el sentinel se filtró al usuario porque el guard sólo lo strippea cuando aparece como *prefix exacto* ([agent.py#L1206-L1208](src/carter_v2/turn/agent.py#L1206-L1208)) — si el modelo lo emite como respuesta entera sin prefijo "NO_TOOL_NEEDED:" se pasa tal cual.

---

## 3. Flujo actual de "abre Notepad y luego ciérralo"

```
user_text -> AgentEngine.run
  build prompt + system context
  select_tools_for_turn(user_text, full_tools)         # UNA sola vez
       |-- top-K por bag-of-words ES/EN sin stems
       |-- always_on = {memory_*, system_get_time, network_get_*, app_open,
                        gui_do, terminal_run_command, web_open_url, ...}
       \-- NO incluye app_close/process_stop_app, NO recibe prior_calls
  build_intent_frame(user_text)                         # frame trivial,
                                                        # sin descomposición
  _try_universal_plan_runner(...)                       # OFF salvo env
                                                        # CARTER_UNIVERSAL_PLAN_RUNNER=1
                                                        # -> retorna None (not_forced)
  for iteration in range(MAX_TOOL_ITERATIONS=8):
      backend.chat_with_tools(messages, _active_tools, require_tool=...)
      if not has_tool_calls:
          _try_universal_frame_text(...)               # solo si el modelo
                                                       # devuelve TaskFrame JSON
          return text reply                            # <- SALIDA TEMPRANA
      execute tool                                     # app_open
      verifier.verify(tc, result)                      # nivel TOOL solamente
      direct_reply = _direct_action_reply(executed)    # app_open ∈ DIRECT_ACTION
      closure = evaluate_direct_action_closure(...)
      if closure.can_close_turn: return                # role=PREPARATORY -> False
      else: messages.append(continuation_prompt)
            continue                                   # iteración 1
                                                       #   sin require_tool
                                                       #   sin reabrir catálogo
  -> iteración 1: LLM responde TEXTO sin tool -> rama "no has_tool_calls"
                  acepta texto como final -> return ok=True
```

**Punto exacto donde se pierde el segundo paso:** [agent.py#L1167-L1217](src/carter_v2/turn/agent.py#L1167-L1217). La rama "no tool calls" siempre cierra el turno con el texto del LLM cuando ya hubo `calls_made` y no hay caveat. Después de un `app_open` confirmado, el continuation prompt es cosmético: si el LLM responde texto, se acepta. No existe un estado "mission incomplete → require_tool en próxima iteración".

Punto secundario: el catálogo no contiene la herramienta de cierre, así que aunque el loop forzara una segunda tool call, el LLM no tendría a qué llamar (o llamaría `app_open` de nuevo, como en el caso 14, generando un loop trivial que el `_loop_detection_message` cortaría tras 3 repeticiones).

---

## 4. Diagnóstico del planner / universal runner

| Componente | Estado | Notas |
|---|---|---|
| `task_frame.TaskFrame` / `WorkUnit` | OK estructural | Modelo de datos correcto. |
| `task_frame_builder.TaskFrameBuilder` | Funcional pero **no se usa** | Sólo lo invoca `_try_universal_plan_runner`, gateado por env. |
| `plan_graph.PlanGraphBuilder` | Funcional | Convierte TaskFrame → grafo con dependencias. |
| `runner.PlanGraphRunner` | Funcional, mutaciones gateadas (`allow_mutations`) | Verifica por nodo. **No reinvoca al LLM por nodo** (un solo tool por nodo, escogido determinísticamente con `_choose_tool`). |
| `checkpoint.PlanGraphCheckpointStore` | Funcional pero opcional (gated por `CARTER_UNIVERSAL_RUN_ID`). |
| `resource_resolver` | Funcional, no es la causa raíz. |
| Auto-route `_try_universal_frame_text` | **Letra muerta para texto natural** | Sólo dispara si la primera respuesta del LLM es un JSON `TaskFrame` literal — el prompt actual no lo pide para tareas de 2 pasos. |
| `_task_frame_needs_universal_runner` | Conservador | Exige ≥2 work_units, dependencias, success_criteria, mutación o ≥2 requirements. Una tarea correctamente descompuesta sí dispararía el runner, pero **nadie la descompone**. |

**Conclusión:** El universal runner está construido y testeado a nivel
unitario, pero está **desconectado del modo texto**. El bridge LLM →
TaskFrame nunca se ejecuta de oficio. El agent loop ignora completamente la
posibilidad de descomponer la instrucción del usuario.

Lo que falta para usarlo en misiones compuestas:
- Un *intent classifier* estructural (no por keywords) que detecte
  multi-action: presencia de conjunciones (`y luego`, `then`, `después`,
  `and then`, comas serializadas) o múltiples verbos imperativos. Aun así
  evitar hardcode: hacerlo con un primer paso del LLM ("¿esta instrucción
  contiene 1 o N acciones independientes?", JSON estricto).
- Llamar a `TaskFrameBuilder` siempre que el clasificador devuelva N>1.
- Si TaskFrame tiene work_units válidas, ejecutar el `PlanGraphRunner`.
  Hoy `_try_universal_plan_runner` requiere `force_runner` env, que nadie
  setea en producción.

---

## 5. Diagnóstico de visión / GUI

| Componente | Estado actual | Se usa en texto simple | Se usa en GUI | Problema | Recomendación |
|---|---|---|---|---|---|
| `adapters/uia.py` (UIA) | Funcional (Windows) | No | Sí (`gui_agent` primary) | Frágil con apps no-UIA (Steam, Discord, juegos). Sólo verifica `actionable_elements >= gui_uia_min_elements` antes de caer a vision. | Mantener como tier 1; añadir snapshot estructural de la ventana activa después de cada `app_open` y exponerlo al LLM como observación. |
| `vision_router._omniparser_available` | Probe local + HTTP `OMNIPARSER_URL` | No | Tier opcional | **Usualmente missing** (no hay paquete instalado ni server local). | Documentar honestamente en el reporte. Posible: empacar instalador opcional. |
| `vision_router._pytesseract_available` | Probe binario tesseract | No | Tier 3 | Suele estar **available** si tesseract.exe existe en `Program Files`. Sólo se usa cuando UIA falla y no hay omniparser/llm_vision. | OK. Añadir telemetría en cada `gui_do`. |
| `vision_router` LLM_VISION | Gated por `settings.use_llm_vision` + endpoint configurado | No | Si activado | Suele estar **disabled** en perfil local. | Mantener opt-in. Cuando active, debe ir antes de OCR. |
| `screen_cache.py` | Cache de screenshot por hash | No | Sí | OK. | OK. |
| `vision_router` (router) | Tier ladder: llm_vision → omniparser → pytesseract | No | Sí | **No se invoca tras `app_open`** — sólo cuando el LLM llama `gui_do`. | Después de cualquier `app_open` exitoso, capturar 1 snapshot + UIA tree y pasarlo como mensaje system al LLM en la siguiente iteración. |
| `gui_agent.GuiAgentCapability` | Funcional | No | Sí | Pipeline `uia_then_vision`. **No emite tool de "observación" pura** que el agente pueda llamar entre pasos. | Exponer `gui_observe` (UIA snapshot + screenshot+OCR opcional) para re-observación explícita entre pasos. |
| `_gui_planner.py` | LLM mini-planner para `gui_do` | No | Sí | Plan local per-gui_do, pero no integrado al loop de misión. | Reutilizar para descomponer pasos GUI en sub-pasos. |
| `turn/perception.py` `PerceptionMonitor` | Deterministic, processes + active_window | Sí (snap antes/después de cada tool) | Sí | `capture_screen=False` por defecto → screen_hash siempre vacío → screen_changed siempre False. Diff útil sólo para procesos. | Activar screen_hash bajo flag; o usar screen_cache para diff barato cuando la tool es GUI. |
| `_vision_suggestions.py` | Heurísticas de hint | No | Sí | Limitado. | OK. |

**Honestidad sobre el stack:**
- **UIA**: presente y usado. Tier 1.
- **Playwright**: presente sólo para `WebCapability` (Chromium headless), no para GUI de escritorio. Para web sí cuenta como observación real.
- **Screenshot**: vía `screen_cache` y `vision_router`. Disponible.
- **OCR (pytesseract)**: probado, normalmente *available* en este equipo si Tesseract está instalado.
- **LLM_VISION**: opt-in. Por defecto *disabled*.
- **Omniparser**: típicamente *missing* (no hay paquete pip ni server). El probe baja gracefully.
- **Perception entre pasos**: existe a nivel proceso/título, **NO a nivel pantalla** por configuración por defecto.

---

## 6. Diagnóstico de verification

- **Tool-level verification** (`turn/verification.py`): existe y es buena —
  `_verify_app_open` poll proceso + ventana hasta 3s; `_verify_app_close`
  análogo; `_verify_gui_action` revisa cambios de UIA/screen. Cubre ~20
  tools en `_VERIFIABLE_TOOLS`.
- **Mission-level verification**: **no existe**. No hay objeto que
  represente "el objetivo del usuario" más allá del `IntentFrame` (que es
  literal `user_text`). `evaluate_direct_action_closure` clasifica el rol
  del último tool ejecutado, pero **no** chequea si el conjunto de tools
  ejecutados cubre el conjunto de subtareas implícito en el prompt.
- **Ledger** (`turn/ledger.py`): registra cada call con `verified_outcome`,
  `perception_diff`, blocked. Útil para guard del reply final
  (`guard_reply_against_ledger`). No mantiene estado de "subtareas
  cumplidas vs pendientes".
- **Cuándo Carter dice "listo"**: cuando (a) un tool DIRECT_ACTION
  termina ok y `closure.can_close_turn=True` (sólo TERMINAL_ACTION
  self-contenido, no PREPARATORY); o (b) el LLM responde texto sin
  tool_calls y la rama "no has_tool_calls" se ejecuta. La (b) es la fuga
  por la que se cierran tareas compuestas falsamente.
- **Cuándo debería decir "parcial"**: nunca lo dice. No hay estado
  `partial`, `step_failed_recoverable`, ni `mission_incomplete`. El reply
  final del LLM puede contener un caveat textual, pero la API
  `AgentTurnResult.ok` queda en True salvo excepción / max_iterations /
  empty replies.

---

## 7. Diagnóstico de smoke / probes

**Por qué `18/18 OK` engaña:**

[smoke_runner.py#L82-L113](audit/smoke_runner.py#L82-L113) y [smoke_runner_fsmoke.py#L57-L62](audit/smoke_runner_fsmoke.py#L57-L62):

```python
failures = [r for r in payload["results"] if r.get("error")]
print(f"\nSummary: {len(payload['results']) - len(failures)}/{len(payload['results'])} ok")
```

`error` sólo se setea cuando `engine.run(prompt)` lanza excepción Python.
No hay:
- assert sobre `tool_calls` esperado vs real;
- assert sobre estado final del sistema (¿proceso vivo? ¿ventana cerrada?);
- assert sobre el contenido del reply (no debería contener `NO_TOOL_NEEDED`,
  no debería estar en inglés cuando el usuario pidió en español, etc.);
- assert sobre completitud de misión (paso 2 ejecutado).

Casos del último smoke que son falsos positivos:
- **Caso 14** `cierra Notepad`: reply en inglés "No, the request is not
  fully satisfied. I need to close Notepad." → texto del continuation prompt
  filtrado, tool incorrecta (`app_open` por `cierra`). DEBE ser FAIL.
- **Caso 15** `abre Notepad y luego ciérralo`: solo `app_open`. DEBE ser
  PARTIAL/FAIL.
- **Caso 9** `qué color me gusta`: reply literal `NO_TOOL_NEEDED`. DEBE ser
  FAIL (sentinel filtrado al usuario).
- **Caso 16** `what is the capital of France?`: reply literal `NO_TOOL_NEEDED`.
  DEBE ser FAIL.

Real smoke pass rate honesto: **~14/18** (no 18/18). Y eso sin medir GUI
real: el "abre Notepad" del caso 13 sí cuenta como OK (proceso quedó vivo,
verifier confirmó), pero deja Notepad abierto al final del smoke — no hay
teardown.

**Smoke nuevo propuesto** (per nivel):

1. **Unit** (`tests/unit/`):
   - intent_resolution: dado `IntentFrame(user_text="abre X y luego ciérralo")`
     y un solo `app_open` ejecutado, `evaluate_direct_action_closure` debe
     devolver `can_close_turn=False` y `next_state=INTERMEDIATE_PROGRESS`
     (ya pasa). Añadir caso: con `app_open` + `process_stop_app` ambos ok,
     `can_close_turn=True`.
   - tool_catalog_selection: `select_tools_for_turn("abre Notepad y luego
     ciérralo", full_tools, prior_calls=["app_open"])` debe incluir
     `process_stop_app` o `app_close`.
2. **Integration** (sin Ollama, con backend mock):
   - Mock backend que devuelve `app_open` luego texto. El agent debe forzar
     una iteración adicional con `require_tool=True` o terminar con
     `ok=False, mission_status="partial"`.
   - Mock backend que devuelve `app_open` luego `process_stop_app`. El
     agent debe completar y devolver `ok=True`.
3. **Live runtime** (Ollama opcional, marcado `@pytest.mark.live`):
   - "abre Notepad y luego ciérralo": al final, `psutil.process_iter` no
     debe contener notepad.exe.
   - "abre Notepad, escribe 'hola', guarda en Desktop\\probe.txt y ciérralo":
     debe existir el archivo + Notepad cerrado.
   - "abre Steam, ve a biblioteca y cierra Steam": Steam.exe no debe estar
     vivo al final (best-effort: skip si steam no está instalado).
4. **Task-level assertions** (en `audit/smoke_runner.py`):
   - Cada prompt declara opcionalmente: `expected_tools`, `forbidden_tools`,
     `expected_reply_substring`, `final_state_check` (callable).
   - `payload["summary"]` reporta `pass`, `partial`, `fail` en lugar de
     binario `error`.

---

## 8. Causas raíz ordenadas

| # | Causa | Impacto | Archivo / líneas | Fix recomendado |
|---|---|---|---|---|
| 1 | El agent loop acepta texto sin tool como cierre del turno aun cuando el último tool fue `PREPARATORY_ACTION` y el continuation prompt indicó "no satisfecho". | Crítico — todas las tareas compuestas se cierran en 1 paso. | [agent.py#L1167-L1217](src/carter_v2/turn/agent.py#L1167-L1217) (rama "not response.has_tool_calls") + [agent.py#L1437-L1449](src/carter_v2/turn/agent.py#L1437-L1449) (continuation prompt sin `require_tool`). | Mantener un `mission_state` por turno (`pending|running|partial|complete`). Si el último step quedó en `INTERMEDIATE_PROGRESS`/`ENVIRONMENT_PREPARED` y no hay tool en la respuesta, forzar 1 iteración con `require_tool=True` y catálogo expandido. Si el LLM persiste sin tool, retornar `ok=False, mission_status="partial"` con reply honesto. |
| 2 | El catálogo top-K se calcula UNA vez al inicio del turno, sin `prior_calls`, y no incluye herramientas de cierre cuando el prompt está en español. | Crítico — incluso si el loop quisiera segundo paso, la herramienta no está en `_active_tools`. | [agent.py#L827-L831](src/carter_v2/turn/agent.py#L827-L831), [tool_catalog_selection.py#L113-L184](src/carter_v2/turn/tool_catalog_selection.py#L113-L184). | Recomputar catálogo por iteración con `prior_calls` y un seed semántico ampliado (sinónimos por capability/action, no por idioma). Añadir contraparte: si en el catálogo entró `app_open`, sumar `process_stop_app`/`app_close`/`window_close` como peers de la misma capability. |
| 3 | No hay descomposición de instrucciones. `IntentFrame.objective = user_text.strip()`. Universal runner OFF salvo env. | Crítico para misiones de 3+ pasos. | [intent_resolution.py#L65-L80](src/carter_v2/turn/intent_resolution.py#L65-L80), [agent.py#L853-L860](src/carter_v2/turn/agent.py#L853-L860) (`force_runner` por env). | Antes del loop principal, llamar a `TaskFrameBuilder` para una pasada barata de descomposición (opt-in por longitud / presencia de conjunciones detectadas estructuralmente). Si N≥2 work_units → ejecutar via PlanGraphRunner (con verify=True, allow_mutations gateado por riesgo). |
| 4 | Verificación es por tool, no por misión. | Alto — no se puede distinguir éxito real vs declaración del LLM. | [verification.py](src/carter_v2/turn/verification.py), [ledger.py](src/carter_v2/turn/ledger.py). | Introducir `MissionVerifier` que tome `IntentFrame.expected_outcomes` (poblado por TaskFrame.success_criteria) y compruebe estado final. Para "abrir y cerrar X": chequear `process not in psutil.process_iter()`. |
| 5 | Smoke acepta cualquier turno sin excepción como pass. | Alto — toda la métrica de calidad es ruido. | [smoke_runner.py](audit/smoke_runner.py), [smoke_runner_fsmoke.py](audit/smoke_runner_fsmoke.py). | Reescribir prompts a estructuras `{prompt, expected_tools, forbidden_replies, final_state_check}` y reportar `pass/partial/fail`. |
| 6 | `PerceptionMonitor.capture_screen=False` por defecto. | Medio — el screen_changed siempre False, así que `_perception_confirms` para tools GUI nunca dispara. | [perception.py#L83-L92](src/carter_v2/turn/perception.py#L83-L92). | Activar bajo flag para acciones GUI; usar `screen_cache` para cache barato. |
| 7 | El sentinel `NO_TOOL_NEEDED` se escapa al usuario cuando el modelo lo emite como respuesta entera. | Medio — afecta calidad UX en preguntas que el LLM cree no requieren tool. | [agent.py#L1206-L1208](src/carter_v2/turn/agent.py#L1206-L1208). | Strip estructural: si `reply.strip().upper() == "NO_TOOL_NEEDED"` → retry forzando texto explicativo, no devolver el sentinel al usuario. |
| 8 | `_active_app_followup_tools` filtra tools "deprioritized" pero no añade peers de cierre/control. | Medio. | [agent.py#L479-L482](src/carter_v2/turn/agent.py#L479-L482). | Cuando hay active_app, garantizar peers: `app_close`, `process_stop_app`, `window_close`, `gui_observe`. |
| 9 | El runner universal escoge una sola tool por nodo (`_choose_tool`) sin reabrir LLM si falla. | Medio cuando se active. | [runner.py#L137-L150](src/carter_v2/universal/runner.py#L137-L150). | Permitir reintento por nodo con LLM recuperación, hasta `max_node_retries`. |
| 10 | `gui_agent` no expone una tool atómica `gui_observe` para re-observación entre pasos. | Medio. | [gui_agent.py](src/carter_v2/capabilities/gui_agent.py). | Añadir `gui_observe(target)` que devuelva snapshot UIA + screen text (OCR si disponible). |

---

## 9. Plan de reparación por fases

### M1 — Mission decomposition

- Añadir `IntentDecomposer` que tome `user_text` y devuelva
  `IntentPlan{steps: list[Step]}` vía `TaskFrameBuilder` (LLM, JSON estricto).
- Heurística estructural (no léxica) para decidir cuándo invocarlo:
  longitud > N tokens, presencia de tokens conector (`and|y|then|luego|
  después|after|;|->`), o `intent_frame.preferred_execution_lane==universal_runner`.
- Cache por turno; sin reentrada.

### M2 — Mission state machine

- `MissionStatus = Enum{pending, running, step_success, step_failed,
  partial, complete}`.
- `MissionState{plan, current_step_idx, completed_steps, failed_steps,
  observations}`. Vive durante el turno; opcionalmente persiste con
  `PlanGraphCheckpointStore` para misiones largas.
- Reemplaza `IntentResolution.next_state` por consulta sobre
  `MissionState`.

### M3 — Step-by-step tool loop

- Refactor del bloque `for iteration in range(MAX_TOOL_ITERATIONS)` para:
  - Si hay `MissionState.next_step`, anteponer su objetivo al system prompt
    de la iteración.
  - Si la respuesta no tiene tool y `MissionState.current_step_unfinished`,
    forzar `require_tool=True` con catálogo expandido y continuación
    explícita.
  - Si el LLM persiste 2 iteraciones sin tool ni señal de cierre → marcar
    `step_failed_no_tool`, avanzar a `partial`.

### M4 — Re-observe after action

- Después de `app_open` / `gui_do` / `window_*` / `process_*`:
  - Snapshot UIA estructural de la ventana activa (top 30 elementos
    actionable, profundidad 2).
  - Screenshot bajo flag (uses `screen_cache`).
  - Append como `role="tool"` o `role="system"` con label
    `[OBSERVATION step=N]`.
- Cap de tokens (≤800 chars).

### M5 — Mission-level verification

- `MissionVerifier.verify(plan, observations, ledger)` que evalúe:
  - cada `step.success_criteria` (declarado por TaskFrame o por el
    descomposer);
  - estado final del sistema vía perception monitor (`expected_processes_alive`,
    `expected_processes_dead`, `expected_files_present`).
- `AgentTurnResult` gana campo `mission_status: str`. `ok` queda
  `True` sólo si `complete`.

### M6 — Tool catalog per-step

- `select_tools_for_turn(...)` se invoca por iteración con:
  - `step_objective` adicional al `user_text`;
  - `prior_calls` con todos los tools usados en el turno;
  - `peers` por capability (`app_open` → `app_close`, `process_stop_app`,
    `window_close`).
- Mantener el cap top-K para no inflar contexto.

### M7 — GUI / vision fallback ladder

- Definir cadena explícita en `gui_agent`:
  `UIA → Playwright (sólo web) → screenshot+OCR → LLM_VISION → fail honesto`.
- Para cada eslabón, telemetría: `backend`, `latency_ms`, `success`,
  `evidence`. Loguear en ledger.
- Cap de fallbacks por step (≤2). Si todos fallan → `step_failed_perception`.

### M8 — Compound smoke suite

- Reescribir `audit/smoke_runner_fsmoke.py` como `audit/compound_smoke.py`.
- Casos mínimos:
  1. `abre Notepad y luego ciérralo` → final state: `notepad.exe` no en
     `process_iter`.
  2. `abre Notepad, escribe "compound smoke", guarda como Desktop\\probe.txt
     y ciérralo` → archivo existe + notepad cerrado.
  3. `abre Opera y busca Batman` → ventana de Opera con título conteniendo
     "Batman" o pestaña con URL google `q=Batman`.
  4. `abre Steam, ve a biblioteca y cierra Steam` (skip si Steam no
     instalado).
  5. Tarea con 3 pasos donde el paso 2 falla por diseño → resultado
     `partial`, no `ok`.
  6. Conversación pura (`hola`, `gracias`) → 0 tools, reply en idioma del
     usuario, NO contiene `NO_TOOL_NEEDED`.
- Reporte: `pass / partial / fail` con razón estructurada.

### M9 — Honest final answer

- Plantilla determinística en función del `mission_status`:
  - `complete`: "Listo. Pasos: ...".
  - `partial`: "Completé N de M pasos. Falló: <step>. Lo que observé: <obs>."
  - `step_failed`: "No pude completar el paso <name>. Detalle: <error>."
  - `unverified`: "Ejecuté <tools> pero no pude verificar el resultado:
    <razón>."
- El LLM redacta el contenido textual; el agente garantiza el campo de
  estado (no se confía sólo en el texto del LLM).

---

## 10. Qué NO hacer

- No agregar listas `if "Notepad"`, `if "Steam"`, `if "ciérralo"`, ni
  diccionarios por idioma para detectar segundo paso.
- No "resolver" sólo Notepad: el problema es estructural, no por app.
- No forzar siempre el universal runner ni `vision` en cada turno: aumenta
  latencia y rompe casos triviales (texto puro, identidad, hora).
- No reactivar el camino completo del universal runner para conversación
  simple. El gating por descomposición (M1) debe filtrar.
- No engordar el system prompt con instrucciones sobre cómo cerrar
  Notepad. El cambio es de loop, no de prompt.
- No declarar `ok=True` por `tool_count > 0` en ningún test ni smoke.
- No bloquear la rama feliz introduciendo timeouts agresivos en
  verification (mantener `_MAX_WAIT=3.0` actual).
- No introducir Playwright para GUI desktop. El stack desktop es UIA +
  vision; no mezclar.

---

## 11. Primer bloque recomendado (M1 + M2 mínimos + M8 smoke)

**Archivos a tocar (orden de implementación):**

1. `src/carter_v2/turn/mission.py` (NUEVO, ~200 LOC):
   - `MissionStep`, `MissionState`, `MissionStatus` dataclasses.
   - `MissionStateBuilder.from_intent(intent_frame, decomposed_steps)`.
   - Métodos `current_step()`, `mark_step_completed(tool_name, evidence)`,
     `mark_step_failed(reason)`, `is_complete()`, `is_partial()`.
2. `src/carter_v2/turn/intent_resolution.py`:
   - Añadir `decompose_intent(user_text, llm_backend) -> list[MissionStep]`
     que delegue a `TaskFrameBuilder` (sin tools, JSON estricto).
   - No modificar `evaluate_direct_action_closure` aún; se usa para
     compatibilidad.
3. `src/carter_v2/turn/agent.py`:
   - Inyectar `MissionState` al inicio del turno (sólo si el clasificador
     dice "compuesto"; si dice "simple" → state con 1 step = el actual flow).
   - En la rama "no has_tool_calls" tras `calls_made`: si
     `mission_state.has_pending_steps()` → forzar 1 retry con
     `require_tool=True` y catálogo expandido. Si persiste sin tool →
     retornar `ok=False, mission_status="partial"`.
   - En `_return_turn` añadir `mission_status` al trace y al
     `AgentTurnResult`.
4. `src/carter_v2/turn/tool_catalog_selection.py`:
   - Añadir parámetro `prior_calls` y un mapa estructural de "peers" por
     capability (cargado del registry, no hardcoded por nombre):
     `app_open ↔ app_close, process_start_app ↔ process_stop_app,
     window_focus ↔ window_close`. Calcular ese mapa una vez al inicio del
     proceso desde la metadata `tool_definition().capability + .action`.
5. `audit/compound_smoke.py` (NUEVO, ~200 LOC):
   - Lista de casos con `expected_tools`, `forbidden_replies`,
     `final_state_check(callable)`.
   - Reporta `pass/partial/fail`. Devuelve exit code != 0 si hay fail.
6. `tests/test_compound_decomposition.py` (NUEVO):
   - Tests unitarios con backend mock: 1 step, 2 steps, 3 steps con
     dependencia, fallo en paso 2.
7. `tests/test_mission_state.py` (NUEVO):
   - Lifecycle del MissionState (pending → running → step_success →
     complete; o → step_failed → partial).

**Riesgo:**
- Bajo en M1+M2 si el clasificador es conservador (default = simple).
  Misiones simples siguen exactamente la ruta actual.
- Medio en M3 si el `require_tool` forzado en iteración 2 induce loops con
  modelos que no soportan tool_choice (Ollama: depende del modelo). Mitigar
  con cap de retries (≤1) y fallback `mission_status=partial`.
- Bajo en M8 si se mantiene como suite separada (no reemplaza F-SMOKE
  hasta que los counts sean estables).

**Tests:**
- Unitarios offline: `tests/test_compound_decomposition.py`,
  `tests/test_mission_state.py`, `tests/test_tool_catalog_peers.py`.
- Live (gateado `@pytest.mark.live`): los 6 casos de M8.
- Regresión: `pytest -q` completo (1569 tests actuales) debe seguir
  verde.

**Rollback:**
- Todo nuevo código va detrás de flag `CARTER_MISSION_STATE` (default
  `1`), `CARTER_INTENT_DECOMPOSITION` (default `1`). Si algo regresiona,
  setear `CARTER_MISSION_STATE=0` restaura el agent loop tal cual está
  hoy. M8 vive en `audit/`, no se acopla al runtime.

---

## Anexo — métricas honestas observadas

- LOC core relevantes:
  - `agent.py`: 2240
  - `verification.py`: 808
  - `gui_agent.py`: 1330
  - `vision_router.py`: 1025
  - `runner.py` (universal): 461
  - `intent_resolution.py`: 244
  - `tool_catalog_selection.py`: 186
- Smoke F-SMOKE real: 14 / 18 honesto (4 falsos positivos: 9, 14, 15, 16).
- Universal runner: presente, testeado, **desconectado del modo texto**.
- GUI fallback ladder en gui_agent: parcial (UIA → semantic vision), sin
  telemetría completa de tier por step.
- Mission verification: ausente.
- Compound smoke: ausente.
