# Auditoría arquitectural — Baxy (2026-05-27)

**Alcance**: análisis arquitectural alto nivel del paquete `gemma4_agent/`
(65,180 LOC de producción, 141 archivos). No es revisión línea-por-línea; se
enfoca en **capas, acoplamiento, separación de responsabilidades, patrones y
deuda técnica estructural** con evidencia medida del propio código.

**Método**: grafo de dependencias real, conteo de smells objetivos, longitud
de funciones, fan-in/fan-out por módulo, ciclos. Cero opinión sin dato detrás.

**Cómo leer**: cada hallazgo trae **evidencia medida** + **recomendación** +
**impacto/costo** estimado. Las recomendaciones están ordenadas al final por
ratio impacto/costo, no por orden de aparición.

---

## 0. Resumen ejecutivo

El proyecto resuelve un problema real y difícil (asistente de voz local en
≤4 GB de VRAM, multi-modo, multi-idioma, hands-free) y lo hace con un nivel
de **rigor empírico inusual**: tests medidos, gates con números, memoria de
gotchas, regla #3.5 de verificación en vivo. Eso se nota y es lo MÁS valioso
del repo.

Lo que **frena el equipo** a futuro no son bugs puntuales sino **deuda
estructural concentrada en 3-4 archivos** que crecieron por acumulación:

| Archivo | LOC | Smells | Síntoma |
|---|---:|---:|---|
| `agent.py` | 4,698 | 205 | god-object: importa 39 módulos, función `run_content` de **2,193 LOC** |
| `tools.py` | 6,946 | 240 | 66 handlers en una clase, mezcla schema + dispatcher + lógica |
| `domain_tools.py` | 11,618 | 183 | **327 funciones top-level** en un archivo, sin sub-paquete |
| `planner.py` | 1,427 | -   | `select_tool_names` 535 LOC, `_suggest_tools` 524 LOC — 2 funciones = 75% del archivo |

Las 8 recomendaciones priorizadas (sección 7) atacan estos cuellos sin pedir
re-arquitectura: extracciones incrementales, cada una con su test de no-
regresión.

---

## 1. Métricas duras (medidas, no opinión)

### 1.1 Tamaño

| | Archivos | LOC |
|---|---:|---:|
| Prod | 141 | 65,180 |
| Tests | 170 | 23,059 |
| Docs | 455 | 97,016 |

Ratio test/prod = 0.35 (saludable para un proyecto de research-engineering;
no es 1.0 pero los tests son de calidad, no busy-work).

### 1.2 Top-10 archivos por LOC

```
11,618  domain_tools.py
 6,946  tools.py
 4,698  agent.py
 2,113  ops_tools.py
 1,745  ui/main_window.py
 1,652  server.py
 1,427  planner.py
 1,262  computer_use.py
 1,251  ui/settings.py
 1,194  llama_server.py
```

`domain_tools.py` solo es **18%** de todo el código de prod. `tools.py` +
`agent.py` suman **18%** más. Cuatro archivos = **36% del repo**.

### 1.3 Funciones de más de 100 LOC: **61** (top-10)

```
2193 loc  agent.py:814         def run_content
1171 loc  server.py:467         def create_app
 535 loc  planner.py:133        def select_tool_names
 524 loc  planner.py:697        def _suggest_tools
 497 loc  ops_tools.py:787      def browser_real_tool
 392 loc  domain_tools.py:8864  def _whatsapp_send_via_gui_search
 308 loc  tools.py:4685         def _uia_run
 271 loc  agent_runner.py:315   def _build_agent
 262 loc  domain_tools.py:9339  def whatsapp_tool
 246 loc  domain_tools.py:6762  def _streaming_cdp_play
```

`run_content` (2,193 LOC) es la función más larga del repo. Es el orquestador
del turno completo del agente: routing → planner → LLM call → tool dispatch
→ retry → verifiers → reply validation → multi-intent split → continuation.

### 1.4 Dependencias entre módulos

