# Gemma4 Agent — Roadmap Honesto

Fecha: 2026-05-13
Audiencia: la siguiente sesion (yo o Codex) que continue el agente.

Este documento dice **que hacer y que NO hacer**. Se construye sobre el
inventario real del codigo, no sobre lo que dice `UNIVERSAL_AGENT_TOOL_GAPS.md`
en estado deseado. Si una accion ya devuelve `needs_implementation`, aqui se
marca como hueco verificado, no como tool "implementada".

## Estado Al 2026-05-13 (post Fase A+B)

**Fase A — deuda tecnica P0 cerrada.** Todas las acciones que devolvian
`needs_implementation` ahora tienen logica real:

| Item | Estado | Como |
|---|---|---|
| A1 audio_device.set_default | done | SoundVolumeView /sjson + roles 0/1 (Console+Multimedia) y 2 (Communications), snapshot con rollback a defaults previos, verify leyendo /sjson otra vez. |
| A2 notification.reminder_update + history | done | unregister+re-register Scheduled Task; history merge state + Get-ScheduledTaskInfo (LastRun/NextRun/LastTaskResult). |
| A3 routine cron + run_now + history | done | `manual`, `once` y `cron` (daily/weekly/hourly/minutes) via Scheduled Tasks `\Gemma4Agent\` invocando `python -m gemma4_agent.routine_runner`. process/file/network triggers documentados como deferred. |
| A4 media.now_playing + VLC | done | `GlobalSystemMediaTransportControlsSessionManager` via WinRT con AsTask/GetResult (PowerShell). Probado real: detecto un video de YouTube reproduciendose. VLC CLI opcional. |
| A5 backup_sync.restore/dedupe/verify | done | extract zip con conflict_policy overwrite\|skip\|rename, dedupe por SHA256, testzip para verify. |
| A6 local_calendar.event_update + ics_import | done | parser RFC 5545 con line folding y normalizacion de DTSTART/DTEND a ISO-8601. |
| A7 contacts vCard + resolve_recipient | done | parser/emisor RFC 6350 (FN, N, EMAIL, TEL, NOTE), resolve_recipient con scoring por exact/substring sobre name/email/phone. |
| A8 desktop_layout.restore | done | Win32 EnumWindows+GetWindowRect captura rects reales, MoveWindow+ShowWindow restaura posiciones. |
| A9 printer_scanner.print/cancel/scan | done | Start-Process -Verb Print con default-printer swap temporal, Remove-PrintJob, WIA COM para scanners_list y scan_document. |

**Fase B — P0 faltantes implementadas.**

| Item | Estado | Como |
|---|---|---|
| B1 browser_real_visible | done | attach_visible probe `/json/version` en el puerto CDP; si no responde devuelve needs_user con launch_instructions PowerShell para Chrome/Edge/Opera/Brave en user-data-dir separado. tab_open/close/focus, click_text, extract (main_text/tables/links/html), set_download_path via CDP, wait_for_download (Playwright path; CDP path documented as needs_implementation). |
| B2 document | done | Nueva tool compuesta. extract_text para .pdf (pypdf), .docx (python-docx), .xlsx (openpyxl), .pptx (python-pptx), .html (bs4 con fallback regex), .md/.txt/.csv plain. extract_tables (pdfplumber, openpyxl). extract_images de OOXML zip media y PDF. ocr_pdf via PyMuPDF+Tesseract con fallback pdf2image+poppler. summarize devuelve text_preview (no llama LLM). ingest_to_knowledge encadena con knowledge tool. compare_documents con difflib. |

Verificado end-to-end (probado en esta sesion):
- 42 tools en el catalogo, `eval_smoke` reporta `missing=[]`, `duplicate_count=0`.
- `media.now_playing` leyo titulo de YouTube reproduciendose.
- `local_calendar.ics_import` parseo VEVENT inline, normalizo `20260601T100000Z` → `2026-06-01T10:00:00+00:00`.
- `contacts.import_vcard` + `resolve_recipient` → Juan Perez encontrado.
- `backup_sync` backup → verify → restore → dedupe (encontro 1 grupo duplicado).
- `desktop_layout.snapshot` capturo 5 ventanas con rect real (left/top/right/bottom/width/height).
- `printer_scanner.printers_list` → 7 impresoras detectadas, `scanners_list` → 1 scanner.
- `browser_real`: open headless example.com + extract main_text/links + active_tab + close OK.
- `browser_real.attach_visible` sin browser activo → degrade correcto a `needs_user` con launch_instructions.
- `document` PPTX + XLSX extract + `ingest_to_knowledge` → 1 chunk → `knowledge.search` encontro.

**Fase C — P1 locales completas (2026-05-13).**

| Item | Estado | Como |
|---|---|---|
| C3 developer | done | project_detect por markers (package.json, pyproject.toml, Cargo.toml, go.mod, etc) + sub-deteccion del package manager (npm/yarn/pnpm/poetry/uv). run_tests/lint/format dispatch por stack. git_status/diff/log read-only; git_commit/push intencionalmente NO expuestos (terminal explicito). start/stop_dev_server con Popen detached + PID en state + taskkill /T. |
| C1 device_settings | done | netsh wlan (status/list/scan/connect/disconnect, localizacion ES+EN), Get-PnpDevice -Class Bluetooth + bthserv status, Win32_VideoController + Win32_DesktopMonitor, powercfg /list/setactive con rollback. bluetooth_toggle/night_light/display_set_resolution deferred con razon documentada. |
| C2 game_launcher | done | Epic via `.item` manifests en `%ProgramData%\Epic\EpicGamesLauncher\Data\Manifests`, GOG via `HKLM\SOFTWARE\WOW6432Node\GOG.com\Games`, Xbox via Get-AppxPackage + shell:AppsFolder URI, Riot via `RiotClientInstalls.json`. launch usa URIs nativos (com.epicgames.launcher://, shell:AppsFolder!App, exe directo). Steam queda en su tool dedicada. |
| C7 media_edit | done | ffmpeg wrapper para trim (`-ss/-t -c copy`), concat (concat demuxer + list file), extract_audio (mp3/aac/wav/flac/ogg/m4a), subtitles_extract, normalize (loudnorm EBU R128 I=-23 TP=-2 LRA=7), thumbnail (frames:v 1), transcode (libx264/libvpx-vp9), probe (ffprobe -show_streams). |
| C5 maintenance | done | windows_update_status via COM `Microsoft.Update.AutoUpdate` + history, defender_status via Get-MpComputerStatus, defender_quick_scan via Start-MpScan, firewall_status via Get-NetFirewallProfile, event_logs_query via Get-WinEvent -FilterHashtable, services_list/start/stop con checkpoint+rollback, restore_point_create via Checkpoint-Computer. disk_cleanup describe-only (no ejecuta). |
| C8 watcher + job_manager | done | watcher: file (mtime+size) y url (sha256 body) snapshots, Scheduled Task que invoca gemma4_agent.watcher_runner cada N minutos; on_change dispara un tool+args. job_manager: subprocess.Popen detached con log + PID en state, cancel via taskkill /T. _pid_alive helper para listing. |
| C4 network | done | ping/tracert, dns_get/set (con snapshot+rollback automatico, addresses=['AUTO'] para volver a DHCP), dns_resolve via Resolve-DnsName, port_check via Test-NetConnection, connections via Get-NetTCPConnection, public_ip via api.ipify.org. firewall_allow/block intencionalmente NO expuestos. |
| C6 data_analysis | done | pandas para csv/xlsx + matplotlib Agg headless. csv_profile (dtypes, nulls, unique), csv_describe (statistics), csv_query (.query()), csv_head, csv_to_xlsx, plot_histogram/scatter/line a PNG. needs_dependency si falta pandas/matplotlib. |

Verificado al cierre Fase C: 51 tools, eval_smoke missing=[] duplicate_count=0.
Probado end-to-end: network.public_ip→IP real, dns_resolve→10 records,
game_launcher.discover→17 juegos (Epic+Xbox+Riot), maintenance.defender_status
con AntivirusEnabled=True, data_analysis pipeline (CSV→profile→query→plot PNG),
job_manager pipeline (start→alive→cancel→killed).

Nuevos modulos runner: [routine_runner.py](routine_runner.py),
[watcher_runner.py](watcher_runner.py) — Scheduled Tasks los invocan para
disparar acciones diferidas sin agente en ejecucion.

**Fase D — P2 verticales completas (2026-05-13).**

| Item | Estado | Como |
|---|---|---|
| D1 fact_check | done | TF-IDF + cosine similarity puro Python (sin sklearn). Negation cues EN+ES detectados con ventana de 6 tokens. Verdict heuristico supports/weakly_supports/contradicts/no_evidence; el agente escribe el verdict final desde los snippets rankeados (no llama LLM dentro de la tool). compare(claim, text) y check(claim, sources?, use_knowledge=true) que lee de knowledge.search via executor. |
| D2 photo_library | done | Pillow para EXIF (DateTimeOriginal/DateTime con fallback mtime) y thumbnails (LANCZOS). scan funciona sin Pillow. group_by_date copia/mueve/symlink con granularity year/month/day. find_by_date filtra por YYYY-MM prefix. Face-recognition deferred. |
| D3 container | done | docker CLI wrapper con --format json. start/stop/restart con checkpoint rollback. exec acepta command list explicito (no shell wrap). compose_up/down/ps. Returns needs_dependency si docker no esta en PATH. |
| D4 database | done | SQLite (stdlib), Postgres (psycopg/psycopg2), MySQL (mysql-connector/pymysql). query restringido a SELECT/WITH/EXPLAIN/PRAGMA/SHOW; execute para mutaciones. list_tables, schema, export_csv. Driver selection por arg `driver=sqlite|postgres|mysql`. |
| D5 creative_local | done | Bridge a ComfyUI HTTP local (default :8188). submit→POST /prompt, wait→poll /history/<id>, queue, interrupt, models→/object_info. Returns needs_user con launch instruction si server no responde. Set GEMMA4_COMFYUI_HOST para override. |
| D6 form_filler | done | Orquesta browser_real. discover via page.evaluate (selectores CSS path, label resolution via <label for=>, parent <label>, aria-label, placeholder). plan matchea values dict con discovered fields (exact + substring). apply ejecuta fill/click/select. **submit requiere confirmed=true; sin ello devuelve needs_confirmation con screenshot + summary de campos** — gate explicito para evitar submits silenciosos. |
| D7 peripheral | done | Get-PnpDevice para usb_list, hid_list, controller_status (keywords Xbox/Controller/DualSense/Joystick/Joy-Con), device_manager_problems (Status != OK). device_disable/enable con rollback checkpoint. RGB vendor SDKs deferred con razon. |
| D8 accessibility | done | magnifier_start/stop y narrator_start/stop via Popen + taskkill. settings_panel abre `ms-settings:easeofaccess`. dictation_status reporta servicio. high_contrast deferred — el camino seguro es Left Alt + Left Shift + Print Screen (confirmacion del usuario). |
| D9 study | done | Flashcards + SM-2 spaced repetition (Wozniak 1990): EF' = EF + (0.1 - (5-q)(0.08+(5-q)*0.02)), EF floor 1.3, intervalos 1/6/round(I*EF), reset reps cuando q<3. Storage SQLite en `<state_dir>/study.sqlite`. decks, cards, due, review(q 0..5), stats. |

Verificado al cierre Fase D: **60 tools**, eval_smoke missing=[] duplicate_count=0.
Probado end-to-end: study (SM-2 EF 2.5→2.6→2.7, q=1 reset reps=0 EF=2.16),
database SQLite (create→insert→query→list_tables), fact_check.compare score
0.5965, peripheral.controller_status 14 controllers, fact_check con negation
cue detecto contradicts correctamente en sesion previa.

**Fase F3 — huecos locales cerrados (2026-05-13).**

Lote chico (4 huecos documentados como deferred) y un nuevo dominio
(smart_home local). El user pidio mantenerse 100% local, asi que Fase E
cloud queda pausada.

| Item | Estado | Como |
|---|---|---|
| F3.1 audio_device.set_app_route | done | SoundVolumeView `/SetAppDefault <device> <role> <process>` para enrutar audio por app. Roles 0/1/2. Acepta proceso por nombre o PID. `device="DefaultRenderDevice"` para revertir a default. `get_app_routes` lee `/sjson` filtrando entries con `Type=Application`. snapshot/rollback automatico antes de mutar. |
| F3.2 routine on_app_open/on_app_close | done | Triggers nuevos: el routine instala automaticamente un watcher kind=`process` que polea `Get-Process` cada N minutos. _watcher_check con edge=`rising`/`falling` solo dispara `routine.run_now` cuando el estado cambia en la direccion correcta. routine.delete remueve el watcher + Scheduled Task asociados. |
| F3.3 device_settings.wifi_add_profile | done | `netsh wlan add profile filename=<xml>` con template WPA2-Personal (RFC Microsoft Win32 Native Wifi sample). wifi_connect ahora auto-crea profile si pasas `password=`. wifi_delete_profile via `netsh wlan delete profile`. Validacion: passphrase 8-63 chars. |
| F3.4 smart_home LOCAL | done | Home Assistant REST API local con long-lived access token (`GEMMA4_HASS_TOKEN`). discover/states, get_state, set_state (snapshot rollback), call_service (turn_on/off/toggle snapshot), scene_run, area_list+area_control. mqtt_publish opcional con paho-mqtt si esta instalado. **Cero cloud** — todo va contra tu instancia HA local. |

Verificado: 61 tools, eval_smoke missing=[] duplicate_count=0.
Tu Home Assistant en homeassistant.local fue detectado vivo
(`smart_home.status -> home_assistant=True`).
audio_device.get_app_routes degrada honestamente a `needs_dependency` cuando
no hay SoundVolumeView.
routine.create con `trigger={type:'on_app_open', process:'notepad.exe',
interval_minutes:1}` registro el watcher process snapshot inicial
y se desinstalo limpio con routine.delete.

**Proximo paso (local):** F1 voice_io (Piper TTS + Vosk STT) o F2 capture
(screen_record + camera + mic via ffmpeg/DirectShow) cuando quieras seguir
sin tocar cloud.

## Pulido P4 — tool routing (2026-05-13)

Antes de tocar modalidades nuevas, el usuario pidio pulir el nucleo.
Primera entrega: tool routing.

**Hallazgos previos al pulido:**
- `_suggest_tools` solo conocia las tools originales (Fase A). Las 21 tools
  agregadas en C/D/F3 (developer, fact_check, smart_home, etc) nunca se
  preseleccionaban — el modelo las descubria solo si el catalogo completo
  llegaba a sobrar en su contexto.
- El cap de prioridad cubria 17 tools nombradas + un default 50; las
  nuevas competian sin tiebreaker ni manejo de utility tier.
- Sin telemetria de routing miss: no podiamos saber si Gemma se desviaba
  del subset enviado.
- Sin tests del router: cualquier cambio era a ciegas.

**Cambios:**
- planner.py `_suggest_tools` extendido con regexes para las 21 nuevas
  tools, incluyendo aliases ES (controles, lupa, conexiones activas,
  vigila, recorta video, etc).
- `_related_tools` documenta las dependencias semanticas de cada tool
  nueva (developer -> terminal+filesystem+verify, fact_check ->
  knowledge+web+source_manager, form_filler -> browser_real+state+safety,
  smart_home -> state+dependency, document -> filesystem+knowledge+
  dependency, etc).
- `_cap_tools` reescrito con tabla tier-based:
  - primary (matched o relacionada): keep mention order
  - utility (verify/state/dependency/safety): siempre al final
  - unclassified: mid-tier 50
- agent.py emite traces nuevos por turno:
  - `tool_call` ahora incluye `in_subset` boolean
  - `router_miss` cuando Gemma llama una tool fuera del subset enviado
  - `router_stats` al terminar el turno: subset_size, used_count,
    unused_count, used, unused
- test_router.py: 32 queries reales con `must_include` / `must_exclude`.
  Pasa 32/32 con el router actualizado.

Verificado: eval_smoke missing=[] duplicate_count=0 (61 tools).
test_router 32/32 passing.

## Pulido P4.5 — multi-idioma + semantic fallback (2026-05-13)

User pidio que el router funcione para todos los idiomas y formas de
hablar. Investigamos como lo hacen 10 competidores:

| Proyecto | Filtra por turno? | Como | Multi-idioma |
|---|---|---|---|
| Jarvis local | si | keywords + intents + categorias, max 8, fallback a todas | no |
| open-interpreter | no | 1 tool universal `execute()` | no |
| OpenHands | no | skills por keyword/regex, MCP estatico | no |
| goose | **no, envia todas** | -- | no |
| Agent-S | si | introspeccion Python + filtro por plataforma | no |
| OS-Copilot | **si, embeddings** | `similarity_search_with_score(k=10)` Chroma | no |
| AutoGPT | no | grupos/permisos, no por turno | no |
| autogen | no | `bind_tools` una vez | no |
| LangGraph | no | bind al compilar el grafo | no |
| Mark-XXXIX | no | planner LLM elige plan | **si** |
| openclaw | no | allowlist policy, no semantico | no |

Conclusion: la mayoria envia todas (10-30 tools); el que mejor lo hace
es OS-Copilot con embeddings semanticos.

**Decision: hibrido E1.** Mantener keywords (rapido, deterministico) +
fallback semantico cuando keywords no matchean (multi-idioma automatico).

**Cambios:**
- planner.py: keywords extendidas a ES+EN+PT+FR+IT en TODAS las tools
  (~60 regex con alternancias multi-idioma). Ej: `smart_home` matchea
  (turn on|turn off|enciende|apaga|apague|allumer|eteindre|accendere|
  spegnere) + (light|luz|lumiere|luce).
- planner.py: `document` ahora gana sobre `office` cuando hay verbo de
  lectura (read|lee|leia|lis|leggi|...) + extension (pdf|docx|...).
  Reemplaza "office" en el subset porque "lee este pdf" no es crear,
  es leer.
- planner.py: `select_tool_names` con fallback semantico. Cuando los
  keywords no matchean nada y el mensaje no es casual/saludo, llama
  `semantic_router.suggest_tools_semantic(query, k=12)`.
- planner.py: guard anti-falsos-positivos. El fallback NO se dispara
  para saludos (hola, hi, ciao, bonjour, ola, bom dia, gracias, thanks,
  obrigado, merci, grazie, etc) ni para mensajes de <=3 palabras sin
  signo de pregunta.
- **semantic_router.py NUEVO**: usa `sentence-transformers/paraphrase-
  multilingual-MiniLM-L12-v2` (50+ idiomas, ~120MB). Cosine similarity
  contra descripciones cortas de las 61 tools. Lazy-load, cache en
  memoria. Disable via env GEMMA4_SEMANTIC_FALLBACK=false. Override
  modelo via GEMMA4_SEMANTIC_MODEL.
- agent.py: trace event `tool_subset` ahora incluye flag
  `semantic_fallback` para medir cuanto se usa.
- test_router.py: extendido de 32 a 61 tests (added EN/PT/FR/IT). Cubre
  steam, media, audio, browser, document, smart_home, photo_library en
  cuatro idiomas extra. Pasa 61/61.

Verificado: 61 tools, eval_smoke missing=[] duplicate_count=0.
test_router 61/61 passing en ES+EN+PT+FR+IT.

## G1..G5 — cerrar la brecha vs competidores (2026-05-13)

Despues de auditar 10 competidores (OpenHands, goose, OS-Copilot, Agent-S,
open-interpreter, AutoGPT, autogen, langgraph, Mark-XXXIX, openclaw)
implementamos los 5 huecos mas grandes. **62 tools** (+1 subagent).

| Feature | Estado | Como (verificable en codigo) |
|---|---|---|
| G1 memoria semantica de experiencias | done | `experience.py`: SQLite + sqlite-vec virtual table `experience_vec(embedding float[384])`. Cada turno cerrado se embebe (multilingual-MiniLM) y se persiste con `tools_used`, `mission_status`, `summary`. Disable via `GEMMA4_EXPERIENCE_MEMORY=false`. |
| G5 RAG turn-1 sobre conversaciones | done | `Gemma4Agent.run_content` hace `experience.recall(query, k=3)` antes del LLM call. Resultados se renderizan via `format_recall_for_prompt` y se inyectan al SYSTEM_PROMPT como bullets `past[d=X]: "..." -> tools=[...] status=PASS`. Hint-only, nunca bloquea. Logged como `experience_recall` event. |
| G2 compactacion por summarization | done | `_compact_completed_history` estima uso de contexto (chars/3); si >75% del budget, pide a Gemma 4 mismo que resuma los N mensajes mas viejos en ~200 palabras (max_tokens=400), reemplaza el head con `[Conversation summary so far]` y conserva las ultimas 6. Falla -> degrada a truncate. Disable via `GEMMA4_AGENT_SUMMARIZATION=false`. |
| G3 plan explicito + replanning | done | `explicit_plan.py`: `should_plan(text, det_steps)` heuristica (deterministic_steps >= 2, o usuario dice "plan", o >= 3 verbos imperativos). Si dispara, genera plan numerado max 8 pasos (con instruccion `NO_PLAN_NEEDED` para que el LLM decline tareas triviales). El plan se inyecta al SYSTEM_PROMPT como `# Explicit Plan`. **Replan automatico** cuando se acumulan 2+ tool failures en el turno: pide plan revisado o `GIVE_UP: <razon>`. Disable via `GEMMA4_AGENT_EXPLICIT_PLAN=false`. |
| G4 subagents | done | `subagent.py` + tool `subagent`. `subagent(action="run", task=..., tools=[...], max_turns=4)` arranca una instancia fresca de `Gemma4Agent` con config clonada (max_agent_turns acotado), history vacio. `tools=[...]` filtra schemas que ve el child via wrapper de `schemas_for_names`. Sin parent agent wired -> degrade honesto a `needs_implementation`. |

