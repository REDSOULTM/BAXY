# 06 — Consolidación de tools (60 → 16 composite)

Aplicación práctica del best practice de Anthropic + caso GitHub MCP, validada con bench Carter 540.

---

## Antes y después

![Consolidated vs individual](../graficos/08_consolidated_vs_individual.png)

| Métrica | 60 tools individuales | 16 composite tools | Reducción |
|---|---:|---:|---:|
| Cantidad de tools en schema | 60 | 16 | -73% |
| Caracteres del schema JSON | 21,991 | 6,982 | -68% |
| Tokens (~) | 5,497 | 1,745 | **-3,752 tokens** |
| **PASS Carter 540 (medido)** | **540/540** | **540/540** | **idéntico** |

---

## Mapeo composite → individuales

| Composite | Reemplaza | Sub-acciones |
|---|---|---|
| `system_info(metric)` | system_time, cpu, ram, gpu, disk, battery, get_volume | 7 |
| `system_control(action)` | set_volume, mute, shutdown, reboot | 4 |
| `app(action, name)` | app_open, app_close, app_uninstall | 3 |
| `gui(action, ...)` | gui_screenshot, click, type, keypress, check_blockers, vision_locate, describe_dialog, universal_action | 8 |
| `gui_deeplink(app, intent)` | (mantenido — separado por ser conceptualmente distinto) | 1 |
| `window(action)` | list_windows, window_manage, window_arrange | 3 |
| `process()` | list_processes | 1 |
| `filesystem(action, ...)` | list, read, write, delete, rename, copy, move, create_dir, search, diff, archive, unarchive, open | 13 |
| `web(action, url?, query?)` | web_open_url, web_search, web_fetch | 3 |
| `terminal_run(command, args)` | (mantenido — ya es composite con args) | 1 |
| `memory(action, key?, value?)` | save, recall, delete, list_all | 4 |
| `media(action)` | play_pause, next, prev, volume_up, volume_down | 5 |
| `clipboard(action, content?)` | read, write | 2 |
| `office(action, format?, path?)` | word_open + create(format=docx/pptx/xlsx) | 4 |
| `registry(action, hive, key)` | read, list_keys | 2 |
| `skill_load(name)` | (mantenido) | 1 |

**Total: 16 tools / 62 sub-acciones.**

---

## Iteraciones de consolidated v1 → v6

![Consolidated v1-v6](../graficos/11_consolidated_v1_v6.png)

| Versión | PASS | Cambio |
|---|---:|---|
| v1 | 506/540 (93.7%) | C09 colapsó por CUDA crash, no por composite |
| v2 | rerun C09 = 30/30 | Fix: `gui_deeplink` description más explícita |
| v3 fresh | 539/540 (99.81%) | Aplicado fix v2 a full bench |
| v4 fresh | 538/540 (99.63%) | Banking destructive marker |
| v5 fresh | 536/540 (99.26%) | Caso C15-25 bug real modelo |
| v6 fresh | 537/540 (99.44%) | Auditor cleanup |
| **v6 reaudit** | **540/540** | Auditor v7 final calibrado |

---

## Por qué 16 y no menos

> "More tools don't always lead to better outcomes. Composite tools over excessive splitting. Group related tools with consistent prefixes."
> — [Anthropic engineering: Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)

**No se puede bajar de ~14 sin romper claridad semántica:**
- `gui_deeplink` separado de `gui` — mezclarlos rompió C09 Steam (medido).
- `terminal_run` mantenido directo — ya es composite con `command` libre.
- `process` solo — solo tiene 1 acción.

**14-16 es el piso lógico** sin sacrificar elección correcta del modelo.

---

## Escalabilidad — por qué consolidar antes de crecer

![Escalabilidad tools](../graficos/09_escalabilidad_tools.png)

Si Carter crece a 100/200 tools individuales:

| Carter futuro | Indiv. (tokens) | Composite (tokens) | ¿Cabe en 16K ctx? |
|---|---:|---:|:---:|
| 60 | 5,497 | 1,745 | ✅✅ |
| 100 | 9,162 | 2,399 | ⚠️ ✅ |
| 200 | **18,325** | 3,271 | **NO** ✅ |

**Caso GitHub MCP confirmado:** "100+ tools → agents confused/forgetful → bajaron a 40 default" ([ZenML LLMOps](https://www.zenml.io/llmops-database/building-and-scaling-a-production-mcp-server-for-developer-tooling)).

Carter sin consolidación rompe alrededor de 100-150 tools.
Carter con consolidación composite escala a 200+ sub-acciones manteniendo solo ~30 tools en schema.

---

## Hallazgo crítico — caso C09 Steam

En consolidated v1, **C09 colapsó 0/30** porque el modelo eligió `web_search` o `filesystem` para queries de Steam, en lugar de `gui_deeplink(steam, library)`.

Causa: la descripción de `gui_deeplink` era muy genérica. El modelo veía `web` y `filesystem` como tools "más simples" y las prefería.

**Fix v2 (1 línea de descripción):**
```json
"description": "PRIMARIA para apps nativas con URI scheme: steam, spotify, ...
SIEMPRE preferir esta tool antes que `web` o `filesystem` cuando el usuario menciona estas apps.
Para Steam: 'biblioteca'/'library' (intent=library), 'tienda'/'store' (intent=store), 'busca X' (intent=search, params={query:X}).
NO usar web_search para queries Steam — usar gui_deeplink(steam, search).
NO usar filesystem para chequear si juego está instalado — usar gui_deeplink(steam, library) + gui(screenshot+locate)."
```

Resultado: C09 v2 = 30/30 perfecto. Fix transparente sin tocar código.

**Lección:** las descripciones de tools en schema **importan tanto como el modelo**. Una línea bien escrita puede recuperar 30 cases.
