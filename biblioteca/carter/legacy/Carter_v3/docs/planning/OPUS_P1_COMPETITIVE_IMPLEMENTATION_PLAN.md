# OPUS_P1_COMPETITIVE_IMPLEMENTATION_PLAN.md
# Plan de implementación P1 — Ideas competitivas para Carter v3
# Fecha: 2026-05-06
# Generado por: Claude Code (claude-sonnet-4-6)
# IMPORTANTE: Este plan es POSTERIOR a cerrar todos los P0 blockers (B2-B6 + live validation).

---

## PRECONDICIÓN OBLIGATORIA

**NO implementar nada de este plan hasta que:**
- [ ] B2 cerrado (confirmaciones Sí/OK/YES funcionan)
- [ ] B3 cerrado (fake_success_guard cubre texto completo)
- [ ] B4 cerrado (notify_toast → SKIPPED)
- [ ] B5 cerrado (progress reporting en misiones)
- [ ] B6 cerrado (system prompt no ejecuta al preguntar)
- [ ] Validación live documentada (≥10 spotchecks con Ollama real)
- [ ] pytest → 0 fallos post-fixes P0
- [ ] hardcode_guard → CLEAN post-fixes P0

---

## Bloque P1-A: Pipeline de inspectores componibles (de Goose)

**Origen:** `crates/goose/src/agents/agent.rs:1454` — Goose crea 5 inspectores ordenados.

**Problema que resuelve:** `security/policy.py` de Carter es un analizador monolítico.
No es fácil añadir nuevos inspectores sin modificar el core. Goose demuestra que un
pipeline componible (cada inspector = un objeto con `inspect(call) -> Decision`) es
más mantenible y testeable.

**Archivos Carter a modificar:**
- `Carter_v3/src/carter_v3/security/policy.py` — refactor a lista de inspectors
- Nuevo: `Carter_v3/src/carter_v3/security/inspectors/` (directorio)
  - `base.py` — clase abstracta `Inspector.inspect(tool_call) -> InspectionDecision`
  - `security_inspector.py` — patterns peligrosos actuales (ya existen, solo mover)
  - `egress_inspector.py` — URLs/IPs privadas (SSRF protection — ver P1-B)
  - `repetition_inspector.py` — detecta mismo tool + mismo args N veces (bucle)

**Interfaces esperadas:**
```python
class Inspector(Protocol):
    def inspect(self, tool_call: ToolCall, context: InspectionContext) -> InspectionDecision: ...

@dataclass
class InspectionDecision:
    outcome: Literal["allow", "block", "require_approval"]
    reason: str = ""
```

**Test a escribir:** `test_inspector_pipeline.py` — que el orden importa, que primero
que bloquea gana, que un inspector nuevo puede insertarse sin romper los otros.

**Complejidad:** BAJA (refactor, no funcionalidad nueva)
**Tiempo estimado Codex:** 1-2 sesiones
**Riesgo de regresión:** BAJO — la política actual se mueve, no cambia

---

## Bloque P1-B: SSRF protection en web_fetch

**Origen:** OpenClaw filtra IPs privadas antes de fetch.

**Problema que resuelve:** Carter puede hacer requests a `http://192.168.1.1/api/secret`
o `http://127.0.0.1:11434` (Ollama mismo) desde la tool web_fetch. Esto es una
vulnerabilidad SSRF si el LLM es manipulado.

**Archivos Carter a modificar:**
- `Carter_v3/src/carter_v3/tools/web_helpers.py`
  - Añadir `_is_private_ip(url: str) -> bool`
  - Bloques: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `::1`
  - Llamar antes de cualquier HTTP request en el dispatch

**Test a escribir:** `test_ssrf_protection.py` — que IPs privadas son rechazadas,
que IPs públicas pasan, que localhost es rechazado.

**Complejidad:** MUY BAJA (validación de IP en una función)
**Tiempo estimado Codex:** <1 sesión
**Riesgo de regresión:** MUY BAJO

---

## Bloque P1-C: ToolAnnotations en ToolSpec (de Goose)

**Origen:** Goose `ToolAnnotations { read_only: bool, destructive: bool, idempotent: bool }`

**Problema que resuelve:** Carter trata todos los tools igual en términos de cuánta
verificación requieren. Con annotations, la policy puede saltarse verificación heavy
cuando `read_only=True`. El futuro SmartApprove mode puede usarlos para decisiones.

**Archivos Carter a modificar:**
- `Carter_v3/src/carter_v3/tools/catalog.py`
  - Añadir a `ToolSpec`: `read_only: bool = False`, `destructive: bool = False`, `idempotent: bool = False`
  - Anotar los 32 tools existentes:
    - `read_only=True`: memory_recall, filesystem_read_text, filesystem_list_directory, filesystem_search_files, app_get_state, system_info, clock_get_time, notify_toast
    - `destructive=True`: filesystem_delete, memory_delete, process_kill, terminal_run_command (cuando rm/del)
    - `idempotent=True`: app_open, app_close, filesystem_write_text (reescribir mismo archivo)
