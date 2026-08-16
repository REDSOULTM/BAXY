# PROMPT — Sprint 4 (refactor estructural sin tocar comportamiento)

> Continúa el mismo chat de Claude Code que corrió Sprints 0+1+2+3a.
> El agente conoce el repo, los logs y el reporte.
>
> **Diferencia con sprints previos:** este toca código que YA SE USA
> (no son tools muertas ni stack ineficiente). El objetivo es ELIMINAR
> DUPLICACIÓN estructural — código que hace lo mismo dos veces — sin
> cambiar el comportamiento observable. Riesgo medio: cada cambio
> requiere verificar que la funcionalidad sigue igual.

---

## Datos verificados antes de armar este prompt

Estado HEAD (`196c472`):
- 54 497 LOC totales, working tree limpio.
- 65 compound tools intactas.
- Tests preexistentes pasan; 1 falla pre-existente (no regresión).

Targets confirmados vivos en HEAD:
- `gemma4_agent/ui/agent_thread.py:35` clase `AgentWorker` (220 LOC).
- `gemma4_agent/agent_runner.py:72` clase `AgentRunner` (552 LOC archivo).
- `gemma4_agent/ui/main_window.py:81` clase anidada `ServerBootWorker`.
- `gemma4_agent/tools.py:176` función `_redact_sensitive`.
- `gemma4_agent/domain_tools.py:50` función `_redact_credentials`
  (con comentario auto-confesando duplicación).
- `gemma4_agent/tools.py:3922` y `gemma4_agent/domain_tools.py:68`:
  doble `_hard_gate`.
- `gemma4_agent/tracing.py` 67 LOC (`TraceLogger`).
- `gemma4_agent/timeline.py` 137 LOC (`TimelineWriter`).
- `gemma4_agent/log_recorder.py` 220 LOC (canónico).
- `gemma4_agent/domain_tools.py` 10 539 LOC con 17 imports
  top-level pesados.

Sprint 4 ataca SOLO estas duplicaciones estructurales. **NO toca
tools, NO toca god classes (`ToolRegistry` y `Gemma4Agent` quedan
para Sprint 5), NO toca personas/microagents/skills**.

---

## Prompt completo (copy/paste al chat existente)