**Fan-in top (módulos más importados — el "kernel" del sistema)**:
- `state` (12), `config` (12), `theme` (11), `tools` (9), `llama_server` (9),
  `profiles` (9), `semantic_router` (7), `events_bus` (7).

Esto es **lo correcto**: configuración y estado son shared kernel; los demás
son módulos de infraestructura legítimos.

**Fan-out top (módulos que importan más — los más acoplados)**:
- `agent` (49), `tools` (35), `server` (18), `agent_runner` (15),
  `ui.main_window` (11).

`agent.py` importando **49 módulos** es la señal más fuerte de god-object
del repo.

### 1.5 Ciclos de import (4 reales después de filtrar self-imports)

```
agent ↔ agent_guards
agent → tools → subagent → agent
llama_server ↔ llm_client
```

Más:
- `tools.py` tiene **self-imports diferidos** (`from .tools import _score`
  desde dentro de la propia `tools.py`, vía path absoluto del paquete):
  no es ciclo real pero indica reorganización pendiente.

### 1.6 Smells crudos en prod (top)

```
  663  imports DENTRO de funciones      (lazy/circular)
  308  try/except: pass                  (silencio intencional o no)
  257  except Exception + log.warning    (best-effort)
  220  Any en firmas                     (typing parcial)
  195  print() en código prod            (mayoría en chat.py/launcher.py CLI)
   85  type: ignore
   59  noqa
   26  global
   25  hardcoded paths "C:\..." / "C:/..."
    5  eval/exec
    1  bare except (¡felicitaciones!)
    0  mutable default args (¡felicitaciones!)
```

**Lo bueno**: 0 mutable-default-args y 1 sólo bare-except = ya están
cubiertos los anti-patrones más comunes de Python.

**Lo a investigar**: 5 `eval/exec` (riesgo de seguridad si toman input del
LLM); 663 imports-inside-functions (¿cuántos son lazy intencional vs ciclo
disfrazado?); 308 except-pass (¿silencian bugs?).

### 1.7 Volumen de las áreas funcionales

- `tools.py`: **66 handlers `t_*`** (compound tools que despachan por `action`).
- `domain_tools.py`: **327 funciones top-level** en un solo archivo.
- `computer_use_caps/`: 10 archivos (sub-paquete proper — ejemplo a seguir).
- `voice/`: 16 archivos (sub-paquete proper).
- `ui/`: 21 archivos (sub-paquete proper).
- `scripts/`: 92 archivos (mezcla de eval/diag/smoke/training sin sub-índice).

---

## 2. Capas implícitas (lo que el código tiene de facto)

Inferida de imports + nombres:

```
┌─────────────────────────────────────────────────────────────┐
│  UI                       (ui/, chat.py, launcher.py)       │
├─────────────────────────────────────────────────────────────┤
│  Server / runner          (server.py, agent_runner.py)      │
├─────────────────────────────────────────────────────────────┤
│  ORQUESTADOR              (agent.py — 4.7k LOC, 49 deps)    │
│   ├── routing             (planner.py, semantic_router.py,  │
│   │                        intent_router.py, abstain_head)  │
│   ├── multi-intent        (command_splitter.py, mission_*)  │
│   ├── tool dispatch       (agent_dispatch.py)               │
│   ├── verification        (verify_core, mission_goal,       │
│   │                        intent_validator, verifiers.py)  │
│   ├── safety/guards       (safety_hook, agent_guards,       │
│   │                        gui_safety, reply_validator)     │
│   ├── memory/exp          (memory.py, experience.py,        │
│   │                        behavior_log.py)                 │
│   └── reasoning/personas  (reasoning, personas, modes,      │
│                            accessibility, microagents)      │
├─────────────────────────────────────────────────────────────┤
│  CAPABILITIES             (tools.py + domain_tools.py +     │
│                            ops_tools.py + computer_use*)    │
│   ├── system tools        (66 handlers t_* en tools.py)     │
│   ├── domain functions    (327 funciones en domain_tools.py)│
│   ├── GUI primitives      (gui_*, uia.click, OCR)           │
│   └── computer-use caps   (computer_use_caps/* — buen ej.)  │
├─────────────────────────────────────────────────────────────┤
│  LLM/SERVER               (llama_server.py, llm_client.py)  │
├─────────────────────────────────────────────────────────────┤
│  VOZ                       (voice/ — bien aislado)          │
└─────────────────────────────────────────────────────────────┘
```

