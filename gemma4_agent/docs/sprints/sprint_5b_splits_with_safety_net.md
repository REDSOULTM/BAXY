# PROMPT — Sprint 5b (splits con red de seguridad de Sprint 5a)

> ⚠ **PRE-REQUISITO:** Sprint 5a debe haber terminado con todos los
> tests nuevos en verde. Si Sprint 5a SKIP de Qt está en `_sprint5a_log.md`,
> Sprint 5b va a SKIP las tareas 5b.4 y 5b.5 (MainWindow + SettingsDialog).
>
> Continúa el mismo chat de Claude Code que corrió Sprints 0+1+2+3a+4+5a.

---

## Estado del repo al arrancar

- Rama: `PortandoLoMejor`. HEAD: último commit de Sprint 5a
  (`sprint5a: write log`).
- Working tree limpio.
- 65 compound tools intactas.
- Tests de contrato para los 4 god classes existen y pasan
  (más los 40 preexistentes).

---

## Filosofía de Sprint 5b

Cada tarea sigue el ciclo **GREEN → REFACTOR → GREEN**:

1. **GREEN:** correr los tests del god class objetivo. **Todos en verde.**
2. **REFACTOR:** mover código (extract method/class/file). NO cambiar
   comportamiento.
3. **GREEN:** correr los MISMOS tests. **Todos en verde de nuevo.**

Si después del refactor un test queda rojo:
- Primero entender por qué (mock-path quedó obsoleto vs bug real).
- Si es ajuste de import paths en el test: ajustar el test
  (es válido — el split cambió rutas, no comportamiento).
- Si es bug real introducido por el split: `git reset --hard HEAD~1`,
  anotar blocker en `_sprint5b_log.md`, pasar a la siguiente tarea.

**El objetivo NO es completar las 5 tareas a toda costa. Es completar
las que pueden hacerse sin bajar la barra de los tests.**

---

## Prompt completo (copy/paste al chat existente)

```
Continuamos. Estado: rama PortandoLoMejor, HEAD en el último commit
de Sprint 5a, working tree limpio, 65 compound tools intactas, red
de tests-de-contrato lista en test_tool_registry_contract.py,
test_gemma4agent_contract.py, test_agent_workers_parity.py,
test_main_window_contract.py, test_settings_dialog_contract.py.

# OBJETIVO DE SPRINT 5b

Splitear los 4 god classes en sub-módulos cohesivos, usando los tests
de contrato del Sprint 5a como red de seguridad. NO se eliminan LOC
(los splits MUEVEN código). El valor es mantenibilidad: cada bug
queda localizado a un archivo más chico.

# REGLAS GENERALES

1. Trabajás en PortandoLoMejor. Commits chicos. Prefijo
   "sprint5b: <tarea>". NO push, NO toques main.
2. WORKFLOW OBLIGATORIO por tarea:
   a) Correr los tests del god class objetivo. Si NO están todos
      en verde antes del refactor: abortar, anotar blocker.
   b) Hacer el split (mover código a archivo/clase nueva).
   c) Correr los MISMOS tests. Deben pasar 100%.
   d) Si fallan: `git reset --hard HEAD~1`, anotar blocker, siguiente
      tarea.
   e) Si pasan: `git commit`.
3. Después de cada commit:
   `python -c "import gemma4_agent; from gemma4_agent.tools import
   COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"` debe
   imprimir 65.
4. Después de cada commit:
   `python -m gemma4_agent.launcher status 2>&1 | head -5` no
   debe lanzar TraceError.
5. NO instales deps. NO ejecutes el agente real ni llama-server.
6. NO toques: voice/, mission_goal.py, mission_outcome.py,
   verifiers.py, verify_core.py, personas.py, microagents.py,
   skills_registry.py, traces.jsonl en disco.
7. NO modifiques COMPOUND_TOOL_SCHEMAS — sólo el código que lo
   procesa.
8. PRESERVAR API PÚBLICA. Las firmas y nombres de clase que
   importan otras superficies (chat.py, ui/, server.py, mcp_server.py,
   *_runner.py) NO cambian. Los splits son INTERNOS.
