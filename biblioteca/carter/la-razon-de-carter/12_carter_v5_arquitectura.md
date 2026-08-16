# 12 — Arquitectura Carter v5

**Fecha**: 2026-05-11
**Pre-requisito**: leer `11_lecciones_v1_a_v4.md` (errores y validaciones medidas).
**Objetivo**: arquitectura **multi-perfil por VRAM**, basada en Gemma 4, que evita los 13 anti-patrones identificados.

---

## 1. Principios de diseño (de las 10 lecciones)

| # | Principio | Implementación |
|---|---|---|
| P1 | TODO sobre Gemma 4 | Cada tier elige una quant Gemma 4 según VRAM disponible |
| P2 | Honestidad por construcción (V3) | Verifier estructural + Mission goal + `UNVERIFIED` honesto |
| P3 | Universal, sin per-app (V6, V7) | Resolve_app + HKCR registry + SequenceMatcher 0.75 |
| P4 | Prompt estable preserva cache | system_msg fijo por sesión, history append-only |
| P5 | Catalog estable preserva cache | Tools fijas por tier (consolidated 16), no retrieval dinámico |
| P6 | Verifier por-misión + per-tool | MissionGoal estructural + outcomes per-tool como señal |
| P7 | UN router pre-LLM, sin solapamiento | core/router.py único |
| P8 | Bench como sanity, calidad como criterio | Bench cada cambio + review de respuestas reales |
| P9 | Cada cambio medible aislado | Una variable por iteración + golden tests |
| P10 | Trabajo determinista FUERA del LLM | LLM = interpretar + descomponer + explicar. Código = todo lo demás |

---

## 2. Estructura de carpetas

