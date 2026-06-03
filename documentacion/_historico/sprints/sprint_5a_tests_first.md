# PROMPT — Sprint 5a (tests-first para los 4 god classes)

> Continúa el mismo chat de Claude Code que corrió Sprints 0+1+2+3a+4.
> El agente conoce el repo, los logs y el reporte.
>
> **Sprint 5a NO refactoriza nada.** Solo escribe tests de contrato
> que pinen la API pública de los 4 god classes antes de splitearlos
> en Sprint 5b. Cuando Sprint 5b mueva código, estos tests detectan
> regresiones en segundos.

---

## Por qué tests-first es no-negociable para Sprint 5

Los splits de Sprint 5b van a tocar **~7 587 LOC en 4 clases que
tocan TODO**:

| Clase | LOC | Métodos | Si rompe, ¿qué se cae? |
|---|--:|--:|---|
| `Gemma4Agent` | 1 852 | 21 | CLI + UI Desktop + UI Field + MCP + Voice = todo |
| `ToolRegistry` | 3 157 | 142 | 65 tools fallan en silencio |
| `MainWindow` | 1 430 | 53 | UI Desktop no abre |
| `SettingsDialog` | 1 148 | 22 | No se puede cambiar profile |

Los bugs típicos de un split sin red de seguridad son **silenciosos**:
el agente responde "Listo, abrí Spotify" pero no abrió nada. El
sistema tiene 6 `_guard_*` methods justamente para parchar este
problema — pero los guards no detectan si un guard se rompió.
**Sprint 5a construye la red. Sprint 5b corre por arriba.**

---

## Estado del repo al arrancar este sprint

- Rama: `PortandoLoMejor`. HEAD: `6107783` (sprint4: write log).
- Working tree limpio. 65 compound tools intactas.
- 40 archivos de tests existentes (33 con `unittest.TestCase`).
- 69/69 tests pasan en los 4 grupos del prompt anterior.
- Cold import `gemma4_agent.tools`: 0.152s.

---

## Prompt completo (copy/paste al chat existente)

```
Continuamos. Estado: rama PortandoLoMejor, HEAD en 6107783, working
tree limpio, 65 compound tools intactas, 40 test files existentes,
69/69 tests pasaron en sprint 4.

# OBJETIVO DE SPRINT 5a

Crear una RED DE TESTS DE CONTRATO para los 4 god classes que Sprint
5b va a splitear. NO se refactoriza ningún god class en este sprint.
Solo se agregan tests.

# REGLAS GENERALES

1. Trabajás en PortandoLoMejor. Commits chicos por tarea, prefijo
   "sprint5a: <tarea>". NO push, NO toques main.
2. Después de CADA commit: `python -m pytest <test_file_recien_escrito> -q`
   debe pasar 100% (los tests que vos mismo agregás deben pasar antes
   de commitear; si no pasan, el test está mal escrito, no el código).
3. Después de cada commit:
   `python -c "import gemma4_agent; from gemma4_agent.tools import
   COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"` debe
   imprimir 65.
4. NO refactorices NINGÚN god class. NO modifiques agent.py, tools.py,
   ui/main_window.py, ui/settings.py salvo lo MÍNIMO necesario para
   exponer un valor que necesita un test (e.g. un `def __len__` en
   ToolRegistry). Cualquier modificación de los god classes en este
   sprint debe ser **aditiva** (nuevos métodos públicos read-only),
   nunca reescritura de los existentes.
5. NO instales deps. NO ejecutes el agente real ni llama-server.
6. NO toques data/, ~/.gemma4/, captures/, logs/, models/.
7. NO modifiques tests existentes salvo para FIJAR bugs preexistentes
   conocidos (sólo si tropezás con uno que rompe en este sprint).
8. NO crees fixtures complejos con sqlite real. Si necesitás
   stub/mock, usá `unittest.mock` (stdlib).
9. Si un test que escribís captura un bug REAL del código (no falla
   por mal-mock): NO arregles el código en este sprint. Anotalo en
   `docs/architecture/sprint_prompts/_sprint5a_log.md` como "BUG
   FOUND" con repro mínimo. Sprint 5b o 6 lo arregla.