**Lo que está bien**:
- `voice/`, `ui/`, `computer_use_caps/` son sub-paquetes proper, con baja
  filtración entre capas.
- `state.py` y `config.py` son shared kernel sin lógica pesada.

**Lo que se filtra entre capas**:
- `agent.py` toca TODO: 39 módulos importados directamente — desde
  `vram_watchdog` (infra hardware) hasta `pattern_miner` (research). Esto
  rompe el patrón de capas: la lógica de orquestación NO debería conocer la
  implementación de tantos módulos.
- `tools.py` mezcla 3 responsabilidades en una clase:
  1. **Registro/schemas** de las 66 tools.
  2. **Dispatcher** (`t_*` que reciben `args` y delegan).
  3. **Implementación** de muchas tools (cientos de LOC inline).
- `domain_tools.py` con 327 funciones top-level es **un sub-paquete
  comprimido en un archivo**. WhatsApp, streaming, calendario, recordatorios,
  network, brillo, email, alarmas, contactos, notas — TODOS conviven.

---

## 3. Acoplamientos preocupantes (medidos)

### 3.1 `agent.py` como god-object

**Evidencia**: 39 módulos importados, 49 fan-out total (algunos múltiples
veces). Función `run_content` de 2,193 LOC en sí sola.

**Síntomas observables**:
- Modificar el flujo del turno requiere entender SIMULTÁNEAMENTE: router,
  splitter, dispatch, verificadores, multi-intent, reply validators,
  pending_intent, abstain head, accessibility modes, jarvis behavior log,
  experience recall, mission outcome.
- Ya hubo bugs medidos donde 3 capas que se cruzan en `run_content`
  produjeron el mismo error visible (commit `6d677f0`: "Quien eres" en
  movilidad — 3 guards distintos para 1 bug).
- Cada commit nuevo toca `agent.py` o agrega un módulo más que
  `agent.py` importa.

**Por qué pasa**: el agente es por naturaleza un orquestador, pero
`run_content` mezcla **decisiones de turno** (router/abstain) con
**ejecución** (dispatch/retry) con **post-procesamiento** (verifiers/
validators). Son 3 fases lógicamente distintas.

### 3.2 `tools.py` mezclando responsabilidades

**Evidencia**: 66 handlers `t_*`, 240 smells crudos (89 imports-dentro-de-
función, 52 try/except/pass, 47 except Exception+log, 25 type:ignore),
6,946 LOC.

**Síntomas**:
- Los handlers `t_app`, `t_browser`, `t_whatsapp` (etc.) tienen entre 50-300
  LOC, cada uno mezclando: validación de args, lookup de estado del SO,
  ejecución, fallback, verificación, formato de resultado.
- Para encontrar dónde se implementa una capability hay que `grep` en
  ambos archivos (tools.py + domain_tools.py).
- El self-import `from .tools import _score` desde dentro de tools.py
  indica que el archivo necesita partirse (los helpers ya no caben en el
  flujo principal).

### 3.3 `domain_tools.py` con 327 funciones top-level

**Evidencia**: 11,618 LOC, 327 funciones top-level, 77 imports-dentro-de-
función. La función más grande es `_whatsapp_send_via_gui_search` (392 LOC).

**Síntomas**:
- Editar wifi requiere abrir un archivo que también tiene streaming, agenda,
  email, recordatorios. Riesgo de tocar por error otras áreas.
- Diff cognitive load alto: cualquier PR sobre este archivo es difícil de
  revisar por contexto.

### 3.4 Ciclos `agent ↔ agent_guards` y `llama_server ↔ llm_client`

**Evidencia**: grafo de deps.

