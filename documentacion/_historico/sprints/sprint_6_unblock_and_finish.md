# PROMPT — Sprint 6 (desbloquear y terminar el plan)

> Continúa el mismo chat de Claude Code que corrió Sprints 0+1+2+3a+4+5a+5b.
>
> **Sprint 6 es el cierre del plan.** Toma todo lo que Sprint 5b dejó
> SKIPPED por falta de red de tests, escribe la red faltante, y
> ejecuta los splits diferidos. Riesgo controlado: cada bloqueo se
> desbloquea con tests antes de tocar código.

---

## Lo que Sprint 5b dejó pendiente (cita del `_sprint5b_log.md`)

| Tarea SKIP | Por qué SKIP | Cómo desbloquear |
|---|---|---|
| 5b.2.a `_guard_*` extraction | 17 fallas pre-existentes en `test_promise_guard.py` (Stub class sin `_build_user_facing_fallback`) | Fix de 1 línea en el test, luego extraer |
| 5b.2.b compaction | dependía de 5b.2.a | sigue después de 6.2 |
| 5b.2.d agent_dispatch | dependía de 5b.2.a | sigue después de 6.2 |
| 5b.1.c dispatch pipeline | 8+ helpers privados con cycle complejo | escribir tests del pipeline antes de tocar |
| 5b.3 workers collapse | divergencia genuina, parity tests no cubren flujo interno | tests de flow interno antes de colapsar |
| 5b.4 MainWindow | 55 métodos comparten 15+ state attrs | tests de lifecycle por sub-widget |
| 5b.5 SettingsDialog | tabs comparten refs vía `self._gather()` | tests de cada tab antes de extraer |

**Además:**
- Commit `8fbf30e` arrastró WIP del working tree (`voice/app_inventory.py` nuevo +639, `voice/stt.py` +156, `test_gx_features.py` +109). **No es bug; es cosmético.** Hay que decidir si quedan en el repo o se separan en commits propios.

---

## Estado verificado del repo

- HEAD: `8106b61` (sprint5b: write log).
- Working tree limpio. 65 compound tools intactas.
- 152/152 tests pasan; 17 pre-existentes rotos en `test_promise_guard.py`.
- LOC totales: 56 381 (subió por las extractions + tests de Sprint 5a; el conteo neto del plan es −3 059 vs baseline 55 633).
- god classes pendientes: `Gemma4Agent` 2 470 LOC, `tools.py` 4 282 LOC, `ui/main_window.py` 1 430 LOC, `ui/settings.py` 1 148 LOC.

---

## Prompt completo (copy/paste al chat existente)

```
Continuamos. Estado: rama PortandoLoMejor, HEAD 8106b61, working tree
limpio, 65 compound tools intactas, 152/152 tests verde, 17 fallas
pre-existentes en test_promise_guard.py documentadas.

# OBJETIVO DE SPRINT 6

Cerrar el plan: desbloquear todas las tareas SKIPPED de Sprint 5b
escribiendo la red de tests faltante ANTES de cada refactor. Mismo
patrón GREEN → REFACTOR → GREEN que sprint 5b.

# REGLAS GENERALES

1. Trabajás en PortandoLoMejor. Commits chicos por tarea, prefijo
   "sprint6.X: <tarea>" donde X es el número de sección.
2. Workflow por refactor:
   a) Tests del componente target en VERDE (los preexistentes + los
      que vos escribís).
   b) Hacer el refactor (extract/split/move).
   c) Mismos tests en VERDE.
   d) Si rojo: reset + log + siguiente tarea.
3. Cada commit verifica:
   `python -c "import gemma4_agent; from gemma4_agent.tools import
   COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"` == 65.
   `python -m gemma4_agent.launcher status` no crash.
4. NO instales deps. NO ejecutes el agente real ni llama-server.
5. NO toques: voice/, mission_goal.py, mission_outcome.py,
   verifiers.py, verify_core.py, personas.py, microagents.py,
   skills_registry.py, traces.jsonl en disco.
6. NO toques COMPOUND_TOOL_SCHEMAS.
7. PRESERVAR API PÚBLICA. Cualquier import desde fuera del paquete
   sigue funcionando idéntico.
8. Si dudás entre splitear o dejar: dejá. Anotá en log. Es Sprint 6
   pero la regla NO desaparece.
