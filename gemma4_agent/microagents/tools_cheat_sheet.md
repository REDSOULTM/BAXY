---
name: tools-cheat-sheet
priority: low
examples: ["qué cosas podés hacer por mí, cuáles son tus capacidades", "en qué me podés ayudar, qué herramientas tenés", "qué sabés hacer, mostrame tu lista de herramientas", "what can you do for me, what are your capabilities", "o que você consegue fazer, quais são suas ferramentas"]
---

# Tools disponibles (cheat sheet)

Baxy tiene 62 tools por dominio. El router muestra solo un subset por turn — esta lista es referencia, no lo que el LLM ve por turn.

## Sistema y procesos
- **system**: time, processes, cpu_ram_gpu, disk, battery, brightness_get/set, shutdown, restart, sleep.
- **terminal**: ejecutar comandos shell (timeout + captura stdout/stderr).
- **clipboard**: read/write.
- **window**: list, active, focus, close, minimize, maximize, restore.

## Apps y juegos
- **app**: open, close, search, uninstall. Universal (Steam, Epic, browser…).
- **steam**: open, library, store, search_library, store_page, launch_game, list_games.
- **game_launcher**: Epic, GOG, Xbox, Riot.
- **package**: winget install/uninstall/search/list.

## GUI y vision
- **gui**: screenshot, click, double_click, right_click, scroll, drag, keypress, type. Fire-and-forget; verificar con vision si dudás.
- **vision**: describe_screen, find_element, ocr, locate_target. Costoso — on-demand.
- **uia**: tree, find, click, focus, set_value. Más limpio que GUI cuando hay automation ID.

## Web
- **browser**: open, search, youtube_play, media_pause/stop, active_tab_title.
- **browser_real**: Playwright — tabs, click, fill, press, text extraction. Real DOM, no fire-and-forget.
- **web**: search, open, read, research (multi-source extraction).

## Filesystem
- **filesystem**: list, read, write, search, delete, copy, move, rename, mkdir, diff.
- **download**: fetch (URL→archivo), hash (SHA256/MD5), signature (Authenticode).

## Audio y media
- **audio**: get_volume, set_volume, mute, media_play_pause/stop/next/prev.
- **audio_device**: list, set_default, set_app_route (requiere SoundVolumeView).
- **media**: play, pause, resume, now_playing.
- **media_edit**: trim, concat, transcode (requiere ffmpeg).

## Conocimiento y memoria
- **memory**: save, recall, list, delete (preferences persistentes).
- **knowledge**: ingest, search, list (RAG local con sqlite-vec).
- **notes_tasks**: notes y tasks con due dates.
- **local_calendar**: events, ics_export/import.
- **contacts**: CRUD + vcard.
- **habit_tracker**: habits con streak.
- **source_manager**: citations y bibtex.

## Documentos
- **document**: extract_text/tables/images, ocr_pdf, summarize, ingest_to_knowledge, compare_documents.
- **office**: create_presentation/document/spreadsheet, inspect.

## Sistema técnico
- **env**: get, set, delete env vars (scope process/user/machine).
- **registry**: query, export, backup, add, delete, import.
- **input**: language_list, current_keyboard, switch_keyboard.
- **device_settings**: wifi, bluetooth, displays, power plans.
- **peripheral**: usb_list, hid_list, controllers.
- **printer_scanner**: list printers, default, print job.
- **network**: ping, traceroute, dns_get/set, dns_lookup, port_check.

## Maintenance y dev
- **maintenance**: windows_update_status, defender_status, firewall_status, event_logs_query, services.
- **developer**: project_detect, run_tests, lint, format, git ops.
- **container**: docker ps/inspect/logs/start/stop/restart.
- **database**: list_tables, schema, query (SELECT-only).
- **data_analysis**: csv_describe/filter/group_agg/plot (pandas).

## Productividad local
- **routine**: automation con triggers cron / on_phrase / on_app_open.
- **notification**: timers, alarms, toast.
- **reminder**: local o Microsoft Graph.
- **email**: send via Microsoft Graph (requiere GEMMA4_GRAPH_TOKEN).
- **local_search**: file name + content search con budget.
- **desktop_layout**: window snapshots.
- **backup_sync**: ZIP backups.
- **watcher**: file/url change watchers.
- **job_manager**: background jobs.

## Avanzadas
- **fact_check**: TF-IDF + cosine vs sources ingestadas.
- **form_filler**: discover→fill→submit forms en browser_real.
- **creative_local**: ComfyUI bridge (img2img, txt2img).
- **photo_library**: scan, exif, group_by_date, duplicates.
- **study**: SM-2 spaced repetition flashcards.
- **smart_home**: Home Assistant call_service + MQTT.
- **subagent**: delegación a child agente con context limpio.
- **safety**: status, pending, confirm, cancel del gate destructive.
- **state**: resources, cleanup, checkpoint, rollback.
- **verify**: app_opened, file_exists, window_exists, clipboard_contains.
- **dependency**: list missing pip/binaries.
- **accessibility**: magnifier, narrator, high_contrast.

## Pro tip
Si el user pregunta por una capacidad específica, **NO** listar las 62. Decir "sí, puedo hacer X via `<tool>`" si existe, o "no tengo herramienta para eso" si no.
