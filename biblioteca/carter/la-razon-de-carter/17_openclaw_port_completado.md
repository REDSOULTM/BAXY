# 17 — Portación openclaw → Carter v5 COMPLETADA

**Fecha**: 2026-05-11 noche
**Estado**: ✅ Todo P0 + P1 + P2 implementado, 279/279 tests pass.
**Predecesor**: [16_openclaw_vs_carter.md](16_openclaw_vs_carter.md) (análisis y plan)

---

## TL;DR

Porté los **7 patterns** de openclaw que mejoran Carter sin romper nada:

| # | Pattern | Archivo nuevo | Tests | LOC |
|---|---|---|---|---|
| 1 | UIA tree serializer (ARIA-text) | [tools/uia_snapshot.py](../carter_v5/tools/uia_snapshot.py) | 6 | ~440 |
| 2 | `gui(snapshot/act)` composite | [tools/composite_dispatcher.py](../carter_v5/tools/composite_dispatcher.py) | 2 | +30 |
| 3 | install-game skill reescrito | [skills/install-game/SKILL.md](../carter_v5/skills/install-game/SKILL.md) | — | rewrite |
| 4 | Tool call repair (JSON + names) | [adapters/tool_call_repair.py](../carter_v5/adapters/tool_call_repair.py) | 16 | ~230 |
| 5 | Skills `requires:` filter | [skills/registry.py](../carter_v5/skills/registry.py) (+60 LOC) | 7 | +60 |
| 6 | Workspace modular | [core/workspace.py](../carter_v5/core/workspace.py) | 7 | ~240 |
| 7 | Active-memory pre-turn recall | [memory/active_recall.py](../carter_v5/memory/active_recall.py) | 7 | ~160 |
| 8 | Memory wiki export | [memory/wiki.py](../carter_v5/memory/wiki.py) | 4 | ~290 |

**Total**: 51 tests nuevos, 279/279 suite pass (era 228, +51 nuevos), 0 regresiones.

---

## El cambio fundamental: GUI text-based

**Antes** Carter intentaba clickear botones por coordenadas + vision. Gemma 4 26B-A4B no podía coordinar 7 pasos visuales sin perderse.

**Ahora** Carter expone:
```
- Window "Steam"
  - tab "BIBLIOTECA" [ref=e3]
  - button "INSTALAR" [ref=e42]
```

El LLM lee texto, decide `act ref=e42`. **Sin coordenadas. Sin VLM. Sin pixels.** Validado en vivo con VSCode foreground:

```
# Window: workspace.py - Carter OS AI - Visual Studio Code

- button "Minimize" [ref=e1]
- button "Maximize" [ref=e2]
- button "Close" [ref=e4]
- menuitem "File" [ref=e5]
- menuitem "Edit" [ref=e6]
...
```

**16 elementos interactivos enumerados con refs estables en <50ms.**

---

## Detalle por patrón

### 1. UIA tree serializer ([tools/uia_snapshot.py](../carter_v5/tools/uia_snapshot.py))

Port directo del CDP ARIA tree de openclaw, adaptado a Windows UIA.

**Diseño**:
- 3 sets de roles: `INTERACTIVE_CONTROLS`, `CONTENT_CONTROLS`, `STRUCTURAL_CONTROLS`
- DFS walk con `max_elements` cap (default 200)
- Refs `e1`, `e2`, ... asignados solo a interactive + named content
- Duplicados handled con `[nth=N]` cuando `role:name` colisiona
- `compact=True` (default) elimina structural sin name
- `interactive_only=True` opcional para tareas focused
- Output truncado en `max_chars` con `[...TRUNCATED]` marker
- Module-level `_RefStore` thread-safe que sobrevive entre snapshot y act
- Reset por turn vía `reset_snapshot_store()` en `execute_turn`

**API**:
```python
snap = take_uia_snapshot(interactive_only=True, max_elements=200)
# snap.text → LLM lee esto
# snap.refs → dict[ref → SnapshotNode] para resolución
# snap.stats → {elements, interactive, refs, scanned}
```