Verificado:
- 62 tools, eval_smoke missing=[] duplicate_count=0.
- test_router 61/61 (ES+EN+PT+FR+IT).
- test_gx_features 8/8 (record/recall, parse plan, generate plan con
  mock, replan give-up, subagent sin parent, subagent con parent mock,
  summarization toggleable).
- experience.sqlite + experience_vec funcionan end-to-end con queries
  reales tipo "abre steam y mira mi biblioteca" recuperando una
  experiencia previa de Steam con d=0.90.

**Lo que NO hicimos esta vez (pendiente para sesion futura):**
- MCP support (la pieza mas grande que falta vs Goose/OpenHands/AutoGPT).
- Subagents paralelos (la implementacion actual es sincrona).
- Best-of-N rollouts a la Agent-S.
- Dashboard de observability.
- Voice + Camera (F1/F2 explicitamente diferidas por decision del user).

## G6 — rutinas por frase ("Alexa-like text triggers", 2026-05-13)

Usuario pidio que el agente reaccione a frases tipo "cuando te diga X
haz Y", como las rutinas de Alexa pero solo por texto.

**Implementacion:**

- `routine_tool` acepta un nuevo trigger type `on_phrase` (alias `on_keyword`)
  con campo `phrase` (>=3 chars, validado al crear). Ejemplo:
  ```text
  routine(action="create",
    name="gamer_mode",
    trigger={"type": "on_phrase", "phrase": "modo gaming"},
    steps=[
      {"tool": "audio", "args": {"action": "set_volume", "level": 30}},
      {"tool": "app", "args": {"action": "open", "name": "Discord"}}
    ])
  ```
