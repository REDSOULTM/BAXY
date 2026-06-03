# Fase 7 — Inventario de tools del agente

> Extraído del `COMPOUND_TOOL_SCHEMAS` real de `tools.py:4645+` (no inventado).
> Cruzado con `ToolRegistry._impls` y verificado contra el código.

## Resumen ejecutivo

| Métrica | Valor |
|---|--:|
| Compound tools (lo que el LLM ve) | **65** |
| Entries en `ToolRegistry._impls` | **88** |
| → de las cuales **legacy plain** (NO visibles al LLM) | **23** |
| → Tools con handler pero sin schema (declared-no-impl) | **0** |
| → Schemas sin handler (BUG potencial) | **0** |
| Total handlers de tools en `domain_tools.py` | 33 funciones `<name>_tool(state, args)` |
| Total handlers de tools en `ops_tools.py` | 10 funciones |
| Total handlers DENTRO de `ToolRegistry` | resto (~22, incluyendo los compuestos `t_<name>` que delegan) |

## Las 65 compound tools (lo que el LLM realmente ve)

Ordenadas por **cantidad de acciones distintas** (proxy de complejidad):

| # | Tool | #params | #req | #actions | Acciones | Handler |
|--:|---|--:|--:|--:|---|---|
| 1 | `browser_real` | 25 | 1 | **21** | status, open, goto, tabs, click, fill, extract, screenshot, ... (Playwright CDP) | `ops_tools.browser_real_tool` |
| 2 | `device_settings` | 11 | 1 | 21 | wifi_status, wifi_list, wifi_connect, bluetooth_*, displays_*, power_plans, ... | `domain_tools.device_settings_tool` |
| 3 | `notification` | 14 | 1 | 20 | toast_now, toast_schedule, timer_*, alarm_*, reminder_* | `domain_tools.notification_tool` |
| 4 | `notes_tasks` | 11 | 1 | 19 | note_create, note_list, note_search, note_update, note_delete, task_* | `domain_tools.notes_tasks_tool` |
| 5 | `media` | 16 | 1 | 16 | play, pause, resume, play_pause, stop, next, previous, ... | `domain_tools.media_tool` |
| 6 | `gui` | 18 | 1 | 13 | screenshot, click, double_click, right_click, type, keypress, scroll, drag, wait_for | `ToolRegistry.t_gui` (delegate) |
| 7 | `filesystem` | 19 | 1 | 13 | list, read, write, search, delete, copy, move, rename, mkdir, diff, archive, unarchive, open | `ToolRegistry.t_filesystem` |
| 8 | `developer` | 10 | 1 | 13 | project_detect, run_tests, run_lint, run_format, git_status, git_diff, ... | `domain_tools.developer_tool` |
| 9 | `maintenance` | 8 | 1 | 13 | windows_update_status, defender_status, firewall_*, event_logs, services, restore_points | `domain_tools.maintenance_tool` |
| 10 | `network` | 10 | 1 | 13 | ping, traceroute, dns_*, port_check, active_connections, public_ip | `domain_tools.network_tool` |
| 11 | `container` | 10 | 1 | 13 | ps, ps_all, images, inspect, logs, start, stop, exec, compose_* | `domain_tools.container_tool` |
| 12 | `peripheral` | 4 | 1 | 11 | usb_list, hid_list, controller_status, ... | `domain_tools.peripheral_tool` |
| 13 | `accessibility` | 1 | 1 | 11 | magnifier_start/stop, narrator_start/stop, dictation_*, ... | `domain_tools.accessibility_tool` |
| 14 | `smart_home` | 20 | 1 | 11 | HomeAssistant REST + MQTT publish | `domain_tools.smart_home_tool` |
| 15 | `system` | 4 | 1 | 10 | time, processes, cpu_ram_gpu, disk, battery, brightness_get/set, ... | `ToolRegistry.t_system` |
| 16 | `office` | 9 | 1 | 10 | create_presentation, edit_presentation, create_doc, ... | `domain_tools.office_tool` |
| 17 | `routine` | 15 | 1 | 10 | create, list, enable, disable, delete, run_now, history, import | `domain_tools.routine_tool` |
| 18 | `source_manager` | 13 | 1 | 10 | save, add, list, sources, search, read, get | `domain_tools.source_manager_tool` |
| 19 | `contacts` | 14 | 1 | 10 | create, add, list, search, delete, update, import_vcard, export_vcard | `domain_tools.contacts_tool` |
| 20 | `printer_scanner` | 9 | 1 | 10 | printers_list, printer_default_*, print_file, scan_document | `domain_tools.printer_scanner_tool` |
| 21 | `study` | 12 | 1 | 10 | deck_create, deck_list, card_create, card_review (SM-2) | `domain_tools.study_tool` |
| 22 | `audio` | 4 | 1 | 9 | get_volume, set_volume, mute, devices, set_default, media_play_pause, media_stop, ... | `ToolRegistry.t_audio` |
| 23 | `steam` | 5 | 1 | 9 | open, library, store, list_games, launch_game, search_library, ... | `ToolRegistry.t_steam` |
| 24 | `browser` | 10 | 1 | 9 | open, search, youtube_play, media_pause, media_stop, ... | `ToolRegistry.t_browser` |
| 25 | `local_calendar` | 13 | 1 | 9 | event_create, event_list, event_update, event_delete, ICS import/export | `domain_tools.local_calendar_tool` |
| 26 | `media_edit` | 17 | 1 | 9 | probe, trim, concat, extract_audio, transcode, ... (ffmpeg) | `domain_tools.media_edit_tool` |
| 27 | `job_manager` | 8 | 1 | 9 | start, list, log, status_of, cancel (long-running subprocess jobs) | `domain_tools.job_manager_tool` |
| 28 | `data_analysis` | 13 | 1 | 9 | csv_profile, csv_describe, csv_query, plot_* | `domain_tools.data_analysis_tool` |
| 29 | `window` | 8 | 1 | 8 | list, active, focus, close, minimize, maximize, restore, move | `ToolRegistry.t_window` |
| 30 | `state` | 8 | 1 | 8 | resources, cleanup_plan, cleanup, checkpoint, checkpoints, rollback, note, confirm | `ToolRegistry.t_state` |
| 31 | `audio_device` | 9 | 1 | 8 | list, set_default, set_default_communications, ... (SoundVolumeView) | `domain_tools.audio_device_tool` |
| 32 | `document` | 11 | 1 | 8 | extract_text, extract_tables, extract_images, ... (PDF/DOCX/XLSX/PPTX/HTML) | `domain_tools.document_tool` |
| 33 | `game_launcher` | 5 | 1 | 7 | discover, launch, open_library_page (Epic, GOG, Xbox, Riot) | `domain_tools.game_launcher_tool` |
| 34 | `creative_local` | 9 | 1 | 7 | submit, ... (ComfyUI bridge) | `domain_tools.creative_local_tool` |
| 35 | `registry` | 10 | 1 | 6 | query, export, import, add, delete, backup | `ops_tools.registry_tool` |
| 36 | `dependency` | 3 | 1 | 6 | list, verify, explain_missing, install, repair | `domain_tools.dependency_tool` |
| 37 | `habit_tracker` | 10 | 1 | 6 | create, list, log, stats, delete | `domain_tools.habit_tracker_tool` |
| 38 | `desktop_layout` | 5 | 1 | 6 | windows, list_windows, displays, snapshot, restore | `domain_tools.desktop_layout_tool` |
| 39 | `backup_sync` | 11 | 1 | 6 | backup_create, list, restore, dedupe, verify | `domain_tools.backup_sync_tool` |
| 40 | `watcher` | 9 | 1 | 6 | list, watch_file, watch_url, check, delete | `domain_tools.watcher_tool` |
| 41 | `photo_library` | 11 | 1 | 6 | scan, exif, group_by_date, thumbnails, find | `domain_tools.photo_library_tool` |
| 42 | `database` | 16 | 1 | 6 | list_tables, schema, query (SELECT-only), execute (mutating) | `domain_tools.database_tool` |
| 43 | `uia` | 10 | 1 | 5 | tree, find, click, focus, set_value | `ToolRegistry.t_uia` |
| 44 | `input` | 4 | 1 | 5 | language_list, keyboard_layouts, current_keyboard, set_lang | `ops_tools.input_tool` |
| 45 | `knowledge` | 9 | 1 | 5 | ingest, search, list, delete (RAG sobre SQLite FTS5) | `ToolRegistry.t_knowledge` |
| 46 | `form_filler` | 6 | 1 | 5 | discover, plan, apply, submit (over browser_real) | `domain_tools.form_filler_tool` |
| 47 | `app` | 5 | 1 | 4 | search, open, close, uninstall (dynamic discovery via AppResolver) | `ToolRegistry.t_app` |
| 48 | `vision` | 6 | 1 | 4 | describe_screen, find_element, ocr, compare_before_after | `ToolRegistry.t_vision` |
| 49 | `web` | 9 | 1 | 4 | search, read, research, open | `ToolRegistry.t_web` |
| 50 | `env` | 5 | 1 | 4 | get, set, delete, list | `ops_tools.env_tool` |
| 51 | `reminder` | 8 | 1 | 4 | create, list, delete | `ops_tools.reminder_tool` |
| 52 | `safety` | 4 | 1 | 4 | pending, confirm, cancel | `ToolRegistry.t_safety` |
| 53 | `package` | 3 | 1 | 4 | list, search, install, uninstall (winget) | `ToolRegistry.t_package` |
| 54 | `memory` | 4 | 1 | 4 | save, recall, list, delete | `ToolRegistry.t_memory` |
| 55 | `verify` | 6 | 1 | 4 | app_opened, file_exists, window_exists, clipboard_contains | `ToolRegistry.t_verify` |
| 56 | `download` | 9 | 1 | 3 | fetch, hash, signature | `ops_tools.download_tool` |
| 57 | `email` | 6 | 1 | 3 | draft, send (Microsoft Graph) | `ops_tools.email_tool` |
| 58 | `local_search` | 8 | 1 | 3 | search, recent (filesystem por name + content) | `domain_tools.local_search_tool` |
| 59 | `fact_check` | 6 | 1 | 3 | check, compare (TF-IDF + cosine) | `domain_tools.fact_check_tool` |
| 60 | `subagent` | 6 | 1 | 2 | run(task, tools?, max_turns?) — sub-Gemma4Agent fresco | `ToolRegistry.t_subagent` |
| 61 | `clipboard` | 3 | 1 | 2 | read, write | `ToolRegistry.t_clipboard` |
| 62 | `terminal` | 8 | 2 | 1 | run (command, args, cwd, timeout) | `ToolRegistry.t_terminal` |
| 63 | `session` | 1 | 1 | 1 | cancel_turn (meta — interrumpir turn actual) | `ToolRegistry.t_session` |
| 64 | `whatsapp` | 12 | 1 | 0* | status, send_message, open_chat (no en enum) | `domain_tools.whatsapp_tool` |
| 65 | `skill_load` | 1 | 1 | 0* | (no enum, loads SKILL.md body) | `ToolRegistry.t_skill_load` |