9. Si tenés que cambiar un import en un caller (e.g. una superficie
   que importaba un nombre que ahora vive en otro módulo): hacer un
   re-export en el módulo viejo para no romper. Ejemplo:
   ```python
   # tools.py (después del split)
   from .tool_registry.dispatch import ToolRegistry  # re-export
   ```
10. Si dudás entre splitear o dejar: dejá. Anotá en log. Sprint 6
    puede continuar.

# WORKFLOW

5 tareas, ordenadas de menor a mayor riesgo. Si una falla, las
posteriores siguen pudiendo correr (cada split es independiente).

## 5b.1 — Split `ToolRegistry` (3 157 LOC)

⚠ La pieza más grande del repo, pero también la más mecánica para
splitear. La estrategia es **extraer 1 cosa a la vez**, no reescribir.

**Pre-flight:**
```bash
python -m pytest gemma4_agent/test_tool_registry_contract.py \
                 gemma4_agent/test_tool_dispatch_contract.py \
                 gemma4_agent/test_tool_call_rescue.py \
                 gemma4_agent/test_tool_watchdog.py -v
```
Todos deben estar en verde antes de empezar.

**Sub-tareas (cada una es un commit chico):**

(5b.1.a) Extraer `AppResolver` + `AppCandidate` a `gemma4_agent/app_resolver.py`.
- Mover las 2 clases (de `tools.py:642-1155` aprox) a archivo nuevo.
- En `tools.py` agregar `from .app_resolver import AppResolver, AppCandidate`.
- `ToolRegistry.apps = AppResolver()` sigue funcionando igual.
- Verificación: `python -c "from gemma4_agent.tools import ToolRegistry"` ✓
- Re-correr tests del pre-flight. Verde.
- Commit: "sprint5b: extract AppResolver + AppCandidate to app_resolver.py"

(5b.1.b) Extraer `_SSRFGuardRedirectHandler` a `gemma4_agent/ssrf_guard.py`.
- Audit §4.20 ya lo marcó como `[1-USER]`. Mover ~30 LOC.
- Re-importar en `tools.py` para los callers internos (`web_read`,
  `download_tool`).
- Verificación + tests + commit.

(5b.1.c) Extraer `_normalize_tool_result` + `_coerce_and_validate_tool_args`
+ `_PRE_VALIDATORS` + `_parameters_for_tool` a
`gemma4_agent/tool_dispatch.py`.
- Son las helpers del pipeline de `execute()`. Independientes de
  `self`.
- `ToolRegistry.execute()` queda como wrapper de ~30 LOC que llama a
  `tool_dispatch.run_pipeline(name, args, _impls, state, safety_enabled)`.
- ATENCIÓN: este es el cambio más sutil. Después del refactor,
  `test_tool_dispatch_contract.py` debe seguir verde 100%.
- Verificación: corré los 5 invariantes del contract. Tests + commit.

(5b.1.d) Extraer `COMPOUND_TOOL_SCHEMAS` literal (líneas 4 645+) a
`gemma4_agent/tool_schemas.py`.
- Es una lista enorme de dicts. Moverla a su propio archivo.
- `tools.py` mantiene `from .tool_schemas import COMPOUND_TOOL_SCHEMAS`.
- Esto NO cambia comportamiento, solo ubicación del literal.
- Verificación: `len(COMPOUND_TOOL_SCHEMAS) == 65` desde `tools.py` y
  desde `tool_schemas.py`. Tests + commit.

(5b.1.e) DECISIÓN OPCIONAL: extraer wrappers `t_*` a `tool_handlers.py`.
- Los métodos `t_office`, `t_audio_device`, ..., `t_smart_home`
  (~50 wrappers que solo reenvían a `domain_tools.<name>_tool(state, args)`).
- Si lo hacés: convertir el dict `_impls` para que se construya
  programáticamente en `tool_handlers.build_impls(state)`.
- Si lo dejás: anotar en log. Es un refactor cosmético que no agrega
  valor inmediato.
- Sugerencia: SKIP en este sprint. Espera a Sprint 6 si querés.