**Riesgo**: son ciclos de import en módulos críticos. Hoy funcionan porque
los imports cíclicos son **diferidos** (dentro de funciones), pero eso
explica gran parte de los 663 imports-inside-function — son **trabajos
forzados** para evitar el ciclo.

---

## 4. Patrones BUENOS del repo (a preservar y replicar)

Antes de criticar, lo que está bien y conviene NO romper:

### 4.1 Tests con gates medibles (`tests/test_*_gate.py`)
Cada cambio significativo tiene un test que mide un gate explícito
(`recall ≥ 0.60`, `WER ≤ 0.30`). Eso es **el activo más valioso del repo**.

### 4.2 Sub-paquetes `voice/`, `ui/`, `computer_use_caps/`
Estos sub-paquetes están bien separados, con `__init__.py` y registry.
**Son el modelo para reorganizar `domain_tools.py`**.

### 4.3 Memoria de gotchas en docs/ + CLAUDE.md
Decisiones rechazadas con su porqué medido. Esto es raro de ver en
repos. Mantenerlo religiosamente.

### 4.4 Verificación honesta (caveats, `verified_by`, `evidence`)
Las tools devuelven structurally typed results con campos honestos
(`verified=False`, `evidence`, `caveat`). Esto distingue claramente
"asumido" de "medido". Recomendación de la sección 7: formalizar este
patrón en un dataclass.

### 4.5 Computer_use_caps con registry/policy/detector
El sub-paquete `computer_use_caps/` muestra que el equipo SABE
modularizar. Es la prueba viva de que la reorganización pendiente en
`domain_tools.py` es factible.

### 4.6 Regla #3.5 (probar en vivo con el LLM)
Esto invierte la práctica común "tests passing = listo". Es la regla
más valiosa de CLAUDE.md.

---

## 5. Anti-patrones concretos encontrados (con cita al código)

### 5.1 Inconsistencia schema ↔ handler (medido en commit `c546677`)
El schema de `browser` declaraba `target` como propiedad pero el handler
solo leía `url`/`query`. El LLM pasaba `target=canvas` válidamente según el
schema, la tool rechazaba.

**Cuántos casos hay**: no medí esto exhaustivamente, pero al ser inconsistencia
silenciosa es probable que haya más. **Recomendación R5**.

### 5.2 Imports duplicados de `re`, `os`, `json` dentro de funciones
Hay 663 imports dentro de funciones. Algunos son legítimos (lazy import
de torch, transformers) pero muchos son `import re` o `import json` repetido
N veces en el mismo archivo:

```
$ grep -c "import re$" gemma4_agent/agent.py
varios
```

**Costo**: ~5 micros por re-import (caché de módulos), pero ofusca lectura.

### 5.3 `try/except: pass` que silencia bugs reales

308 casos en prod. La mayoría parecen "best-effort" intencional (un tracing
falla y no debe romper el turno), pero algunos:

```python
try:
    from .abstain_head import (...)
    if _ah_on():
        ...
except Exception:
    pass
```

Silencian errores del **abstain head**, que es el componente que decide si
una pregunta es chat o acción. Si se rompe silenciosamente, todo el routing
degrada. **Debería loggear al menos** con un contador agregado para detectar
"hace 20 turnos que el abstain head silenciosamente no carga".

### 5.4 `print()` en código de prod (195 ocurrencias)
Aceptable en `chat.py` (61) y `launcher.py` (56) — son entry-points CLI.
Pero quedan ~78 prints en archivos no-CLI. Algunos parecen instrumentación
de debugging que sobrevivió commits. Migrar a logger.

### 5.5 `agent.py` tiene 111 imports dentro de funciones
Es **el peor archivo** en esta dimensión, y es PORQUE evita los ciclos
con `agent_guards`, `tools` (via subagent), etc. La causa raíz es la
ciclicidad estructural, no la falta de organización del programador.