> *0 actions enum: la tool tiene actions documentadas en descripción pero el schema no las declara como enum. El LLM puede elegir cualquier string como `action`. Más laxo. Verificar si es intencional o falta documentación.

## Las 23 "legacy plain" (en `_impls` pero NO en `COMPOUND_TOOL_SCHEMAS`)

```
app_close, app_open, app_search,
clipboard_read, clipboard_write,
filesystem_delete, filesystem_list, filesystem_read, filesystem_search, filesystem_write,
gui_click, gui_keypress, gui_screenshot, gui_type,
list_processes, list_windows,
memory_delete, memory_list, memory_recall, memory_save,
system_time, terminal_run, web_open_url
```

### ¿Las llama alguien?

| Camino | Resultado |
|---|---|
| LLM via `execute("filesystem_list", ...)` | **NO** — no están en `COMPOUND_TOOL_SCHEMAS`, el LLM no las ve. |
| Código externo (otro archivo del paquete) via `tools.execute("name", ...)` | **NO** — `grep execute\("(legacy_name)"\)` = 0 matches en el paquete. |
| Otros métodos del `ToolRegistry` via `self.app_open(...)`, `self.filesystem_list(...)`, etc | **SÍ** — 59 referencias internas en `tools.py`. Las usan los compound (`t_app`, `t_filesystem`, etc) como helpers. |