**Resultado esperado:** `tools.py` baja de 4 825 LOC a ~700 LOC
(solo `ToolRegistry.__init__` + los `t_X` wrappers + re-exports).
Total LOC sin cambio neto (se movieron, no se borraron).

## 5b.2 — Split `Gemma4Agent` (1 852 LOC)

⚠ Riesgo más alto del sprint. `run_content` solo es 892 LOC.

**Pre-flight:**
```bash
python -m pytest gemma4_agent/test_gemma4agent_contract.py \
                 gemma4_agent/test_promise_guard.py \
                 gemma4_agent/test_phrase_trigger_guards.py \
                 gemma4_agent/test_inherit_tools_safety.py \
                 gemma4_agent/test_loop_detection.py -v
```
Todos verde antes de empezar.

**Sub-tareas (cada una es un commit. Si una falla, abortar las
posteriores):**

(5b.2.a) Extraer 6 `_guard_*` methods + `_build_user_facing_fallback`
a `gemma4_agent/agent_guards.py`.
- ~337 LOC.
- Cada guard se vuelve función pura: recibe `content`, `events`,
  `history`, `mission_outcome` como parámetros explícitos.
- En `Gemma4Agent`, los 6 methods se vuelven wrappers de 3 líneas
  que llaman al módulo.
- Verificación: `test_promise_guard.py` + `test_phrase_trigger_guards.py`
  100% verde.
- Commit.

(5b.2.b) Extraer `_extract_facts` + `_summarize_history_block` +
`_compact_completed_history` + `_compact_active_history_for_retry` +
los helpers `_compact_*` top-level a `gemma4_agent/agent_compaction.py`.
- ~370 LOC.
- Mismo patrón: funciones puras con state explícito.
- Verificación: import + smoke test de run_content con mock LLM
  (5a.2 test (d)).
- Commit.

(5b.2.c) Extraer `_system_message` + `_tool_schemas_hint` +
`_messages` + `CORE_PROMPT` + `TOOL_RULES` a
`gemma4_agent/agent_prompt.py`.
- ~675 LOC (incluyendo CORE_PROMPT 160 LOC + TOOL_RULES 330 LOC +
  builders).
- `Gemma4Agent._system_message` se vuelve wrapper de 5 líneas.
- ATENCIÓN: `CORE_PROMPT` y `TOOL_RULES` son MÓDULO-level en
  `agent.py`, NO instance attributes. Al moverlos preservar el
  acceso como atributos del nuevo módulo.
- Verificación + commit.

(5b.2.d) Extraer `_execute_calls_sequential` + `_execute_calls_parallel`
a `gemma4_agent/agent_dispatch.py`.
- ~183 LOC.
- Tomar `tool_calls`, `tool_registry`, `progress_cb` como parámetros.
- Devolver `list[ToolEvent]`.
- Verificación + commit.

(5b.2.e) Lo que queda en `agent.py`:
- `Gemma4Agent.__init__` + `clear` + `set_persona` + `get_persona` +
  `run_text` + `run_content` (ahora más corto, llama a los módulos
  extraídos) + atributos.
- LOC esperadas en agent.py post-split: 500-700.
- Verificación FINAL: `test_gemma4agent_contract.py` 100%, smoke
  test de run_text con mock LLM ok.

**Resultado esperado:** `agent.py` baja de 2 968 a ~700 LOC.
4 archivos nuevos. Total LOC sin cambio neto.

## 5b.3 — Colapsar `AgentWorker` ≡ `AgentRunner` (con red de 5a.3)

⚠ Esta tarea SÓLO se intenta si Sprint 4 (commit `86c9c0a`) la
canceló pero ahora con tests-first es viable. Si en `_sprint4_log.md`
el agente explicó que los workers divergen genuinamente en threading
model y output channel: re-evaluar.

**Estrategia:** crear `gemma4_agent/agent_serial.py` con clase
abstracta `AgentSerialBase` que define las **operaciones invariantes**:
- `_inbox: Queue[TurnRequest]`
- `_build_agent()` (con autostart llama-server)
- `_run()` worker loop
- `_progress_forwarder()` (abstract — cada subclase lo implementa)