# CONTEXTO

- `docs/architecture/02_components/` y `03_classes/` describen los
  god classes en detalle. Léelos antes de empezar cada tarea.
- `docs/architecture/04_sequences/` describe los flujos críticos que
  los tests deben proteger (voice_turn, boot, slot_filling,
  router_fallback, shutdown).
- Tests existentes ya cubren PARTES: `test_tool_dispatch_contract.py`
  fija contrato de `ToolRegistry.execute`. **NO duplicar lo que ya
  está cubierto.** Antes de escribir cada test nuevo:
  `grep -rn "<api_a_testear>" gemma4_agent/test_*.py`.

# WORKFLOW

5 tareas, ordenadas por valor y dependencia. Cada tarea es 1 archivo
de tests nuevo + 1 commit.

## 5a.1 — test_tool_registry_contract.py (extiende lo existente)

`test_tool_dispatch_contract.py` ya pina `execute()` (5 invariantes).
Faltan tests para:

- `schemas()` → returns `list[dict]` con cada entry teniendo
  `{type: "function", function: {name, description, parameters}}`.
  Length == 65.
- `schema_names()` → returns `list[str]`, length 65, sin duplicados.
- `schemas_for_names(["audio", "media"])` → returns subset
  filtrado correctamente, en el orden pedido, no falla con
  nombres inexistentes (los ignora silenciosamente).
- `execute_routine_step(name, args, confirmed_at_create=True)` →
  inyecta `routine_context=True` y `confirmed_at_create=True` al
  handler (verificá con un mock handler que captura args).
  Cuando `confirmed_at_create=False` y la tool requiere
  confirmación, debe devolver `status="needs_confirmation"`.
- `safety_enabled=True` flag al constructor: tools peligrosas
  (`whatsapp`, `terminal`, etc) devuelven
  `status="needs_confirmation"` si no vienen `confirmed=True`.
- `safety_enabled=False`: las mismas tools corren sin
  confirmación.
- `_impls` dict tiene EXACTAMENTE 65 entries — anti-regresión por
  si Sprint 5b accidentalmente borra un wrapper.
- `parent_agent` attribute: se puede setear, defaults a None, lo
  lee la tool `subagent` para crear un sub-Gemma4Agent.

Patrón de test (referencia `test_tool_dispatch_contract.py`):

```python
import unittest
import tempfile
from pathlib import Path
from gemma4_agent.tools import ToolRegistry, COMPOUND_TOOL_SCHEMAS
from gemma4_agent.memory import MemoryStore
from gemma4_agent.state import AgentState

class ToolRegistryContract(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.mem = MemoryStore(Path(tmp) / "mem.json")
        self.state = AgentState(Path(tmp) / "state.json")
        self.captures = Path(tmp) / "captures"
        self.reg = ToolRegistry(self.mem, self.captures, self.state,
                                 safety_enabled=False)

    def test_schemas_returns_65_entries(self): ...
    def test_schemas_for_names_filters_correctly(self): ...
    # etc.
```

Verificación post: `python -m pytest
gemma4_agent/test_tool_registry_contract.py -q` debe ser 100% green.

Commit: "sprint5a: add ToolRegistry contract tests (schemas API,
execute_routine_step, safety_enabled flag, _impls integrity)"

## 5a.2 — test_gemma4agent_contract.py

Cubre la API pública de `Gemma4Agent` que las 4 superficies (CLI, UI
Desktop, UI Field, MCP) usan. Sin esto, splitear `run_content`
(892 LOC) es un acto de fe.

Tests requeridos:

(a) **Constructor invariants:**
    - `Gemma4Agent(config)` instancia OK con un `AgentConfig` mínimo
      (memory_path en tmpdir, state_path en tmpdir).
    - Después de `__init__`, los atributos `self.memory`, `self.state`,
      `self.client`, `self.tools`, `self.experience`, `self.trace`,
      `self.history`, `self._persona` existen y tienen tipos
      correctos.
    - `len(self.history) == 0`.
    - `self.tools.parent_agent is self` (backref correcto).