**Veredicto:** las 23 son **métodos privados disfrazados**. Su registración en `_impls` (líneas 1561-1584 de `tools.py`) es ruido — solo necesitan ser métodos. Eliminar las 23 entradas del dict `_impls` ahorra ~25 LOC + reduce el surface area del `execute()` dispatcher. **Quick win seguro.**

## Tools sospechosas de no usarse (a verificar en logs)

Sin acceso a traces.jsonl agregado podemos sospechar basándonos en la
complejidad y el dominio:

| Tool | Por qué sospecha | Acción Fase 8 |
|---|---|---|
| `smart_home` | Requiere Home Assistant local configurado | grep `traces.jsonl` por `"name":"smart_home"` |
| `creative_local` | Requiere ComfyUI corriendo en localhost:8188 | grep |
| `container` | Requiere Docker instalado | grep |
| `database` | Requiere conexión a mysql/postgres | grep |
| `form_filler` | Construido sobre `browser_real`, feature niche | grep |
| `peripheral` | USB/HID listing | grep |
| `accessibility` | Magnifier/Narrator | grep |
| `fact_check` | TF-IDF lexical (cara) | grep |
| `source_manager` | Citation manager | grep |
| `email` | Requiere Microsoft Graph auth | grep |
| `printer_scanner` | Requiere impresora/scanner | grep |
| `data_analysis` | CSV + plots (matplotlib) | grep |
| `media_edit` | ffmpeg | grep |
| `study` | Flashcards SM-2 | grep |
| `habit_tracker` | Habit logging | grep |