`AgentRunner` (FastAPI) y `AgentWorker` (PyQt) heredan + sobrescriben
SOLO la output. La duplicación del **build sequence** desaparece.

**Pre-flight:**
```bash
python -m pytest gemma4_agent/test_agent_workers_parity.py -v
```
Verde.

**Pasos:**

(5b.3.a) Crear `gemma4_agent/agent_serial.py` con `AgentSerialBase`.
- Mover el código común de `agent_runner._build_agent` + `_run` +
  `_autostart_llama_server` (~250 LOC).
- Los outputs son hookeables: `_on_state_change(state: str)`,
  `_on_activity(src: str, msg: str)`, `_on_progress(event: str,
  payload: dict)`. Por defecto no-op.
- Commit: "sprint5b: extract AgentSerialBase from AgentRunner/AgentWorker"

(5b.3.b) Migrar `AgentRunner` a heredar de `AgentSerialBase`.
- Sobrescribir los hooks para publicar al BUS.
- `RUNNER` singleton conservado.
- Verificación: `test_agent_workers_parity.py` aún verde.
- Commit.

(5b.3.c) Migrar `AgentWorker` (PyQt) a heredar de `AgentSerialBase`
+ `QThread`.
- Sobrescribir los hooks para emitir pyqtSignals.
- Las 7 signals (`state_changed`, `progress`, `log`, `reply_ready`,
  `llm_error`, `connection_changed`, `health_status`) se mantienen
  como API pública de la clase.
- Verificación: `test_agent_workers_parity.py` aún verde (incluyendo
  los slots de Qt si tu entorno los corre).
- Commit.

(5b.3.d) Eliminar `ServerBootWorker` anidado en
`ui/main_window.py:81`.
- Reemplazar su uso por una llamada directa a
  `AgentSerialBase._autostart_llama_server()` en un thread daemon,
  con callback que emite pyqtSignal para el progreso.
- Verificación: `test_main_window_contract.py` aún verde.
- Commit.

Si los workers REALMENTE divergen genuinamente (lo cual Sprint 4
sugirió), entonces 5b.3.a-c se vuelven SKIP con razón documentada.
Aún así 5b.3.d puede valer la pena por separado.

## 5b.4 — Split `MainWindow` (1 430 LOC, 53 métodos)

**PRE-REQUISITO:** `test_main_window_contract.py` debe estar
**verde** (no skipped por Qt headless). Si en
`_sprint5a_log.md` está SKIP por Qt, este sprint task **se cancela
y va a Sprint 6**.

**Estrategia:** mover cada widget de side panel + dialog wiring a
su propio archivo. `MainWindow` queda como integrador.

Sub-tareas:

(5b.4.a) Extraer wiring de menú/atajos a `ui/main_menu.py`.
(5b.4.b) Extraer setup de central layout (hud + log) a
`ui/main_layout.py`.
(5b.4.c) Extraer event handlers de tray / persistencia / cleanup a
`ui/main_window_lifecycle.py`.

Cada commit: verificación + 5a.4 verde.

Si los métodos están demasiado entrelazados con state interno
(probable, dado que son 53 en 1 clase), **SKIP** lo que no se pueda
splitear sin tocar contratos.

## 5b.5 — Split `SettingsDialog` (1 148 LOC, 22 métodos)

**PRE-REQUISITO:** `test_settings_dialog_contract.py` verde.

**Estrategia:** split por tab. El dialog tiene ~5-7 tabs visibles
(Profile, Voice, Server, etc). Cada tab pasa a `ui/settings_<tab>.py`.

`SettingsDialog` queda como integrador que instancia cada sub-widget.

Cada commit: el split de 1 tab + verificación + tests verde.

Si Qt está skipped o los tabs comparten state global: SKIP las
sub-tareas que no pueden hacerse limpias.

## 5b.6 — Reporting

Escribí `docs/architecture/sprint_prompts/_sprint5b_log.md`:

- Timestamp inicio/fin.
- Tareas hechas con SHA del commit.
- Tareas SKIPPED con razón explícita.
- LOC delta: `git diff --shortstat <base_5a>..HEAD`. Probable ~0
  net (los splits mueven).