- `routine.status` ahora reporta `on_phrase` en su lista de triggers
  disponibles + nota explicativa.
- Nuevo helper publico `domain_tools.active_phrase_triggers(state)` que
  lista las rutinas `on_phrase` abiertas y habilitadas.
- `Gemma4Agent.run_content` ejecuta el hook **antes** del LLM call:
  - Extrae texto plano del input, lo normaliza (case + acentos via NFKD).
  - Por cada rutina activa, verifica substring case-insensitive de la
    frase guardada.
  - Si matchea, ejecuta los `steps` directamente via `self.tools.execute`
    y guarda los resultados en `self._phrase_fires`.
  - Logged como `phrase_trigger_fired` event en `traces.jsonl`.
- `_system_message` inyecta un bloque "Phrase-triggered routines already
  executed this turn" que le dice a Gemma que NO re-ejecute los steps;
  solo confirme brevemente al usuario que hizo.
- Router `_suggest_tools` agrega keywords ES+EN+PT+FR+IT: "cuando te diga",
  "si te digo", "cada vez que diga", "when i say", "every time i say",
  "quando eu disser", "quand je dis", "quando dico", etc. → `routine`.
- SYSTEM_PROMPT tiene una regla nueva "Voice-command-like routines rule"
  explicando como construir el trigger y como reportar lo ya ejecutado.