- `Carter_v3/src/carter_v3/security/policy.py` (o nuevo inspectors/)
  - Usar `tool.read_only` para reducir nivel de inspección

**Complejidad:** BAJA (añadir campos, anotar tools)
**Tiempo estimado Codex:** 1 sesión
**Riesgo de regresión:** MUY BAJO (campos adicionales, compatibles)

---

## Bloque P1-D: Model failover entre adapters

**Origen:** OpenClaw tiene fallback entre proveedores de LLM.

**Problema que resuelve:** Si Ollama no está corriendo, Carter falla con error opaco.
No hay punto de fallo alternativo.

**Archivos Carter a modificar:**
- `Carter_v3/src/carter_v3/adapters/` — añadir método `available() -> bool` a cada adapter
- `Carter_v3/src/carter_v3/config.py` — añadir `fallback_adapters: list[str]` al config
- Donde se selecciona el adapter activo — intentar en orden hasta encontrar uno disponible

**Interfaces esperadas:**
```python
class LLMAdapter(Protocol):
    def available(self) -> bool: ...  # ping rápido, sin llamar el LLM
    async def complete(self, messages, tools) -> Response: ...
```

**Test a escribir:** `test_adapter_failover.py` — que si primary no está available(),
se selecciona el segundo en la lista.

**Complejidad:** BAJA
**Tiempo estimado Codex:** 1 sesión
**Riesgo de regresión:** BAJO

---

## Bloque P1-E: VRAM/RAM degradation automática

**Origen:** ContextoCarter.md Valor 22 (resource awareness). Ningún competidor lo hace.

**Problema que resuelve:** Carter puede intentar cargar un modelo de 7B cuando el sistema
está al 95% RAM, causando crash o freeze.

**Archivos Carter a modificar:**
- `Carter_v3/src/carter_v3/models/selector.py`
  - Al startup, leer RAM disponible (psutil) y VRAM (pynvml si disponible)
  - Si RAM < umbral configurable (e.g. 2GB libre) → forzar modelo más pequeño del registry
  - Si VRAM < umbral → deshabilitar VLM, deshabilitar preload de embedding model
- `Carter_v3/src/carter_v3/config.py`
  - Añadir `min_free_ram_mb: int = 2048`, `min_free_vram_mb: int = 2048`

**Complejidad:** BAJA-MEDIA (psutil disponible, pynvml opcional)
**Tiempo estimado Codex:** 1 sesión
**Riesgo de regresión:** BAJO (solo afecta selección de modelo, no lógica)

---

## Bloque P1-F: Error taxonomy estructural (retry/skip/abort)

**Origen:** Mark XXXIX usa LLM para generar fix scripts (anti-patrón). Carter necesita
la alternativa: clasificación estructural sin LLM.

**Problema que resuelve:** Actualmente solo `app_open` tiene retry. El resto de errores
no se clasifican — simplemente retornan FAILED.

**Nuevo archivo:** `Carter_v3/src/carter_v3/recovery/error_taxonomy.py`

```python
class ErrorClass(Enum):
    TRANSIENT = "retry"       # timeout, network blip
    PERMANENT = "abort"       # wrong tool, no permission
    PARTIAL = "next_hint"     # tool started but target not found

def classify(verifier_status: VerifierStatus, error_code: str) -> ErrorClass: ...
```

**Archivos Carter a modificar:**
- `Carter_v3/src/carter_v3/recovery.py` — usar `classify()` en lugar de if-else plano
- `Carter_v3/src/carter_v3/agent.py` — leer `ErrorClass` en el loop de steps

**Complejidad:** MEDIA (nueva abstracción, integración con loop)
**Tiempo estimado Codex:** 1-2 sesiones
**Riesgo de regresión:** MEDIO — tocar el loop de steps es delicado

---

## Bloque P1-G: TerminationCondition componibles (de AutoGen)

**Origen:** AutoGen `_terminations.py` con MaxMessageTermination, TokenBudgetTermination,
HandoffTermination, TimeoutTermination.

**Problema que resuelve:** Carter tiene solo `step_budget` como condición de terminación.
No hay control por tokens, tiempo, o handoff explícito.

**Nuevo archivo:** `Carter_v3/src/carter_v3/runtime/termination.py`

```python
class TerminationCondition(Protocol):
    def is_met(self, state: SessionState) -> bool: ...

class MaxTurnsTermination:
    def __init__(self, max_turns: int): ...

class TokenBudgetTermination:
    def __init__(self, max_tokens: int): ...

class TimeoutTermination:
    def __init__(self, max_seconds: float): ...
```

**Archivos Carter a modificar:**
- `Carter_v3/src/carter_v3/agent.py` — reemplazar `if steps >= step_budget` por
  `if any(c.is_met(state) for c in termination_conditions)`