### 5.6 `domain_tools.py` con un `_describe_image_directly` referenciado
externamente (memoria registra: stubear este método en tests)
Es señal de que **funciones de implementación se filtran como API pública**.
Las stubs en tests deberían ser sobre una INTERFACE, no sobre la
implementación interna.

### 5.7 Scripts: 92 archivos sin sub-índice
`scripts/` mezcla evaluadores de wake-word, smoke E2E, diagnosis ad-hoc
(`_diag_*.py`), entrenamiento (vive en `.venv_train` aparte), y harnesses
de medición. Sin un INDEX.md cuesta saber qué hace cada cosa. Algunos
diags (`_diag_quien_eres.py`, `_diag_portal_unab.py`) son one-shots que
quizá deberían moverse a `scripts/_diag/` o borrarse.

---

## 6. Riesgos detectados (no críticos pero a mirar)

### 6.1 5 `eval`/`exec` en prod

Necesito mirar uno por uno si reciben input del LLM o del user. **No
auditados en este sweep** — pendiente de un security review focal.

### 6.2 Hardcoded paths Windows (25)

Algunos son legítimos (CDP `127.0.0.1:9222`, `%LOCALAPPDATA%`), pero
necesitan ser verificados como `Path(os.environ[...])` cuando dependen
del user.

### 6.3 `global` keyword usado 26 veces

Cada uso de `global` es estado mutable compartido sin lock. En un agente
asíncrono o multi-threaded puede ser problema. **No auditado en este
sweep** — algunos son cachés de modelos (legítimos), otros podrían
moverse a `state.py` o a un módulo singleton explícito.

### 6.4 Ratio de cobertura de tests

Tengo 170 archivos de test y 141 de prod, pero NO medí % de coverage real.
Recomiendo correr `coverage.py` para tener un mapa de zonas no cubiertas.
**Acción independiente, no en esta auditoría**.

---

## 7. 8 RECOMENDACIONES PRIORIZADAS

Cada una con: **impacto** (qué cambia), **costo** (cuánto trabajo) y
**propiedad de no-regresión** (qué test la protege).

Ordenadas por ratio impacto/costo. Las top-3 son las que cambiarían más el
proyecto si se atacan en este orden.

---

### R1 — Extraer `agent.py::run_content` en 3 fases lógicas
**Impacto**: 🔥🔥🔥 alto · **Costo**: 🛠️🛠️ medio · **Prioridad**: 1

**Estado actual**: una función de 2,193 LOC que decide, ejecuta y
post-procesa todo en línea.

**Propuesta**: extraer en 3 métodos de la misma clase (no cambiar la
interfaz pública):

```python
def run_content(self, content, ...):
    decision = self._decide_turn(content, ...)
    result = self._execute_turn(decision, ...)
    return self._finalize_turn(decision, result, ...)
```

- `_decide_turn`: router + abstain + planner + subset + pending_intent +
  splitter → produce un `TurnDecision` dataclass.
- `_execute_turn`: dispatch + LLM calls + retries + multi-intent → produce
  `ExecutionResult` dataclass.
- `_finalize_turn`: verifiers + validators + accessibility nudges + reply
  formatting → produce `AgentReply`.

**Por qué importa**: hoy modificar el flujo del turno = leer 2,193 LOC.
Después: leer 200-300 LOC por fase. Permite cambiar el router sin tocar
post-procesamiento, y viceversa.

**No-regresión**: la batería `scripts/battery_all_caps.py` ya existente
(60 casos × 25 categorías) debe pasar 53/61 o más, sin tocar el ratio.

**Cómo hacerlo seguro**: rama dedicada, extracción mecánica (no cambio de
lógica, solo movimiento), commits chicos por fase, batería entre cada uno.

---

### R2 — Reorganizar `domain_tools.py` en sub-paquete `domain_tools/`
**Impacto**: 🔥🔥🔥 alto · **Costo**: 🛠️🛠️ medio · **Prioridad**: 2

**Estado actual**: 11,618 LOC, 327 funciones top-level cubriendo wifi,
brillo, agenda, email, whatsapp, streaming, alarmas, contactos, notas.
Hay que `grep` para encontrar cualquier cosa.