9. **Importante (lesson learned de Sprint 5b):** usar `git add
   <archivos_específicos>`, NUNCA `git add -A` ni `git add .` para
   evitar arrastrar WIP del working tree. Si el working tree está
   sucio al arrancar una tarea, primero stash + commit chiquito de
   limpieza, después la tarea.

# WORKFLOW

7 secciones. Si una falla, las siguientes pueden seguir. La sección 1
es PRE-REQUISITO para 2, 3 y 4. La sección 5 es PRE-REQUISITO para 6.
La 7 es independiente.

## 6.1 — Fix del Stub bug en test_promise_guard.py

**Pre-flight:**
```bash
python -m pytest gemma4_agent/test_promise_guard.py -q --tb=no
```
Esperado: "17 failed, 4 passed".

**Causa raíz (ya identificada en sprint5b log):**
`test_promise_guard.py` instancia un stub así:
```python
self._stub = type("Stub", (), {"trace": _DummyTraceMixin()})()
```
y llama a `_guard_promise_without_action` con ese stub como `self`.
El guard internamente llama `self._build_user_facing_fallback(...)`,
método que el stub no tiene → `AttributeError`.

**Fix:** dotar al stub de un `_build_user_facing_fallback` mínimo.
NO es mock de comportamiento ML — sólo un retorno determinístico.
Algo así:

```python
def _stub_build_fallback(self, *, reason, rejected_reply, trace_label,
                          missing=""):
    # Determinístic, content-aware: enough to satisfy
    # _guard_promise_without_action which only checks "did the reply
    # change" (presence of promise phrases gone). Used only in tests.
    return "No alcancé a completar la acción. ¿La repetimos?"

self._stub = type("Stub", (), {
    "trace": _DummyTraceMixin(),
    "_build_user_facing_fallback": _stub_build_fallback,
})()
```

Si el guard también referencia `self._last_router_subset`,
`self._fallback_streak`, `self._last_fallback_user_text`,
`self._current_user_text` (todos atributos que el _build_user_facing_fallback
mira), agregalos al stub como defaults (`[]`, `0`, `""`, `""`).
Leer agent.py:1764-1820 para ver qué attrs lee.

**Verificación:**
```bash
python -m pytest gemma4_agent/test_promise_guard.py -q
```
Esperado: 21/21 pass (los 17 ahora verde + los 4 que ya pasaban).

**Importante:** este fix es del TEST, no del código de producción.
NO modificar agent.py ni grounding_gate.py para este fix.

Commit: "sprint6.1: fix test_promise_guard.py Stub missing
_build_user_facing_fallback (unblocks 5b.2.a)"

## 6.2 — Extraer _guard_* + helpers a agent_guards.py (era 5b.2.a)

**Pre-flight obligatorio:**
```bash
python -m pytest gemma4_agent/test_promise_guard.py \
                 gemma4_agent/test_phrase_trigger_guards.py \
                 gemma4_agent/test_inherit_tools_safety.py \
                 gemma4_agent/test_gemma4agent_contract.py -q
```
Debe ser 100% verde. Si NO: blocker → abortar.

**Targets de extracción:** 6 métodos `_guard_*` + `_build_user_facing_fallback`
de `gemma4_agent/agent.py`.

| Método | LOC aprox |
|---|--:|
| `_guard_unverified_final` | ~70 |
| `_guard_phrase_confirm` | ~45 |
| `_build_user_facing_fallback` | ~55 |
| `_guard_promise_without_action` | ~95 |
| `_guard_grounded_action_claim` | ~80 |
| `_guard_plan_status` | ~25 |

Total: ~370 LOC.

**Estrategia:** convertirlos en funciones puras que toman state
explícito (no `self`). El `Gemma4Agent` métodos quedan como
wrappers de 3 líneas:

```python
# agent.py
from .agent_guards import guard_promise_without_action

class Gemma4Agent:
    def _guard_promise_without_action(self, content, events):
        return guard_promise_without_action(
            content, events,
            trace=self.trace,
            current_user_text=getattr(self, "_current_user_text", ""),
            ...
        )
```

**Sub-tareas (1 commit por guard, lo más conservador posible):**

