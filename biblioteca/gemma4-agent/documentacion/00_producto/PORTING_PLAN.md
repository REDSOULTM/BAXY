# Porting Plan — TIER 1 + TIER 2 desde Carter v5 / Competidores

> **Branch**: `PortandoLoMejor` (creada desde `develop@23fd70c`)
> **Tag de rollback**: `backup/pre-portandolomejor-20260515`
> **Fecha**: 2026-05-15

## Estado final del porting (cierre de la branch)

| # | Patrón | Estado | Commit |
|---|---|---|---|
| 1 | Loop detection estructural | ✅ DONE | `a82a034` |
| 2 | Verifier por-tool (12 tools) | ✅ DONE | `08e05cc` |
| 3 | Microagents (4 eager) | ✅ DONE | `7fc677c` |
| 4 | Skills system (10 curados, 1 critical eager) | ✅ DONE | `5b30322` + `01c62a0` |
| 5 | Mission Goal verifier (Voyager pattern) | ✅ DONE | `370840a` |
| 6 | StateGraph + checkpoints | ⏭️ SKIP | n/a — loop actual funciona; sin payoff inmediato; user decidió skip |
| 7 | MCP server exposure | ✅ DONE | `7327628` |

Tests totales sumando todos los suites de los TIER portados: **177**
(loop_detection 19, verifiers 45, microagents 28, skills 26, mission_goal
45, mcp_server 14). Todos pasan.

## TL;DR

Carter v5 tiene 7 patrones que Baxy no implementa y que aportan
**capacidad real, no tweaks de latencia**. Son portables porque:

1. Carter v5 es Python local sobre `llama-server` igual que Baxy.
2. Ya tenemos los puntos de extensión: `run_content` loop, semantic router,
   system_prompt builder, tools registry.
3. El código de referencia es chico (~1.7K líneas para los 7 patrones).

Después de portar los 4 TIER 1 + (opcionalmente) los 3 TIER 2, Baxy
va a ser:

- Más **honesto** (verifier estructural + mission goal)
- Más **robusto** (loop detection real, no `max_turns` ciego)
- Más **escalable** (skills como markdown, no Python hardcoded)
- Más **abierto** (MCP server expone tools al ecosistema)

Estimación total: **8-12 días de trabajo** para TIER 1 completo; TIER 2
opcional añade 5-7 días más.

## Estado actual de Baxy (baseline, no inventar)

Lo que YA tiene (verificado leyendo el código):