(b) **`clear()` resetea TODO lo enumerable:**
    - history vacía después de clear.
    - `_recent_recalls`, `_phrase_fires`, `_cached_microagents` vacíos.
    - `_cached_skills_menu`, `_cached_skills_critical` None.
    - `_turn_counter == 0`.
    - `_last_turn_ts is None`.

(c) **`set_persona()` / `get_persona()`:**
    - Default persona name == "default".
    - `set_persona("coder")` cambia, `get_persona()["persona"] == "coder"`.
    - `set_persona("nonexistent")` devuelve `{"ok": False, "error": ...}`
      sin cambiar persona.

(d) **`run_text` smoke test SIN LLM real:**
    Mock `LLMClient.chat` para que devuelva un response sintético
    (`{"choices": [{"message": {"content": "ok", "tool_calls": []}}]}`).
    - `run_text("hola")` devuelve un `AgentReply`.
    - El reply tiene los atributos `content`, `tool_events`, `error`,
      `mission`.
    - `len(self.history) > 0` después del turn (system + user + assistant).
    - `_turn_counter == 1`.

(e) **`run_text` con tool call mockeado:**
    Mock `LLMClient.chat` para devolver tool_calls en el primer
    response y un reply natural en el segundo. Mock
    `ToolRegistry.execute` para devolver `{"ok": True, "status": "ok",
    ...}`.
    - El reply final tiene `tool_events` con el evento del tool
      mockeado.
    - `self.history` contiene el mensaje role=tool con el resultado.

(f) **Guards inline (los 6 `_guard_*`) son llamados:**
    No testees el comportamiento de cada guard (eso es de
    `test_promise_guard.py`, `test_phrase_trigger_guards.py`). Sólo
    pina que **al menos uno se invoca** post-reply. Usá
    `unittest.mock.patch.object` para spy on `_guard_promise_without_action`.

(g) **history limit & compaction triggers:**
    No corras la compaction (cara). Sólo verificá:
    - `_compute_context_budget(context_size=4096)` retorna un dict
      con keys esperadas (`live_tokens`, `compact_threshold`, etc).
    - Mock `_compact_completed_history` y verificá que se llama si
      el budget se excede.

Patrón de mocking obligatorio: nunca toques llama-server, nunca cargues
modelos ML. `unittest.mock.MagicMock` para `LLMClient`.

Si el test (d) o (e) revela que `Gemma4Agent.run_text` necesita
parámetros opcionales que no documenté: leé `agent.py:run_text` y
ajustá el test al contrato real. NO modifiques `run_text`.

Commit: "sprint5a: add Gemma4Agent contract tests (init, clear,
persona, run_text smoke + tool_call flow, guards spy)"

## 5a.3 — test_agent_workers_parity.py

⚠ El test más importante de este sprint. Sprint 5b va a colapsar
`AgentWorker` (PyQt QThread) y `AgentRunner` (threading + queue +
singleton) en una base compartida. Sin paridad pineada, podés cambiar
el comportamiento de uno y romperle el contrato al otro.

Tests requeridos:

(a) **`AgentRunner.submit("hola")` no bloquea:**
    - Llamá `.submit("hola")` en main thread.
    - Verificá que retorna en < 100 ms.
    - Verificá que `_inbox` tiene 1 item después.

(b) **`AgentRunner.stop()` desbloquea el worker:**
    - Iniciá runner con `.start()`.
    - Llamá `.stop()`.
    - El thread interno debe terminar en < 2 s.
    - `agent_ready()` retorna False después.

(c) **`AgentRunner.restart()`:**
    - Después de `.start()`, llamar `.restart()` resetea
      `_warmed_up = False`.
    - El thread vivo no se duplica (no leak).