(6.2.a) Crear `agent_guards.py` con `_build_user_facing_fallback` PURE.
        Es la dependencia compartida que casi todos los guards usan.
        Su firma como función pura:
        ```python
        def build_user_facing_fallback(
            *,
            reason: str,
            rejected_reply: str,
            trace_label: str,
            missing: str = "",
            current_user_text: str = "",
            last_fallback_user_text: str = "",
            fallback_streak: int = 0,
            last_router_subset: list[str] = (),
            trace: TraceLogger | None = None,
        ) -> tuple[str, int, str]:  # returns (text, new_streak, new_last_text)
        ```
        El método de Gemma4Agent llama a esta función y actualiza
        sus atributos con el return.

(6.2.b) Migrar `_guard_promise_without_action`. Test:
        `test_promise_guard.py` 21/21 verde.

(6.2.c) Migrar `_guard_phrase_confirm`. Test:
        `test_phrase_trigger_guards.py` verde.

(6.2.d) Migrar `_guard_grounded_action_claim`. Test:
        cualquier test que toque grounding (post-reply hooks).

(6.2.e) Migrar `_guard_unverified_final` + `_guard_plan_status`.
        Tests preexistentes que cubrirían eso.

Verificación final: agent.py LOC baja ~370. test_gemma4agent_contract.py
sigue verde (los wrappers preservan API).

Commit: "sprint6.2: extract _guard_* methods to agent_guards.py"
(o un commit por sub-tarea si querés).

## 6.3 — Extraer compaction a agent_compaction.py (era 5b.2.b)

**Pre-flight:**
- Verificar que 6.2 está completo y verde.
- Identificar tests que cubren compaction: `test_context_overflow.py`,
  `test_gemma4agent_contract.py` parcialmente.

**Targets:**
- `Gemma4Agent._compact_completed_history`
- `Gemma4Agent._compact_active_history_for_retry`
- `Gemma4Agent._extract_facts` (LLM call para fact extraction)
- `Gemma4Agent._summarize_history_block` (LLM call para summarizar)
- Helpers top-level `_compact_live_content`, `_compact_history_content`,
  `_compact_tool_result`, `_compact_json`, `_compute_context_budget`,
  `_message_text_estimate`.

Total: ~370 LOC.

**Estrategia:** mismo patrón que 6.2. Funciones puras que toman
`history`, `config`, `llm_client` como params. Los métodos quedan
wrappers de 3 líneas.

**Sub-tareas:**
(6.3.a) Crear `agent_compaction.py` con los helpers top-level
        (`_compute_context_budget`, `_compact_json`, etc).
(6.3.b) Migrar `_compact_completed_history` y `_compact_active_history_for_retry`.
(6.3.c) Migrar `_extract_facts` y `_summarize_history_block`.

Verificación: `test_context_overflow.py` verde. agent.py LOC baja
~370.

Commit por sub-tarea.

## 6.4 — Extraer dispatch a agent_dispatch.py (era 5b.2.d)

**Pre-flight:**
- Tests `test_session847_fixes.py`, `test_thread_affine_tools.py`,
  `test_tool_dispatch_contract.py` verde.

**Targets:**
- `Gemma4Agent._execute_calls_sequential` (~86 LOC)
- `Gemma4Agent._execute_calls_parallel` (~97 LOC)

**Estrategia:** función `execute_tool_calls(tool_calls, registry,
parallel: bool, progress_cb, trace, turn_id)` con flag para los dos
modos. Los 2 métodos del agent quedan wrappers de 5 líneas.

Verificación: tests preexistentes verdes. agent.py LOC baja ~183.

Commit: "sprint6.4: extract _execute_calls_* to agent_dispatch.py"

## 6.5 — Tests para dispatch pipeline de tools.py (pre-requisito de 6.6)

**Targets a testear (lo que sprint 5b.1.c no pudo extraer):**
- `_normalize_tool_result` (helper top-level)
- `_coerce_and_validate_tool_args` (helper top-level)
- `_PRE_VALIDATORS` (dict de validators)
- `_parameters_for_tool` (helper)

Esos 4 son los componentes del pipeline `execute()` en tools.py.

**Escribir `gemma4_agent/test_tool_pipeline_helpers.py`:**

- `_normalize_tool_result`: pasarle un dict raw del handler y
  verificar que devuelve dict con keys `{ok, status, verified, tool,
  evidence}`. Casos: ok=True, ok=False, raise interno (excepción
  capturada), `completion_status='opened_*'` → status='dispatched'
  + verified=None.
