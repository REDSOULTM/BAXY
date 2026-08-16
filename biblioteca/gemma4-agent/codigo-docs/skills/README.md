# Carter Agent skills

Skills son **recetas markdown** que el LLM carga **lazy** via la tool
`skill_load(name="X")` cuando matchea semánticamente el pedido del usuario.

Spec: [Anthropic Agent Skills](https://www.anthropic.com/news/agent-skills).
Extensión Carter: `priority` + `requires`.

## ¿Skill vs microagent vs TOOL_RULES?

| | Carga | Trigger | Contenido típico |
|---|---|---|---|
| `TOOL_RULES["X"]` | con el subset del router | tool X en el subset | cómo USAR la tool X |
| microagent `glossary.md` | eager por trigger | substring en user_text | qué SIGNIFICA un término |
| **skill `install-steam-game/`** | **lazy on-demand** | LLM decide cargar | **cómo HACER un workflow** multi-tool |

## Cuándo crear una skill

Si tu workflow:
- Combina 2+ tools en orden específico (e.g. `app.open` + `verify` + `gui`)
- Tiene reglas honest-critical (no clickear "Buy" sin confirmación)
- Tiene matices semánticos que no caben en TOOL_RULES (e.g. "primero buscar
  en biblioteca de Steam, si no está, ir a la tienda y pedir confirmación")

→ es una skill.

Si solo es una tool sin pasos extra → no crear skill. Si es definición de
término → usar microagent.

## Formato

Cada skill es una **carpeta** con un archivo `SKILL.md`:

```
gemma4_agent/skills/
├── install-steam-game/
│   └── SKILL.md
├── purchase-guard/
│   └── SKILL.md
└── ...
```

`SKILL.md`:

```markdown
---
name: install-steam-game
description: Install a Steam game from name. Searches library, falls back to store.
priority: high
requires:
  any_bins: [steam, steam.exe]
  os: [windows]
---

# Install a Steam game

**Tools used**: steam, verify, gui.
**Honesty-critical**: yes — apply purchase-guard if not owned.

## Steps
1. steam(action="search_library", query="<game>") ...
2. ...
```

### Reglas de naming

Anthropic spec: lowercase + hyphens, max 64 chars. **install-steam-game**, no
`install_steam_game`. El linter rechaza el otro.

### `priority`

| Valor | Comportamiento |
|---|---|
| `critical` | **Eager**: full body inyectado al system_prompt en cada turn. Reservado para safety/honestidad. |
| `high` / `medium` / `low` | **Lazy**: el LLM ve el name+description en el menú, llama `skill_load()` cuando lo necesita. |

Cap por profile de cuántas `skill_load()` puede emitir en un turn:

| Profile | Cap |
|---|---|
| standby | 0 |
| light | 1 |
| balanced | 2 |
| balanced_8gb | 3 |
| performance | 5 |

### `requires` (eligibility filter)

| Key | Comportamiento |
|---|---|
| `bins: [a, b]` | Todos deben estar en PATH |
| `any_bins: [a, b]` | Al menos uno en PATH |
| `env: [VAR1]` | Todos los env vars deben estar set |
| `os: [windows, linux]` | OS actual debe estar en la lista |

Skills con requirements no cumplidos se **ocultan del menú** (el LLM nunca
las ve, no las intenta cargar).

## CLI

```powershell
# Listar skills + menu preview
python -m gemma4_agent.tools_pkg.skills_registry list

# Imprimir el body de uno
python -m gemma4_agent.tools_pkg.skills_registry load install-steam-game
```

## Opt-out

`GEMMA4_SKILLS_OFF=1` desactiva todo el sistema (menu vacío, `skill_load`
retorna `skills disabled`).

## Skills incluidos (10)

| Folder | Priority | Cuándo |
|---|---|---|
| `purchase-guard/` | **critical** | Universal: jamás clickear "Buy"/"Comprar"/"Subscribe" sin "sí" explícito |
| `install-steam-game/` | high | Usuario pide "instalá/abrí/jugá X" donde X es juego Steam (requires Steam en PATH) |
| `safe-file-cleanup/` | high | Usuario pide "borrá X", "limpiá Y". Preview antes de delete. |
| `backup-then-clean/` | high | Usuario pide "limpiá pero hacé backup". ZIP + SHA256 antes de borrar. |
| `research-and-summarize/` | medium | Usuario pide "investigá X", "buscá info en internet". Multi-source con citas honestas. |
| `screenshot-and-analyze/` | medium | Usuario pide "qué ves", "leé la pantalla". Capture + vision/OCR. |
| `debug-app-crash/` | medium | Usuario pide "por qué crasheó X", "X se colgó". Event Viewer + WER + logs. |
| `schedule-recurring-task/` | medium | Usuario pide "todas las mañanas/horas/lunes Y". Cron/phrase/app_open triggers. |
| `voice-record-transcribe/` | medium | Usuario pide "grabá audio", "transcribí lo que dije" |
| `new-development-project/` | low | Usuario pide "creá proyecto Python/Node/etc" |

## Cuándo NO crear más skills

Si tu workflow:
- Es 1 sola tool → usar la tool directo, no skill.
- Es definición de término → usar microagent.
- Es regla de uso de una tool específica → usar `TOOL_RULES` en `agent.py`.
- Es especulativo ("por si alguien quiere") → NO crear. Esperar evidencia.

Las skills son **deuda técnica**: si la tool subyacente cambia firma, la
skill queda obsoleta. Cada una agrega ~50-80 tokens al system_prompt en
cada turn. Pensar antes de crear.