**14 tools dominio-específicas** que pueden estar dormidas. Cada una arrastra
deps externas pesadas en `domain_tools.py`. Si un grupo nunca se usa, su
dep puede salir del `requirements.txt` (que primero hay que crear) y de la
cabecera de `domain_tools.py`.

## Cómo cruzar con uso real

Comando para ejecutar después de Fase 8 (cuando se decida actuar):

```powershell
# Count tool calls per name from traces
$env:PYTHONIOENCODING="utf-8"
python -c "
import json, collections
counter = collections.Counter()
with open('gemma4_agent/data/traces.jsonl', encoding='utf-8') as f:
    for line in f:
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get('kind') == 'tool_end':
            counter[ev.get('name','?')] += 1
print('Tool call counts from traces.jsonl:')
for name, n in counter.most_common():
    print(f'{n:5d}  {name}')
"
```

(Saldrá una distribución real. Las que cuentan ≤1-2 son candidatas a borrar.)

## Tools con MUY alta complejidad por params

| Tool | #params | Razón | Comentario |
|---|--:|---|---|
| `browser_real` | **25** | Playwright tabs, selectors, viewport, headers, timeout, ... | Justificado — Playwright tiene muchas opciones. |
| `smart_home` | 20 | Home Assistant entities + MQTT topics | Probablemente fragmentable |
| `filesystem` | 19 | 13 actions × params variados | Posible split |
| `gui` | 18 | 13 actions: click/type/scroll/drag con coords + timing | Justificado por dominio |
| `media_edit` | 17 | ffmpeg: input/output/codec/start/end/bitrate/... | Justificado |
| `media` | 16 | 16 actions | OK |
| `database` | 16 | SQL queries + connections + drivers | Justificado |
| `routine` | 15 | create + steps + triggers + history | Justificado |
| `notification` | 14 | toast + timer + alarm + reminder en una sola | Posible split (timer vs toast vs alarm son features distintos) |
| `contacts` | 14 | vCard + CRUD | Justificado |

## Hallazgos a `_findings_seed.md`

### HIGH
- **23 "legacy plain" tools en `_impls` que el LLM no ve y código externo no llama** — son helpers internos privados disfrazados de tools. Eliminar las 23 entradas del dict `_impls` (líneas 1561-1584 de `tools.py`). Quick win seguro, ~25 LOC + reduce surface area del dispatcher.
- **`browser_real` con 25 params + 21 actions** — la tool más compleja. Si se usa poco, peso muerto significativo. Si se usa mucho, candidata a partir en `browser_navigate`, `browser_interact`, `browser_extract`.
- **`notification` 20 actions** mezcla toast + timer + alarm + reminder en una sola tool. Si el LLM se confunde entre ellas (verificar `intent_validator` cross-reject pairs), split en tools separadas reduce errores.

### MED
- **14 tools dominio-específicas sospechosas** (`smart_home`, `creative_local`, `container`, `database`, `form_filler`, `peripheral`, `accessibility`, `fact_check`, `source_manager`, `email`, `printer_scanner`, `data_analysis`, `media_edit`, `study`, `habit_tracker`). Cada una arrastra deps en `domain_tools.py`. Si una no se usa, su dep sale.
- **`whatsapp` y `skill_load` tienen actions documentadas en descripción pero NO en enum del schema** — el LLM puede pasar cualquier string. Más laxo, posiblemente confuso.

### LOW
- **`smart_home` 20 params** — confirmable a fragmentar en tools (`hass_state`, `hass_call_service`, `mqtt_publish`).
- **9 compound tools delegan a métodos `t_<name>` adentro de `ToolRegistry`** en vez de a `domain_tools.<name>_tool` directo: `t_audio`, `t_browser`, `t_filesystem`, `t_gui`, `t_steam`, `t_system`, `t_uia`, `t_vision`, `t_web`. **Razón:** estas tools necesitan acceso a `AppResolver`, `MemoryStore`, `_audio_endpoint_volume`, etc., que viven dentro de `ToolRegistry`. Justificado, pero contribuye al tamaño god-class de la Registry.

## Artefactos a borrar al cerrar Fase 7

- `gemma4_agent/_tool_inventory.py` (script)
- `gemma4_agent/_tool_inventory.json` (output crudo)