- `_coerce_and_validate_tool_args`: tipos string vs int vs bool
  coercion. Argumentos faltantes (los requeridos por schema).
  Argumentos extra (deberían ignorarse silenciosamente, no fallar).
- `_PRE_VALIDATORS`: si una tool tiene pre-validator registrado,
  se ejecuta antes del handler. Su return dict reemplaza el
  resultado del handler si tiene `ok=False`.
- `_parameters_for_tool`: dado un nombre de tool, retorna el dict
  de schema.parameters. Para tool inexistente, dict vacío.

Patrón:
```python
import unittest
from gemma4_agent.tools import _normalize_tool_result, _PRE_VALIDATORS

class ToolPipelineHelpersTest(unittest.TestCase):
    def test_normalize_adds_ok_when_missing(self):
        out = _normalize_tool_result("audio", {"action": "mute"},
                                     {"status": "done"})
        self.assertIn("ok", out)
        # ... etc
```

**Verificación:** test nuevo 100% verde antes de commit.

Commit: "sprint6.5: add test_tool_pipeline_helpers.py (pre-req for 6.6)"

## 6.6 — Extraer dispatch pipeline a tool_dispatch.py (era 5b.1.c)

**Pre-flight:**
- `test_tool_pipeline_helpers.py` verde (de 6.5).
- `test_tool_dispatch_contract.py` verde.

**Estrategia:** crear `gemma4_agent/tool_dispatch.py` con las 4
piezas extraídas como funciones puras (sin self, sin estado
implícito). `ToolRegistry.execute` queda como wrapper que orquesta:

```python
# tools.py (después)
from .tool_dispatch import (
    normalize_tool_result, coerce_and_validate_tool_args,
    PRE_VALIDATORS, parameters_for_tool,
)

class ToolRegistry:
    def execute(self, name, args):
        clean_args = dict(args or {})
        for forbidden in ("_internal_safe", "routine_context", "confirmed_at_create"):
            clean_args.pop(forbidden, None)
        confirmed = bool(clean_args.pop("confirmed", False))
        impl = self._impls.get(name)
        if not impl:
            return normalize_tool_result(name, clean_args, _err(f"unknown tool: {name}"))
        clean_args, errors = coerce_and_validate_tool_args(name, clean_args)
        if errors:
            return normalize_tool_result(name, clean_args,
                _err("invalid tool arguments", validation_errors=errors,
                     expected_schema=parameters_for_tool(name)))
        validator = PRE_VALIDATORS.get(name)
        if validator is not None:
            err = validator(clean_args)
            if err is not None:
                return normalize_tool_result(name, clean_args, err)
        # safety classification stays in ToolRegistry (has state)
        if self.safety_enabled and not confirmed and name != "safety":
            decision = classify_tool_call(name, clean_args)
            if decision.requires_confirmation:
                pending = self.state.create_confirmation(...)
                return normalize_tool_result(...)
        impl_args = dict(clean_args)
        if confirmed:
            impl_args["confirmed"] = True
        try:
            result = impl(impl_args)
        except Exception as exc:
            result = _err(f"{type(exc).__name__}: {exc}")
        return normalize_tool_result(name, clean_args, result)
```

`tools.py` baja ~150 LOC (pipeline helpers movidos).

**Verificación:** test_tool_pipeline_helpers + test_tool_dispatch_contract
+ test_session847_fixes en verde.

Commit: "sprint6.6: extract dispatch pipeline helpers to tool_dispatch.py
(completes 5b.1.c)"

## 6.7 — Decisión sobre workers + MainWindow + SettingsDialog (5b.3/4/5)

Tres tareas grandes que Sprint 5b dejó SKIP por **falta de tests de
flow interno** (no de API).

**OPCIÓN A: SKIP TODAS las 3.** Recomendado. Razones:
- Workers (5b.3): Sprint 4 ya argumentó que divergen genuinamente.
  Colapsarlos requeriría tests de flujo de boot end-to-end (con
  llama-server real) que no son escribibles fácilmente.
- MainWindow (5b.4): 55 métodos con 15+ state attrs compartidos =
  diseño genuinamente acoplado, no accidentalmente god class.
  Splitear sin entender los handlers de signals romperá la UI.
- SettingsDialog (5b.5): tabs comparten `self._gather()` → split
  por tab requiere rediseñar la persistencia, no solo mover código.