**Resolución (act_on_ref)**:
- Re-bind via UIA `RuntimeId` (estable durante vida del elemento)
- Fallback a `ControlFromPoint(bbox_center)` si RuntimeId invalidado
- Soporta `click`/`invoke`/`type`/`focus`/`check`/`uncheck`/`select`
- Click via UIA `InvokePattern` (semántico) → fallback a `pyautogui` (física)

### 2. Composite gui(snapshot/act)

`gui(action="snapshot")` y `gui(action="act", ref="eN", kind="click")` agregadas al composite_dispatcher.

**Schema actualizado** en `schemas_consolidated.json` — el LLM ve la nueva action enumerada con descripción que recomienda preferir `snapshot`+`act` sobre coords XY.

### 3. install-game skill — vision-loop a UIA-tree-loop

Reescrito completamente. La filosofía nueva (citando el skill):

> The LLM doesn't need a per-game recipe — the UIA tree shows what's actionable.

Funciona para Steam, Epic, Ubisoft, EA — sin per-launcher hardcoding. Solo cambia el deeplink inicial. Todo el resto del flujo (snapshot, find game in tree, click, snapshot again, decide INSTALAR vs COMPRAR) es universal.

**Branch de honestidad explícita** preservado: si solo aparece "COMPRAR" → reporta y espera "sí" del user.

### 4. Tool call repair ([adapters/tool_call_repair.py](../carter_v5/adapters/tool_call_repair.py))

Tres funciones pure:

- **`extract_balanced_json_prefix(text)`**: extrae el primer JSON balanceado, devuelve `(parsed, rest)`. Maneja strings con braces (`"x": "has } in it"`), nested, garbage trailing.
- **`repair_truncated_json(text)`**: parsea JSON cortado mid-string o mid-value, cierra brackets automáticamente.
- **`normalize_tool_name(name, registry)`**: matching case-insensitive + segment fallback (`"functions.gui.click"` → `"gui"`).
- **`repair_tool_call(name, args, registry)`**: pipeline completo, retorna `(canonical_name, args_dict)`.

**Integración** en `llamacpp.py:212`: antes parseaba JSON crudo, ahora pasa por `repair_tool_call`. Si Gemma 4 emite `{"action": "snapshot"}garbage` o `"GUI"` (mayúsculas), se repara silenciosamente.

### 5. Skills `requires:` filter

`SkillMeta` ahora tiene campo `requires: dict`. La función `check_skill_eligibility(skill)` filtra skills que no cumplen requirements ANTES de exponerlas al LLM:

```yaml
---
name: steam-skill
requires:
  bins: ["steam"]           # Steam.exe debe estar en PATH
  any_bins: ["chrome", "edge"]  # al menos uno
  env: ["STEAM_API_KEY"]
  os: ["windows"]
---
```

`scan_skills()` filtra automáticamente. **Reduce el choice load para el LLM** — no le ofrece skills que van a fallar al primer tool.

### 6. Workspace modular ([core/workspace.py](../carter_v5/core/workspace.py))

7 archivos editables en `~/.carter_v5/workspace/`:
- `AGENTS.md` — operating rules (subagent-safe)
- `SOUL.md` — persona/tono
- `IDENTITY.md` — nombre, hardware self-description
- `USER.md` — lo que Carter sabe del humano
- `TOOLS.md` — paths/binarios locales (subagent-safe)
- `HEARTBEAT.md` — proactive checklist (P3)
- `MEMORY.md` — memorias curadas exportadas

**Subagent allowlist** mirroring openclaw: subagentes solo reciben AGENTS + TOOLS, no la persona completa.

**Filosofía**: `prompts.py` queda como **floor estable** (validado por bench 540). Workspace agrega **customización editable** sin recompilar.

### 7. Active-memory pre-turn recall ([memory/active_recall.py](../carter_v5/memory/active_recall.py))

Antes de cada turno (excepto trivial inputs <8 chars), llama `memory.get_relevant(user_text)` y inyecta los facts como mensaje system:

```
## Relevant memory
- proyecto_lab: C:\projects\lab_v2
- preferencia: respuestas cortas
```

**Circuit breaker**: 3 fallos consecutivos en 60s → abre breaker por 120s. Latencia recall capped a 1.5s. Si recall falla o es lento, turno sigue normalmente.