```
Continuamos. Estado: rama PortandoLoMejor, HEAD en 196c472, working
tree limpio, 54 497 LOC, 65 compound tools intactas. El reporte de
uso de Sprint 2 está en _sprint2_usage_report.md (no muta este
sprint pero da contexto).

# OBJETIVO DE SPRINT 4

Eliminar duplicaciones estructurales auto-confesadas en el código.
Cada cambio debe ser comportamiento-invariante (nada que el usuario
note). NO se borran tools, NO se splittean god classes, NO se eliminan
features que dependan de datos de uso.

# REGLAS GENERALES (mismas que sprints anteriores)

1. Trabajás en PortandoLoMejor. Commits chicos por tarea, prefijo
   "sprint4: <tarea>". NO push, NO toques main.
2. Después de cada commit: `python -c "import gemma4_agent"` Y
   `python -m gemma4_agent.launcher status 2>&1 | head -5`. Si rompe:
   git reset --hard HEAD~1, anotá blocker en
   docs/architecture/sprint_prompts/_sprint4_log.md, seguís.
3. Después de cambios que tocan código de la pila ToolRegistry, agent,
   experience: corré tests que cubran lo afectado, e.g.:
     - `python -m pytest gemma4_agent/test_tool_dispatch_contract.py -q`
     - `python -m pytest gemma4_agent/test_session847_fixes.py -q`
     - `python -m pytest gemma4_agent/test_log_audit_fixes.py -q`
   Si un test ROMPE por la refactor: leelo, evaluá si es ajuste de
   prueba legítimo (importar el nuevo path) o si rompiste contrato.
   En duda: reset + SKIP la tarea.
4. NO instales deps nuevas. NO ejecutes el agente real ni
   llama-server.
5. NO toques: voice/, mission_goal.py, mission_outcome.py,
   verifiers.py, verify_core.py, personas.py, microagents.py,
   skills_registry.py, tools.py:COMPOUND_TOOL_SCHEMAS.
6. NO modifiques data/, ~/.gemma4/, captures/, logs/, models/.
7. NO toques traces.jsonl ni borres sinks ya escritos en disco.
8. Stash @{0} restante NO LO TOQUES.

# CONTEXTO TÉCNICO (referencias al audit)

- `docs/architecture/08_findings.md §2.1` — AgentWorker/AgentRunner/
  ServerBootWorker triple duplicación.
- `docs/architecture/08_findings.md §2.2` — funciones duplicadas
  `_redact_*` / `_hard_gate`.
- `docs/architecture/08_findings.md §2.5` — 4 sinks redundantes
  (TraceLogger + LogRecorder/full + LogRecorder/chat + Timeline +
  Telemetry opt-in).
- `docs/architecture/08_findings.md §1.4` — domain_tools.py deps
  pesadas top-level.

# WORKFLOW

Hay 5 tareas. Ordenadas por riesgo creciente y por dependencias
(las tempranas no rompen las tardías).

## 4.1 — Unificar `_redact_sensitive` ↔ `_redact_credentials`

Justificación (audit §2.2): comentario en `domain_tools.py:51` dice
literalmente "CC-105: paralelo a tools._redact_sensitive". Es decir,
el autor sabía que estaba duplicando y lo dejó así para evitar
import circular. Lo arreglamos.

Estrategia: crear `gemma4_agent/_shared.py` (nuevo módulo de
helpers comunes que NO importa nada del paquete), mover la función
ahí, y hacer que tanto `tools.py` como `domain_tools.py` la importen.

Pasos:

  1. Leé `gemma4_agent/tools.py:176-205` (`_redact_sensitive` y su
     constante `_SENSITIVE_KEY_RX`).
  2. Leé `gemma4_agent/domain_tools.py:47-65` (`_redact_credentials`
     y su `_SENSITIVE_KEY_RX`).
  3. Verificá que las DOS funciones son equivalentes (regex idéntico,
     mismo depth limit, mismo branching). Si difieren en algún
     detalle, anotalo en `_sprint4_log.md` y unificá conservando la
     UNIÓN de comportamientos (e.g. si una tiene más keywords,
     consolidalas).
  4. Creá `gemma4_agent/_shared.py` con:
     - `_SENSITIVE_KEY_RX` (regex compilado, copia de la versión
       conservada).
     - `redact_sensitive(value: Any, depth: int = 0) -> Any` (nombre
       canonical — sin guión bajo inicial; ahora es API pública del
       módulo `_shared`).
     - Docstring breve explicando el propósito (mask de credenciales
       en logs/state).
     - NO importa nada de gemma4_agent — es código puro stdlib.
  5. En `tools.py`:
     - Reemplazar `_SENSITIVE_KEY_RX` y `_redact_sensitive` por
       `from ._shared import redact_sensitive as _redact_sensitive`
       (el alias preserva nombre interno).
     - Verificá que los 4 call sites siguen funcionando.
  6. En `domain_tools.py`:
     - Reemplazar `_SENSITIVE_KEY_RX` y `_redact_credentials` por
       `from ._shared import redact_sensitive as _redact_credentials`.
     - Verificá callers.
  7. Test: `python -m pytest gemma4_agent/test_log_audit_fixes.py -q`
     debe pasar (cubre redaction).
  8. Verificá imports + launcher status.

  Commit: "sprint4: unify _redact_sensitive ≡ _redact_credentials into
  gemma4_agent/_shared.redact_sensitive (audit §2.2)"

## 4.2 — Unificar `_hard_gate` dual

Justificación: misma razón que 4.1. Comentario en `domain_tools.py:68`
admite "CC-101: gate duro replicable desde domain_tools (sin
ToolRegistry)".

Pasos:

  1. Leé `gemma4_agent/tools.py:3922-3990` (`ToolRegistry._hard_gate`
     método). Es método de clase — toma `self.state` implícitamente.
  2. Leé `gemma4_agent/domain_tools.py:68-92` (`_hard_gate` función
     top-level — toma `state: AgentState` explícito).
  3. La versión de `domain_tools.py` es la **más portable** (función
     pura, recibe state como parámetro). Esa es la canonical.
  4. Si las firmas/comportamientos coinciden:
     - Mover la versión de domain_tools.py a
       `gemma4_agent/_shared.py` (ya creado en 4.1) o a un
       `gemma4_agent/safety_gates.py` nuevo si preferís namespace
       claro.
     - El método `ToolRegistry._hard_gate` se vuelve un wrapper
       de 3 líneas que llama al helper compartido pasándole
       `self.state`.
  5. Si las firmas/comportamientos DIFIEREN:
     - Documentá la diferencia en `_sprint4_log.md`.
     - Si la diferencia es menor (e.g. param adicional opcional),
       unificá agregándolo como kwarg con default.
     - Si la diferencia es fundamental: SKIP la tarea, dejar para
       Sprint 5.
  6. Test relevante:
     - `python -m pytest gemma4_agent/test_tool_dispatch_contract.py -q`
     - `python -m pytest gemma4_agent/test_session847_fixes.py -q`
     - `python -m pytest gemma4_agent/test_inherit_tools_safety.py -q`
  7. Verificá imports + launcher status.

  Commit: "sprint4: unify dual _hard_gate (tools.py ToolRegistry
  method + domain_tools.py top-level fn) into shared helper (audit §2.2)"

## 4.3 — Colapsar `AgentWorker` ≡ `AgentRunner` ≡ `ServerBootWorker`

⚠ TAREA DE MAYOR RIESGO DE ESTE SPRINT. Si tenés dudas durante la
implementación, parcializá: hacé 4.3.a (la base + AgentRunner como
primer adapter) en un commit, 4.3.b (AgentWorker como segundo
adapter) en otro, 4.3.c (ServerBootWorker) en un tercero.

Justificación (audit §2.1, ya verificado en Fase 3 atributo por
atributo):
- AgentWorker (PyQt QThread, 220 LOC) y AgentRunner (threading +
  queue + singleton, 552 LOC) tienen mismos atributos privados
  (`_inbox: Queue`, `_agent`, `_stop_event`, `_thread`,
  `_running`), mismos métodos públicos (`submit`, `stop`,
  `_build_agent`, `_run`), misma responsabilidad: serializar
  requests a Gemma4Agent sync.
- ServerBootWorker (anidado en ui/main_window.py:81, ~100 LOC)
  duplica la lógica de _autostart_llama_server de agent_runner.

Diseño objetivo:

```
gemma4_agent/agent_serial.py        # nuevo módulo, ~280 LOC
├── class AgentSerialWorker:        # lógica común
│   ├── _inbox: queue.Queue
│   ├── _stop_event: threading.Event
│   ├── _running: bool
│   ├── _agent: Gemma4Agent | None
│   ├── _build_lock: threading.Lock
│   ├── _warmed_up: bool
│   ├── _server_manager: LlamaServerManager | None
│   ├── submit(text, images, audios)
│   ├── stop()
│   ├── restart()
│   ├── is_warmed_up() -> bool
│   ├── _build_agent()           # incluye autostart llama-server
│   ├── _autostart_llama_server()
│   ├── _progress_forwarder()    # callback hookeable
│   └── _run()                   # worker loop
└── reporters: callables que vienen por inyección
              (1 para state changes, 1 para activity, 1 para errors)