Si **OPCIÓN A**: anotar las 3 como SKIP final del plan en
`_sprint6_log.md`. NO trabajo más sobre ellas. Los archivos quedan
como están (1 430 / 1 148 / 552+220 LOC). Documentar para futuros:
"god classes intencionales del proyecto, su tamaño refleja
acoplamiento real del dominio".

**OPCIÓN B: intentar 1 sola, la más segura.** Si dudás, elegí 5b.5
SettingsDialog porque es el dialog modal más independiente (no
maneja signals del runtime). Pero solo si:
- `test_settings_dialog_contract.py` y la suite de Qt offscreen
  siguen 100% verde.
- Podés identificar AL MENOS 1 tab que NO toque
  `self._gather()` (tab puramente read-only).
- El split sería extraer ese 1 tab a `ui/settings_<tabname>.py`
  con su propio constructor independiente.

Si en 30 min de inspección no encontrás un tab limpio: OPCIÓN A.
No fuerces el split.

**Mi recomendación fuerte: OPCIÓN A.** Cerramos el plan acá.

Commit (si A): no hace falta — solo se documenta en el log.
Commit (si B): "sprint6.7: extract settings_<tabname> as
independent tab module (partial 5b.5)"

## 6.8 — Reporting + cierre del plan

Escribí `docs/architecture/sprint_prompts/_sprint6_log.md`:

- Timestamp inicio/fin.
- Tareas hechas con SHA del commit.
- Tareas SKIPPED con razón explícita (probable 6.7).
- LOC delta total: `git diff --shortstat 8106b61..HEAD`.
- LOC POR ARCHIVO ahora (final del plan):
  ```bash
  wc -l gemma4_agent/agent.py gemma4_agent/tools.py \
        gemma4_agent/agent_prompt.py gemma4_agent/agent_guards.py \
        gemma4_agent/agent_compaction.py gemma4_agent/agent_dispatch.py \
        gemma4_agent/tool_schemas.py gemma4_agent/tool_dispatch.py \
        gemma4_agent/app_resolver.py gemma4_agent/ssrf_guard.py \
        gemma4_agent/ui/main_window.py gemma4_agent/ui/settings.py
  ```
- Tests totales: `python -m pytest gemma4_agent/ -q --tb=no | tail -3`.
- Estado final: `git log --oneline -25` + `git status`.

Adicionalmente, escribí `docs/architecture/PLAN_CERRADO.md` (raíz
de docs/architecture, no en sprint_prompts):

```markdown
# Plan de optimización Carter Agent — Cerrado

## Resumen

- **Sprints ejecutados:** 0, 1, 2, 3a, 4, 5a, 5b, 6.
- **Sprint 3b (datos de uso real):** intencionalmente diferido a
  cuando el operador acumule 7-10 días de uso con la instrumentación
  de Sprint 2 (`persona_active`, `microagent_matched`, `skill_loaded`).
- **Baseline:** 55 633 LOC, 0 cycles, 0 tests de contrato, 65 tools.
- **Cierre:** XXX LOC, 0 cycles, XXX tests, 65 tools intactas.

## LOC final por archivo (los que se tocaron):
- agent.py: 2 968 → ~X
- tools.py: 4 825 → ~X
- domain_tools.py: 10 539 → 10 539 (no se tocó por imports lazy
  pre-existentes confirmados en Sprint 4)
- ui/main_window.py: 1 430 → 1 430 (SKIPPED en 6.7)
- ui/settings.py: 1 148 → 1 148 (SKIPPED en 6.7)
- agent_worker / agent_runner: combined 772 → 772 (SKIPPED — divergencia genuina)

## Lo que NO se hizo y por qué
[copiar la sección de skips de _sprint6_log.md]

## Lo que valdría hacer si vuelve a haber energía
1. Sprint 3b cuando los logs tengan datos: eliminar features dormidas.
2. Refactor de las 3 god classes restantes (workers, MainWindow,
   SettingsDialog) con tests de flujo interno escritos de cero.
3. Eliminación de TraceLogger (50+ call sites) hacia LogRecorder
   solo, si la operación amerita el riesgo de coordinación.

## Métricas finales
- Tests: 152 → XXX (todos verde)
- god classes >1000 LOC: 4 → X
- Duplicaciones auto-confesadas: 3 → 0 (eliminadas en Sprint 4)
- Tools sin uso: 45 → 45 (decisión consciente de conservar para
  "uso total del PC")
```