| Capacidad | Implementación actual |
|---|---|
| Tool selection | `semantic_router.select_tool_names()` con embeddings multilingüe |
| Lazy schemas | `_tool_schemas_hint(selected_tool_names)` filtra markdown por subset |
| Reglas por tool | `agent.TOOL_RULES` + `build_system_prompt(selected_tool_names)` |
| Verify | Tool `verify` con 4 acciones: `app_opened`, `file_exists`, `window_exists`, `clipboard_contains` |
| Safety | `_hard_gate()` en herramientas destructivas + spec con `is_destructive` |
| Memory | `MemoryStore` SQLite + LRU cache de embeds (`semantic_router._EMBED_CACHE`) |
| Multimodal | `multimodal.py` (image counter + leak mitigation #21690), Whisper STT, Piper TTS |
| Loop detection | **NO** — solo `max_agent_turns` como tope duro |
| Verifier por-tool | **NO** — la verificación está mezclada dentro de cada herramienta |
| Microagents | **NO** |
| Skills system | **NO** |
| Mission goal verifier | **NO** — `MissionPlan` (planner.py) solo prioriza tools, no verifica intención |
| MCP server exposure | **NO** |

## Análisis costo/beneficio (ROI)

| # | Patrón | Diff esperado | Esfuerzo | Riesgo | ROI |
|---|---|---|---|---|---|
| 1 | Loop detection | +280 / -10 LOC | 1 día | bajo | ⭐⭐⭐⭐⭐ |
| 2 | Verifier por-tool | +800 / -300 LOC | 2 días | medio | ⭐⭐⭐⭐⭐ |
| 3 | Microagents | +250 / -0 LOC | 1 día | bajo | ⭐⭐⭐⭐ |
| 4 | Skills system | +500 / -0 LOC | 2-3 días | medio | ⭐⭐⭐⭐⭐ |
| 5 | Mission goal verifier | +600 / -100 LOC | 3 días | medio | ⭐⭐⭐⭐ |
| 6 | StateGraph + checkpoints | +1500 / -500 LOC | 5-7 días | alto | ⭐⭐⭐ |
| 7 | MCP server | +300 LOC nuevo file | 1-2 días | bajo | ⭐⭐⭐⭐ |

**Recomendación**: hacer 1 → 3 → 2 → 4 → 7 en ese orden. Saltar 5 y 6 hasta
medir impacto real (5 puede colisionar con 2 si no se diseña bien; 6 es un
refactor grande sin payoff inmediato).

---

# TIER 1 — 4 patrones de alto valor / esfuerzo medio

## 1. Loop detection estructural

### Por qué importa

Hoy si el LLM se queda en un loop (llama la misma tool con los mismos args
repetidamente porque el resultado no le da progreso), el único corte es
`max_agent_turns`. Eso significa **N turnos completos desperdiciados** antes
de abortar, en vez de cortar al tercer intento idéntico.

Carter detecta 5 patrones de stuck con **two-tier escalation** (warning →
critical) usando un paper de Reflexion (NeurIPS 2023):

| Patrón | Cuándo dispara | Acción |
|---|---|---|
| `generic_repeat` | mismo `(tool, args, result_sig)` 3× consecutivos | warning → 5× → abort |
| `unknown_tool_repeat` | tool inexistente llamada ≥3× | abort inmediato |
| `ping_pong` | A→B→A→B→A→B sin progreso | abort |
| `circuit_breaker` | >30 tool_calls totales en sesión | abort |
| `no_progress` | N tool_calls sin que cambie ningún `evidence_key` | warning |
| `vision_locate_visible_false_repeat` (bonus) | vision devuelve `visible=False` ≥3× | abort |

El **result_signature hashing** es la idea más fina: hashea `result` filtrando
campos ruidosos (timestamps, pids, latencias). Polling legítimo cambia el
output cada vez → no se confunde con loop. Loop genuino devuelve el mismo
result → se detecta limpio.

### Origen

- `carter_v5/loop/detection.py` (239 LOC, self-contained, sin imports de Carter)
- Usado en `carter_v5/core/execution.py:81,149,199-204`

### Plan de port — Baxy

**Archivo nuevo**: `gemma4_agent/loop_detection.py` (~250 LOC)

Estructura:

```python
# loop_detection.py
@dataclass
class StuckSignal:
    level: str            # 'warning' | 'critical'
    pattern: str          # 'generic_repeat' | ... | 'no_progress'
    message: str          # texto para inyectar al LLM
    detail: dict

@dataclass
class LoopState:
    history: deque
    unknown_tool_count: dict[str, int]
    global_count: int
    evidence_keys_changed: set
    warning_count: int

    def record(self, tool_name, args, exists, result)
    def record_evidence(self, evidence_key)
    def detect_stuck(self) -> StuckSignal | None
    def reset(self)
```

**Cambios en `agent.py:run_content`** (~10 LOC):

1. Crear `loop_state = LoopState()` al inicio del turn.
2. Después de cada tool execution en `Phase 3`, llamar
   `loop_state.record(name, args, exists=spec_exists, result=result)`.
3. Llamar `stuck = loop_state.detect_stuck()` después de cada record.
4. Si `stuck.level == "critical"`: cortar el for loop con un
   `_publish_activity` y un `self.history.append({"role": "tool", "content":
   stuck.message})` para que el LLM vea por qué se cortó.
5. Si `stuck.level == "warning"`: solo inyectar el mensaje al LLM como
   `tool_result` virtual con `_loop_warn` y dejar que el modelo decida.

**Evidencia de progreso** (importante): registrar `evidence_key` cuando
algo cambia. Ejemplos canónicos:

- Después de `app.open(...)` exitoso: `loop_state.record_evidence(f"app:{name}")`
- Después de `filesystem.write(...)` con `verified=True`: `record_evidence(f"file:{path}")`
- Después de `window.focus(...)` con `verified=True`: `record_evidence(f"window:{query}")`

El verifier per-tool (#2) inyectará esos evidence keys automáticamente.

**Constantes ajustables** (`gemma4_agent/loop_detection.py`):

```python
REPEAT_WARNING = 3                # primer warning
REPEAT_CRITICAL = 5               # abort
UNKNOWN_TOOL_LIMIT = 3
PING_PONG_WINDOW = 6
GLOBAL_CIRCUIT_BREAKER = 30
```

Hacerlas opt-out via env: `GEMMA4_LOOP_DETECTOR_OFF=1` los bypassea.

### Testing

- Unit test `test_loop_detector.py` (~80 LOC):
  - simular 3× misma tool+args+result → expect warning
  - simular 5× misma tool+args+result → expect critical
  - simular polling (result distinto cada vez) → expect None
  - simular ping_pong A↔B 3× → expect critical
  - simular 30 tools distintas → expect circuit_breaker

- Smoke test en agente real: bench actual debe pasar igual; loops detectados
  generan eventos en trace, visible en log.

### Riesgos

- **Falsos positivos** en polling con timestamps no filtrados. Mitigación:
  expandir la blacklist de `_result_signature` (ya filtra `ts`, `pid`,
  `latency_ms`; agregar `_ts`, `created_at`, `now`, `monotonic`).
- **Tools con efecto async** (deeplink) devuelven mismo result pero el
  efecto ocurre fuera. Mitigación: lista whitelist `_INCONCLUSIVE_BY_NATURE`
  (igual que Carter) — esas tools no cuentan para repeat detection.

---

## 2. Verifier estructural por-tool con decorator

### Por qué importa

Hoy las herramientas mezclan ejecución y verificación inline. Ejemplo en
[gemma4_agent/tools_pkg/tools.py](../../gemma4_agent/tools_pkg/tools.py):

```python
preexisting = self.verify_app_opened({"name": name})
open_result = self.apps.open(best)
...
verified = bool(post.get("found"))
```

Cada tool re-implementa su propia verificación. El LLM recibe `verified=True`
o `verified=False` pero **no hay un reporte global** de cuántas tools del turn
fueron verificadas vs cuántas se ejecutaron sin verifier.

Carter separa esa preocupación: cada tool ejecuta, después un **verifier
registrado por-tool** lee el estado real del sistema. El verifier devuelve
`VerifierOutcome(confirmed: True | False | None, reason)` donde `None` =
"no verificable" (honest). Al final del turn se genera un footer:

```
[3 verificada(s), 1 no confirmada(s), 2 no verificable(s)]
```

El LLM ve eso en el próximo turn y ajusta su comportamiento. **Esto es honest
by design**, no parchado con prompting.

### Origen

- `carter_v5/verify/core.py` (423 LOC): registry + `register_verifier` decorator,
  `summarize_verifiers`, `no_action_footer`, `_has_completion_claim`,
  `rewrite_claim_to_unverified`, `strip_planning_leakage`, `fix_carter_vocative`.
- `carter_v5/verify/runtime.py` (244 LOC): 8 verifiers concretos
  (`verify_app_open`, `verify_app_close`, `verify_system_set_volume`,
  `verify_system_mute`, `verify_filesystem_write`, `verify_filesystem_delete`,
  `verify_terminal_run`, `verify_gui_screenshot`).
- Status enum: `COMPLETED | UNVERIFIED | PARTIAL | BLOCKED`.

### Plan de port — Baxy

**Archivo nuevo**: `gemma4_agent/verify_core.py` (~250 LOC, copia adaptada de
`carter_v5/verify/core.py`).

Estructura:

```python
@dataclass
class VerifierOutcome:
    tool_name: str
    confirmed: bool | None       # None = no verifiable
    reason: str
    detail: dict | None = None
    evidence_keys: list[str] = []  # NUEVO: para loop_state.record_evidence

_VERIFIERS: dict[str, Callable] = {}

def register_verifier(tool_name: str):
    def decorator(fn):
        _VERIFIERS[tool_name] = fn
        return fn
    return decorator

def verify(tool_name, args, result) -> VerifierOutcome:
    fn = _VERIFIERS.get(tool_name)
    if fn is None:
        return VerifierOutcome(tool_name, None, "no verifier")
    try:
        return fn(args, result)
    except Exception as exc:
        return VerifierOutcome(tool_name, False, f"verifier crashed: {exc}")

def summarize_verifiers(outcomes: list[VerifierOutcome]) -> str:
    confirmed = sum(1 for o in outcomes if o.confirmed is True)
    failed = sum(1 for o in outcomes if o.confirmed is False)
    unverifiable = sum(1 for o in outcomes if o.confirmed is None)
    if failed == 0 and unverifiable == 0:
        return ""
    parts = []
    if confirmed: parts.append(f"{confirmed} verificada(s)")
    if failed:    parts.append(f"{failed} no confirmada(s)")
    if unverifiable: parts.append(f"{unverifiable} no verificable(s)")
    return f"\n\n[{', '.join(parts)}]"
```

**Archivo nuevo**: `gemma4_agent/verifiers.py` (~400-600 LOC) — implementaciones
concretas usando los tools/helpers existentes de Carter. Por tool:

```python
from .verify_core import register_verifier, VerifierOutcome

@register_verifier("app")
def verify_app(args, result):
    action = args.get("action", "")
    if action == "open":
        # Verificar via tasklist o psutil (ya tenemos _running_process_names)
        name = args.get("name", "")
        if not result.get("ok"):
            return VerifierOutcome("app", False, f"tool error: {result.get('error')}")
        # Wait 2s + psutil check
        import time
        from .tools import _running_process_names
        deadline = time.monotonic() + 2.0
        target = (name + ".exe").lower() if not name.endswith(".exe") else name.lower()
        while time.monotonic() < deadline:
            if any(target in p for p in _running_process_names()):
                return VerifierOutcome(
                    "app", True, f"proceso {target} encontrado",
                    evidence_keys=[f"app:{name}"],
                )
            time.sleep(0.25)
        return VerifierOutcome("app", None, f"proceso {target} no encontrado")

@register_verifier("filesystem")
def verify_filesystem(args, result):
    action = args.get("action", "")
    if action == "write":
        path = args.get("path") or result.get("path")
        if not path:
            return VerifierOutcome("filesystem", None, "path vacio")
        p = Path(path).expanduser()
        if not p.exists():
            return VerifierOutcome("filesystem", False, "archivo no existe post-write")
        size = p.stat().st_size
        if size == 0 and args.get("content"):
            return VerifierOutcome("filesystem", False, "archivo vacio post-write")
        return VerifierOutcome(
            "filesystem", True,
            f"archivo verificado: {size} bytes",
            evidence_keys=[f"file:{path}"],
        )
    # ... resto de actions: read, delete, copy, move, etc.

@register_verifier("audio")
def verify_audio(args, result):
    # usa pycaw como Carter para leer estado real post-action
    ...

@register_verifier("window")
def verify_window(args, result):
    # usa win32gui.GetForegroundWindow / EnumWindows para confirmar focus/close
    ...

# ... resto de tools del catálogo
```

**Wiring en `agent.py:run_content`** (~30 LOC):

Después de Phase 3 de tools execution:

```python
from .verify_core import verify, summarize_verifiers
from .loop_detection import LoopState  # ya creado en TIER 1 #1

verifier_outcomes = []
for prep in prepared:
    result = prep.get("result") or {}
    outcome = verify(prep["name"], prep["args"], result)
    verifier_outcomes.append(outcome)
    # Inyectar evidence en loop_state para anti-loop
    for ek in (outcome.evidence_keys or []):
        loop_state.record_evidence(ek)
    # Si verifier dice failed pero result decia ok → reportar inconsistencia
    if outcome.confirmed is False and result.get("ok"):
        self.trace.event(turn_id, "verifier_disagrees", tool=prep["name"],
                         reason=outcome.reason)

# Al final del turn, append footer al reply
footer = summarize_verifiers(verifier_outcomes)
if footer:
    assistant_content = (assistant_content or "") + footer
```

**Cobertura mínima**: portar verifiers para las **10 tools más usadas**
según el log que ya tenemos:

1. `app` (open/close/search)
2. `steam` (open/launch_game)
3. `window` (focus/close/minimize/maximize)
4. `gui` (screenshot, click, keypress, type)
5. `audio` (set_volume, mute)
6. `filesystem` (read/write/delete/list)
7. `terminal` (run)
8. `web` (open_url/search/read)
9. `system` (time, processes — read-only siempre confirmed=None)
10. `verify` (paradójico pero útil para evitar recursión: confirmed=None siempre)

### Testing

- Unit test `test_verifiers.py` (~150 LOC) por cada verifier con resultados
  mockeados (no spawnear apps reales en CI).
- Integration test: corre un turn real con `app.open` de algo que no existe
  → verifier debe devolver `confirmed=False`, footer debe aparecer.

### Riesgos

- **Doble verificación**: hoy `app_open` ya hace su propio polling. Si
  agregamos verifier externo, hay dos checks. Solución: pasar `_internal_verified`
  flag desde la tool al verifier, y el verifier respeta eso (no re-mide).
  Alternativa más limpia: refactorizar la tool para que NO haga su propio
  polling (lo hace el verifier afuera) — más invasivo pero coherente.
- **Tools async (deeplink, browser.open)**: el verifier no puede medir efecto
  inmediato. Devolver `confirmed=None` con `reason="async dispatch"`.

---

## 3. Microagents (contexto eager por trigger)

### Por qué importa

El SYSTEM_PROMPT actual tiene reglas universales + reglas por tool (post
commit `23fd70c`). Pero **hay conocimiento de dominio que no es regla de
tool sino contexto** que el LLM necesita cuando aparecen ciertos temas:

- "qué es deeplink", "qué significa HKCR", "qué es mmproj" → glossary
- "no funciona X", "se rompió Y" → troubleshoot flow
- "comando Windows para …" → tabla de equivalencias

Hoy si el usuario pregunta "qué significa HKCR" el LLM tiene que adivinar
porque el SYSTEM_PROMPT no incluye contexto técnico Windows.

**Microagents** = markdown files con frontmatter `triggers: [...]`. El loader
matchea triggers contra el user_text del **primer mensaje del turn** y
appendea el contenido al system_prompt como `# CONTEXT: <nombre>`.

Esto es **complementario a TOOL_RULES**: TOOL_RULES inyecta reglas de uso
de una tool cuando esa tool está en el subset; microagents inyecta
glosarios/troubleshoot cuando el texto del usuario coincide con triggers.

### Origen

- `carter_v5/microagents/loader.py` (131 LOC): parser YAML frontmatter + selector.
- `carter_v5/microagents/glossary.md`, `windows_commands.md`,
  `troubleshoot.md`, `tools_cheat_sheet.md` — ejemplos.
- Pattern original: OpenHands `.openhands/microagents/`.

### Plan de port — Baxy

**Archivo nuevo**: `gemma4_agent/microagents.py` (~150 LOC) — port directo de
`carter_v5/microagents/loader.py`.

**Carpeta nueva**: `gemma4_agent/microagents/` con archivos markdown
(4 iniciales):

```
gemma4_agent/microagents/
├── README.md         (explica el formato)
├── glossary.md       (jerga Windows + Gemma 4: HKCR, mmproj, llama-server, ...)
├── windows_commands.md (equivalencias bash↔cmd↔powershell)
├── troubleshoot.md   (flow diagnóstico: app no abre, audio no funciona, ...)
└── tools_cheat_sheet.md (lista compacta de las 62 tools agrupadas por dominio)
```

Formato de cada `*.md`:

```markdown
---
name: glossary
triggers: ["qué significa", "que significa", "qué es", "glossary", "vocabulario", "jerga"]
priority: low
---

# Glossary
- **deeplink**: URI scheme like `steam://`, `spotify:`, etc.
- **HKCR**: Windows registry `HKEY_CLASSES_ROOT`.
- **mmproj**: multimodal projector file for vision/audio in llama.cpp.
- **OUTCOME**: COMPLETED | PARTIAL | FAILED | UNVERIFIED | NEEDS_USER | ...
```

**Wiring en `agent.py:build_system_prompt`** (~15 LOC):

```python
def build_system_prompt(selected_tool_names=None, user_text=None):
    parts = [CORE_PROMPT]
    # TOOL_RULES (existente)
    ...
    # NUEVO: microagents
    if user_text:
        from .microagents import load_microagents, select_microagents, format_microagents_for_prompt
        all_ma = load_microagents()
        matched = select_microagents(user_text, all_ma, max_microagents=3)
        if matched:
            parts.append(format_microagents_for_prompt(matched))
    return "\n\n".join(parts)
```

**Punto de inyección**: `_system_message(...)` debe recibir `user_text` para
matchear triggers. Modificar la llamada desde `run_content` para pasar
`raw_text_early` que ya está disponible.

**Cache**: Microagents que matchean en el primer turn de la sesión se cachean
para el resto de la sesión (igual que Carter). Si el usuario inicia turn 2
con otro tema, **no** se re-evalúa para no invalidar el KV cache del
llama-server.

### Testing

- Unit test `test_microagents.py` (~80 LOC):
  - Parser de frontmatter (válido / sin frontmatter / sin triggers)
  - Selector: trigger match → microagent en lista; sin match → lista vacía
  - Cap a 3 microagents por turn
  - Sorting por priority (high → medium → low)

### Riesgos

- **Token budget**: 3 microagents × 500 chars cada = 1.5K chars (~370
  tokens). Aceptable, pero si se ponen 10 microagents muy grandes infla el
  prompt. Mitigación: cap max_microagents=3 + soft limit por microagent
  (alertar en log si supera 2K chars).
- **Triggers ambiguos**: "qué es" matchea casi cualquier pregunta. Mitigación:
  triggers más específicos en glossary ("qué es HKCR" en vez de "qué es");
  priority="low" para que pierda contra microagents más específicos.

---

## 4. Skills system (lazy-loaded recipes)

### Por qué importa

Hoy si quiero que el LLM aprenda un workflow nuevo ("instala un juego de
Steam"), tengo que:

- O escribir una tool nueva en Python (alto esfuerzo, requiere recompilar).
- O agregarlo al SYSTEM_PROMPT (consume contexto, va en TODOS los turns).

**Skills** = markdown files con `name + description + priority` que viven en
un directorio. Al boot, el LLM ve un **menú compacto**:

```
# SKILLS AVAILABLE
Call `skill_load(name)` to load the full recipe when needed.
- **install-game** [lazy, priority=high]: Install a Steam game from name. Uses gui_deeplink + verify.
- **purchase-guard** [ALWAYS LOADED]: Never spend real money without explicit user "sí" confirmation.
- **steam-library-check** [lazy, priority=medium]: Search if a game is owned in Steam library.
```

Cuando el usuario dice "instala doom eternal", el LLM emite
`skill_load(name="install-game")`. El tool retorna el body completo del
markdown (~500-2000 chars) como tool_result. El LLM lo lee y ejecuta los
tools que la receta describe.

**Critical skills** (priority=critical) se cargan eager al boot — usados
para constraints universales tipo `purchase-guard` que nunca deben olvidarse.

### Origen

- `carter_v5/skills/registry.py` (357 LOC): scan + parse + menu builder +
  eligibility filter (requires bins/env/os).
- `carter_v5/skills/` carpetas: `filesystem-workflow/`, `gui-visual-action/`,
  `install-game/`, `purchase-guard/`, `steam-library-check/`.
- Cap por tier: `tier_6gb=1, tier_8gb=2, tier_16gb=5`.
- Spec: Anthropic Agent Skills (`code.claude.com/docs/en/custom-skills`).

### Plan de port — Baxy

**Archivo nuevo**: `gemma4_agent/skills_registry.py` (~300 LOC) — port adaptado
de `carter_v5/skills/registry.py`.

Estructura:

```python
@dataclass(frozen=True)
class SkillMeta:
    name: str                 # lowercase + hyphens, ≤64 chars
    description: str
    priority: str             # critical | high | medium | low
    path: Path
    requires: dict            # {bins, any_bins, env, os}

def scan_skills(skills_dir=None) -> list[SkillMeta]: ...
def check_skill_eligibility(skill) -> bool: ...
def build_menu(skills, max_chars=200) -> str: ...
def build_critical_block(skills) -> str: ...
def load_skill_content(name, skills_dir=None) -> str | None: ...
def get_skill_cap(profile_name: str) -> int: ...  # Baxy usa profiles, no tiers
```

**Cap por perfil** (mapear los 5 perfiles VRAM):

```python
CAP_PER_PROFILE = {
    "standby":     0,
    "light":       1,
    "balanced":    2,
    "balanced_8gb": 3,
    "performance": 5,
}
```

**Tool nueva**: `skill_load` en `tools.py`:

```python
{
    "type": "function",
    "function": {
        "name": "skill_load",
        "description": "Load the full body of a skill recipe by name. Use only when the user request matches a skill description from the SKILLS AVAILABLE menu.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
},
```

Handler:

```python
def t_skill_load(self, args):
    from .skills_registry import load_skill_content
    name = str(args.get("name", "")).strip()
    if not name:
        return _err("skill_load requires name", status="needs_user")
    body = load_skill_content(name)
    if body is None:
        return _err(f"skill '{name}' not found", status="needs_user")
    # Cap por turn: contar cuántas veces se llamó skill_load en este turn
    # (vive en self.state o un counter por-turn)
    return _ok(skill=name, recipe=body, source="local")
```

**Wiring en `_system_message`**:

```python
from .skills_registry import scan_skills, build_menu, build_critical_block

skills = scan_skills()  # cache nivel-agente, se invalida cuando agent restart
critical_block = build_critical_block(skills)
menu_block = build_menu(skills)

content = f"{CORE_PROMPT}{tool_rules_section}{tools_section}{critical_block}{menu_block}..."
```

**Carpeta nueva**: `gemma4_agent/skills/` con 5 skills iniciales:

```
gemma4_agent/skills/
├── README.md
├── install-steam-game/SKILL.md     (chain steam + verify)
├── purchase-guard/SKILL.md          (CRITICAL: never click "Buy" without sí)
├── new-development-project/SKILL.md (filesystem + git + developer chain)
├── voice-record-and-transcribe/SKILL.md (voice + filesystem)
└── safe-file-cleanup/SKILL.md       (preview con dry-run antes de borrar)
```

Ejemplo `purchase-guard/SKILL.md`:

```markdown
---
name: purchase-guard
description: Universal hard rule — never spend real money without explicit user "sí" confirmation. Applies to Steam, Epic, GOG, browser checkout, subscriptions.
priority: critical
---

# Purchase guard (universal honesty rule)

**Tools used**: none (behavioral rule, not a recipe).
**Honesty-critical**: yes.

## The rule
- NEVER click "Comprar", "Buy", "Subscribe", "Pay" without the user having
  said "sí", "yes", "dale", "confirmá" IN THE CURRENT TURN.
- Opening a store page → ALLOWED.
- Clicking a payment button → REQUIRES explicit affirmative in user's latest message.

## How to apply
If the user said "comprá X":
1. Treat as INTENT, not authorization.
2. Open the store page (deeplink / web).
3. Report price, edition, availability.
4. Ask: "¿Confirmás la compra? (sí/no)"
5. Wait for NEXT turn confirmation before clicking Buy.
```

Ejemplo `install-steam-game/SKILL.md`:

```markdown
---
name: install-steam-game
description: Install a Steam game from its name. Searches library first, falls back to store. Verifies install before reporting.
priority: high
requires:
  bins: []
  any_bins: [steam]
  os: [windows]
---

# Install Steam game

**Tools used**: steam, gui, verify, purchase-guard (constraint).
**Honesty-critical**: yes — purchase-guard applies if game is not owned.

## Steps
1. `steam(action="search_library", query="<game>")` — owned games first.
2. If found owned: `steam(action="launch_game", query="<game>")` then `verify(action="app_opened", name="<game>")`.
3. If NOT owned: `steam(action="store_page", query="<game>")`, report price, apply purchase-guard rule.

## Honest outcomes
- Game launched and verified: COMPLETED.
- Store opened, user needs to confirm: NEEDS_USER (apply purchase-guard).
- Game not found anywhere: report honestly, do not invent App IDs.
```

### Testing

- Unit test `test_skills_registry.py` (~120 LOC):
  - Parser de frontmatter válido / inválido
  - `scan_skills` filtra por eligibility (mock `shutil.which`)
  - `build_menu` formato
  - `build_critical_block` solo incluye critical
  - `get_skill_cap` por perfil
- Integration: `skill_load(name="install-steam-game")` retorna el body
  completo como tool_result.

### Riesgos

- **Cap por turn**: el LLM podría llamar `skill_load` 10× en un turn. Mitigación:
  contador per-turn que devuelve `_err("skill_load cap reached for this profile")`
  después de N llamadas.
- **Skills mal escritas**: una skill que recomienda tools que no existen.
  Mitigación: validar en `scan_skills` que las tools mencionadas en
  "Tools used:" existen en COMPOUND_TOOL_SCHEMAS. Warning en log si no.
- **Conflicto con TOOL_RULES**: una skill podría duplicar contenido de
  TOOL_RULES. Convención: TOOL_RULES dice "cómo usar la tool"; skill dice
  "qué chain de tools usar para X workflow". No overlap natural.

---

# TIER 2 — 3 patrones opcionales (alto valor / esfuerzo alto)

## 5. Mission Goal verifier estructural

### Por qué importa

Hoy el agente sabe si **las tools** se ejecutaron OK (commit `verify=True`).
Lo que NO sabe es si la **intención del usuario** se cumplió.

Ejemplo:
- Usuario: "abre Steam"
- Tool: `app.open(name="Steam")` → ok=True
- Verifier (TIER 1 #2): `confirmed=True` (proceso Steam.exe en tasklist)
- **Mission goal**: ¿el objetivo "abre Steam" está cumplido? Sí → `COMPLETED`.

Más complejo:
- Usuario: "abre Steam y ve a mi biblioteca"
- Tool 1: `app.open(name="Steam")` → ok=True, verifier confirmed
- Tool 2: `steam(action="library")` → ok=True, verifier inconclusive (deeplink async)
- Tool 3: el LLM se distrajo y respondió sin más
- **Mission goal**: 2 de 3 sub-objetivos cumplidos → `PARTIAL`.

Sin mission goal, el LLM dice "listo, abrí Steam y la biblioteca" aunque la
biblioteca no esté visible. Con mission goal, recibe footer
`[mission PARTIAL: 1/2 expected satisfied]` y puede corregir.

### Origen

- `carter_v5/mission/goal.py` (364 LOC): `MissionGoal` con `ExpectedOutcome`
  (kind: `open_target`, `close_target`, `set_state`, etc.) construido por
  regex multilingüe del input del usuario.
- `carter_v5/mission/verifier.py` (162 LOC): `compute_mission_outcome` que
  combina `MissionGoal.is_fulfilled()` con counts de verifier outcomes.
- Inspirado en Voyager (NeurIPS 2023).

### Plan de port — Baxy

**Archivos nuevos**:

- `gemma4_agent/mission_goal.py` (~400 LOC): `MissionGoal`, `ExpectedOutcome`,
  parsers de imperativos multilingües (verbos abrir/cerrar/mutear/escribir/etc.).
- `gemma4_agent/mission_outcome.py` (~200 LOC): `compute_mission_outcome` +
  `OutcomeStatus` enum (`COMPLETED`, `PARTIAL`, `FAILED`, `UNVERIFIED`,
  `INTENT_NOT_FULFILLED`, `NEEDS_USER`, `BLOCKED`, `TOOL_OK_VERIFIER_INCONCLUSIVE`).

**Wiring en `run_content`**:

```python
from .mission_goal import build_mission_goal
from .mission_outcome import compute_mission_outcome

mission_goal = build_mission_goal(raw_text_early)  # parse del user input

# (durante el loop) cada tool actualiza el goal:
mission_goal.update_with_tool(name, args, ok=result.get("ok", False))

# (al final) combinar con verifier outcomes:
outcome = compute_mission_outcome(mission_goal, tool_records, reply_text=assistant_content)
if outcome.status == OutcomeStatus.PARTIAL:
    assistant_content += f"\n\n[mission PARTIAL: {outcome.expected_satisfied}/{outcome.expected_total}]"
elif outcome.status == OutcomeStatus.INTENT_NOT_FULFILLED:
    assistant_content += f"\n\n[mission NOT FULFILLED: {outcome.summary}]"
```

### Trade-off

- **+600 LOC** de regex multilingüe y mapeo tool→expected_outcome.
- **Acoplado** a TIER 1 #2 (verifier per-tool). Si #2 no está, #5 pierde
  precisión.
- **Riesgo de falsos negativos**: mission_goal parser puede no entender
  ciertas frases ambiguas → reporta PARTIAL cuando es COMPLETED.

**Recomendación**: hacer #5 solo después de medir #2 funcionando en el log
real. Si el footer de #2 ya resuelve el problema, #5 puede no agregar valor.

---

## 6. StateGraph + durable checkpoints

### Por qué importa

`run_content` hoy es un loop imperativo. Para conversaciones complejas con
human-in-the-loop (e.g. usuario aprueba/rechaza una acción, agente continúa)
sería más limpio modelarlo como **grafo de estados**.

LangGraph hace exactamente eso: `StateGraph` con nodos (planning, executing,
verifying, awaiting_user) y edges (condicionales). Permite:

- Checkpoints automáticos (SQLite) → resume después de crash.
- Human-in-the-loop interrupts → pausar en un nodo, modificar state,
  resume.
- Visualización del grafo → debug visual.

### Plan de port — Baxy

**Esfuerzo**: alto. Refactor de `run_content` (~600 LOC actuales) a un
state machine. Probablemente +1500 / -500 LOC.

**Recomendación**: NO hacer en esta iteración. Validar primero que #1+#2+#3+#4
no se vuelven inmanejables sin StateGraph. Si en 3 meses la lógica de
confirmations + retries + multi-turn missions se vuelve un spaghetti,
revisitar.

Si se hace: usar `langgraph` directo (es BSD-3, pure Python, pip install).
No portar; integrar.

---

## 7. MCP server exposure

### Por qué importa

Baxy hoy es **consumer** de tools (las llama internamente). Si lo
exponemos como **MCP server**, otros agentes (Claude Desktop, Cursor, Goose,
OpenHands) pueden usar Baxy como backend.

Caso de uso real: el usuario tiene Cursor abierto, le dice a Cursor "abre
Steam y verificá que mi juego se actualizó". Cursor (que ya soporta MCP)
llama al MCP server de Baxy que ejecuta `steam.launch_game` + `verify`.

**Diferencial competitivo**: Carter v5 hizo esto, Carter v5 es el único Jarvis
local que también es MCP tool provider. Si Baxy lo hace, gana esa
batalla.

### Origen

- `carter_v5/mcp_server.py` (186 LOC): stdio + HTTP modes, 3 handlers
  (initialize, tools/list, tools/call).
- Spec MCP: `modelcontextprotocol.io/`.

### Plan de port — Baxy

**Archivo nuevo**: `gemma4_agent/mcp_server.py` (~250 LOC). Port casi directo
de `carter_v5/mcp_server.py` con dos cambios:

1. `_build_tool_list()` lee de `COMPOUND_TOOL_SCHEMAS` de Baxy (62 tools).
2. `_handle_tools_call()` dispatcha al agente Baxy vía `Toolbelt.execute()`.

Modos:
- `python -m gemma4_agent.tools_pkg.mcp_server` → stdio (Claude Desktop default).
- `python -m gemma4_agent.tools_pkg.mcp_server --port 8765` → HTTP.

**Wiring en `launcher.py`**:

```python
# Nuevo subcomando:
mcp = sub.add_parser("mcp", help="Expose Baxy tools as MCP server")
mcp.add_argument("--port", type=int, default=None)
```

**Documentación** (`docs/MCP.md`):

```markdown
# Baxy como MCP server

## Para Claude Desktop

En `~/.config/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "gemma4": {
      "command": "python",
      "args": ["-m", "gemma4_agent.mcp_server"]
    }
  }
}
```

## Para Goose

```bash
goose config add gemma4-mcp --command "python -m gemma4_agent.tools_pkg.mcp_server"
```
```

### Testing

- Smoke con `curl` al modo HTTP:
  ```bash
  python -m gemma4_agent.tools_pkg.mcp_server --port 8765 &
  curl -X POST http://127.0.0.1:8765/mcp -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
  ```
- Verificar shape de respuesta MCP-compliant.

### Riesgos

- **Tools que requieren confirmación** (e.g. `filesystem.delete`) pueden
  no funcionar bien sobre MCP porque MCP es stateless. Mitigación: para esa
  primera versión, deshabilitar tools destructivas sobre MCP (whitelist
  de tools "safe-to-expose").
- **VRAM compartida**: si Cursor y la GUI de Baxy corren a la vez, el
  llama-server tiene un solo slot. Documentar.

---

# Cronograma sugerido

## Semana 1 — Loop detection + Verifier (TIER 1 #1 + #2)

- Día 1: Port `loop_detection.py` + tests + wire en `run_content`.
- Día 2: Smoke en agente real, ajustar constantes según observación.
- Día 3-4: `verify_core.py` + `verifiers.py` para 5 tools (app, filesystem, audio, window, terminal).
- Día 5: Wire en `run_content` + tests + smoke. Commit.

## Semana 2 — Microagents + Skills (TIER 1 #3 + #4)

- Día 1: Port `microagents.py` + 4 microagents iniciales (glossary, troubleshoot, windows_commands, tools_cheat_sheet).
- Día 2: Smoke con queries que matcheen triggers. Commit.
- Día 3-4: Port `skills_registry.py` + tool `skill_load` + 5 skills iniciales.
- Día 5: Smoke con `skill_load(install-steam-game)`. Commit.

## Semana 3 (opcional) — MCP + cosas pendientes

- Día 1-2: Port `mcp_server.py` + docs + smoke con Claude Desktop config.
- Día 3-5: Polish, escribir audit/PORTING_LOG.md con métricas.

## Total estimado

- TIER 1 completo (4 patrones): **2 semanas**.
- TIER 1 + #7 MCP: **2.5 semanas**.
- TIER 1 + #5 mission goal + #7: **3.5 semanas**.

# Decisiones de diseño no negociables

Heredadas de Carter v5 ContextoCarter.md (25 valores) que ya aplican a Baxy:

1. **Honesty by construction**: no decir "listo" sin verifier confirmed.
2. **Multilingüe estructural**: regex multilingüe sin keyword lists per idioma.
3. **Sin per-app hardcodes**: skills usan tools genéricos, no `if Steam`.
4. **Sin contaminación de ventana activa**: ya está en CORE_PROMPT.
5. **Tools caras (vision, GUI) on-demand**: skills + microagents NO incluyen vision por default.

# Métricas de éxito post-port

Medir en el log real del agente:

| Métrica | Hoy | Target post-port |
|---|---|---|
| Tool calls totales por turn (promedio) | ~3 | ~2 (loop detector corta antes) |
| Mensajes "abrió Steam pero no abrió" reportados | ocasional | 0 (verifier los reescribe) |
| Workflows complejos (install-game, etc.) | no soportados | soportados via skills |
| Tiempo entre user input y tool_call (promedio) | ~2-3s (post fase 3) | igual o mejor (no afecta) |
| Capacidad para usar Baxy desde Cursor / Claude Desktop | no | sí (post MCP) |

# Apéndice: archivos clave a leer antes de portar

Pre-port:

- `carter_v5/loop/detection.py` (239 LOC)
- `carter_v5/verify/core.py` (423 LOC)
- `carter_v5/verify/runtime.py` (244 LOC)
- `carter_v5/microagents/loader.py` (131 LOC)
- `carter_v5/microagents/glossary.md`, `troubleshoot.md`, `windows_commands.md` (ejemplos)
- `carter_v5/skills/registry.py` (357 LOC)
- `carter_v5/skills/purchase-guard/SKILL.md`, `install-game/SKILL.md` (ejemplos)
- `carter_v5/mission/verifier.py` (162 LOC) — solo si vamos a TIER 2 #5
- `carter_v5/mcp_server.py` (186 LOC)

Tests de Carter (para referencia, no portar):

- `carter_v5/tests/` — ver qué cubren para no inventar tests redundantes.

# Apéndice: lo que NO portamos (decisiones explícitas)

| Carter v5 / Competidor | Por qué NO portar |
|---|---|
| `carter_v5/core/durable_state.py` | Cubierto por TIER 2 #6, postpuesto |
| `carter_v5/microagents/skills_workflow.md` (skill chains que disparan otras skills) | Sobre-ingeniería para nuestro caso; no soportado en spec MCP |
| `Carter_v3/plan_execute` | Probado y revertido en Carter v4 |
| OpenHands runtime containerization | Scope creep, ya tenemos sandbox por subprocess |
| LangGraph `Send` parallel | Ya tenemos `parallel_tool_calls` en `t_agent` |
| AutoGen multi-agent group chat | Subagent ya cubre el caso |
| Mark XXXIX voice loop | Ya tenemos Whisper+Piper+Vosk |
| Agent S trajectory memory con vision | Postergar hasta tener log con vision real |

---

**Fin del plan**. Aprobación pendiente. Próximo paso: ejecutar Semana 1 día 1.