- `Carter_v3/src/carter_v3/config.py` — permitir configurar condiciones

**Complejidad:** BAJA (interface simple, composición trivial)
**Tiempo estimado Codex:** 1 sesión
**Riesgo de regresión:** BAJO

---

## Bloque P1-H: ActionRequired bidireccional (de Goose)

**Origen:** Goose `MessageContent::ActionRequired(ActionRequiredData)` con `user_data: Option<serde_json::Value>`.

**Problema que resuelve:** Carter modela follow-ups como `pending_intent` libre (texto).
Goose demuestra que el LLM puede pedir DATOS TIPADOS al usuario (no solo yes/no),
con un schema JSON que el CLI/UI puede presentar estructuradamente.

**Nuevo elemento en `session_state.py`:**
```python
@dataclass
class PendingDataRequest:
    id: str
    prompt: str  # qué pregunta el LLM
    schema: dict  # JSON schema del dato esperado
    source_tool: str  # qué tool necesita el dato
```

**Archivos Carter a modificar:**
- `Carter_v3/src/carter_v3/session_state.py` — añadir `PendingDataRequest`
- `Carter_v3/src/carter_v3/agent.py` — cuando LLM requiere dato, crear `PendingDataRequest`
  y pausar ejecución hasta que el usuario lo provea
- CLI — presentar el schema al usuario de forma legible

**Complejidad:** MEDIA (nuevo tipo de mensaje, integración con loop)
**Tiempo estimado Codex:** 1-2 sesiones
**Riesgo de regresión:** MEDIO

---

## Bloque P1-I: Browser automation básico (Playwright)

**Origen:** Mark XXXIX y OpenClaw tienen Playwright. Carter no puede automatizar browsers.

**Problema que resuelve:** Carter no puede hacer clicks en páginas web, rellenar
formularios, o leer texto de páginas que requieren JavaScript.

**Archivos Carter a modificar:**
- Nuevo: `Carter_v3/src/carter_v3/tools/dispatch_browser.py`
  - Tools: `browser_navigate(url)`, `browser_click(selector)`, `browser_type(selector, text)`,
    `browser_get_text(selector)`, `browser_screenshot()`
- `Carter_v3/src/carter_v3/tools/catalog.py` — registrar tools nuevas
- `requirements.txt` (o `pyproject.toml`) — añadir `playwright>=1.40`

**Condición:** Solo disponible si `playwright` está instalado. Si no, los tools
retornan `NEEDS_ENVIRONMENT("playwright no instalado")`.

**Complejidad:** MEDIA-ALTA (nueva dependencia, async, manejo de estado de browser)
**Tiempo estimado Codex:** 2-3 sesiones
**Riesgo de regresión:** BAJO (tools nuevas, no modifica tools existentes)

---

## Bloque P1-J: Context compaction

**Origen:** Goose `context_mgmt/mod.rs:check_if_compaction_needed()` — threshold 0.75 del context window.

**Problema que resuelve:** Con conversaciones largas, Carter trunca turns viejos sin avisar.
La compaction proactiva resume los turns viejos en un "context summary" preservando la información clave.

**Archivos Carter a modificar:**
- `Carter_v3/src/carter_v3/turn_support.py` — añadir `check_compaction_needed(messages, model)`
- Nuevo: `Carter_v3/src/carter_v3/context_compaction.py`
  - `compact_turns(old_turns: list[Turn], model_context: int) -> str` — genera summary
  - Threshold configurable (default 80% del context window del modelo activo)

**Complejidad:** MEDIA (requiere nueva llamada LLM para summarizar)
**Riesgo de regresión:** MEDIO

---

## Orden de implementación recomendado

```
1. P1-B (SSRF)        — más fácil, más seguridad inmediata
2. P1-C (ToolAnnotations) — fundamento para P1-A
3. P1-A (Pipeline inspectores) — requiere P1-C
4. P1-D (Model failover) — independiente, baja complejidad
5. P1-E (VRAM degradation) — independiente, baja complejidad
6. P1-G (TerminationCondition) — independiente, baja complejidad
7. P1-F (Error taxonomy) — mejora loop de steps
8. P1-J (Context compaction) — mejora conversaciones largas
9. P1-H (ActionRequired) — requiere B2 estable
10. P1-I (Browser Playwright) — mayor complejidad, mayor impacto
```

---

## Criterios de aceptación para cada bloque P1

- [ ] pytest → 0 fallos después de implementar cada bloque
- [ ] hardcode_guard → CLEAN después de cada bloque
- [ ] El nuevo código NO introduce listas de verbos, aliases de app, ni frases hardcodeadas
- [ ] Cada nuevo tool/inspector tiene al menos 3 tests que lo cubren
- [ ] No se rompe ningún test de `test_no_semantic_hardcodes.py`

---

*Generado por Claude Code (claude-sonnet-4-6) — Plan de implementación post-P0 — 2026-05-06*