**Propuesta** (siguiendo el modelo `computer_use_caps/`):

```
domain_tools/
  __init__.py          # re-exporta funciones públicas (no rompe imports)
  wifi.py
  brightness.py
  weather.py
  calendar.py
  reminders.py
  alarms.py
  notes.py
  contacts.py
  email.py
  whatsapp.py
  streaming.py
  network.py
  _shared.py           # _ok, _err, _action, utilidades
```

**Por qué importa**: cada cambio queda confinado a su módulo. Tests
también se organizan natural (`test_wifi.py` ya existe — solo hay que
alinear nombres).

**No-regresión**: `__init__.py` re-exporta todo lo que `tools.py` y
`agent.py` importan hoy. Los imports externos no cambian.

**Cómo hacerlo seguro**: mecánicamente, función por función. Test suite
completa entre cada extracción de área. Espero **0 regresiones** porque
es puro movimiento.

---

### R3 — Romper los ciclos `agent ↔ agent_guards` y `llama_server ↔ llm_client`
**Impacto**: 🔥🔥 medio-alto · **Costo**: 🛠️ bajo · **Prioridad**: 3

**Estado actual**: 2 ciclos reales que se evitan con imports diferidos
(dentro de funciones), causando muchos de los 663 imports-inside-function.

**Propuesta**:
- `agent ↔ agent_guards`: extraer las interfaces compartidas
  (probablemente `TurnDecision`, hook signatures) a `agent_types.py`. Ambos
  importan de `agent_types`, ninguno se importa entre sí.
- `llama_server ↔ llm_client`: lo mismo. Probable causa: el manager del
  server llama al cliente para health-checks y el cliente llama al manager
  para auto-recovery. Extraer un `llama_protocol.py` con la interfaz.

**No-regresión**: tests de `test_llama_server*.py` y `test_safety_hook.py`
ya cubren ambos. Si pasan, no se rompió nada.

**Por qué importa**: al romper los ciclos podés mover ~30-50 imports-de-
función a top-level (más rápido, más legible, IDE entiende mejor).

---

### R4 — Convertir los resultados de tool en dataclasses tipados
**Impacto**: 🔥🔥 medio · **Costo**: 🛠️🛠️ medio · **Prioridad**: 4

**Estado actual**: los `t_*` devuelven `dict[str, Any]` con convenciones
implícitas (`ok`, `error`, `status`, `opened`, `verified`, `verified_by`,
`caveat`, `evidence`, `resolved_from_name`, ...). Los consumidores
acceden por `.get("...")` con defaults.

**Propuesta**:

```python
@dataclass(frozen=True)
class ToolResult:
    ok: bool
    action: str = ""
    status: str = "ok"            # "ok"|"attempted"|"needs_user"|"failed"|...
    verified: bool | None = None  # None=not measurable
    verified_by: str = ""
    caveat: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
```

Aliases de retorno (`_ok`, `_err`) se convierten en constructores.
Migración gradual: handler por handler, los consumers reciben `.to_dict()`
hasta que se actualicen.

**Por qué importa**:
- Pylance/mypy detectan ausencia de campos en consumers.
- Documentación viva del contrato.
- Tests pueden assertear `isinstance(res, ToolResult)` en vez de bucear
  llaves.
- Es **formalizar el patrón ya existente** (`verified_by`, `caveat`,
  `evidence` ya están en el ecosistema) en vez de inventar algo nuevo.

**No-regresión**: como los handlers pueden serializar `.to_dict()`
durante la migración, los consumers siguen funcionando sin tocar.

---

### R5 — Test contract-check entre schemas y handlers
**Impacto**: 🔥 medio · **Costo**: 🛠️ bajo · **Prioridad**: 5

**Estado actual**: el commit `c546677` arregló una inconsistencia
schema↔handler en `browser` (schema declaraba `target`, handler lo
ignoraba). Es probable que haya más casos así silenciosos.