**Tests (test_gx_features.py):**
- `test_g6_phrase_trigger_creation_validation`: rechaza phrase <3 chars y
  phrase ausente.
- `test_g6_active_phrase_triggers_returns_enabled`: create -> listed,
  disable -> not listed.
- `test_g6_phrase_hook_fires_on_match`: crea routine, llama run_text con
  texto que matchea, verifica `_phrase_fires` se pobla y los steps
  retornaron `ok=True`. LLM mockeado para no depender de llama-server.

Verificado: 62 tools, eval_smoke missing=[] duplicate_count=0,
test_router 61/61, test_gx_features 11/11.

**Diferencia conceptual:** esto NO es un wake-word (eso es F1 voice_io,
diferido). G6 reacciona a frases en el chat de texto, ejecuta los steps
y deja que Gemma confirme con prosa natural. Es la pieza que falta para
parecerse a Alexa **sin** microfono.

## Catalogo Actual Verificado

42 tools registradas en [tools.py](tools.py) (`ToolRegistry._impls`):

`system, audio, app, steam, window, gui, vision, browser, web, uia, filesystem,
package, clipboard, terminal, memory, verify, state, input, env, registry,
download, email, reminder, browser_real, knowledge, office, audio_device,
notification, routine, media, source_manager, dependency, contacts, notes_tasks,
local_calendar, habit_tracker, local_search, printer_scanner, desktop_layout,
backup_sync, safety` + alias planos (`system_time`, `app_open`, etc).