**Wire** en `agent_base.run_turn:247` — inyección como mensaje role="system" antes del user message del turno.

### 8. Memory wiki export ([memory/wiki.py](../carter_v5/memory/wiki.py))

CLI:
```
python -m carter_v5.memory.wiki export
```

Output:
```
~/.carter_v5/wiki/
├── index.md
├── preferences/
├── reminders/
├── entities/
└── facts/
```

Cada archivo tiene Obsidian-compatible frontmatter. El usuario puede ver/auditar/editar lo que Carter "sabe".

**Categorización** estructural (no per-language keywords):
- `preferences/` si key empieza con `pref`/`preferencia`/`modo`/`estilo`
- `reminders/` si key empieza con `recordatorio`/`reminder`/`evento`
- `entities/` si value contiene path (`/` o `\`) o key sugiere proyecto
- `facts/` por defecto

---

## Decisiones explícitas

### Lo que NO porté (justificado)

- **Plugin TypeScript SDK**: Carter es Python, romper stack no vale
- **Channels (WhatsApp/Discord/Slack)**: Carter es local-first, no gateway
- **pi-ai dependency**: Carter ya tiene `llamacpp.py` propio
- **CDP/Playwright**: Carter es Windows-native, no browser-first (aunque podría agregarse como extension futura)
- **Dreaming cron jobs** (`light/REM/deep` consolidation): valioso pero requiere infra de background jobs separada. Difiero a v5.1
- **BOOTSTRAP conversational**: el primer ritual de identity-filling. Difiero — el usuario puede crear `IDENTITY.md` manualmente por ahora
- **Heartbeat proactive mode**: P3, requiere wire con cron Windows

### Coexistencia con código existente

Todo el código nuevo es **aditivo**:
- `prompts.py` sigue siendo la base; workspace agrega encima
- `gui_universal.py` sigue funcionando; `snapshot`/`act` son nuevas actions
- `memory/store.py` intacto; `active_recall.py` y `wiki.py` son layers sobre él
- Test suite original (228 tests) intacta — 0 cambios, +51 nuevos

Si algo en los ports falla, Carter sigue funcionando con el flujo viejo.

---

## Validación

| Métrica | Antes | Después | Δ |
|---|---|---|---|
| Tests pass | 228/228 | **279/279** | +51 |
| Files | 87 | 95 | +8 |
| LOC producción | 11,371 | ~12,800 | +1,400 |
| Regresiones | — | 0 | — |
| UIA snapshot funcional | ❌ | ✅ (16 elements de VSCode en <50ms) | — |
| Refs estables | ❌ | ✅ (RuntimeId + bbox fallback) | — |
| Tool call repair | ❌ | ✅ (3 casos malformed cubiertos) | — |
| Workspace modular | ❌ | ✅ (7 files + subagent filter) | — |
| Active-memory recall | ❌ | ✅ (con circuit breaker) | — |
| Memory wiki | ❌ | ✅ (CLI + Obsidian-compatible) | — |

---

## Próximos pasos (no bloqueantes)

- **Bench 540 contra tier_16gb con UIA snapshot** — medir si el patrón resuelve "instala Doom Eternal"
- **Refinar honesty gate** para que reconozca el reply del install-game flow honesto ("requiere compra")
- **Dreaming cron jobs** (v5.1): light/REM/deep consolidation nocturna
- **Heartbeat proactive mode** (v5.1): cron Windows + HEARTBEAT.md
- **BOOTSTRAP first-run** (v5.1): conversación inicial para llenar IDENTITY.md y USER.md

---

## Atribución

Patrones tomados de openclaw (MIT license). Ver:
- ARIA tree: `extensions/browser/src/browser/cdp.ts` + `chrome-mcp.snapshot.ts`
- Workspace: `src/agents/workspace.ts`
- Skills eligibility: `extensions/<id>/skills/`
- Active-memory: `extensions/active-memory/index.ts`
- Memory wiki: `extensions/memory-wiki/`
- Tool call repair: `src/agents/pi-embedded-runner/run/attempt.tool-call-argument-repair.ts`

Adaptados a Python + Windows UIA + Gemma 4. Diseño preservado, código reescrito.