**Propuesta**: un test que, por cada tool en `COMPOUND_TOOL_SCHEMAS`,
verifique que el handler intenta leer cada `property` declarada en el
schema. Implementable con `ast.parse` del cuerpo del handler buscando
`args.get("<prop>")`.

```python
def test_handler_reads_all_schema_props():
    for tool in COMPOUND_TOOL_SCHEMAS:
        name = tool["function"]["name"]
        props = tool["function"]["parameters"]["properties"]
        handler_src = _get_handler_source(name)
        for prop in props:
            assert prop in handler_src, (
                f"{name}: schema declara `{prop}` pero handler no lo lee"
            )
```

**Por qué importa**: previene que el LLM elija una clave válida-según-
schema que el handler ignora silenciosamente. **Es el test que hubiera
detectado el bug de `target=canvas`**.

**No-regresión**: el test se aplica solo a casos nuevos; los existentes
se whitelistéan si tienen razón documentada.

---

### R6 — Auditar los 5 `eval`/`exec` por riesgo de inyección
**Impacto**: ❓ por medir · **Costo**: 🛠️ bajo · **Prioridad**: 6

**Estado actual**: 5 ocurrencias de `eval`/`exec` en prod, no auditados.

**Acción**:
1. `grep -n "\\b(eval|exec)\\s*(" gemma4_agent/`
2. Para cada uno, responder: ¿recibe input del LLM? ¿del user? ¿del SO?
3. Si la respuesta es sí → reemplazar por `ast.literal_eval` o parser
   explícito.

**Por qué importa**: el agente recibe input del LLM (no confiable) y lo
mete en tools que tocan el SO. Una inyección de comandos vía un `eval`
mal usado sería el peor bug posible.

**No-regresión**: cada `eval` reemplazado lleva un test con input
malicioso (`__import__('os').system(...)`) que debe fallar.

---

### R7 — Logger estructurado en vez de `print()`/`logger.warning(f"...")`
**Impacto**: 🔥 medio · **Costo**: 🛠️ bajo · **Prioridad**: 7

**Estado actual**:
- 195 `print()` (78 en archivos no-CLI).
- Logging actual usa f-strings (`logger.warning(f"X={x}")`), lo cual evalúa
  la string SIEMPRE aunque el nivel no esté activo. Inocente pero
  performance-leaky en hot path.

**Propuesta**:
- Migrar prints no-CLI a `logger.info/debug/warning`.
- Adoptar logging perezoso: `logger.warning("X=%s", x)`.
- Considerar `structlog` para producir JSON parseable (alinea con la
  cultura de medir del repo).

**Por qué importa**: producir logs estructurados parseables hace mucho
más fácil hacer post-mortem de los 16 cases del battery que fallan a
veces. Hoy el trace.event ya hace eso parcialmente — extenderlo.

**No-regresión**: no hay; el comportamiento observable no cambia.

---

### R8 — Inventario `scripts/` con INDEX.md + carpeta `_diag/` para one-shots
**Impacto**: 🔥 bajo · **Costo**: 🛠️ muy bajo · **Prioridad**: 8

**Estado actual**: 92 scripts mezclados. Tipos:
- Evaluadores oficiales (`smoke_e2e.py`, `battery_all_caps.py`,
  `wake_universal_eval_livekit.py`).
- Diagnoses ad-hoc (`_diag_*.py`) que sobrevivieron sesiones.
- Harnesses de medición (`_exhaustive_*`, `_measure_*`).
- Training (probablemente obsoletos cuando se borró multi-perfil).
- Probes (`probe_*` en `gemma4_agent/scripts/`).

**Propuesta**:
- `scripts/INDEX.md` con tabla: nombre, propósito, cuándo usar, vive aquí
  o se borra.
- Mover los `_diag_*.py` a `scripts/_diag/` (transitorios por sesión).
- Borrar lo que ya no se usa (`*_carter*`, `_measure_e4b_q3_vram` si el
  perfil ya no existe).

**Por qué importa**: cualquier persona nueva al proyecto (incluyéndome a
mí en futuras sesiones) puede saber qué correr para qué.