## Estado Real De Las Tools "Completas"

`grep needs_implementation/needs_dependency` en [domain_tools.py](domain_tools.py)
y [ops_tools.py](ops_tools.py) revela huecos que NO estaban documentados como
pendientes:

| Tool | Accion | Estado real |
|---|---|---|
| `audio_device` | `set_default` | `needs_dependency` si no hay SoundVolumeView. Verificado [domain_tools.py:58](domain_tools.py#L58) |
| `notification` | `reminder_update` | `needs_implementation`. [domain_tools.py:112](domain_tools.py#L112) |
| `routine` | `run_now` sin executor | `needs_implementation`. [domain_tools.py:147](domain_tools.py#L147) |
| `media` | acciones distintas de `play`/`pause`/`stop` | `needs_dependency`. [domain_tools.py:205](domain_tools.py#L205) |
| `contacts` | varias acciones secundarias | `needs_implementation`. [domain_tools.py:299](domain_tools.py#L299) |
| `local_calendar` | varias acciones | `needs_implementation`. [domain_tools.py:363](domain_tools.py#L363) |
| `printer_scanner` | print/scan reales | `needs_implementation`. [domain_tools.py:461](domain_tools.py#L461) |
| `desktop_layout` | `restore` | `needs_implementation`. [domain_tools.py:478](domain_tools.py#L478) |
| `backup_sync` | `restore`, dedupe | `needs_implementation`. [domain_tools.py:507](domain_tools.py#L507) |
| `office` | `edit_*`, `export_pdf` | `needs_dependency`. [domain_tools.py:557,574](domain_tools.py#L557) |

Regla derivada: **antes de marcar nuevas tools como "completas" hay que
verificar que TODAS las acciones del contrato funcionan**, no solo el happy path
del smoke.

## Roadmap Por Fases

### Fase A — Cerrar Deuda Tecnica De P0 Ya Empezadas

Antes de agregar tools nuevas, dejar pulido lo iniciado. Esto evita inflar
catalogo con tools que mienten en su contrato.

#### A1. `audio_device.set_default` real

- Hacer: detectar/instalar SoundVolumeView automaticamente via `dependency` +
  `package(winget)`. Implementar `set_default` y `set_default_communications`
  con snapshot/restore. Validar con un dispositivo conocido (AUX/Focusrite).
- No hacer: routing por app (Windows lo permite solo desde 21H2 con
  `AudioEndpointManager` privado y es fragil). Marcar `set_app_route` como
  `needs_implementation` documentado y seguir.
- Evidencia: device ID antes/despues, exit code helper, snapshot id en `state`.

#### A2. `notification.reminder_update` y persistencia

- Hacer: completar `reminder_update`/`reminder_delete` consistentes con
  Scheduled Tasks creadas en `reminder_create`. Anadir `notification.history`
  leyendo de `state`.
- No hacer: una UI de administracion. Es CLI/tool, no app.

#### A3. `routine` con executor real

- Hacer: pasar el `ToolRegistry` como executor a `t_routine`. `run_now` debe
  ejecutar cada step via las tools reales con args validados, no string-match.
- Hacer: triggers persistentes simples — solo `cron` (Scheduled Task) y
  `on_app_open` (poll cada N segundos sobre `list_processes`). Resto, marcar
  `needs_implementation`.
- No hacer: motor de eventos complejo (file_watcher, USB, MQTT) en esta fase.

#### A4. `media` unificado con backends reales

- Hacer: `play(provider="youtube")` ya funciona — extender a `local` via VLC
  CLI si esta en PATH (sino `needs_dependency`), `media keys` para
  `pause/resume/stop/next/previous`, `now_playing` leyendo
  `Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager`
  via WinRT (PowerShell). Si WinRT no responde, devolver
  `needs_verification`.
- No hacer: Spotify API ni cuentas cloud (P3).

#### A5. `backup_sync.restore` y dedupe

- Hacer: `restore(backup_id)` extrayendo el ZIP a destino con preview y
  conflict policy (overwrite/skip/rename). `dedupe(path)` con SHA256.
- No hacer: rsync incremental ni snapshots VSS (complejo, postergar).

#### A6. `local_calendar` mas allas de `event_create`

- Hacer: `event_list/update/delete`, `ics_import` (parser estandar
  `icalendar` o regex minimo VEVENT), `ics_export` ya existe segun el doc
  pero validarlo.
- No hacer: invitaciones, attendees, RSVP — eso es Graph, va en P3.

#### A7. `contacts` import/export vCard

- Hacer: `vcard_import` + `vcard_export` con libreria `vobject` (si no esta,
  `needs_dependency`). `resolve_recipient(query)` matcheando nombre/email.
- No hacer: foto de contacto, sync con Outlook/Google.

#### A8. `desktop_layout.restore`

- Hacer: aplicar el snapshot guardado moviendo ventanas a las posiciones
  registradas via Win32 `SetWindowPos`/`MoveWindow`. Si una ventana ya no
  existe, marcar `partial` con detalle.

#### A9. `printer_scanner` print real

- Hacer: `print_file(path, printer?)` via `Start-Process -Verb Print` con
  monitoreo de cola. `scan_document` solo si WIA esta disponible — sino
  `needs_dependency`.

**Salida esperada de Fase A:** ningun action en P0 devuelve
`needs_implementation` sin justificacion documentada. Smoke tests cubren cada
action por separado, no solo una happy path por tool.

### Fase B — Tools P0 Faltantes

#### B1. `browser_real_visible` — fortalecer `browser_real`

- Hacer: extender [tools.py](tools.py) `t_browser_real` con:
  - `attach_visible(browser="chrome|edge|opera|brave", endpoint?)`: detectar
    si el usuario corre el navegador con `--remote-debugging-port=9222`, sino
    devolver `needs_user` con la instruccion exacta.
  - `active_tab`: URL/titulo del front-most en el contexto CDP.
  - `tab_open/close/focus`.
  - `click_text(text)`, `click_selector(css)`, `fill(selector, value)`,
    `press(key)`.
  - `download_wait(timeout)`: capturar `Page.downloadWillBegin` /
    `Browser.downloadProgress`. Devolver ruta+SHA256.
  - `extract(mode="readability|main_text|tables")`.
  - `screenshot_visible`.
- No hacer: control del navegador personal del usuario sin perfil separado por
  defecto. Si attach_visible, marcar `evidence.session=user_profile` para que
  Gemma sepa que esta tocando estado real del usuario.
- Dependencia: Playwright + Chromium. Si falta, ya devuelve `needs_dependency`.

#### B2. `document` — parsing PDF/DOCX/XLSX/PPTX/HTML

- Hacer: nueva tool compound `t_document` registrada en `_impls`:
  - `extract_text(path)`: pdf via `pypdf` (sin Tesseract), docx via
    `python-docx`, xlsx via `openpyxl`, pptx via `python-pptx`, html via
    `bs4` o regex.
  - `extract_tables(path)`: pdf via `pdfplumber`, xlsx via `openpyxl`.
  - `extract_images(path)`: pptx/docx/pdf, escribir a `data/extracted/`.
  - `ocr_pdf(path)`: paginas a PNG temporal + Tesseract.
  - `summarize(path)`: extraer texto + reinyectar al chat (NO llamar otro LLM
    dentro de la tool — el agente principal resume).
  - `ingest_to_knowledge(path)`: chunk + insertar en SQLite FTS5.
  - `compare_documents(a, b)`: diff textual.
- No hacer: parseo de PDFs escaneados sin OCR explicito, formatos propietarios
  (Pages, Numbers, Keynote).
- Dependencias nuevas: `pypdf`, `pdfplumber`, `beautifulsoup4`. Detectar via
  `dependency` y devolver `needs_dependency` con install hint.

### Fase C — Tools P1 Locales

Orden recomendado, una a la vez:

| # | Tool | Hacer | NO hacer |
|---|---|---|---|
| C1 | `device_settings` | `wifi_list/connect/status`, `bluetooth_status/toggle`, `display_list`, `power_plan_get/set`, `night_light` via `netsh`/`powercfg`/registry. | `wifi_connect` con SSID nuevo sin profile XML preconfigurado: NEEDS_USER. Pairing BT real, dejar `needs_implementation`. |
| C2 | `game_launcher` | Discovery Epic (`%LocalAppData%\EpicGamesLauncher\Saved\Data\Manifests\*.item`), GOG Galaxy DB, Xbox Store URI. `launch(launcher, game_id)`. | Battle.net/Riot/EA/Ubisoft solo manifest scan — `launch` por URI cuando exista. Sin scraping web. |
| C3 | `developer` | `project_detect` (`package.json`, `pyproject.toml`, `Cargo.toml`, `.git`), `run_tests`/`run_lint`/`run_format` con auto-deteccion, `git_status/diff`, `start_dev_server/stop_dev_server` con PID en `state`. | `git_commit` sin args explicitos del usuario. NO ejecutar `npm install` u otros side-effects sin pedirlo. |
| C4 | `network` | `wifi_scan`, `dns_get/set`, `ping`, `traceroute`, `port_check`, `connections_active` via `netstat`. | Cambiar firewall rules en bulk (riesgoso). Solo `firewall_status`. |
| C5 | `maintenance` | `windows_update_status` (USOClient query), `defender_status`, `event_logs_query` (Get-WinEvent filtrado), `disk_cleanup` (cleanmgr /sagerun), `restore_point_create`. | `defender_scan` lleno (toma horas). Solo `quick_scan`. Cualquier `restore_point_revert` queda fuera. |
| C6 | `data_analysis` | `csv_profile` (filas/cols/tipos/null), `csv_query` con pandas `query()`, `plot_histogram/scatter/line` a PNG, `to_xlsx`. | Models ML o predicciones. |
| C7 | `media_edit` | `transcode`, `trim`, `concat`, `extract_audio`, `subtitles_extract`, `normalize`, `thumbnail` via ffmpeg CLI. | Encoding pesado sin advertir tamano/tiempo. |
| C8 | `watcher` + `job_manager` | `watch_file(path, on_change)`, `watch_url(url, interval, on_change)`, `job_list/cancel/result`. Job state en `data/jobs/`. | Threads de Python persistiendo entre sesiones — usar Scheduled Tasks o proceso hijo. |

### Fase D — Tools P2 Avanzadas

Solo cuando Fase A-C esten verificadas:

- `source_manager` ya existe; falta `fact_check(claim, sources)` que compare
  texto contra excerpts ingested. Local, sin LLM externo.
- `photo_library`: EXIF, agrupar por fecha/lugar/persona (sin face-rec por
  defecto), thumbnails. Requiere `Pillow`.
- `study`: flashcards + spaced repetition local en SQLite. AnkiConnect opcional.
- `container`: Docker CLI wrapper (`ps`, `up`, `down`, `logs`, `exec`).
- `database`: SQLite/Postgres/MySQL local connect/query/export.
- `creative_local`: si hay ComfyUI/SD instalado, pasar prompt y devolver path.
  Si no, `needs_dependency`.
- `form_filler`: estructurado, basado en `browser_real_visible`. Requiere
  review obligatorio antes de submit.
- `peripheral`: USB list, controller status. RGB vendor APIs — postergar.
- `accessibility`: magnifier/narrator/high_contrast via setx + ToggleKeys.
- `driver_manager`: solo discovery + URLs del vendor; no instalar.

### Fase E — Externo (P3)

NO empezar hasta Fase A-C. Cuando se haga:

- `calendar_cloud`, `mail_cloud`, `todo_cloud`, `drive_cloud`, `music_cloud`,
  `smart_home_cloud`, `weather_news`, `communications_cloud`.
- Cada uno como tool separada. Cada uno con su propio token en env var
  documentada. Si falta token, `needs_user`.

### Fase F — Smart Home (P1 si tiene HA)

- `smart_home` solo si el usuario confirma que tiene Home Assistant local. Si
  no, marcar diferida. Backends en orden: HA REST -> HA WS -> MQTT -> Matter.

## Reglas Que NO Cambian

1. **Compound tools por dominio.** Una tool por accion suelta = ruido para
   Gemma. Cada tool nueva debe tener `action` enum cerrado.
2. **Evidencia obligatoria.** Cada return tiene `ok`, `status`, `verified`,
   `evidence`. Sin evidencia = `needs_verification`.
3. **No fingir.** Si falta dep o cuenta, `needs_dependency` / `needs_user`.
   Nunca `ok=true` simulado.
4. **Snapshot antes de mutar.** Cualquier accion reversible (audio device,
   registry, env, display config) guarda snapshot en `state` para `rollback`.
5. **Cleanup registrado.** Tool que abre recursos lo registra en
   `state.resources_open` para que `state(cleanup)` los cierre.
6. **No inventar tools.** El schema enum esta para que Gemma no llame
   `action="frobnicate"`. Mantenerlo cerrado.
7. **El catalogo se envia parcial por turno.** El router de `modes.py` ya hace
   tool subsetting; cualquier tool nueva debe declarar su grupo (apps, media,
   files, etc) para que entre en el subset cuando corresponde.
8. **Tests antes de marcar completo.** `eval_smoke.py` debe cubrir cada
   `action` nueva. PASS = `missing=[]` y `duplicate_count=0`.
9. **No copiar de Jarvis/jarvis-personal-ai sin filtrar.** Esos repos viven en
   `gemma4_agent/jarvis*` solo como referencia de arquitectura. NO importar
   modulos de ahi.
10. **Carter queda separado.** No mezclar `harness_carter540/` con este agente.

## Que NO Hacer (lista negra explicita)

- No crear `voice_io` ahora. Diferido por decision de producto.
- No crear `capture` (camara/mic) ahora. Diferido.
- No agregar auth propia tipo Jarvis-personal con email/password.
- No agregar UI web/movil. Es CLI.
- No agregar dependencias cloud sin necesidad (sin OpenAI fallback, sin
  embeddings cloud, sin Anthropic API).
- No tocar `harness_carter540/`.
- No marcar tools como "completas" cuando algunas acciones devuelven
  `needs_implementation` — anotar siempre en este roadmap.
- No agregar 100 funciones sueltas. Mantener el conteo de tools compuestas
  bajo control. Objetivo: ≤ 60 tools al terminar P0+P1.
- No tocar el system prompt sin actualizar tambien `modes.py` y
  `planner.py` — los tres estan acoplados.
- No quitar el alias plano (`app_open`, `filesystem_read`, etc) hasta validar
  que ningun test o script externo los usa.

## Prioridad De La Proxima Sesion

Fases A, B, C, D y F3 (huecos locales) completas y verificadas (2026-05-13).
**61 tools** registradas, eval_smoke limpio. Usuario pidio mantener todo
local, asi que **Fase E (P3 cloud) queda pausada**. Las dos siguientes piezas
locales con mayor valor son:

### Frente F1 — voice_io local

Hacer del agente un Jarvis real con voz. Sin nube.

- **TTS**: Piper (modelo `es_ES-davefx-medium` o `es_AR-daniela-high`) via CLI.
  Out-of-the-box neural, pesos ~25-60MB.
- **STT**: Vosk (modelos ES `vosk-model-small-es-0.42` ~50MB) o
  whisper.cpp con `ggml-base.bin` (~140MB).
- Tool unica `voice_io` con actions: `status`, `tts_speak(text)`,
  `tts_save(text, path)`, `stt_transcribe(audio_path)`,
  `stt_listen(duration)`. Audio via `sounddevice` o ffmpeg.
- El chat actual puede enganchar `tts_speak` al final de cada respuesta
  via un hook opcional del prompt; el modo audio que ya existe en
  `modes.py` cierra el ciclo "habla → transcribe → razona → habla".

### Frente F2 — capture local

- `capture(action="screen_record|screen_snapshot|webcam_snapshot|mic_record")`
  via ffmpeg gdigrab+dshow (Windows nativo).
- `screen_record(seconds, dst)` con buffer rolling para "graba los ultimos
  30 segundos" estilo NVIDIA Shadowplay.
- Webcam list via `dshow` o `Get-PnpDevice -Class Image`.

### Mejoras a tools existentes (cuando aparezcan)

- `routine.on_file_change` → reusar `watcher` kind=file (la pieza ya existe).
- `peripheral.rgb_*` → integraciones por vendor (Logitech LCM, Razer Synapse
  SDK) solo si el usuario tiene esos perifericos especificos.
- `accessibility.high_contrast` real via WinAPI `SystemParametersInfo` con
  `SPI_SETHIGHCONTRAST` + broadcast `WM_SETTINGCHANGE`.
- `creative_local` extensions: Krita CLI, Blender CLI scripts.

### Cuando se quiera cloud (Fase E, postergada por decision del user)

`weather_news`, `calendar_cloud`, `mail_cloud`, `todo_cloud`, `drive_cloud`,
`music_cloud`, `smart_home_cloud`, `communications_cloud`, `maps_places`.
Cada uno con su env var de token y `needs_user` si falta.

**Mantener la disciplina:**
- 100% local mientras no se decida lo contrario.
- NO scrappar UIs cuando hay API publica.
- NO leer/escribir datos sensibles sin gate explicito con
  `safety.create_confirmation`.
- eval_smoke debe seguir reportando missing=[] duplicate_count=0.
- Ninguna tool nueva queda con acciones devolviendo `needs_implementation`
  sin justificacion documentada aqui.

### (Original Fase E queue — pausada)

En orden de impacto:

1. **`weather_news`** — API meteorologica + RSS/news. Lowest barrier (no auth en
   APIs publicas tipo open-meteo). Cubre "que tiempo hace", "ultimas noticias".
2. **`calendar_cloud`** — Microsoft Graph Calendar + Google Calendar. El user
   ya tiene patron `GEMMA4_GRAPH_TOKEN` del email tool — reutilizar.
3. **`mail_cloud`** — extender el `email` tool actual con read inbox / search
   inbox / reply. Hoy solo envia.
4. **`todo_cloud`** — Microsoft To Do + Google Tasks. Mismo patron de token.
5. **`drive_cloud`** — OneDrive + Google Drive. Solo search/read/upload (sin
   share por seguridad).
6. **`music_cloud`** — Spotify Web API (Client Credentials para search, OAuth
   para playback). YouTube Music via private endpoints (fragil — diferir).
7. **`smart_home_cloud`** — Home Assistant local primero (deja `smart_home` ya
   propuesto), luego SmartThings/Tuya como bridges separados.
8. **`communications_cloud`** — Telegram (Bot API), Discord (webhooks),
   Slack (incoming webhooks). Sin leer mensajes en esta sesion (privacidad).
9. **`maps_places`** — OpenStreetMap/Nominatim primero (sin token), Google
   Maps Places API si el usuario provee key.

Despues de E quedaria solo lo deferido:
- `voice_io` (TTS+STT con Vosk/Piper locales o cloud)
- `capture` (camara/microfono — diferido por decision de producto)
- `creative_local` extensions: bridge a Krita/Blender/GIMP CLI
- Mejoras a tools existentes: `routine.on_app_open` real, `dns_set` con
  profile XML, `audio_device.set_app_route`.

**Mantener la disciplina:**
- Cada cloud tool con su env var documentada y `needs_user` si falta token.
- NO scrappar UIs cuando hay API publica.
- NO leer/escribir datos sensibles (correos, mensajes privados) sin gate
  explicito con `safety.create_confirmation`.
- eval_smoke debe seguir reportando missing=[] duplicate_count=0.
- Ninguna tool nueva queda con acciones devolviendo `needs_implementation`
  sin justificacion documentada aqui.

## Como Validar Cada Cierre

```powershell
python -m gemma4_agent.eval_smoke
python -m compileall -q gemma4_agent
```

`eval_smoke` debe imprimir `missing=[]` y `duplicate_count=0`. Cualquier
action nueva del contrato debe tener al menos un caso en `eval_smoke`. Si la
tool falla por dependencia real, el smoke debe aceptar `needs_dependency`
como passing, pero documentarlo aqui.

## Fuentes Tecnicas Para Implementar

- SoundVolumeView CLI:
  <https://www.nirsoft.net/utils/sound_volume_view.html>
- AudioDeviceCmdlets (PowerShell module):
  <https://github.com/frgnca/AudioDeviceCmdlets>
- Windows Media Session (WinRT):
  <https://learn.microsoft.com/uwp/api/windows.media.control.globalsystemmediatransportcontrolssessionmanager>
- Chromium DevTools Protocol:
  <https://chromedevtools.github.io/devtools-protocol/>
- pypdf:
  <https://pypdf.readthedocs.io/>
- pdfplumber:
  <https://github.com/jsvine/pdfplumber>
- icalendar:
  <https://icalendar.readthedocs.io/>
- vobject (vCard):
  <https://vobject.skyhouseconsulting.com/>
- Home Assistant REST:
  <https://developers.home-assistant.io/docs/api/rest/>
- Win32 SetWindowPos:
  <https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-setwindowpos>
- Windows Scheduled Tasks (PowerShell):
  <https://learn.microsoft.com/powershell/module/scheduledtasks/>
- ffmpeg CLI:
  <https://ffmpeg.org/ffmpeg.html>