```
Carter OS AI/
├── Carter_v4_legacy/             ← v4 entero (snapshot, read-only)
│   └── (estructura actual completa, no se toca)
│
├── carter_v5/                    ← repo nuevo, paralelo
│   ├── core/                     ← código compartido por todos los perfiles
│   │   ├── __init__.py
│   │   ├── agent_base.py         ← Base class con while loop minimal (~200 LOC)
│   │   ├── router.py             ← UN router pre-LLM (~150 LOC)
│   │   ├── execution.py          ← dispatch + verify + chain (~200 LOC)
│   │   ├── reply.py              ← assemble reply final (~80 LOC)
│   │   ├── context_builder.py    ← system_msg STABLE prefix (~100 LOC)
│   │   └── observability.py      ← jsonl tracing per turn (~80 LOC)
│   │
│   ├── mission/                  ← código compartido
│   │   ├── goal.py               ← MissionGoal (Voyager pattern)
│   │   ├── outcome.py            ← 9 estados estructurales
│   │   └── verifier.py           ← composición per-tool + mission_goal
│   │
│   ├── tools/                    ← compartidos (NO duplicados por tier)
│   │   ├── _base.py              ← @tool decorator
│   │   ├── registry.py           ← get_catalog, dispatch
│   │   ├── apps.py               ← (copiado de v4: resolve_app universal)
│   │   ├── gui.py                ← (copiado de v4: causal focus + win32)
│   │   ├── gui_universal.py      ← (copiado de v4: 5 tiers UIA/OCR/VLM)
│   │   ├── filesystem.py         ← (copiado de v4: sandbox)
│   │   ├── web.py                ← (copiado de v4: deeplink-first)
│   │   ├── deeplink.py           ← (copiado de v4: HKCR)
│   │   ├── system.py             ← (copiado de v4: pycaw)
│   │   ├── terminal.py           ← (copiado de v4)
│   │   ├── vision_tools.py       ← (copiado de v4: enable_thinking:False)
│   │   ├── memory_tool.py        ← (copiado de v4)
│   │   ├── clipboard.py          ← (copiado de v4)
│   │   ├── media.py              ← (copiado de v4)
│   │   ├── office.py             ← (copiado de v4)
│   │   ├── registry.py           ← (copiado de v4)
│   │   ├── composite_dispatcher.py ← (copiado de v4: 16→60 routing)
│   │   └── schemas_consolidated.json ← (copiado del harness ganador)
│   │
│   ├── adapters/                 ← compartidos
│   │   ├── llamacpp.py           ← (copiado de v4: chat + chat_stream + Gemma quirks)
│   │   └── base.py               ← LLMAdapter protocol
│   │
│   ├── verify/                   ← compartidos
│   │   ├── core.py               ← (copiado de v4: VerifierOutcome + register)
│   │   └── runtime.py            ← (copiado de v4: pycaw + EnumWindows + frame_diff)
│   │
│   ├── memory/                   ← compartido
│   │   └── store.py              ← (copiado de v4: SQLite + embedder)
│   │
│   ├── safety/                   ← compartido
│   │   └── intent.py             ← (copiado de v4: destructive intent Snowball)
│   │
│   ├── loop/                     ← compartido
│   │   └── detection.py          ← (copiado de v4: v2 result-aware)
│   │
│   ├── hardware/                 ← compartido
│   │   ├── detect.py             ← (copiado de v4: nvidia-smi)
│   │   └── profile.py            ← selector tier por VRAM
│   │
│   ├── profiles/                 ← ⭐ POR TIER (lo diferente)
│   │   ├── tier_6gb/             ← Carter mínimo viable
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          ← Agent6GB(AgentBase): loop super-simple
│   │   │   ├── prompt.py         ← CORE_PROMPT recortado (~800 tok)
│   │   │   ├── config.py         ← model, sampling, anchors, tools visibles
│   │   │   └── tools_subset.py   ← qué tools expone (subset reducido)
│   │   │
│   │   ├── tier_8gb/             ← Balanced
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          ← Agent8GB(AgentBase): + cadenas cortas
│   │   │   ├── prompt.py         ← (~1000 tok)
│   │   │   ├── config.py
│   │   │   └── tools_subset.py
│   │   │
│   │   ├── tier_10gb/            ← Medio
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          ← Agent10GB(AgentBase): + MissionGoal
│   │   │   ├── prompt.py         ← (~1200 tok)
│   │   │   ├── config.py
│   │   │   └── tools_subset.py
│   │   │
│   │   ├── tier_12gb/            ← High quality
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          ← Agent12GB(AgentBase): + vision inline
│   │   │   ├── prompt.py         ← (~1400 tok)
│   │   │   ├── config.py
│   │   │   └── tools_subset.py
│   │   │
│   │   └── tier_16gb/            ← Full power (validado 540/540)
│   │       ├── __init__.py
│   │       ├── agent.py          ← Agent16GB(AgentBase): full features
│   │       ├── prompt.py         ← (CORE_PROMPT v3 completo, 143 líneas)
│   │       ├── config.py
│   │       └── tools_subset.py   ← 16 composite tools completas
│   │
│   ├── tests/
│   │   ├── unit/                 ← tests por módulo (mover de v4 los útiles)
│   │   │   └── test_*.py
│   │   ├── integration/          ← golden paths con mock LLM
│   │   │   └── test_agent_per_tier.py
│   │   └── bench/                ← orchestrador bench 540 per tier
│   │       └── run_bench.py
│   │
│   ├── scripts/
│   │   ├── start_carter.py       ← bootstrap: detect VRAM → spawn llama-server → REPL
│   │   ├── start_llama_server.ps1 ← arrancar llama-server con flags tier
│   │   └── compare_baseline.py   ← diff vs Carter v4 legacy
│   │
│   ├── cli.py                    ← REPL principal
│   └── pyproject.toml            ← deps + package config
│
└── La razon de carter/           ← documentación
    ├── 00_estado_actual.md
    ├── 01_auditoria_arquitectura.md
    ├── ...
    ├── 11_lecciones_v1_a_v4.md
    ├── 12_carter_v5_arquitectura.md (este doc)
    ├── 13_carter_v5_perfiles_vram.md (próximo)
    └── benchmarks/               ← JSON results per tier
```

---

## 3. El flujo de un turn en Carter v5 (genérico)