Commit final: "sprint6: write log + close plan with PLAN_CERRADO.md".

# VERIFICACIONES OBLIGATORIAS AL CIERRE

```bash
# 1. Import básico
python -c "import gemma4_agent"

# 2. Tools intactas
python -c "from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"
# Esperado: 65

# 3. Launcher status
python -m gemma4_agent.launcher status 2>&1 | head -5

# 4. Tests de Sprint 5a (red de contrato)
python -m pytest gemma4_agent/test_tool_registry_contract.py \
                 gemma4_agent/test_gemma4agent_contract.py \
                 gemma4_agent/test_agent_workers_parity.py \
                 gemma4_agent/test_main_window_contract.py \
                 gemma4_agent/test_settings_dialog_contract.py -q

# 5. Tests nuevos de Sprint 6
python -m pytest gemma4_agent/test_tool_pipeline_helpers.py -q

# 6. Tests pre-existentes (incluye los 17 ahora arreglados de 6.1)
python -m pytest gemma4_agent/test_promise_guard.py \
                 gemma4_agent/test_phrase_trigger_guards.py \
                 gemma4_agent/test_inherit_tools_safety.py \
                 gemma4_agent/test_session847_fixes.py \
                 gemma4_agent/test_log_audit_fixes.py \
                 gemma4_agent/test_loop_detection.py \
                 gemma4_agent/test_tool_dispatch_contract.py -q

# 7. Toda la suite (debe haber subido vs Sprint 5b)
python -m pytest gemma4_agent/ -q --tb=no 2>&1 | tail -3
```

# QUÉ NO HAGAS

- NO bajar la barra de tests: rojo no se ignora.
- NO uses `git add -A` ni `git add .`. Siempre archivos específicos
  (lesson from Sprint 5b commit 8fbf30e).
- NO cambies API pública.
- NO toques mission_*, verifiers, verify_core, voice/, personas,
  microagents, skills.
- NO modifiques COMPOUND_TOOL_SCHEMAS.
- NO instales deps. NO ejecutes agente real / llama-server / modelos.
- NO fuerces splits. Si en 30-60 min de intentar no podés mantener
  tests verde, SKIP la tarea.
- Stash @{0} restante NO LO TOQUES.

Arrancá.
```

---

## Notas para vos al despertar

1. **Si todo cierra OK:** vas a tener un `PLAN_CERRADO.md` y un repo
   con ~9 god classes parcialmente domesticadas, ~250 tests, y
   estructura clara.
2. **Si 6.7 queda en OPCIÓN A:** está bien, lo dijimos antes. Workers
   y UI god classes son acoplamiento real del dominio, no accidental.
3. **LOC esperadas removidas en Sprint 6:** ~0 net (todo es
   movimiento). Las baja real en agent.py va de 2 470 → ~1 200-1 400
   si 6.2 + 6.3 + 6.4 todos cierran verde.
4. **Métrica final esperada del plan completo:**
   - LOC: 55 633 → ~52 500 (−3 100 neto).
   - Tests: 80 → ~250.
   - god classes >1 000 LOC: 4 → 2 (los UI god, mantenidos
     conscientemente).
   - 0 ciclos de import. 0 código muerto. 0 deuda Carter funcional.
5. **Sprint 3b:** queda como referencia para vos cuando acumules
   datos de uso real. Es opt-in.

## Plan completo de sprints (referencia histórica)

| Sprint | Tarea principal | Resultado |
|---|---|---|
| 0 | requirements.txt + pyproject.toml | infra reproducible |
| 1 | quick wins puros (Carter, 23 wrappers, etc) | −3 883 LOC |
| 2 | instrumentación trace events nuevos | +684 LOC, +0 tests |
| 3a | matar NLI stack + regex ES+EN | −1 691 LOC |
| 4 | shared helpers + duplications + Timeline | −162 LOC |
| 5a | red de tests de contrato | +1 993 LOC, +83 tests |
| 5b | splits seguros (4 done, 6 skip) | +966 LOC (movió) |
| 6 | **(este)** desbloquear skips de 5b + cerrar plan | esperado ~+800 LOC movido |
| 3b | opcional cuando haya datos | TBD |