(d) **`AgentWorker` (PyQt) tests sin GUI:**
    Si `PyQt6` no está disponible o no podés instanciar QApplication
    sin display: SKIP toda esta sección con
    `@unittest.skipUnless(...)`. Si SÍ podés:
    - `QApplication([])` headless + crear `AgentWorker()`.
    - Conectá un slot a `state_changed` y `log` signals.
    - Llamá `.submit("hola")`.
    - Procesá `app.processEvents()` por unos ms.
    - Verificá que las signals se emitieron (al menos `state_changed`
      a "INITIALISING" o "OFFLINE").

(e) **Paridad de API:**
    Verificá que ambos workers tienen los mismos métodos públicos:

    ```python
    runner_methods = {m for m in dir(AgentRunner) if not m.startswith('_')}
    worker_methods = {m for m in dir(AgentWorker) if not m.startswith('_')}
    common = runner_methods & worker_methods
    self.assertIn("submit", common)
    self.assertIn("stop", common)
    ```

    No exigir paridad COMPLETA (cada uno tiene su superficie), pero
    sí los métodos críticos: `submit`, `stop`.

(f) **Singleton RUNNER:**
    `from gemma4_agent.agent_runner import RUNNER` debe ser la misma
    instancia entre 2 imports en el mismo proceso.

Para todos: mock `Gemma4Agent` con `MagicMock` para no cargar el
stack pesado.

Commit: "sprint5a: add AgentWorker/AgentRunner parity contract tests"

## 5a.4 — test_main_window_contract.py

Sprint 5b va a splitear `MainWindow` (1 430 LOC, 53 métodos) en
sub-widgets. Necesitamos pinear:

(a) **Importable sin display:**
    Si Qt no anda en headless: SKIP entero. Si sí:
    - `from gemma4_agent.ui.main_window import MainWindow` no
      explota.
    - `MainWindow()` instancia sin crashear.
    - Métodos públicos esperados existen: `closeEvent`, y los slots
      conectados a las pyqtSignals de AgentWorker / EventBusBridge /
      VoiceBridge.

(b) **Widget children críticos:**
    Después de instanciar MainWindow, verificar que existen como
    atributos:
    - `self.worker` (AgentWorker instance).
    - `self.bus_bridge` (EventBusBridge instance).
    - Cualquier otro widget que Sprint 5b vaya a mover a archivo
      separado (e.g. `self.hud`, `self.log_widget`, `self.panels`,
      `self.sessions_panel`, `self.tool_explorer`).

(c) **No falla en `closeEvent`:**
    Simular cierre con `QCloseEvent` mockeado. No debe lanzar.

(d) **Signals conectados:**
    Verificar que la signal `worker.state_changed` tiene al menos un
    slot conectado (lo cual implica que MainWindow registró su
    handler).

Si no tenés Qt funcional en el entorno: marcá toda la suite como
`unittest.SkipTest` con razón clara. Sprint 5b va a correr en un
entorno que sí lo tenga.

Commit: "sprint5a: add MainWindow contract tests (importable, key
widgets, signal wiring)"

## 5a.5 — test_settings_dialog_contract.py

`SettingsDialog` (1 148 LOC, 22 métodos). El split de Sprint 5b va a
ser **por tab**, así que los tests deben pinear el contrato por
tab/sección:

(a) **Importable + instanciable:**
    Igual que 5a.4 — si Qt no anda, SKIP.

(b) **`apply_to_env()` / `apply_to_config()`:**
    Estos métodos toman valores del UI y los aplican. Sprint 5b los
    va a partir por tab.
    - Constructor con valores default.
    - Llamar `apply_to_env()` con mock de `os.environ`.
    - Verificar que escribe las keys esperadas (`GEMMA4_AGENT_*`).

(c) **`apply_persisted_on_startup` (function, no method):**
    - Mock `Path.home()` a tmpdir.
    - Sin `gui.json` → no falla, no aplica nada.
    - Con `gui.json` existente con `{"temperature": 0.7}` →
      `os.environ["GEMMA4_AGENT_TEMPERATURE"] == "0.7"`.

(d) **Cada tab/sección existe como widget identificable:**
    Sprint 5b va a mover cada tab a su propio archivo. Pinear los
    nombres de las tabs (con `tabWidget.tabText(i)` o similar) para
    que el split sepa qué grupos respetar.