```
USER INPUT
   │
   ▼
┌─────────────────────────────────────────────┐
│ Agent<TIER>.run_turn(user_text)             │
│   (hereda de AgentBase, agrega capacidades  │
│    según tier)                              │
└─────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────┐
│ 1. core/router.py — UN solo router          │
│    → Intent(archetype, mission_goal,        │
│             expected_outcomes, profile)     │
└─────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────┐
│ 2. Pre-LLM short-circuit (si trivial)       │
│    → reply directo sin LLM                  │
└─────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────┐
│ 3. core/context_builder.py                  │
│    → system_msg STABLE (cache-friendly)     │
│    → tools_subset[TIER] (16 composite)      │
│    → history append-only                    │
└─────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────┐
│ 4. LLM call #1 (llama-server :8080)         │
│    sampling: T=1.0, top_p=0.95, top_k=64    │
└─────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────┐
│ 5. core/execution.py                        │
│    while tool_calls:                        │
│      a. safety.evaluate (confirm si dest)   │
│      b. tools.dispatch                      │
│      c. verify.verify (per-tool)            │
│      d. mission.update_with_tool            │
│      e. loop_detection.check                │
│      f. if mission.is_fulfilled: break      │
│      g. LLM call #N+1 (follow-up)           │
└─────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────┐
│ 6. mission/verifier.py                      │
│    → final outcome:                         │
│      COMPLETED | PARTIAL | UNVERIFIED       │
│      FAILED | NEEDS_USER | NEEDS_PERMISSION │
│      BLOCKED_BY_POLICY | INTENT_NOT_FULFILLED│
└─────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────┐
│ 7. core/reply.py                            │
│    → reply final (sin rewriter agresivo)    │
│    → footer honesto si outcome != COMPLETED │
└─────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────┐
│ 8. observability/tracing.py                 │
│    → jsonl trace: {ts, trace_id, user_text, │
│       archetype, tools, outcome, latency_ms}│
└─────────────────────────────────────────────┘
   │
   ▼
TurnResult(reply, tool_calls, outcomes, outcome)
```

---

## 4. Diferencias por tier (qué hace cada Agent<TIER>)

| Capacidad | tier_6gb | tier_8gb | tier_10gb | tier_12gb | tier_16gb |
|---|:---:|:---:|:---:|:---:|:---:|
| Pre-LLM short-circuit triviales | ✅ | ✅ | ✅ | ✅ | ✅ |
| Tools simples (1 tool) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Cadenas cortas (2-3 tools) | limitado | ✅ | ✅ | ✅ | ✅ |
| Cadenas largas (4+ tools) | ❌ | limitado | ✅ | ✅ | ✅ |
| MissionGoal verifier | básico | básico | ✅ | ✅ | ✅ |
| Vision tools (mmproj) | ❌ | ❌ | opcional | ✅ | ✅ |
| Vision inline auto-step | ❌ | ❌ | ❌ | ✅ | ✅ |
| Memory (SQLite) | mínimo | ✅ | ✅ | ✅ | ✅ |
| Streaming SSE | ✅ | ✅ | ✅ | ✅ | ✅ |
| Tracing jsonl | ✅ | ✅ | ✅ | ✅ | ✅ |
| Loop detection v2 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Causal focus | básico | ✅ | ✅ | ✅ | ✅ |

**Justificación**: en tier 6GB, el modelo (E2B-Q4) tiene capacidad limitada de razonamiento → tools limitados, cadenas cortas, sin vision. En tier 16GB (E4B-Q6_K validado 540/540) → todo activado.

---

## 5. Contratos de interfaz (no negociables)

### 5.1 `AgentBase.run_turn(user_text: str) → TurnResult`

```python
@dataclass
class TurnResult:
    user_text: str
    reply: str
    tool_calls: list[ToolCallRecord]      # NUEVO: nombres explícitos
    verifier_outcomes: list[VerifierOutcome]
    mission_outcome: MissionOutcome        # NUEVO: estado mission-level
    latency_ms: int
    trace_id: str                          # NUEVO: jsonl correlation
    pending_confirm: dict | None
```

### 5.2 `Router.route(user_text, history, mission_state) → Intent`

```python
@dataclass(frozen=True)
class Intent:
    archetype: Literal["TRIVIAL", "KNOWLEDGE", "TOOL_SIMPLE",
                       "TOOL_VERIFY", "MISSION", "MISSION_LONG",
                       "DESTRUCTIVE"]
    mission_goal: MissionGoal              # de mission/goal.py
    sampling: TurnProfile                  # T, top_p, etc.
    pre_llm_short_circuit: str | None     # canned reply o None
    forced_action: ToolCall | None         # solo si trivialmente determinístico
    expected_tools: list[str]              # candidatos para retrieval
```

### 5.3 `MissionGoal`

```python
@dataclass
class MissionGoal:
    user_text: str
    expected: list[ExpectedOutcome]
    executed_tools: list[tuple[str, dict, bool]]

    def update_with_tool(self, name: str, args: dict, ok: bool)
    def is_fulfilled(self) -> bool
    def progress(self) -> tuple[int, int]
    def summary(self) -> str
```

### 5.4 `Tool.dispatch(name, args) → dict`