- LOC POR ARCHIVO ahora vs antes (`wc -l` antes y después de los
  god classes): "agent.py 2968 → XXX, tools.py 4825 → XXX,
  ui/main_window.py 1430 → XXX, ui/settings.py 1148 → XXX".
- Lista de archivos NUEVOS creados con sus LOC.
- Estado final: `git log --oneline -20` + `git status`.

Commit final: "sprint5b: write log".

# VERIFICACIONES OBLIGATORIAS AL CIERRE

```bash
# 1. Tools intactas
python -c "from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"
# Esperado: 65

# 2. Launcher status
python -m gemma4_agent.launcher status 2>&1 | head -5

# 3. Tests de contrato (de Sprint 5a)
python -m pytest gemma4_agent/test_tool_registry_contract.py \
                 gemma4_agent/test_gemma4agent_contract.py \
                 gemma4_agent/test_agent_workers_parity.py \
                 gemma4_agent/test_main_window_contract.py \
                 gemma4_agent/test_settings_dialog_contract.py -q

# 4. Tests preexistentes (regresión)
python -m pytest gemma4_agent/test_tool_dispatch_contract.py \
                 gemma4_agent/test_session847_fixes.py \
                 gemma4_agent/test_log_audit_fixes.py \
                 gemma4_agent/test_inherit_tools_safety.py \
                 gemma4_agent/test_loop_detection.py -q

# 5. Toda la suite
python -m pytest gemma4_agent/ -q --tb=no 2>&1 | tail -3
```

# QUÉ NO HAGAS

- NO bajar la barra de tests: si un test rojo no es por mock-path,
  abortar la tarea.
- NO cambiar API pública (firmas de Gemma4Agent.run_text,
  ToolRegistry.execute, AgentRunner.submit, etc).
- NO modificar COMPOUND_TOOL_SCHEMAS ni la lógica de routing,
  capability, grounding, mission_outcome.
- NO borrar tools.
- NO completar las 5 tareas a costa de tests rojos: el orden
  preferido si hay que abandonar es 5b.5 > 5b.4 > 5b.3 > 5b.2 >
  5b.1 (las UI son menos críticas que los cores).
- NO instales deps. NO ejecutes el agente real.

Arrancá.
```

---

## Notas para vos al despertar

1. **Métrica de éxito:** todos los tests pasan en verde.
2. **LOC esperadas:** ~0 net (los splits mueven, no borran). El
   valor es **cada archivo nuevo es <500 LOC**, no la baja de LOC.
3. **Tabla de LOC por archivo esperada:**

| Archivo | Antes | Después | Δ |
|---|--:|--:|---|
| `agent.py` | 2 968 | ~700 | mueve a `agent_guards`, `agent_compaction`, `agent_prompt`, `agent_dispatch` |
| `tools.py` | 4 825 | ~700-1 000 | mueve a `app_resolver`, `ssrf_guard`, `tool_dispatch`, `tool_schemas` |
| `ui/main_window.py` | 1 430 | ~800-1 000 | mueve a `ui/main_menu`, `ui/main_layout`, etc |
| `ui/settings.py` | 1 148 | ~300-500 | mueve a `ui/settings_<tab>.py` por cada tab |
| Total | ~10 371 | ~2 500-3 200 | el resto vive en archivos nuevos |

4. **Si todo va bien:** quedás con ~10 archivos nuevos de 200-500
   LOC cada uno. Mucho más mantenible.

5. **Si algo falla:** seguís teniendo Sprint 6 disponible. Cada
   tarea es independiente.

6. **No esperes que cierre todas las 5.** 5b.4 y 5b.5 son los más
   probables a SKIP por entanglement Qt. 5b.1, 5b.2, 5b.3 son los
   premios reales.

## Lo que viene después

- **Sprint 3b** (datos personas/microagents/skills, 7-10 días con
  uso real).
- **Sprint 6** (si Sprint 5b dejó tareas en SKIP, o si Sprint 3b
  revela features a borrar).

Después de Sprint 5b, el repo está en su mejor estado estructural:
sin god classes >700 LOC, sin duplicaciones auto-confesadas, con
red de tests de contrato cubriendo las APIs públicas.