Si no podés ejecutar Qt headless: SKIP. La regla es la misma que
5a.4.

Commit: "sprint5a: add SettingsDialog contract tests (env application,
persisted startup, tab structure)"

## 5a.6 — Reporting

Escribí `docs/architecture/sprint_prompts/_sprint5a_log.md`:

- Timestamp inicio/fin.
- Tareas hechas con SHA del commit y cantidad de tests agregados.
- Tareas SKIPPED con razón (probable: 5a.4 / 5a.5 por Qt headless).
- "BUGS FOUND" encontrados al escribir los tests (con repro
  mínimo), sin arreglarlos.
- LOC delta total: `git diff --shortstat 6107783..HEAD`. Sólo
  agregado (LOC removidas == 0).
- Estado final: `git log --oneline -15` + `git status`.
- Total tests nuevos: `python -m pytest gemma4_agent/test_tool_registry_contract.py
  gemma4_agent/test_gemma4agent_contract.py
  gemma4_agent/test_agent_workers_parity.py
  gemma4_agent/test_main_window_contract.py
  gemma4_agent/test_settings_dialog_contract.py -q --tb=no 2>&1 | tail -5`.

Commit final: "sprint5a: write log".

# VERIFICACIONES OBLIGATORIAS AL CIERRE

```bash
# 1. Import básico (no rompimos nada accidentalmente)
python -c "import gemma4_agent"

# 2. Tools intactas
python -c "from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"
# Esperado: 65

# 3. Tests preexistentes siguen pasando
python -m pytest gemma4_agent/test_tool_dispatch_contract.py \
                 gemma4_agent/test_session847_fixes.py \
                 gemma4_agent/test_log_audit_fixes.py \
                 gemma4_agent/test_inherit_tools_safety.py -q

# 4. Tests NUEVOS pasan
python -m pytest gemma4_agent/test_tool_registry_contract.py \
                 gemma4_agent/test_gemma4agent_contract.py \
                 gemma4_agent/test_agent_workers_parity.py -q
# Esperado: todos pasan. Si los de Qt están skipped por headless,
# OK, anotalo en log.

# 5. Total de tests del paquete (suma)
python -m pytest gemma4_agent/ -q --tb=no 2>&1 | tail -3
```

# QUÉ NO HAGAS

- NO modifiques agent.py, tools.py, ui/main_window.py, ui/settings.py
  salvo agregar métodos read-only mínimos si un test lo necesita.
- NO splittees nada. NO muevas código. Sólo tests.
- NO toques mission_goal.py, mission_outcome.py, verifiers.py,
  verify_core.py, personas.py, microagents.py, skills_registry.py,
  voice/.
- NO modifiques COMPOUND_TOOL_SCHEMAS.
- NO instales deps. NO toques llama-server / agente real / modelos.
- NO arregles bugs encontrados — sólo anotarlos.
- NO crees mocks que se importen entre tests; cada archivo es
  self-contained.

Arrancá.
```

---

## Notas para vos al despertar

1. **El número clave:** todos los tests nuevos pasan en verde. Si
   alguno se commiteó rojo (no debería poder, regla 2), revisar.
2. **Tests esperados agregados:** ~40-80 entre los 5 archivos.
3. **LOC delta:** sólo positivo (pure add). Esperá ~800-1 500 LOC
   nuevas (tests son verbosos).
4. **Si los tests de Qt fueron SKIP por headless:** OK. Sprint 5b
   los va a correr en un entorno con Qt funcional. Lo importante es
   que los archivos existan con la lógica correcta para el día que
   sí corran.
5. **Si encontró bugs reales:** son hallazgos valiosos. NO los
   arreglar en 5a — Sprint 5b o un sprint nuevo. El valor del
   tests-first es justamente eso: pinea el comportamiento ACTUAL
   (bugs incluidos) y después decidís qué arreglar.

## Lo que viene

**Sprint 5b** se lanza **solo si Sprint 5a termina verde**. Si
algún test crítico no pudo escribirse (e.g. Qt completamente roto en
tu entorno), evaluamos antes de splitear los widgets UI.