```python
# Tool result contract
{
    "ok": bool,
    "error": str | None,
    "error_kind": Literal["NOT_FOUND", "PERMISSION_DENIED",
                          "TIMEOUT", "INVALID_ARG", "INTERNAL"] | None,
    "verification": {"status": str, "evidence": dict, "reason": str},
    # ... tool-specific fields
}
```

### 5.5 `ModelCapability` (selector por tier)

```python
@dataclass(frozen=True)
class ModelCapability:
    name: str                              # "gemma-4-E4B-Q6_K"
    quant: str                             # "Q6_K"
    vram_gb: float                         # 7.1
    max_tools_visible: int                 # 16 default
    sampling_defaults: dict                # T=1.0 top_p=0.95 top_k=64
    system_prompt_path: str                # prompts/<tier>/prompt.py
    supports_vision: bool                  # mmproj cargado
    supports_thinking_strip: bool          # b9090+ → True
    requires_alt_press_focus: bool         # Windows → True
```

---

## 6. Decisiones de diseño con fundamentación

### 6.1 Repo paralelo `carter_v5/` (NO refactor de v4)

**Por qué**: refactor incremental rompió -13pts en 1 sesión. Repo nuevo permite empezar desde la lección aprendida sin arrastrar debt.

**Fuente**: 11_lecciones §3.1 acumulación sin remoción.

### 6.2 Carpeta por tier (agent + prompt distintos)

**Por qué**: tu decisión explícita. Justificada porque modelos distintos (E2B vs E4B vs 26B-A4B) tienen capacidades distintas y necesitan ser tratados como targets de optimización separados.

**Trade-off**: bugs se arreglan N veces. Mitigación: lógica común en `core/`, solo overrides en `profiles/`.

### 6.3 Tools compartidos (no duplicados por tier)

**Por qué**: las 60 tools (resolve_app, gui_universal, frame_diff verifier, deeplinks, pycaw, etc.) son código probado de utilidad. Re-implementarlas N veces es regresión asegurada.

**Cada tier define qué subset expone al LLM** (en `tools_subset.py`) pero el código de cada tool es común.

### 6.4 Catalog consolidated 16 default

**Por qué**: Probando Gemma 4 midió que consolidated da MISMO PASS rate que individual (-68% tokens). Para Gemma 4 con context 16K es importante.

**Fuente**: `Probando Gemma 4/documentacion/06_consolidacion_tools/`.

### 6.5 system_msg STABLE prefix

**Por qué**: history + memory_facts + archetype-specific blocks cambia entre turns → llama-server invalida KV cache → +1-3s overhead.

**Solución**:
- Prefijo del prompt (system + tools) es FIJO por sesión
- History va como user/assistant messages append-only
- Memory_facts NO se inyectan en system, sino como user prefix del primer turn de la sesión

**Fuente**: 11_lecciones §3.5.

### 6.6 NO retrieval per-turn

**Por qué**: cambia el catalog → cache se rompe. RAG-MCP top-K se aplica UNA SOLA VEZ al cargar la sesión (selecciona tools del subset del tier).

**Fuente**: 11_lecciones §3.6.

### 6.7 MissionGoal estructural sin LLM

**Por qué**: Voyager dice "verifier verifica el OBJETIVO". Carter v5 lo implementa con regex sobre verbos imperativos + matching contra tools ejecutadas. Cero LLM call extra.

**Fuente**: `mission_goal.py` que ya creé en v4 (18 tests passing). Lo migramos tal cual.

### 6.8 Sin step_planner con per-app lists

**Por qué**: viola V7. La detección de archetype se hace estructuralmente (longitud, separadores, verbos imperativos), NO con listas de apps.

**Para "abre Steam"**: el LLM decide. Si la latencia sube, el cost-benefit acepta porque V7 es no-negociable.

### 6.9 Sin retry-with-nudge post-LLM

**Por qué**: 8 capas de rewriter producen "respuestas pobres". Carter v5 confía en el modelo + prompt v3 validado.

**Excepción**: si el LLM emite content vacío + tool_calls vacío, UN retry con mensaje explícito. NO más.

### 6.10 Per-tier model = decisión medida

**Por qué**: tu pedido. Cada tier elige una quant Gemma 4 validada por Probando Gemma 4 según VRAM disponible.

**Detalle en Doc 13.**

---

## 7. Bootstrap & detección de tier