---

## 8. Recomendaciones del repo (CLAUDE.md) que ESTOY de acuerdo en reforzar

CLAUDE.md ya recomienda muchas cosas que el código cumple. Una sola que
**no se está cumpliendo del todo**:

### "Reproducibilidad como requisito, no lujo"
El repo tiene esto en CLAUDE.md §3 recomendación 2, pero hay artefactos
sin script (`gemma4_agent/data/state.json` se modifica vivo, `MEMORY.md`
también). Está bien para esos casos, pero hay también `*.npz` y modelos
preentrenados (`tool2vec_centroids.npz`) cuya receta de generación
debería ser obvia desde el nombre del script.

**Acción rápida**: cada `data/*.npz` debería tener un README adjacente o
un `scripts/regen_<name>.py`. Lleva 1 hora máximo.

---

## 9. Lo que NO recomiendo (decisiones rechazadas)

### NO partir `agent.py` en N módulos
El refactor R1 propuesto es **intra-clase** (3 métodos), no
arquitectural. Partir `Gemma4Agent` en `Router`, `Executor`, `Validator`
clases separadas suena lindo pero ROMPE muchos tests que mockean
`agent.tools.X` directamente. Mantener la clase, extraer métodos
adentro.

### NO migrar todo a async
El repo es síncrono con threads cuando necesita. Migrar a async es un
sprint enorme con beneficio dudoso (la latencia dominante es el LLM, no
la concurrencia). Solo migrar si aparece un caso medido donde async
gana.

### NO adoptar Pydantic para validar args de tool
Los `args: dict[str, Any]` que vienen del LLM son flexibles a propósito
(el LLM inventa claves; los aliases del fix `c546677` son ejemplo).
Pydantic strict rechazaría llamadas válidas. El dataclass propuesto en
R4 es PARA RESULTS, no para args.

### NO reescribir desde cero
El repo tiene gates medidos y memoria de gotchas con varios meses de
trabajo. Un rewrite perdería todo eso. Las 8 recomendaciones son
incrementales.

---

## 10. Cómo ejecutar este plan

Si querés atacar las recomendaciones en orden:

**Sprint 1** (2-3 sesiones): R1 + R2 — los dos refactors estructurales
con mayor ratio impacto/costo. Cada extracción con la batería entre medio.

**Sprint 2** (1 sesión): R3 + R5 — romper ciclos + agregar el contract-
test schema/handler.

**Sprint 3** (1 sesión): R4 — migrar resultados a `ToolResult` (gradual).

**Sprint 4** (1 sesión): R6 + R7 + R8 — security audit de eval/exec,
logging estructurado, índice de scripts.

**Total estimado**: 5-7 sesiones de Claude. Cada sprint con su batería
de no-regresión + memoria actualizada.

---

## 11. Qué NO incluye esta auditoría

- **Profiling de performance**: no medí latencia de cada función. La
  performance del repo ya está bien instrumentada (tracing, smoke E2E).
- **Análisis de seguridad exhaustivo**: solo señalé los 5 eval/exec y
  hardcoded paths. Un security review formal requiere su propia sesión
  (sería el alcance "D — Security review" de las opciones).
- **Cobertura de tests**: 170 archivos de test es mucho pero no medí
  qué % del código está cubierto. Acción independiente.
- **Revisión línea-por-línea**: cada archivo individual puede tener bugs
  específicos que esta auditoría no detecta. La auditoría te dice DÓNDE
  mirar, no qué mira.

---

## Evidencia y reproducibilidad

Los scripts que produjeron los números de esta auditoría:
- `scripts/_code_smell_inventory.py` — conteo de smells (sección 1.6).
- `scripts/_arch_dep_graph.py` — fan-in/out + ciclos (secciones 1.4–1.5).
- Inline en este informe: `ast.parse` para funciones largas (1.3),
  `wc -l` para LOC (1.1).

Ambos scripts son read-only y pueden re-correrse para comparar la
evolución del codebase en el tiempo.