```

Adapters delgados:

```
gemma4_agent/agent_runner.py        # ahora ~80 LOC vs 552
└── class AgentRunner(AgentSerialWorker):
    def __init__(self):
        super().__init__(
            on_state=lambda s: BUS.publish({"type":"state","value":s}),
            on_activity=lambda src, msg: BUS.publish({...}),
            on_error=lambda e: BUS.publish({...}),
        )
RUNNER = AgentRunner()  # singleton conservado

gemma4_agent/ui/agent_thread.py     # ahora ~70 LOC vs 220
└── class AgentWorker(QThread):
    state_changed = pyqtSignal(str)
    log = pyqtSignal(str, str)
    reply_ready = pyqtSignal(str, list)
    # ... otras pyqtSignals igual que antes

    def __init__(self, parent=None):
        super().__init__(parent)
        self._impl = AgentSerialWorker(
            on_state=lambda s: self.state_changed.emit(s),
            on_activity=lambda src, msg: self.log.emit(msg, src.lower()),
            on_error=lambda e: self.llm_error.emit(str(e)),
        )

    def run(self):  # QThread entry
        self._impl._run()

    def submit(self, text, **kw):
        self._impl.submit(text, **kw)

    def stop(self):
        self._impl.stop()
```

ServerBootWorker (boot-only) — eliminar la clase anidada y reemplazar
sus callers por una llamada a `AgentSerialWorker._autostart_llama_server`
ejecutada en un thread daemon. Si la clase tiene state propio que
el caller (MainWindow) necesita, conservá una pyqtSignal de progreso
emitida por la closure.

Pasos:

  1. **Pre-flight:** leé los 3 archivos enteros. Mapa de atributos
     en `_sprint4_log.md`. Detectar cualquier divergencia real (no
     solo cosmética) entre `AgentRunner._build_agent` y
     `AgentWorker._build_agent`.
  2. **Crear** `gemma4_agent/agent_serial.py` con la clase base.
     Migrar la lógica de `AgentRunner._build_agent` (más completa,
     incluye prewarm + autostart + vision_relaunch callback wiring).
  3. **Migrar AgentRunner** a heredar de AgentSerialWorker. Conservar
     el módulo-level `RUNNER` singleton. Conservar API pública:
     `RUNNER.submit/stop/start/restart/is_warmed_up/agent_ready`.
  4. **Verificar**: `python -m gemma4_agent.launcher status` →
     `python -c "from gemma4_agent.agent_runner import RUNNER; print(type(RUNNER))"` →
     `python -m pytest gemma4_agent/test_session847_fixes.py -q`.
  5. **Commit 4.3.a:** "sprint4: extract AgentSerialWorker base
     class + migrate AgentRunner (audit §2.1, part 1/3)".
  6. **Migrar AgentWorker** a usar composición con AgentSerialWorker
     interno + adaptación a pyqtSignals.
     - Conservar las 7 pyqtSignals existentes (state_changed,
       progress, log, reply_ready, llm_error, connection_changed,
       health_status).
     - Conservar API pública: `submit/stop/get_agent/get_config`.
  7. **Verificar:** PyQt6 UI debería importar sin error.
     `python -c "from gemma4_agent.ui.agent_thread import AgentWorker; print('OK')"`.
  8. **Commit 4.3.b:** "sprint4: migrate AgentWorker to compose
     AgentSerialWorker + pyqtSignals adapter (audit §2.1, part 2/3)".
  9. **Eliminar ServerBootWorker** anidado en ui/main_window.py.
     Reemplazar por llamada directa a la función de boot en
     `agent_serial`, ejecutada en un thread daemon con callback que
     emite pyqtSignal de progreso.
  10. **Verificar** import de main_window.py.
  11. **Commit 4.3.c:** "sprint4: remove ServerBootWorker, delegate
      boot to AgentSerialWorker (audit §2.1, part 3/3)".

LOC esperadas eliminadas: 220 + 552 + 100 = 872 borradas. Nuevo
módulo agent_serial.py ~280 LOC. Adapters AgentRunner ~80 +
AgentWorker ~70 + delete ServerBootWorker. Net: **~440 LOC menos**.

## 4.4 — Eliminar TraceLogger + Timeline (4 sinks → 2)

Justificación (audit §2.4 + §2.5): TraceLogger (67 LOC) y
LogRecorder/full.log persisten información cuasi-equivalente. Timeline
(137 LOC) es un 4to sink que se descubrió en Fase 5 sin propósito
ortogonal claro. Quedan vivos: LogRecorder (canónico) y Telemetry
(opt-in para métricas numéricas).

⚠ ANTES DE ELIMINAR: verificar que LogRecorder/full.log captura
TODO lo que TraceLogger escribía. Si TraceLogger emite un kind de
evento que LogRecorder NO escucha, hay que asegurar que el caller
publique al BUS antes (que es donde LogRecorder escucha).

Pasos:

  1. **Pre-flight:** mapear callers de TraceLogger y Timeline.
     - `grep -rn "TraceLogger\|self.trace\|trace.event" gemma4_agent/`
     - `grep -rn "TimelineWriter\|timeline\." gemma4_agent/`
     - El uso más fuerte de `TraceLogger` es `Gemma4Agent.trace`
       (atributo de instancia).
  2. **Estrategia:** migrar `self.trace.event(turn_id, kind,
     **payload)` a `BUS.publish({"type": "trace", "turn_id":
     turn_id, "kind": kind, **payload})` y que LogRecorder lo
     capture en `full.log`. La conversión es mecánica.
  3. Eliminar:
     - `gemma4_agent/tracing.py` entero (`TraceLogger`,
       `summarize_content`, `_json_safe`).
     - `gemma4_agent/timeline.py` entero (`TimelineWriter`).
     - `agent.py`: el atributo `self.trace = TraceLogger(...)` en
       `Gemma4Agent.__init__`. Los call sites
       `self.trace.event(...)` se migran a
       `BUS.publish({"type":"trace", ...})`.
     - `agent_runner.py` / `voice_runner.py` / etc: revisar y
       migrar.
     - Tests: si hay `test_tracing.py` o tests que importan
       TraceLogger, ajustarlos o eliminarlos.
  4. **Mantener** `gemma4_agent/data/traces.jsonl` en disco:
     LogRecorder ya escribe a `~/.gemma4/logs/<sid>/full.log` que es
     el reemplazo natural. NO borres el archivo histórico, pero el
     código deja de escribir ahí. Anotalo en log.
  5. Si el script `scripts/analyze_traces.py` lee de
     `gemma4_agent/data/traces.jsonl`: actualizar para que lea de
     `~/.gemma4/logs/*/full.log` (lo cual es mejor — agrega por
     sesión).
     SI la actualización del script es no-trivial: SKIP por ahora,
     anotalo en log y dejá el script apuntando al archivo viejo.
     Sprint 5 lo ajusta.
  6. **Verificar:** import + launcher status + tests que toquen
     tracing.
  7. Commit: "sprint4: eliminate TraceLogger + Timeline; migrate to
     LogRecorder via BUS (audit §2.4-2.5)".

LOC esperadas eliminadas: 67 + 137 = 204 + cualquier call site
ahorrado en agent.py. Net: **~250-300 LOC**.

## 4.5 — Lazy imports en `domain_tools.py`

Justificación (audit §1.4 CRITICAL): el módulo carga 17 imports
top-level pesados (PIL, bs4, fitz, pdfplumber, pdf2image, pypdf,
matplotlib, pandas, openpyxl, paho, mysql, psycopg, psycopg2,
pymysql, docx, pptx). Cualquier proceso que importe
`gemma4_agent.tools` paga el boot completo.

⚠ Esta tarea cambia el tiempo de import en producción. Si rompe,
es por dependencias circulares o por imports usados a nivel módulo
(no dentro de funciones).

Pasos:

  1. **Leé el bloque de imports** de `gemma4_agent/domain_tools.py`
     (líneas 1-30 aprox).
  2. **Para cada import pesado**, identificar:
     - ¿Se usa a nivel módulo (top-level)? Si sí, NO lo muevas —
       hay alguna decisión de diseño detrás.
     - ¿Se usa solo dentro de una función específica? Si sí,
       moverlo dentro de esa función como lazy import.
  3. **Patrón canonical** para cada lazy:
     ```python
     def some_tool(state, args):
         import pandas as pd   # lazy: only loaded when this tool runs
         # ... rest of function
     ```
  4. Imports a mover (probables):
     - PIL → `image_*_tool`, `photo_library_tool`
     - bs4 → web parsing functions
     - fitz / pdfplumber / pdf2image / pypdf → `document_tool` PDF
       paths
     - matplotlib → `data_analysis_tool` plotting
     - pandas / openpyxl → `data_analysis_tool` /
       `office_tool`
     - paho.mqtt → `smart_home_tool`
     - mysql / psycopg / psycopg2 / pymysql → `database_tool`
     - docx → `office_tool` / `document_tool` Word
     - pptx → `office_tool` PowerPoint
  5. Conservá top-level los imports STDLIB (`re`, `os`, `pathlib`,
     etc) y los livianos (`_ps` que es del paquete mismo).
  6. **Verificación cuantitativa:** medí tiempo de import antes y
     después:
     ```
     python -c "import time; t=time.time(); import gemma4_agent.tools; print(f'tools import: {time.time()-t:.2f}s')"
     ```
     Esperado: bajada significativa (de varios segundos a sub-segundo
     o ~1s). Anotalo en `_sprint4_log.md`.
  7. **Tests:** correr `python -m pytest gemma4_agent/test_*.py -q
     -k "tools or domain"` (sin garantía de que todos pasen — si
     fallaba uno preexistente, sigue fallando).
  8. Commit: "sprint4: lazy-load heavy deps in domain_tools.py
     (audit §1.4 CRITICAL)".

LOC esperadas: ~+30 (movimiento de imports + algún boilerplate),
pero el VALOR es latencia de import (no LOC).

## 4.6 — Reporting

Escribí `docs/architecture/sprint_prompts/_sprint4_log.md`:

- Timestamp inicio/fin.
- Tareas hechas con SHA + LOC delta + verificaciones (tests pasaron,
  launcher status OK).
- Tareas SKIPPED con razón explícita (probable: alguna sub-tarea de
  4.3 si la divergencia entre AgentRunner y AgentWorker fue
  fundamental, o 4.5 si los imports estaban más entangled).
- Tiempo de import de `gemma4_agent.tools` antes vs después de 4.5.
- LOC delta total: `git diff --shortstat 196c472..HEAD`.
- Estado final: `git log --oneline -15` + `git status`.
- Headline: "Sprint 4: structural duplication removed. ~XXX LOC.
  Tools intactas (65). Tests pasan. agent_serial.py created, 3
  workers collapsed, TraceLogger + Timeline removed, domain_tools
  imports lazy."

Commit: "sprint4: write log".

# VERIFICACIONES OBLIGATORIAS DESPUÉS DEL SPRINT

```bash
# 1. Import básico
python -c "import gemma4_agent"

# 2. Conteo de tools intactas
python -c "from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"
# Esperado: 65

# 3. Launcher status (sirve para validar config + import chain)
python -m gemma4_agent.launcher status 2>&1 | head -10

# 4. Tiempo de import (objetivo de 4.5)
python -c "import time; t=time.time(); import gemma4_agent.tools; print(f'{time.time()-t:.3f}s')"

# 5. Tests del paquete tocados por refactor
python -m pytest gemma4_agent/test_tool_dispatch_contract.py \
                gemma4_agent/test_session847_fixes.py \
                gemma4_agent/test_log_audit_fixes.py \
                gemma4_agent/test_inherit_tools_safety.py \
                -q
```

# QUÉ NO HAGAS (recap)

- NO borres compound tools.
- NO toques mission_goal.py, mission_outcome.py, verifiers.py,
  verify_core.py, personas.py, microagents.py, skills_registry.py,
  voice/.
- NO splittees ToolRegistry ni Gemma4Agent (es Sprint 5).
- NO modifiques `COMPOUND_TOOL_SCHEMAS`.
- NO cambies API pública de AgentWorker / AgentRunner (las
  superficies — chat.py, ui/, server.py — siguen funcionando con
  los mismos métodos: submit, stop, etc).
- NO toques traces.jsonl en disco (solo el código que lo escribe).
- NO instales deps.
- Si dudás entre "refactorizar" y "dejar": dejá. Anotá en log para
  Sprint 5.

Arrancá.
```

---

## Notas para vos cuando despiertes

1. **LOC esperadas removidas:** ~750-1 000 (4.1 ~30 + 4.2 ~50 + 4.3
   ~440 + 4.4 ~250).
   El gran tema NO es LOC sino **mantenibilidad**: 3 workers
   colapsados a 1 base + 2 adaptadores significa que un bug en el
   worker loop se arregla en UN solo lugar.
2. **El número clave a verificar:** `len(COMPOUND_TOOL_SCHEMAS) == 65`
   sigue siendo verdad. Si bajó, algo rompió.
3. **El otro número a verificar:** tiempo de `import gemma4_agent.tools`.
   Antes de 4.5 esperás varios segundos (deps pesadas eager). Después
   esperás <1 s. Si no bajó, los lazy imports no se aplicaron como
   se esperaba.
4. **Tarea más riesgosa:** 4.3 (workers). Si el agente la abortó o la
   splitteó, está bien — la consigna le permite hacerlo en 3 commits
   separados (4.3.a/b/c) y SKIP los que no funcionen.
5. **Sprint 3b** sigue esperando: 7-10 días con uso real para datos
   de personas/microagents/skills.
6. **Sprint 5** (god classes — `ToolRegistry` 3 157 LOC + `Gemma4Agent`
   1 852 LOC + `MainWindow` 1 430 LOC + `SettingsDialog` 1 148 LOC):
   requiere tests sólidos antes. Es el último gran sprint. Cuando
   llegues, te armo un prompt detallado por clase.