```python
# scripts/start_carter.py (esquema)

def main():
    vram_mb = hardware.detect.detect_vram_mb()
    profile = hardware.profile.select_profile(vram_mb)
    # profile.tier = "tier_16gb" | "tier_12gb" | ... | "cpu_fallback"

    if profile.tier == "cpu_fallback":
        # Ollama qwen3:1.7b
        agent = AgentCPU(profile)
    else:
        # Spawn llama-server con modelo del tier
        spawn_llama_server(profile.model_gguf, profile.flags)
        # Import dinámico del Agent<TIER>
        AgentClass = importlib.import_module(
            f"carter_v5.profiles.{profile.tier}.agent"
        ).Agent
        agent = AgentClass(profile)

    # REPL común
    cli.run_repl(agent)
```

---

## 8. Plan de testing

### 8.1 Tests unitarios (compartidos)
- Per-module en `tests/unit/test_<module>.py`
- ~200 tests target (migrar lo útil de v4)

### 8.2 Tests de integración (per-tier)
- `tests/integration/test_agent_per_tier.py` parametrizado
- Mock LLM con scripts pre-definidos
- Golden paths por archetype

### 8.3 Bench oficial 540 (per-tier)
- `tests/bench/run_bench.py --tier 16gb`
- Per tier, comparar contra baseline v4 (75.93%) y harness ganador (99.81%)

### 8.4 Calidad subjetiva (review humano)
- Smoke test con 20 prompts reales
- Vos revisas respuestas y das veredicto
- NO declaramos éxito sin tu OK

---

## 9. Cronograma realista

| Día | Actividad | Entregable |
|---|---|---|
| 1 | Aprobación Doc 12 + 13 | (este pasaje) |
| 2 | Mover Carter_v4 → Carter_v4_legacy, scaffold carter_v5/ | Repo limpio |
| 3-4 | core/ + tier_16gb/ (target validado 540/540) | Bench 16GB ≥75% PASS |
| 5 | tier_12gb/ | Bench 12GB |
| 6 | tier_10gb/ | Bench 10GB |
| 7 | tier_8gb/ | Bench 8GB |
| 8 | tier_6gb/ | Bench 6GB |
| 9 | Comparativa cross-tier + reporte final | Tabla de PASS rate por tier |
| 10 | Buffer para fixes | — |

**Total: 10 días de trabajo enfocado** (~30-50 horas reales según tu disponibilidad).

---

## 10. Criterios de éxito (no negociables)

Carter v5 declara éxito tier por tier SOLO si:

| Tier | Bench P0 PASS | Latencia tool simple p50 | Latencia trivial p50 | VRAM cargado | Status |
|---|---|---|---|---|---|
| 6GB | ≥70% | ≤8s | ≤5s | ≤5GB | extrapolado |
| 8GB | ≥80% | ≤6s | ≤4s | ≤7GB | extrapolado |
| 10GB | ≥85% | ≤5s | ≤4s | ≤9GB | extrapolado |
| 12GB | ≥90% | ≤4s | ≤3s | ≤11GB | extrapolado |
| **16GB** | **≥95%** | **≤4s** | **≤3s** | **≤14GB** | **validado** |

**Si un tier no llega a su target**, lo documentamos honestamente — NO inflamos números.

---

## 11. Lo que NO va en v5 (explícito)

Para que no haya ambigüedad:

- ❌ Routers compitiendo
- ❌ Per-app hardcodes (`_WEB_APP_URLS`, `_DEEPLINK_APPS`, `_NATIVE_APPS`)
- ❌ Post-LLM rewriter stack (`strip_planning_leakage`, `fix_carter_vocative`, `rewrite_claim_to_unverified` agresivo, `no_action_footer` agresivo)
- ❌ `_looks_like_surrender`, `emitted_tool_as_text`, `canned_trivial` heurísticas
- ❌ Retry-with-nudge LLM call extra
- ❌ History dinámica en system_msg
- ❌ Retrieval per-turn que cambia catalog
- ❌ `plan_mission` con LLM call extra
- ❌ Skill_store auto-LLM-critic (queda como referencia, no se usa en core loop)
- ❌ Audio nativo Gemma 4 (Whisper aparte cuando llegue audio)
- ❌ `--reasoning off`, strip `assistant.content`, KV cache q8_0

---

## 12. Próximo paso

**Leer `13_carter_v5_perfiles_vram.md`** que detalla cada uno de los 5 tiers con:
- Modelo Gemma 4 exacto
- Quant validada
- Sampling
- Tools visibles
- Prompt size
- Criterios de éxito
- Path al `.gguf` en disco

Después de leer Doc 13 vos decís "OK, este diseño me gusta" y arrancamos implementación.
