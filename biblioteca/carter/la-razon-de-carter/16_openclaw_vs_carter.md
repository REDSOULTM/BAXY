# 16 — openclaw vs Carter v5: análisis profundo + plan de portación

**Fecha**: 2026-05-11
**Trigger**: el usuario observó que openclaw funciona efectivamente con Gemma 4 mientras Carter v5 lucha con tareas GUI complejas. Pidió investigar openclaw a fondo y portar lo mejor sin romper Carter.

**Insumos**: análisis de `Extras/Competidores/openclaw-main` (3 sub-agentes paralelos = ~2h equivalentes de investigación), docs oficiales online ([openclaw.ai](https://openclaw.ai), [docs.openclaw.ai](https://docs.openclaw.ai)), análisis del SKILL.md de `browser-automation`, lectura de `cdp.ts`, `chrome-mcp.ts`, plugin manifests, system de memoria.

---

## TL;DR

openclaw resuelve **3 problemas que Carter v5 también tiene**, con patrones elegantes y portables:

1. **GUI agency sin vision**: serializa el árbol de accesibilidad (ARIA en browsers, UIA en Windows) a texto plano con refs estables (`[ref=e3]`). El LLM lee texto, decide `act ref=e3`, openclaw resuelve. NO usa screenshots como input, NO usa coordenadas, NO usa VLM. **Por eso funciona perfecto con Gemma 4** — el modelo juega a su fortaleza (texto), no a su debilidad (vision).

2. **Workspace persona modular**: separa SOUL.md (personalidad), IDENTITY.md (nombre/vibe), TOOLS.md (infra local), USER.md (sobre el humano), HEARTBEAT.md (proactive checklist), MEMORY.md (memorias curadas). Carter tiene `prompt.py` monolítico — falta modularización.

3. **Robustez al output del LLM**: `tool-call-argument-repair.ts` extrae JSON balanced de respuestas malformed; `tool-call-normalization.ts` matchea tool names case-insensitive con segment fallback. Carter sufre cuando Gemma 4 emite JSON ruidoso; este es código portable directamente.

**Lo que openclaw NO tiene** (y que pensaba que tenía): control de apps nativas Windows/macOS. openclaw es **browser-only** para GUI (CDP + ARIA tree). `phone-control/` es allowlist, no UI; `openshell/` es SSH. **Carter SÍ tiene la pieza nativa** (`gui_universal.py:_enumerate_clickable_uia`) — falta serializarla como ARIA tree.

---

## 1. Patrón GUI: ARIA tree text + refs estables

### Cómo lo hace openclaw

Browser extension (`extensions/browser/src/browser/`):

```
1. tool("browser", action="snapshot", targetId="t1", refs="aria")
   → CDP: Accessibility.getFullAXTree
   → buildRoleTree() — filter INTERACTIVE_ROLES, CONTENT_ROLES with name
   → render con indentación 2 espacios + refs e1, e2, ...:

      - main
        - heading "Welcome" [ref=e1]
        - searchbox "Search" [ref=e2]
        - button "Sign in" [ref=e3]

2. LLM lee este texto, emite tool("browser", action="act", kind="click", ref="e3")

3. refLocator(page, "e3") en pw-session.ts:984
   → locator(`aria-ref=e3`).click()  ← Playwright durable refs
   → success o "Unknown ref e3. Run new snapshot."

4. Skill instruye: "after navigation/modal change, snapshot again"
```

**Innovaciones críticas**:
- Refs `[nth=0]` `[nth=1]` para duplicados (`role:name` collision)
- 3 sets estáticos: `INTERACTIVE_ROLES` (buttons, links, inputs), `CONTENT_ROLES` (headings, text), `STRUCTURAL_ROLES` (main, nav)
- `compact` mode (drops structural without refs in subtree)
- `interactive` mode (flat list, one line per actionable)
- Truncation explícita con marker `[...TRUNCATED - page too large]`
- Stale-ref recovery delegada al modelo (fail fast, model retries con nuevo snapshot)

**Por qué Gemma 4 lo maneja bien**: el modelo NO necesita razonamiento visual. Solo lee texto estructurado. Las tareas como "instala Doom Eternal" se reducen a:

```
- main
  - heading "Doom Eternal"
  - button "Instalar" [ref=e42]
  - button "Comprar" [ref=e43]
```

LLM emite `click e42`. Punto. Sin coordenadas, sin pixels.

### Cómo lo hace Carter v5

[carter_v5/tools/gui_universal.py:150](carter_v5/tools/gui_universal.py#L150) — `_enumerate_clickable_uia()`:

```python
elements.append({
    "name": name,
    "control_type": ctype,         # "ButtonControl", "MenuItemControl", etc.
    "bbox": (l, t, r, b),
    "automation_id": node.AutomationId or "",
})
```

Devuelve lista flat sin árbol, sin refs estables, sin filtering por rol. El LLM debe matchear por descripción ("botón Instalar"), Carter hace fuzzy match en código (línea 202+). Frágil cuando hay duplicados (`"BIBLIOTECA"` matcheó `"Filtros de la biblioteca"` token-match 100%).

### Gap concreto

| Aspecto | openclaw | Carter v5 |
|---|---|---|
| Estructura | Árbol indentado con depth | Lista flat |
| Refs estables | Sí (`e1`, `e2`, persisten en aria-ref) | No (debe re-match por nombre cada vez) |
| Duplicate handling | `[nth=0]`, `[nth=1]` automático | Fuzzy match con scoring |
| Filtering | `INTERACTIVE_ROLES` + `CONTENT_ROLES` constantes | Hardcoded set en función |
| Stale recovery | Fail-fast, model retries | Loop interno de retry |
| Format | Pure text, LLM-readable | dict, requiere serialización ad-hoc |

### Plan de portación (P0 — máximo ROI)

**Archivo nuevo**: `carter_v5/tools/uia_snapshot.py` (~200 LOC).

**API target**:
```python
def take_uia_snapshot(
    hwnd: int | None = None,           # current foreground if None
    interactive_only: bool = False,    # only actionable elements
    compact: bool = False,             # drop structural empty
    max_chars: int = 8000,             # context budget
) -> UiaSnapshot:
    """Returns text + ref_map."""

@dataclass
class UiaSnapshot:
    text: str                          # indented serialized tree
    refs: dict[str, dict]              # {"e1": {role, name, runtime_id, ...}}
    truncated: bool
```

**Composite tool nuevo**: `gui(action="snapshot")` y `gui(action="act", ref="e7")` reemplazan el `gui(locate, click)` actual. El composite_dispatcher rutea.

**Ref resolution**: usar `UIAutomationElement.GetRuntimeId()` que Windows garantiza estable durante la vida del elemento. Cuando el ref es stale → fail con mensaje claro, agente re-snapshotea.

**Sets de roles** (constantes en módulo):
```python
INTERACTIVE_CONTROLS = frozenset({
    "ButtonControl", "MenuItemControl", "HyperlinkControl",
    "TabItemControl", "ListItemControl", "TreeItemControl",
    "EditControl", "ComboBoxControl", "CheckBoxControl",
    "RadioButtonControl",
})
CONTENT_CONTROLS = frozenset({
    "TextControl", "HeaderControl", "GroupControl",
})
STRUCTURAL_CONTROLS = frozenset({
    "WindowControl", "PaneControl", "ToolBarControl",
    "StatusBarControl", "MenuBarControl",
})
```

**ROI estimado**: probablemente saca a Carter del "no puede instalar Steam game" sin necesitar Agent-S ni VLM. Bajo riesgo porque coexiste con `gui_universal.py` actual.

---

## 2. Workspace persona modular

### Cómo lo hace openclaw

`src/agents/workspace.ts:21-28`:

```typescript
DEFAULT_AGENTS_FILENAME = "AGENTS.md";      // operating rules
DEFAULT_SOUL_FILENAME = "SOUL.md";          // persona/personality
DEFAULT_TOOLS_FILENAME = "TOOLS.md";        // local infra
DEFAULT_IDENTITY_FILENAME = "IDENTITY.md";  // name, vibe, emoji
DEFAULT_USER_FILENAME = "USER.md";          // about the human
DEFAULT_HEARTBEAT_FILENAME = "HEARTBEAT.md";// proactive checklist
DEFAULT_BOOTSTRAP_FILENAME = "BOOTSTRAP.md";// first-run ritual (self-deletes)
DEFAULT_MEMORY_FILENAME = "MEMORY.md";      // long-term curated
```

**Innovación**: separa lo *fijo* (SOUL persona) de lo *aprendido* (IDENTITY, completada en BOOTSTRAP conversando con humano) de lo *operacional* (TOOLS rutas locales). Subagentes solo reciben AGENTS+TOOLS — workspace.ts:690-698 `MINIMAL_BOOTSTRAP_ALLOWLIST`.

**BOOTSTRAP ritual**: primer arranque, agente conversa con humano para llenar IDENTITY+USER, después se auto-borra. "Rito de nacimiento".

### Cómo lo hace Carter v5

Todo el system_prompt vive en [carter_v5/core/prompts.py](carter_v5/core/prompts.py) hardcodeado en Python. No hay separación entre persona/identidad/operación. Carter tiene `ContextoCarter.md` que es estilo prosa, no telegraph.

### Gap

| Aspecto | openclaw | Carter v5 |
|---|---|---|
| Persona file | SOUL.md (editable por user) | Hardcoded en prompts.py |
| Identidad mutable | IDENTITY.md (agente learns) | No existe |
| Info local infra | TOOLS.md | Hardcoded |
| Info user | USER.md (learns sobre humano) | memory.db pero no exportable a texto |
| Subagent filter | MINIMAL_BOOTSTRAP_ALLOWLIST | N/A (Carter no tiene subagents formales) |
| Bootstrap | BOOTSTRAP.md self-deleting | N/A |

### Plan de portación (P1 — alto valor pero más trabajo)

**Archivos nuevos**: en `~/.carter_v5/workspace/` (o configurable):

```
~/.carter_v5/workspace/
├── AGENTS.md          ← reglas operativas (telegraph style, port de prompts.py reglas)
├── SOUL.md            ← personalidad Rioplatense, honestidad, etc.
├── IDENTITY.md        ← "soy Carter, RTX 4060 Ti, Gemma 4 26B-A4B..."
├── USER.md            ← lo que Carter aprende de usuario
├── TOOLS.md           ← C:\llamacpp-cuda\, paths de modelos, etc.
└── MEMORY.md          ← memoria curada exportable
```

**Loader**: en `core/context_builder.py`, leer estos archivos al boot y concatenarlos al system_msg. Editables sin tocar código.

**BOOTSTRAP**: primer arranque sin IDENTITY.md → agente pregunta "¿cómo querés que te trate?" y llena IDENTITY+USER.

**ROI**: alta personalización sin recompilar. Bajo riesgo si se mantiene `prompts.py` como fallback.

---

## 3. Tool call robustness — JSON malformado y nombres ambiguos

### Cómo lo hace openclaw

`src/agents/pi-embedded-runner/run/attempt.tool-call-argument-repair.ts`:
- `extractBalancedJsonPrefix()`: extrae JSON válido del prefix cuando Gemma/Qwen emiten texto extra antes/después
- Maneja JSON truncado por max_tokens

`attempt.tool-call-normalization.ts`:
- Case-insensitive tool name matching
- Segment fallback: `functions.foo.bar` → `bar`
- Para outputs ruidosos de modelos locales

`provider-tools.ts`:
- `cleanSchemaForGemini()`: quita keywords JSON Schema que provider no soporta
- `XAI_UNSUPPORTED_SCHEMA_KEYWORDS`: similar para xAI

### Cómo lo hace Carter v5

[carter_v5/adapters/llamacpp.py](carter_v5/adapters/llamacpp.py) hace parsing OpenAI-compat directo. **No tiene repair**, no tiene normalización. Si Gemma 4 emite JSON malformed, Carter falla con `JSONDecodeError`.

### Gap

Carter v5 ya vio bugs por este tema en sesión 1: el LLM emitía text + JSON mezclados o nombres tool mayúsculas/minúsculas distintas.

### Plan de portación (P0 — código bajo riesgo, alto ROI)

**Archivo nuevo**: `carter_v5/adapters/tool_call_repair.py` (~100 LOC).

```python
def extract_balanced_json_prefix(text: str) -> tuple[dict | None, str]:
    """Find first balanced JSON object in text. Returns (parsed, rest)."""

def normalize_tool_name(name: str, registry: set[str]) -> str | None:
    """Case-insensitive + segment fallback. 'Functions.GUI.click' → 'gui'."""

def repair_tool_call(raw: dict, registry: set[str]) -> dict | None:
    """Try to fix a malformed tool_call. None = unfixable."""
```

Llamarlo en `llamacpp.py` después de parsear `tool_calls`. Si falla parse, intenta repair antes de retornar error.

**ROI**: arregla bugs intermitentes con Gemma 4 sin tocar el agent loop. Bajo riesgo.

---

## 4. Memory system — dreaming, active recall, wiki

### Cómo lo hace openclaw

**4 capas ortogonales**:

1. **`memory-core`** (`extensions/memory-core/`): tools `memory_get`, `memory_search`. Backend que decide dedupe/retention.
2. **`memory-lancedb`**: vector store pluggable con LanceDB para semantic search.
3. **`active-memory`**: **sub-agente blocking pre-reply**. Antes de responder al user, lanza un mini-agente con timeout+circuit-breaker que llama `memory_recall` y devuelve summary inyectado al system prompt.
4. **`memory-wiki`**: compila memorias durables a vault Obsidian-compatible. El humano puede leer/editar lo que Carter "sabe".

**Dreaming** (`src/dreaming-phases.ts`):
- **Light** (frecuente): dedupe por similarity cosine, escribe a daily file
- **REM** (mid-frequency): extrae reflections + candidate-truths, agrupa por tag, patrón recurrente → belief
- **Deep** (raro): consolida high-recall/high-score en long-term wisdom

Cron `0 3 * * *` (3 AM). Inspiración: el agente "duerme" y procesa.

### Cómo lo hace Carter v5

[carter_v5/memory/store.py](carter_v5/memory/store.py): SQLite key-value plano + multilingual-e5-small embeddings para recall semántico. Sin dreaming, sin sub-agent active recall, sin wiki export.

### Plan de portación (P2 — high value, medium effort)

**Pieza más valiosa**: active-memory sub-agent. ~50 LOC en `agent_base.py`:

```python
def _active_memory_preamble(self, user_text: str) -> str:
    """Pre-turn: call memory.search() with timeout + circuit breaker.
    Returns summary <500 chars to inject into system prompt this turn."""
```

**Dreaming**: cron job nightly (3 AM) que corre `python -m carter_v5.memory.dreaming light|rem|deep`. Light siempre, REM weekly, Deep monthly.

**Wiki**: comando `carter wiki compile` que exporta `memory.db` a `~/.carter_v5/wiki/` markdown.

---

## 5. Skills eligibility + install manifests

### openclaw

`SkillSnapshot` (`src/agents/skills/types.ts:95`) tiene `requires: { bins, env }` y `install: [{ kind: "brew", formula: "jq" }, ...]`. El runtime chequea antes de exponer la skill — si falta `jq`, ni se menciona al LLM. Si el LLM la pide, puede ejecutar el install block.

### Carter v5

Skills system ya existe (Anthropic format) pero todas las skills están siempre visibles. Si una skill usa `pycaw` y no está instalado, el LLM la intenta y falla.

### Plan de portación (P1)

Agregar `requires:` y `install:` opcionales al frontmatter de SKILL.md de Carter:

```yaml
---
name: install-game
description: ...
priority: high
requires:
  bins: ["steam"]      # solo expone si steam.exe está en PATH
  env: []
install:
  - kind: download
    url: https://store.steampowered.com/about/
    label: "Install Steam from steampowered.com"
---
```

Filter en `skills/registry.py:scan_skills()` antes de armar el menú.

---

## 6. Heartbeat / proactive mode

### openclaw

`HEARTBEAT.md` + cron 30min. Prompt fijo: *"Read HEARTBEAT.md if it exists. Follow it strictly. If nothing needs attention, reply HEARTBEAT_OK."*

Anti-spam:
- File-empty skip
- `HEARTBEAT_OK` token suppression
- `directPolicy: "block"` para DMs
- AGENTS.md telegraph instruye al modelo a usar `memory/heartbeat-state.json` para rotar checks

### Carter v5

No tiene proactive loop. Carter solo responde cuando el user habla.

### Plan de portación (P2)

`carter_v5/heartbeat/runner.py` + script Windows Task Scheduler. Bajo riesgo, alto valor cuando el usuario quiera Carter "tipo Tamagotchi".

---

## 7. Telegraph style AGENTS.md

### openclaw

Reglas como bullets imperativos cortos, sin prosa. ~200 líneas alta densidad informacional, bajo token-burn.

### Carter v5

`prompts.py STANDARD` tiene 13580 chars (~3400 tokens) en prosa con "User: ... → tool_call(X)". Funciona pero verbose.

### Plan (P1)

Refactor incremental de `prompts.py` a estilo telegraph. **Riesgo**: el prompt actual está validado con bench 540. Hay que medir antes de cambiar.

---

## 8. Lo que openclaw NO tiene (y Carter SÍ necesita)

| Capacidad | openclaw | Carter v5 |
|---|---|---|
| Apps nativas Windows (UIA) | ❌ | ✅ (`gui_universal.py`) |
| Apps nativas macOS (AX) | ❌ | N/A |
| OCR fallback | Solo `labels=true` browser | ✅ PaddleOCR Tier 2 |
| Deeplinks Steam/Spotify | ❌ | ✅ `deeplinks.py` |
| Audio local (Whisper) | Via plugins remotos | ✅ planeado |
| Backend local 100% offline | Vía Ollama plugin | ✅ llama-server nativo |
| Tool calling sin native function-call | ❌ (asume OpenAI-compat) | ✅ `ollama_xml.py` fallback |

**Carter NO debería intentar ser openclaw.** Carter es Windows-first local-first agente. openclaw es cloud-friendly browser-first chat-gateway. Son complementarios.

---

## Plan de portación priorizado

### P0 — máximo ROI / mínimo riesgo (próximos días)

1. **UIA tree serializer + refs estables** ([1])
   - Archivo nuevo: `carter_v5/tools/uia_snapshot.py`
   - Composite tool nuevo: `gui(action="snapshot")`, `gui(action="act", ref="e7")`
   - Reescribir `install-game` skill para usar este loop
   - **Resuelve directamente el bug "instala doom eternal"**

2. **Tool call repair** ([3])
   - Archivo nuevo: `carter_v5/adapters/tool_call_repair.py`
   - Integrar en `llamacpp.py`
   - **Resuelve bugs intermitentes de JSON malformed con Gemma 4**

### P1 — alto valor, medium effort (próxima semana)

3. **Skills requires/install manifests** ([5])
   - Extender frontmatter SKILL.md
   - Filter en `skills/registry.py`

4. **Workspace persona modular** ([2])
   - Crear `~/.carter_v5/workspace/{AGENTS,SOUL,IDENTITY,USER,TOOLS}.md`
   - Loader en `core/context_builder.py`

5. **Telegraph refactor de prompts.py** ([7])
   - Medir antes/después con bench 540
   - Solo aplicar si pass-rate ≥ baseline

### P2 — alto valor, mayor effort (próximas 2-4 semanas)

6. **Active-memory sub-agent** ([4])
   - Pre-turn blocking recall con circuit breaker

7. **Dreaming cron jobs** ([4])
   - Light/REM/Deep memory consolidation

8. **Memory wiki compile** ([4])
   - Export `memory.db` → vault navegable

9. **Heartbeat proactive mode** ([6])
   - Cron + HEARTBEAT.md + token suppression

### NO portar (decisiones explícitas)

- Plugin TypeScript SDK: Carter es Python, romper stack no vale el costo
- Channels (WhatsApp/Discord/Slack): Carter es local-first, no gateway
- Pi-ai dependency: Carter ya tiene `llamacpp.py` propio
- CDP/Playwright: Carter es Windows-native, no browser-first

---

## Conclusión

openclaw NO es competidor de Carter — es **complementario en filosofía**: openclaw cubre browser + chat-channels, Carter cubre Windows nativo + voice. Pero openclaw resolvió 3 problemas que Carter tiene:

1. **GUI agency text-based** (ARIA tree + refs) → portable a UIA en Windows
2. **Workspace persona modular** → portable directamente
3. **Tool call robustness** → portable directamente

El **paso P0 (UIA snapshot + refs)** probablemente es la diferencia entre Carter "tropieza con Steam" y Carter "instala el juego como si fueras vos haciéndolo". Es el patrón que faltaba.

**Referencias**:
- openclaw browser SKILL: `Extras/Competidores/openclaw-main/extensions/browser/skills/browser-automation/SKILL.md`
- ARIA serializer: `extensions/browser/src/browser/chrome-mcp.snapshot.ts`
- CDP path: `extensions/browser/src/browser/cdp.ts`
- Workspace: `src/agents/workspace.ts`
- Dreaming: `src/dreaming-phases.ts`
- Active-memory: `extensions/active-memory/index.ts`
- Docs: <https://docs.openclaw.ai>
