# Carter Agent — Roadmap Honesto

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
| A3 routine cron + run_now + history | done | `manual`, `once` y `cron` (daily/weekly/hourly/minutes) via Scheduled Tasks `\Gemma4Agent\` invocando `python -m gemma4_agent.infra.routine_runner`. process/file/network triggers documentados como deferred. |
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

## H1 — Hardening del chat de texto (timeouts + guards de honestidad, 2026-05-13)

Auditamos el nucleo de chat tras 8 sesiones de features (A..G6). Hallazgos
en el codigo real (no especulacion):

- LLM chat no aceptaba override de timeout por-call. Llamadas auxiliares
  (summarization, planner, replan) heredaban el global de 180s.
- Phrase trigger ejecutaba steps **sin** timeout. Una tool colgada en una
  rutina bloqueaba el turno entero antes de que Gemma viera el mensaje.
- Guard `_guard_unverified_final` solo aplicaba al final del turno. Si una
  tool fallaba a mitad y luego el LLM seguia llamando mas tools, el fallo
  desaparecia del radar y el agente podia decir "listo" sobre algo que
  fallo.
- `_format_phrase_fires` mostraba `ok=False` y errores pero **no obligaba**
  al LLM a reportarlos honestamente al usuario.
- `failure_log` para replan contaba CUALQUIER `ok=False`, incluyendo
  `needs_user_auth` y `needs_dependency`, que son blocked-on-input y no
  fallos del plan. Replan se disparaba en falsos positivos.

**Fixes:**

| ID | Que cambio | Archivo |
|---|---|---|
| H1.1 | `LLMClient.chat()` acepta `timeout_s` por-call. Las llamadas auxiliares usan 45s (planner/replan) y 60s (summarization). HTTP/socket timeouts se traducen a `RuntimeError('llm_timeout: ...')` en vez de URLError obscuro. | `llm_client.py`, `agent.py` |
| H1.2 | Cada step de phrase_trigger corre con `_run_with_timeout` (default 30s, override `GEMMA4_PHRASE_STEP_TIMEOUT_S`). Si vence, `step_results` recibe `timed_out=True` y la rutina sigue al siguiente step. Si el step lanza excepcion, `exception=True`. Implementacion via ThreadPoolExecutor con `shutdown(wait=False)` para no bloquear el turno por un worker colgado. | `agent.py` |
| H1.3 | Despues de cada batch de tool calls del LLM, si **alguna** tool retorno unverified/failed/needs_verification, insertamos un mensaje `role=user` efimero al historial: `[system note] In the previous step, these tools returned unverified/failed results: ... Do NOT claim those actions are complete`. Gemma no puede ignorarlo en el siguiente turno. Traceado como `unverified_intermediate_warning`. | `agent.py` + helper `_is_unverified_result` |
| H1.4 | `_format_phrase_fires` agrega un bloque WARNING explicito cuando >=1 step fallo: `"WARNING: N of M steps did NOT complete. You MUST tell the user honestly which actions did not run. Do not say 'listo' or 'done' for the failed steps."` Diferencia entre `ok=False` y `timed_out`. | `agent.py` |
| H1.5 | El `failure_log` que cuenta para replan **excluye** results cuyo `status` o `completion_status` empieza con `needs_`. Esos casos no se arreglan replanificando (necesitan accion del usuario). Traceado como `failure_excluded_from_replan`. | `agent.py` |

**Tests nuevos (test_gx_features.py, 11 -> 17):**
- `test_h1_1_chat_timeout_param_accepted`: el parametro existe y reporta error claro contra servidor inalcanzable.
- `test_h1_2_run_with_timeout_returns_on_hang`: una funcion que duerme 5s con timeout=0.5s retorna en <2s con `_timed_out=True`.
- `test_h1_2_run_with_timeout_captures_exception`: excepciones en el thread se capturan en `_error`, no se propagan.
- `test_h1_3_is_unverified_result`: la clasificacion `ok=False`, `verified=False`, `status=needs_verification`, `status=failed` activa el guard; `status=done` no.
- `test_h1_4_format_phrase_fires_failure_warning`: el bloque incluye "WARNING" cuando hay un step fallido, no cuando todos son ok.
- `test_h1_5_replan_excludes_needs_user_failures`: `needs_user_auth`, `needs_dependency`, `needs_verification` NO cuentan para replan; `failed` si.

Verificado: 62 tools, eval_smoke missing=[] duplicate_count=0,
test_router 61/61, test_gx_features 17/17.

## H2 — Memoria y bookkeeping (2026-05-13)

Tres fixes para que el agente envejezca bien tras meses de uso.

| ID | Que cambio | Archivo |
|---|---|---|
| H2.1 | `ExperienceMemory.prune(max_records, max_age_days)` con auto-trigger cada 50 inserts. Defaults 5000 records / 180 dias; override via `GEMMA4_EXPERIENCE_MAX_RECORDS` y `GEMMA4_EXPERIENCE_MAX_AGE_DAYS`. `stats()` expone budgets. | `experience.py` |
| H2.2 | Summarization con cooldown. `_compact_completed_history` se llama 3 veces por turno; sin cooldown, cada una podia disparar otro LLM round-trip. Nuevo `_summarization_cooldown_turns()` (default 6, override `GEMMA4_AGENT_SUMMARIZATION_COOLDOWN`). Cuando bloquea, hace truncate-only. `clear()` resetea contador. | `agent.py` |
| H2.3 | Semantic router con retry tras failures transitorios. `_STATE` ahora separa `permanently_disabled` (ImportError) de `last_error`/`attempt_count`. Hasta 3 reintentos con cooldown de 120s entre intentos. `status()` expone attempts y last_error. | `semantic_router.py` |

Tests (17 -> 20):
- `test_h2_1_experience_prune_max_records`: 12 inserts con limit=5, mantiene los 5 mas recientes.
- `test_h2_2_summarization_cooldown_helper`: defaults, env override, fallback a 6 cuando bogus.
- `test_h2_3_semantic_router_transient_retry`: patcha SentenceTransformer para fallar la primera y exito la segunda, confirma que NO marca permanent.

Verificado: 62 tools, eval_smoke limpio, test_router 61/61, test_gx_features 20/20.

## H3 — UX del chat (2026-05-13)

Tres fixes para que el usuario nunca quede colgado sin saber que pasa.

| ID | Que cambio | Archivo |
|---|---|---|
| H3.1 | `_guard_phrase_confirm` post-LLM. Si una rutina por frase se ejecuto y el LLM **no la menciona** en la respuesta (sin tokens 'hecho/listo/done' ni mencion del label o phrase), el agente **prepend** un mensaje corto: `Ejecute tu rutina: <label> N/M pasos.` Asi el usuario siempre sabe que su trigger se disparo aunque Gemma lo ignore. | `agent.py` |
| H3.2 | `_guard_plan_status` solo aparece cuando el explicit plan FALLO (no skipped) **y** la respuesta final es muy corta (<30 chars). Eso evita el caso confuso "pedi algo multi-step, el planner timeout, y el agente solo dijo 'ok'". `_explicit_plan_status` se traza siempre. | `agent.py` |
| H3.3 | `_parse_args` ahora devuelve `(args, parse_error)`. Si la tool-call tiene JSON malformado, **no llamamos** a la tool con datos sucios. En su lugar emitimos un tool_result sintetico con `status=failed` y mensaje claro: `tool args parse error: invalid_json: ... Re-emit the call with valid JSON`. Asi Gemma sabe exactamente que arreglar en la siguiente iteracion. Traceado como `tool_args_parse_error`. | `agent.py` |

Tests (20 -> 23):
- `test_h3_1_phrase_confirm_prepends_when_unack`: prefix se agrega cuando no hay ack; se omite si la respuesta dice 'hecho' o menciona el label.
- `test_h3_2_plan_status_surfaces_only_on_short_reply`: solo aparece con plan failed + reply <30 chars; skipped y ready no producen ruido.
- `test_h3_3_parse_args_distinguishes_malformed`: tupla devuelta correctamente para dict/string-json/empty/None/malformed/no-string.

Verificado: 62 tools, eval_smoke limpio, test_router 61/61, test_gx_features 23/23.

**Estado del chat de texto al cierre de H1+H2+H3:**

- 23 tests funcionales, 61 tests de router, 62 tools.
- Sin LLM calls que cuelguen al agente (timeouts por call).
- Sin tools intermedias que mienten "listo" sin verify.
- Sin rutinas que ejecuten en silencio (siempre confirmadas).
- Sin replan disparado por blocked-on-input.
- Sin malformed JSON pasado a tools.
- Sin experience memory que crece infinito.
- Sin summarization disparada cada turno.
- Sin semantic router muerto para siempre tras un fail transitorio.

Listo para empezar voz (F1) o camara (F2) cuando se decida.

## V2+V3 — Re-audit y limpieza de diagnostics (2026-05-13)

Tras decir "el chat esta solido", el user pregunto si estaba seguro. Lo
revise honestamente y la respuesta fue NO: nunca corri el agente contra
llama-server real ni revalide los hallazgos del audit original. Aqui el
resultado de re-verificar uno por uno.

### V3 — Pyright + ruff sobre el core

Instale pyright 1.1.409 y ruff 0.15.12. Corri **solo** sobre los archivos
del chat de texto core: agent.py, llm_client.py, experience.py,
explicit_plan.py, subagent.py, semantic_router.py, planner.py.

- **Pyright**: 3 errores reales antes, 0 al cerrar.
  - 2 falsos positivos en `_compact_json` (variables `out` con tipos
    distintos en bloques separados) -> renombradas a `list_out`/`dict_out`.
  - 1 real en `semantic_router.suggest_tools_semantic`: el `@` entre
    NDArrays podia inferirse como NDArray[bool_]. Cast explicito a
    `np.float32` resuelve la ambiguedad.
- **Ruff F (pyflakes)**: All checks passed. Sin imports muertos, sin
  variables sin usar, sin re-imports.
- Ruff E501 (185 line-too-long) ignorado: regex multi-idioma y schemas de
  tools son largos por diseno.

### V2 — Re-auditoria de los 11 hallazgos del audit original

Score: **11 cerrados, 2 parciales, 4 abiertos** (corregido a **12
cerrados, 2 parciales, 3 abiertos** tras el fix #13).

| # | Hallazgo | Estado | Evidencia (archivo:cambio) |
|---|---|---|---|
| 1 | Phrase trigger sin timeout | CERRADO | `_run_with_timeout` H1.2 |
| 2 | Compaction agresiva | CERRADO | cooldown H2.2 |
| 3 | Rowid mismatch sqlite-vec multi-proceso | ABIERTO (sincronico hoy) | n/a |
| 4 | Replan infinito | CERRADO | `replan_done` 1 vez por turno |
| 5 | Guard unverified solo al final | CERRADO | `unverified_intermediate_warning` H1.3 |
| 6 | Subagent close sin sync | ABIERTO (sincronico hoy) | n/a |
| 7 | Semantic recall silent | PARCIAL | logged pero usuario no ve |
| 8 | Experience memory sin limite | CERRADO | `prune()` H2.1 |
| 9 | Malformed JSON args | CERRADO | tupla `(args, parse_error)` H3.3 |
| 10 | LLM timeout summarization | CERRADO | `timeout_s=60` H1.1 |
| 11 | Semantic router muere para siempre | CERRADO | retry transient H2.3 |
| 12 | Phrase trigger sin feedback | CERRADO | `_guard_phrase_confirm` H3.1 |
| 13 | Subset truncation rigida a 8 | CERRADO esta sesion | `keep_count = max(4, len/2)`, traceado |
| 14 | Plan skipped silencioso | PARCIAL | logged + nota cuando reply <30 chars |
| 15 | LLM ignora rutina | CERRADO | force-prepend H3.1 |
| 16 | Summarization sesga hacia tail | ABIERTO (tradeoff de diseno) | n/a |
| 17 | Replan trigger ambiguo | CERRADO | `needs_*` filtrados H1.5 |

### Estado honesto al cierre

**Lo que SI esta validado:**
- 23 tests funcionales aislados pasan.
- 61 tests del router multi-idioma pasan.
- 62 tools registradas, eval_smoke limpio.
- Pyright 0 errors en el core de chat.
- Ruff pyflakes 0 errors.
- 12 de los 17 hallazgos del audit original cerrados con evidencia.

**Lo que NO esta validado:**
- Ningun turno corrido contra llama-server real. Los tests mockean el LLM.
- No medi latencia ni budget de tokens real.
- Sesion larga (30+ turnos) no probada — el cooldown de summarization
  esta cubierto por test unitario, no por flujo real.
- 3 hallazgos quedan abiertos: #3 (rowid race en multi-proceso, no aplica
  hoy), #6 (subagent close, idem), #16 (summarization tail-bias, tradeoff
  de diseno).
- Tools reales con efectos secundarios (set_app_route, smart_home,
  app.open) no fueron disparadas end-to-end por una rutina G6 en una
  corrida con llama-server.

**Lo que falta para decir "100% solido":**
- V1: arrancar llama-server y correr una bateria manual de 10-15 prompts
  que cubra cada feature. Sin eso, hay riesgo real de bugs que solo
  aparecen en runtime.
- V4: test de stress de 30+ turnos para validar summarization +
  experience pruning + cooldown en una corrida.

Hasta que V1+V4 se hagan, el agente esta **"validado unitariamente"**, no
"validado end-to-end".

## V1-partial — runtime real revelo 2 bugs (2026-05-13)

El user corrio `python -m gemma4_agent.support.chat` por primera vez contra
llama-server real y aparecieron dos bugs que los tests unitarios no
detectaron. Esto es el primer paso de V1.

### Bug A: phrase trigger no se crea

Transcripcion real:
- User: "Cuanto te dija tiempo quiero que aprietes la tecla de parar video"
- Agente: "De acuerdo. Cuando me digas la palabra clave, presionare..."
- User: "tiempo"
- Agente: "Quieres que presione ahora o establecer rutina?"
- User: "quiero que la dejes lista"
- Agente: ejecuto `notes_tasks(task_create)` (incorrecto)
- User: "tiempo"
- Agente: emitio `<|tool_call>call:input{key_code:91}<tool_call|>` literal
  (sintaxis inventada, no es un tool_call valido)
- Resultado: nada se ejecuto pero el agente dijo "Presione la tecla".

Causas:
1. Tipos del user ("Cuanto te dija") no matcheaban el regex del router
   ("cuando te diga") asi que `routine` no entro al subset.
2. La regla del SYSTEM_PROMPT estaba diluida en un parrafo y no era
   imperativa: no decia "MUST call routine(create)".
3. Sin ejemplo concreto end-to-end de "cuando te diga X aprieta Y".

Fixes:
- `planner.py:_suggest_tools`: agregue tipos de "cuando/cuanto te
  diga/dija", verbos imperativos "que aprietes/presiones/pulses/
  ejecutes", "recuerda esto/registra esta rutina", y equivalentes en
  EN/PT/FR/IT. Tambien anclo `gui` y `uia` al subset cuando aparecen
  estos triggers porque la rutina probablemente necesita keypress.
- `planner.py`: nuevo bloque que detecta "tecla de" / "media key" /
  "play.?pause" y agrega `gui` al subset.
- `agent.py` SYSTEM_PROMPT: reescribi la regla on_phrase como MUST
  con un ejemplo literal de la llamada `routine(action="create"...)`
  para "cuando te diga tiempo, aprieta play/pausa". Tambien linea
  explicita: "Never invent custom tool-call syntax like
  `<|tool_call>...`". Hubiera evitado el output malformado.

Verificado: con `Cuanto te dija tiempo quiero que aprietes la tecla
de parar video` el router ahora trae `routine + gui + uia + media`
al subset.

### Bug B: app.open con verified=False induce desconfianza

Transcripcion real:
- User: "abre marvel rivals"
- Agente: ejecuto `app({'action':'open','name':'Marvel Rivals'})`
- Tool retorno `status=attempted verified=False completion_status=launch_requested`
- Agente: "Intente abrir Marvel Rivals pero no pude verificar que se
  haya abierto correctamente"
- User confirmo: "Si abrio el juego pero dijo..."

Causa: `app_open` retornaba sin auto-verificar. El guard
`_is_unverified_result` (H1.3) inyectaba la nota de advertencia, y
Gemma la pasaba al usuario como "no pude verificar". El problema:
Steam-launched games tardan 2-30s en abrir su ventana; entre el
`os.startfile` y el render hay un gap que la herramienta no esperaba.

Fix:
- `tools.py:app_open`: tras lanzar la app, espera 2.5s (configurable
  via `GEMMA4_APP_OPEN_AUTOVERIFY_WAIT_S`) y reintenta
  `verify_app_opened`. Si encuentra ventana coincidente, status=done
  verified=True completion_status=launch_verified. Si no encuentra,
  intenta tambien con el `process_name` resuelto (e.g. "MarvelRivals.exe"
  para "Marvel Rivals"). Si aun asi nada matchea, vuelve a status=
  attempted como antes pero con nota mas precisa explicando que Steam
  games pueden tardar 10-30s.
- Disable con `GEMMA4_APP_OPEN_AUTOVERIFY=false`.

eval_smoke: 62 tools, missing=[] duplicate_count=0.
test_router: 61/61. test_gx_features: 23/23.

## Pendiente para proxima sesion (V1 + V4 completos)

Estos son los 5 puntos que el user pidio especificamente atacar en la
proxima sesion, copiados literal:

> Lo que NO esta validado:
> - Ningun turno corrido contra llama-server real. Todos los tests
>   mockean el LLM. Los bugs runtime-only no estan detectados.
> - No medi latencia real por turno con todas las features encadenadas.
> - No medi token budget real de Gemma 4 ES. El threshold de
>   summarization usa chars * 3 como aproximacion sin haber medido.
> - No hay test de stress de 30+ turnos para validar que summarization
>   + experience pruning + cooldown funcionan acumulativamente.
> - Tools con side effects reales (smart_home, set_app_route, app.open)
>   nunca disparadas end-to-end por una rutina G6.

**Update tras esta sesion:** Bugs A y B son el primer paso del primer
punto (V1 contra llama-server real). Esta sesion el user reporto los
errores tras correr el agente; quedan los otros 4 puntos para la
proxima.

Plan sugerido para la proxima sesion:
1. V1 manual completo: 10-15 prompts cubriendo cada feature; capturar
   trazas reales en `data/traces.jsonl` y revisar.
2. V4 stress: script mock que simula 30+ turnos para tocar
   summarization + pruning + cooldown en una corrida.
3. Medir latencia por turno (timestamp diff en traces).
4. Medir chars/token ratio real de Gemma 4 ES con un prompt conocido
   contra el endpoint `/tokenize` de llama-server.
5. Probar G6 phrase trigger end-to-end con una rutina que llame
   `app.open` o `smart_home.call_service`.

## Analisis de VRAM 6 GB con vision + voz (2026-05-14)

User pregunto si todo cabe en 6 GB VRAM con vision y voz obligatorias.
Respuesta corta: **si cabe pero con margen apretado y un riesgo
documentado de memory leak en llama.cpp**.

### Nomenclatura

El modelo es oficialmente **Gemma 3n E4B**, no "Gemma 4 E4B" (los
archivos en `models/E4B/gemma-4-*` tienen ese nombre por convencion
interna del repo). 3n = familia 3 nano/mobile con Per-Layer
Embeddings; E4B = 4 billion effective parameters. Mas info y fuentes
abajo.

### Audio nativo en Gemma 3n - cambia el juego

Segun ai.google.dev/gemma/docs/capabilities/audio: Gemma 3n incluye
un audio encoder integrado en el modelo principal (Universal Speech
Model). Genera 1 token cada 160ms de audio (~6 tokens/s). Entrenado
en 140+ idiomas.

Implicaciones:
- **No necesitamos whisper.cpp** para STT basico. El modelo lo hace.
- Tu `multimodal.py` ya envia `input_audio` en formato OpenAI; el
  endpoint de llama-server lo procesa con el mismo binario.
- WER de Gemma 3n vs Whisper-Large: 13.0 vs 4.4 (medium.com/ajjay.k).
  Peor para transcripcion verbatim, suficiente para comandos de
  Jarvis-style. Para dictado largo y critico, agregar Whisper sigue
  siendo mejor opcion.

Costo VRAM del audio encoder: **0 GB extra** (esta integrado en el
modelo, no en un mmproj separado).

### Tabla de VRAM consolidada

Fuentes: unsloth.ai/docs/models/gemma-4, knightli.com Gemma 4 quant
table, llama.cpp issue #21690, rhasspy/piper#121.

| Componente | VRAM | Notas |
|---|---|---|
| Gemma 3n E4B Q4_K_M | ~3.9 GB | "sweet spot" para 6 GB |
| Gemma 3n E4B UD-Q4_K_XL | ~4.2 GB | quant dinamico de unsloth; mejor calidad mismo tamaño |
| Gemma 3n E4B Q5_K_M | ~4.6 GB | calidad alta |
| Gemma 3n E4B Q6_K (config actual) | ~5.3 GB | NO cabe en 6 GB con mmproj |
| Gemma 3n E4B Q8_0 | ~6.8 GB | solo 8+ GB cards |
| Gemma 3n E2B Q4_K_M | ~1.5 GB | mucho margen pero reasoning notablemente peor |
| mmproj F16 (vision) | ~1.0 GB | obligatorio si quieres screenshots/imagenes |
| Audio encoder | 0 GB | integrado en el modelo principal |
| KV cache 8k context | ~0.2 GB | crece linealmente con context_size |
| KV cache 16k context (default actual) | ~0.4 GB | |
| Piper TTS | 0 GB VRAM, 50 MB RAM | piper en CPU es 5x mas rapido que GPU (rhasspy#121) |
| MiniLM embedder (fallback router) | 0 GB VRAM, 60 MB RAM | forzar CPU con CUDA_VISIBLE_DEVICES="" |
| Whisper.cpp base (opcional, no necesario con 3n nativo) | 0.5-0.9 GB | solo si WER de Gemma 3n no alcanza |
| Windows desktop @1080p | 0.4-0.7 GB | tipico Intel/AMD/NVIDIA WDDM |

### Calculo final para 6 GB VRAM (vision + voz activas)

```
Gemma 3n E4B Q4_K_M:    3.9 GB
mmproj F16:             1.0 GB
KV cache 8k:            0.2 GB
Audio encoder:          0.0 GB (integrado)
                        -------
Subtotal agente:        5.1 GB

Windows desktop:        ~0.5 GB
                        -------
TOTAL pico:             ~5.6 GB / 6 GB
```

**Cabe con ~400 MB de margen.** Pero hay un riesgo documentado.

### Riesgo: memory leak de mmproj en llama.cpp

[ggml-org/llama.cpp issue #21690](https://github.com/ggml-org/llama.cpp/issues/21690)
documenta que Gemma 3/4 con mmproj sufre un leak gradual de VRAM:
~6.4 MiB por request de imagen mas ~46 MiB de RSS por request en host
memory (cuBLAS workspace caching).

Implicacion practica: tras ~60-80 imagenes procesadas en una sesion,
los 400 MB de margen estan consumidos y el siguiente request OOM.

Mitigaciones:
1. **Restart periodico** del llama-server. El launcher ya soporta
   `--start-server`; agregar reciclaje cada N requests de vision.
2. **Disable vision por sesion**: arrancar sin `--mmproj` cuando la
   sesion es solo texto + audio. Re-arrancar con mmproj solo cuando
   el usuario lo pide.
3. **Cargar Gemma 3n E4B Q5_K_M no es viable** en 6 GB con mmproj.

### Configuracion recomendada por perfil de VRAM

Variables de entorno a setear (no auto-detect por ahora; el user lo
configura manualmente segun su GPU).

**6 GB VRAM (RTX 2060 / 3050 / 4050 mobile)**:
```powershell
$env:GEMMA4_MODEL_PATH = "models\E4B\gemma-4-E4B-it-Q4_K_M.gguf"
$env:GEMMA4_MMPROJ_PATH = "models\E4B\mmproj-F16.gguf"
$env:GEMMA4_AGENT_CONTEXT = "8192"
$env:CUDA_VISIBLE_DEVICES = ""  # para Piper + MiniLM en CPU
```

**8 GB VRAM (RTX 3060 / 3070 / 4060)**:
```powershell
$env:GEMMA4_MODEL_PATH = "models\E4B\gemma-4-E4B-it-Q5_K_M.gguf"
$env:GEMMA4_AGENT_CONTEXT = "16384"
```

**12+ GB VRAM (RTX 3060 12GB / 4070 / 4080)**:
```powershell
# Default actual ya funciona: Q6_K + 16k context
```

**16+ GB VRAM (RTX 4080 / 4090 / 4060 Ti 16GB - la actual del user)**:
```powershell
$env:GEMMA4_MODEL_PATH = "models\E4B\gemma-4-E4B-it-Q8_0.gguf"
$env:GEMMA4_AGENT_CONTEXT = "32768"
```

### Voz local concretamente

**STT (speech-to-text)**:
- **Default**: usar el audio encoder nativo de Gemma 3n via el endpoint
  `/v1/chat/completions` con `input_audio` (ya soportado en
  `multimodal.py`). Sin VRAM extra.
- **Solo si la calidad no alcanza**: instalar whisper.cpp base
  multilingual quantizado Q5_1 (~57 MB en disco, ~570 MB RAM en CPU).
  Eso es F1 voice_io en el roadmap original.

**TTS (text-to-speech)**:
- **Piper** con un voice model espanol (es_AR-daniela o es_ES-davefx).
  Pesos ~25-60 MB. Corre en CPU. Latencia: 100-300 ms para una frase
  de 50 palabras en CPU moderno (Ryzen 5/i5+). GPU es 5x mas lento
  (rhasspy#121).

### Conclusion para 6 GB

Cabe si:
- Bajamos a Q4_K_M.
- Bajamos contexto a 8k.
- Forzamos Piper + MiniLM en CPU.
- Aceptamos restart periodico de llama-server o disable vision en
  sesiones largas para evitar el leak.
- Usamos el audio encoder nativo de Gemma 3n (no whisper) para STT
  basico.

Performance esperada en 6 GB:
- 15-25 tokens/s de generacion (Q4_K_M en RTX 2060/3050).
- Latencia primer token: ~600-900 ms.
- Audio processing: 6 tokens/s, asi que 5 segundos de audio -> 30
  tokens de input. Latencia de transcripcion incluida en el turn
  normal (no es un paso aparte).

Si el user solo tiene 4 GB VRAM o menos: no es viable mantener
vision + audio. Bajaria a Gemma 3n E2B (~1.5 GB) y movemos mmproj a
CPU offload — pero entonces la latencia se dispara y el "Jarvis
local" deja de sentirse instantaneo.

## TriggerCMD bulk import (2026-05-14)

User pidio que el agente importe sus rutinas existentes de TriggerCMD
(JSON con `trigger`/`voice`/`command`/`offCommand`/`ground`/
`allowParams`/...) como on_phrase routines G6.

Mapeo:
- `voice` -> `trigger.phrase`
- `command` -> step `terminal(command=..., shell=True)`
- `offCommand` (si existe) -> segunda routine `<voice> off`
- `ground=background` -> `timeout_sec=5` (no esperamos completion)
- `allowParams=true` -> SKIP con razon (parametrizados se hacen a
  mano por ahora, segun decision del user)

### Forma de usarlo

Tres formas, todas comparten la misma logica:

```powershell
# 1) CLI directo
python -m gemma4_agent.support.import_triggercmd C:\TriggerCMD\commands.json

# 2) Dry-run sin escribir nada
python -m gemma4_agent.support.import_triggercmd C:\TriggerCMD\commands.json --dry-run

# 3) Desde el chat con Gemma
# Le pides "importa mis rutinas de TriggerCMD" y el agente llama:
#   routine(action="import", source="triggercmd",
#           json_path="C:/TriggerCMD/commands.json")
```

### Defensa en profundidad contra comandos destructivos

Las dos capas que protegen al user de disparos accidentales:

**Capa 1: auto-disable al importar.**
`_looks_destructive(command)` detecta tokens como `shutdown`,
`reboot`, `logoff`, `format`, `diskpart`, `rmdir /s`, `del /q`,
`del /f`, `cipher /w`, `Stop-Computer`, `Restart-Computer`,
`Remove-Item`, `uninstall`, etc. Las rutinas que matchean se
importan con `enabled=False`. El user las habilita una por una con
`routine(action="enable", id=...)` cuando confia.

**Capa 2: guard de hipotetico/pregunta en el phrase hook.**
Cuando una rutina activa es destructive (segun la misma deteccion),
el hook descarta el match si:
- El mensaje del user incluye `?` (pregunta).
- Empieza con un hypothetical: "que pasa si", "what if",
  "que ocurre si", "y si digo", "is it ok if", etc.

Casos cubiertos (probados en runtime real):
- `"reboot"` -> dispara
- `"reboot please"` -> dispara
- `"que pasa si digo reboot?"` -> NO dispara
- `"what if i say reboot"` -> NO dispara

Caso NO cubierto (limitacion honesta):
- `"no quiero reboot"` -> dispararia si la rutina esta habilitada.
  La negacion sintactica no se detecta. Mitigacion: capa 1
  mantiene la rutina deshabilitada hasta que el user la habilite
  explicitamente.

### Tests (24 -> 27)

- `test_triggercmd_import_basic`: imports 2 simples (`notepad`,
  `reboot`), skips 3 (allowParams, empty cmd, short voice). Verifica
  que `reboot` queda `enabled=False` y `notepad` `enabled=True`.
- `test_triggercmd_destructive_detection`: 7 cases positivos
  (shutdown, format, rmdir /s, etc) y 4 negativos (notepad, spotify,
  ahk launcher, echo).
- `test_triggercmd_import_off_routine`: entry con `offCommand`
  genera dos routines (`<voice>` y `<voice> off`).
- `test_triggercmd_import_duplicate_skipped`: re-import del mismo
  payload no duplica routines.

### Limitaciones documentadas

- `allowParams=true` no soportado (deferred a manual).
- `voiceReply` ignorado (el SYSTEM_PROMPT de G6 ya pide a Gemma
  confirmar; no necesitamos plantilla fija).
- Negacion sintactica ("no", "nunca") no detectada en el hook (la
  capa 1 deshabilitada-por-default es la mitigacion real).
- Comandos con cwd implicito pueden no funcionar como en TriggerCMD
  si tienen rutas relativas; recomendado siempre full path en el
  comando original.

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
python -m gemma4_agent.support.eval_smoke
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

## Auditoria vs jarvis-personal-ai (2026-05-14)

El usuario pidio comparar contra el repo `jarvis-personal-ai-main` (incluido en
el workspace como referencia de competidor). Se revisaron sus 26 features
declaradas. Estado y recomendacion mia abajo. Implementados los 5 con `Si` en
la columna **Replicar**.

| # | Feature competidor | Tenemos? | Replicar? | Notas |
|---|---|---|---|---|
| 1  | LLM multi-proveedor (OpenAI/Anthropic/Local) | Local-only por decision | No | Mantenemos privacidad 100% local con llama-server. |
| 2  | Tool calling | Si (62 schemas, additionalProperties=false) | — | Mas robusto: subset + router multi-idioma + semantic fallback. |
| 3  | RAG / Knowledge base | Si (SQLite FTS5 + embeddings) | — | Mejorado en J1 con cross-encoder rerank. |
| 4  | Cross-encoder reranking | No (antes de J1) | **Si — J1** | Implementado: ms-marco-MiniLM-L-6-v2 lazy-load con retry-cooldown. Over-fetch 4x BM25. |
| 5  | Fact extraction automatica | No (antes de J2) | **Si — J2 (opt-in)** | Implementado: extrae 0-3 hechos por turno via LLM y guarda con prefijo `auto:` en MemoryStore. Privacidad: OFF por defecto. |
| 6  | Personas / prompts por modo | No (antes de J3) | **Si — J3** | Implementado: 6 personas (default/coder/researcher/creative/planner/casual). CLI `/persona`. |
| 7  | Project context auto-load (CLAUDE.md / AGENTS.md / .cursor/rules) | No (antes de J4) | **Si — J4** | Implementado: walk-up cwd + 3 padres, max 6000 chars, regenera cada turno. Toggle GEMMA4_AGENT_PROJECT_CONTEXT. |
| 8  | Parallel tool execution | No (antes de J5) | **Si — J5 (opt-in)** | Implementado: ThreadPoolExecutor(max_workers=4) cuando hay 2+ tool_calls validos. Orden preservado en history. OFF por defecto. |
| 9  | Memoria persistente entre sesiones | Si | — | MemoryStore + ExperienceMemory (sqlite-vec). |
| 10 | Plan + replan explicito | Si | — | explicit_plan + cooldown + give_up. |
| 11 | Subagents | Si | — | spawn con presupuesto + scoped subset. |
| 12 | Phrase-triggered routines (Alexa-style) | Si | — | G6 + import desde TriggerCMD con safety contra destructivos. |
| 13 | Honesty guard / unverified detection | Si | — | H1: `_is_unverified_result` + auto-inject system note. |
| 14 | Hard timeouts en chat / tools | Si | — | H1: `_run_with_timeout` con executor abandonable. |
| 15 | Summarization / context compaction | Si | — | G2 two-stage (cheap pass + LLM summary) con cooldown H2. |
| 16 | Experience pruning | Si | — | H2: max_records FIFO. |
| 17 | Semantic router multi-idioma | Si | — | P4.5: ES+EN+PT+FR+IT + embedding fallback con retry transient. |
| 18 | Web research con citation | Si | — | web + source_manager + fact_check. |
| 19 | Browser automation visible (attach a Chrome real) | Si | — | B1: browser_real attach_visible via CDP. |
| 20 | Document extraction (PDF/DOCX/PPTX/XLSX/HTML) | Si | — | B2: document tool con extract_text/tables/images/ocr. |
| 21 | Local Office creation (Word/Excel/PowerPoint) | Si | — | python-docx + openpyxl + python-pptx + LibreOffice export_pdf. |
| 22 | Smart home control | Si | — | Home Assistant REST + state cache. |
| 23 | Multi-model analysis (compare outputs de varios LLMs) | No | No | No vale local-only; mantenemos un solo Gemma. |
| 24 | Dynamic skills / plugin loading at runtime | No | No (defer) | Riesgo de side-effects sin sandbox; tools fijas y auditables son mejor por ahora. |
| 25 | Light/Dark mode CLI | No | No | El chat es texto plano; tema es del terminal del usuario. |
| 26 | Voice (TTS/STT) | Parcial (audio_device routing existe, no STT/TTS engines) | Defer hasta F1 | Whisper.cpp + Piper TTS pendiente; requiere modelo extra y deps. |

**Resumen:** 17/26 ya cubierto (a menudo con mas detalle). 5 brechas
replicadas en esta sesion (J1-J5). 4 deferidas para F1/F2 (#26 voice + 3
restantes). 3 explicitamente rechazadas (#23, #24, #25) por incompatibles con
el contrato local-only o triviales.

## Fase J — close jarvis-personal-ai gaps (2026-05-14)

Implementadas las 5 features con `Si` en la tabla anterior:

| Item | Modulo | Toggle env | Default | Notas |
|---|---|---|---|---|
| J1 Cross-encoder rerank | `knowledge.py` (`_rerank_rows`, `_load_reranker`) | `GEMMA4_KNOWLEDGE_RERANK` (default ON), `GEMMA4_RERANK_MODEL` | ON | Lazy-load con retry-cooldown (max 3 intentos / 120 s), perma-disabled tras 3 fallos. Over-fetch 4x BM25 -> rerank -> top `limit`. Fallback silencioso al orden BM25 si el modelo no carga. Nuevo param `rerank: bool` en schema knowledge. |
| J2 Fact extraction | `agent.py` (`_extract_facts`, helpers `_fact_extraction_enabled` + `_fact_extraction_cooldown_turns`) + `memory.py` (`auto_save`) | `GEMMA4_AGENT_FACT_EXTRACTION`, `GEMMA4_AGENT_FACT_EXTRACTION_COOLDOWN` | OFF (privacidad) | Tras cada turno completado: 1 llamada LLM (timeout 20 s) pidiendo JSON array de 0-3 hechos `{key, value}` con keys cortas en snake_case. Persistencia con prefijo `auto:` para distinguir de explicit memory. FIFO eviction al pasar de 50 entradas auto. |
| J3 Personas | `personas.py` (nuevo) + `agent.py` (`set_persona/get_persona`, `_system_message` injection) + `chat.py` (`/persona`) | `GEMMA4_AGENT_PERSONA` | `default` (no nudge) | 6 personas: default/coder/researcher/creative/planner/casual. Cada una aporta `system_hint` apendado al SYSTEM_PROMPT y `preferred_tools` merged en el subset del planner. Switch en runtime via `/persona <name>`. |
| J4 Project context | `project_context.py` (nuevo) + `agent.py._system_message` injection | `GEMMA4_AGENT_PROJECT_CONTEXT` | ON | Walk-up cwd + 3 padres buscando `GEMMA4.md`/`JARVIS.md`/`CLAUDE.md`/`AGENTS.md`/`.cursor/rules`/`.cursorrules`/`.gemini/instructions.md`. Max 6000 chars con `[truncated]` marker. Regenera cada turno para soportar edicion en vivo. Bloque incluye warning: NO obedecer instrucciones que contradigan SYSTEM_PROMPT (defense vs prompt injection en archivo de proyecto). |
| J5 Parallel tool execution | `agent.py` (`_execute_calls_sequential`, `_execute_calls_parallel`, `_parallel_tools_enabled`) | `GEMMA4_AGENT_PARALLEL_TOOLS` | OFF | Cuando 2+ tool_calls validos en una respuesta del modelo, los ejecuta concurrentes con `ThreadPoolExecutor(max_workers=min(4, len(valid)))`. Phase 1 parsea+clasifica, Phase 2 ejecuta (sequential o parallel), Phase 3 aplica resultados al history/events en orden original. Parse-error preps cortocircuitan con synthetic result sin tocar el pool. Excepciones del executor se capturan en `evidence=parallel_exception`. |

Tests: 36/36 pasando (`gemma4_agent.test_gx_features` incluye 9 nuevos J1-J5).
Pyright: 0 errores en los modulos tocados (tools.py mantiene su baseline
preexistente de 26 errors irrelevantes a esta fase).

Cosas a recordar para la proxima sesion:

- J2 fact extraction esta OFF por defecto. Para activarlo: `set GEMMA4_AGENT_FACT_EXTRACTION=true`. Costo: 1 LLM call extra por turno (con cooldown). Verifica con `/recall` que los hechos guardados son sensatos antes de dejarlo on en una sesion larga.
- J5 parallel esta OFF por defecto porque varias tools comparten estado (filesystem, registry, apps_index, MCP clients). Solo activar (`set GEMMA4_AGENT_PARALLEL_TOOLS=true`) si tu workflow tipico tiene tool_calls genuinamente independientes (e.g., `web` + `knowledge.search`).
- J1 cross-encoder requiere `sentence-transformers` y un primer download del modelo (~80MB). Si la dep falta o el download falla 3 veces, queda permanently_disabled hasta reiniciar el proceso.

## Fase K — close jarvis-personal-ai gaps round 2 (2026-05-14)

Despues de la auditoria contra la lista revisada del competidor (26 features
de las cuales nos enfocamos en RAG/tools/memoria/contexto, omitiendo voz, UI
web y camara), se identificaron 3 brechas/mejoras que vale la pena replicar:

| Item | Modulo | Toggle env | Default | Notas |
|---|---|---|---|---|
| K1 Chat history persistente entre sesiones | `sessions.py` (nuevo) + `chat.py` (`/sessions`, `/load <id>`, `/new`, `/title <txt>`) | `GEMMA4_AGENT_SESSIONS`, `GEMMA4_AGENT_SESSIONS_DIR` | ON | Cada `python -m gemma4_agent.support.chat` arranca con una `Session` nueva. Cada turno (user+assistant) se persiste en `~/.gemma4/sessions/<id>.json`. Auto-title con 1 LLM call al primer turno (timeout 10 s, max 30 tokens) y fallback a heuristica de primeras 6 palabras si la LLM falla o esta deshabilitada. `/load <id>` carga la session previa pero el agente arranca con history vacio (los turnos son referencia para el usuario, no se reinyectan al SYSTEM_PROMPT — eso evita perder coherencia con el contrato local-only). |
| K2 Tool timeline export | `timeline.py` (nuevo) + wrapper `TimelineWriter` en `chat.py` | `GEMMA4_AGENT_TIMELINE`, `GEMMA4_AGENT_TIMELINE_DIR` | ON | Forwarder que envuelve el `progress` callback y escribe cada event como JSONL en `~/.gemma4/timeline/<session_id>-turn<NNN>.jsonl`. Truncacion segura: strings > 600 chars marcados con `...[trunc]`, listas > 20 items recortadas, dicts grandes serializados como string. Util para inspeccion post-mortem o render externo. |
| K3 Dynamic context budgets proporcionales | `agent.py` (`_compute_context_budget` nuevo, `_compact_completed_history` reescrito para usarlo) | hereda `GEMMA4_AGENT_CONTEXT` ya existente | — | Reemplaza las constantes `[-30:]` y `[-18:]` y el `keep_tail = 6` por valores derivados de `context_size`. Reserva 30% del context window para el siguiente turno y dedica 70% a history. Numbers: ctx=4K -> soft 17 / hard 8 / keep_tail 4 / threshold 6450; ctx=32K -> 137/68/27/51608; ctx=200K -> 200/100/30/cap 1.575M chars. Conservative cap superior de 200 mensajes evita que ctx muy grandes consuman memoria sin limite. |

Tests: 42/42 pasando (`gemma4_agent.test_gx_features` incluye 6 nuevos
K1-K3). 61/61 router. pyright 0 errors en modulos tocados. eval_smoke 62
schemas, missing=[].

Resumen jarvis-personal-ai post K1-K3 (omitiendo UI web, voz, camara):

- **18/23 features cubiertas o mejores** (RAG con rerank, parallel tools, memory, plan/replan, subagents, doc processing, semantic experience recall, summarization, personas, project context, fact extraction, sessions, timeline, dynamic budgets).
- **2 deferidas a F1**: stop-generation mid-stream (CLI lo aprueba con Ctrl+C; importa solo con UI), strong identity lock (parcial via SYSTEM_PROMPT + personas).
- **2 rechazadas por decision**: multi-model analysis (rompe local-only), dynamic skills runtime (riesgo de exec arbitrario, prefiero tools fijas y auditables).

## Fase U — Jarvis-style desktop GUI (2026-05-14)

Construida una GUI PyQt6 local estilo Mark XXXIX en `gemma4_agent/ui/`. Una sola corrida: `python -m gemma4_agent.ui`. Sin servidor, sin npm, sin browser — todo en proceso.

| Modulo | Que hace |
|---|---|
| ui/theme.py            | Paleta cyan Jarvis, STATE_TABLE (10 estados con simbolo+color), QSS helpers, `symbol_font()` (Segoe UI Symbol fallback). |
| ui/metrics.py          | `SysMetrics` thread daemon que samplea CPU/MEM/NET/GPU/TMP/DISK cada 1.5s. nvidia-smi + rocm-smi + WMI (Windows) + sensors_temperatures (Linux). |
| ui/hud.py              | **HudCanvas** — el centerpiece. 60fps. 3 anillos giratorios con velocidades diferentes, halo radial pulsante, 2 scanners arc cruzandose, tick marks cada 10° con labels grados, brackets esquineros, crosshair, particulas radiales en SPEAKING/THINKING, waveform animado, pulse rings expanding, datos hex orbitando, telemetria CPU·OK MEM·OK NET·ON etc, orbe interior con iris+highlight, metadata strip (modelo / persona / conexion). |
| ui/metric_bar.py       | Barras CPU/MEM/GPU/NET/DISK/TMP con thresholds amber>65% red>85%. |
| ui/log_widget.py       | LogWidget typewriter (4ms/char) coloreado por tag: you/ai/tool/ok/err/sys/file/warn. Thread-safe via signal. |
| ui/agent_thread.py     | AgentWorker QThread. Health poll cada 8s. Emite signals: state_changed/progress/log/reply_ready/llm_error/connection_changed. |
| ui/panels.py           | Header (titulo+reloj+brand+date), Left panel (SYS MONITOR + UP/PROC/OS + CONTEXT BUDGET + status badges), Right panel (LOG + 5 action buttons + COMMAND INPUT con attach), Footer (shortcuts + session id). |
| ui/sessions_panel.py   | Sidebar overlay K1. Search filter, double-click loads, NEW/RENAME/DELETE/LOAD. |
| ui/settings.py         | **9 tabs**: CONNECTION (server URL, model alias, GGUF path, ctx, max_tokens), AGENT (mode, persona, max turns, safety), SAMPLING (temperature, top_p/top_k, min_p, repeat_penalty, seed, enable_thinking, parallel_tool_calls), BEHAVIOUR (cooldowns, timeouts, experience max, strict honesty, auto-replan), TRANSCRIPT (STT provider/model/language, TTS provider/voice/rate, wake word), TOGGLES (8 env-var feature toggles J1-J5+K1-K3+G2+TRACE), PATHS, PROMPT (SYSTEM_PROMPT readonly), ABOUT. Persistido a `~/.gemma4/gui.json`. |
| ui/triggers.py         | Editor TriggerCMD-style. CRUD + run_now + Import JSON. Reusa la tool `routine` con safety contra destructivos. |
| ui/memory_viewer.py    | 3 tabs: PERSISTENT (CRUD MemoryStore), EXPERIENCE (semantic recall sobre sqlite-vec), KNOWLEDGE (search con rerank J1). |
| ui/tool_explorer.py    | Browser de las 62 tools con search filter + schema preview + run form para invocar cualquier action manualmente. |
| ui/main_window.py      | Ensambla todo. 8 shortcuts (F11, Ctrl+L/N/,/T/M/E/Shift+S). |
| ui/app.py              | Splash boot animado + entry point. |

**Estados HUD**: INITIALISING / IDLE / LISTENING / THINKING / PROCESSING / EXECUTING / SPEAKING / ERROR / MUTED / OFFLINE — cada uno con color, simbolo blinking y velocidades de animacion propios.

**Configurable desde la GUI** (pedido explicito del usuario):
- Modelo Gemma (alias + GGUF path + context size)
- Server URL + max_tokens
- Sampling completo (temperature/top_p/top_k/min_p/repeat_penalty/seed/thinking/parallel_tool_calls)
- Modo agente + Persona + max_turns + safety
- Comportamiento (cooldowns, timeouts, experience max, strict honesty, auto-replan)
- Transcripcion (STT/TTS providers/models/voice/rate + wake word)
- 8 toggles env-var (J1-J5, K1-K3, G2, TRACE)
- Paths (memory/state/trace/sessions/timeline)
- Phrase triggers (CRUD + import TriggerCMD JSON)
- Memory (add/delete/clear/search semantico)
- Tools (browse + run manual)

**Validacion:**
- 44/44 tests pasando (2 nuevos U1).
- pyright 0 errores en `ui/`.
- eval_smoke missing=[], 62 schemas.
- HUD verificado renderizando los 9+ estados.
- MainWindow construye sin crash con worker stub (offscreen test).

**Como lanzar:** `python -m gemma4_agent.ui` (requiere `pip install PyQt6`).

## Fase V — perfiles dinamicos de VRAM (2026-05-14)

Cuatro perfiles fijos que cambian context_size, modelo, vision (mmproj),
rerank, parallel_tools y fact_extraction de forma atomica. Reusable como
"gaming mode" sin tener que entrar a Settings y reiniciar a mano.

### Perfiles default

| Perfil | ctx | vision | rerank | parallel_tools | fact_extr | server | est_vram_mb |
|---|---|---|---|---|---|---|---|
| Performance | 32K | ON | ON | ON | ON | running | 7500 |
| Balanced (default) | 16K | ON | ON | OFF | OFF | running | 5500 |
| Light | 4K | OFF (mmproj sin cargar) | OFF | OFF | OFF | running | 3800 |
| Standby | 4K | OFF | OFF | OFF | OFF | **stopped** | 0 |

Los `est_vram_mb` son solo display en UI; no se usan para decisiones.
Numeros derivados del INFORME_ARQUITECTURA_6GB.md (recalibrados pre-merge
para reflejar la arquitectura recomendada: E2B-Q4+mmproj para Balanced,
E4B-Q4+mmproj para Performance, E2B-Q4 sin mmproj para Light).

### Decisiones tomadas

- **Control hibrido.** Manual por default (4 pildoras en panel izquierdo +
  hotkey global Ctrl+Shift+G). Auto-switch es opt-in en Settings -> PROFILES.
- **Server arrancado por Gemma4** via nuevo `LlamaServerManager`. Si detecta
  server externo en :8080 (socket.connect_ex), NO lo mata: aplica env vars
  y reinicia el worker, loggea warning amber tanto en stderr como en el
  activity log. Para usuarios que tenian su propio llama-server arrancado a mano.
- **Modelo chico de Light lo baja el usuario manualmente.** Si LIGHT esta
  activo y `light_model_path` apunta a un archivo inexistente, la GUI muestra
  QMessageBox warning amber con la ruta esperada y cae al modelo principal
  con context=4096 como fallback. `GEMMA4_MODEL_PATH` NO se sobreescribe.
- **Histeresis 30s/60s.** Watcher exige condicion sostenida 30s para bajar
  y ausencia sostenida 60s para subir. Sin oscilaciones.
- **Solo STANDBY pide confirmacion.** Los otros cambios son inmediatos
  (decision del usuario para reducir friccion).
- **GPU usage per-proceso** via `nvidia-smi pmon -c 1 -s u`, excluyendo el
  PID/comando que contenga "llama-server" (asi nuestra propia generacion
  no cuenta como "GPU ocupada"). Costo: subprocess ~50ms cada 10s.

### Modulos involucrados

- `gemma4_agent/profiles.py` — Profile dataclass, PROFILES dict (4 perfiles),
  `detect_vram_mb()` (nvidia-smi -> rocm-smi -> None), `recommend_profile()`,
  `get_active_profile()` (lee `~/.gemma4/active_profile.txt`),
  `set_active_profile()` (atomic write), `apply_profile_to_env()`,
  `load_overrides()`/`save_overrides()` (`~/.gemma4/profiles.json`).
- `gemma4_agent/llama_server.py` — `LlamaServerManager` con
  start/stop/restart/is_running/current_profile/is_external_server.
  Detecta server externo via `port_in_use(127.0.0.1, 8080)`.
- `gemma4_agent/profile_watcher.py` — Thread daemon con `threading.Event.wait`
  (no `time.sleep`). Tres condiciones opt-in: game (psutil), gpu (pmon),
  ram (psutil). Histeresis 30s/60s. Callback `on_change(name, reason)`
  que la GUI marshalla al main thread via `QTimer.singleShot(0, ...)`.
- `gemma4_agent/launcher.py` — `start_server` ahora delega en
  LlamaServerManager y respeta el perfil activo. Maneja external/standby
  /missing_files/timeout explicitamente.
- `gemma4_agent/config.py` — `AgentConfig.from_env()` ahora aplica el
  perfil persistido (`active_profile.txt`) cuando NINGUN env var del perfil
  esta seteado todavia. Cubre el caso "primer arranque tras reboot, GUI no
  clickeo nada todavia". Respeta seteos manuales del usuario.
- `gemma4_agent/ui/panels.py` — Selector de 4 pildoras en panel izquierdo.
  Tooltip por hover con description + est_vram_mb.
- `gemma4_agent/ui/main_window.py` — Wiring del selector, hotkey
  Ctrl+Shift+G (cicla PERF -> BAL -> LIGHT -> STDBY), confirmacion solo para
  STANDBY, warning amber para LIGHT con modelo chico ausente, bloqueo de
  chat input cuando perfil activo es STANDBY ("Server offline — switch
  profile to chat."), reconfiguracion del watcher al guardar settings.
- `gemma4_agent/ui/settings.py` — Nuevo tab PROFILES con tres secciones:
  DETECCION (VRAM medida + perfil recomendado + redetectar),
  AUTO-SWITCH (opt-in master + 3 sub-toggles + dropdowns down/up +
  textarea editable game_watchlist), PERFILES (tabla 5 filas x 3 cols
  editable, boton "RESTAURAR DEFAULTS"). Persiste auto config en
  `gui.json -> profiles_auto`, overrides en `profiles.json`.

### Configurabilidad expuesta

| Cosa | Donde se lee | Donde se setea |
|---|---|---|
| Perfil activo | `~/.gemma4/active_profile.txt` (una linea) | Selector GUI + `set_active_profile()` |
| Overrides de perfiles | `~/.gemma4/profiles.json` | Tab PROFILES -> tabla editable -> Apply |
| Auto-switch config | `~/.gemma4/gui.json` key `profiles_auto` | Tab PROFILES -> AUTO-SWITCH |
| Game watchlist | dentro de `profiles_auto.game_watchlist` (list) | Tab PROFILES -> textarea |
| Env vars escritos por el perfil | `os.environ` (volatil) | `apply_profile_to_env(profile)` |
| `GEMMA4_AGENT_CONTEXT` | `AgentConfig.from_env` | perfil + Settings -> CONNECTION |
| `GEMMA4_KNOWLEDGE_RERANK` | `knowledge.py::_load_reranker` | perfil + Settings -> TOGGLES |
| `GEMMA4_AGENT_PARALLEL_TOOLS` | `agent.py::_parallel_tools_enabled` | perfil + Settings -> TOGGLES |
| `GEMMA4_AGENT_FACT_EXTRACTION` | `agent.py::_fact_extraction_enabled` | perfil + Settings -> TOGGLES |
| `GEMMA4_MMPROJ_PATH=""` | `llama_server.py::llama_command` (omite `--mmproj`) | perfil (vision_enabled=False) |
| `GEMMA4_MODEL_PATH` | `AgentConfig.from_env` + `llama_command` | perfil.model_path si el archivo existe; sino usuario |

### Validacion

- 57/57 tests passing (49 previos + 8 nuevos V1-V8).
- Tests cubren: recommend by vram (V1), atomic set/get (V2), apply complete (V3),
  CRITICAL round-trip via AgentConfig (V4), histeresis 30s/60s (V5),
  standby no arranca server (V6), external server no se mata (V7),
  light con modelo missing cae bien (V8).
- pyright 0 errors en archivos nuevos y modificados.
- UI modules importables sin display (QT_QPA_PLATFORM=offscreen).

### Limitaciones conocidas

- No hay auto-download del GGUF chico de Light. El usuario lo baja a mano
  y configura la ruta en Settings -> PROFILES -> tabla -> `model` (col Light).
- No exponemos un toggle para cantidad de perfiles; siempre son 4.
- Si el usuario tiene un server externo corriendo, la app aplica env vars
  y reinicia su worker, pero el server externo conserva sus propias flags.
  El usuario ve el warning amber en activity log.
- `detect_vram_mb()` no usa dxdiag fallback (parseo poco fiable). Sin
  nvidia-smi ni rocm-smi -> None -> recommend_profile devuelve "balanced".

## Fase W — Voz local (wake-word + STT streaming + TTS streaming) (2026-05-14)

Hablarle al agente con "gemma" / "hey gemma", transcribir en streaming, y que
conteste por voz mientras el LLM genera tokens. Todo 100% CPU. Diseno y
restricciones vienen del INFORME_ARQUITECTURA_6GB.md secciones 2 y 6.

### Arquitectura

```
mic --(int16 16k 30ms)--> AudioCapture (PortAudio thread)
                                |
                                +--> WakeDetector (Vosk small es)  while IDLE_LISTENING
                                |        |
                                |        +--(on wake)--> beep + HUD --(200ms)--> LISTENING
                                |
                                +--> StreamingSTT  (faster-whisper small int8 + Silero VAD)
                                              |
                                              +--(partial)--> GUI placeholder
                                              +--(final)----> agent (via on_send)
                                                                |
                                              [LLM streaming SSE]
                                                                |
                                              +--(deltas)----> StreamingTTS (Piper)
                                                                  |
                                                                  +--(audio)--> speaker
```

Estados de la state machine:
`IDLE_DISABLED | IDLE_LISTENING | WAKE_DETECTED | LISTENING | TRANSCRIBING
| THINKING | SPEAKING | FOLLOWUP | FAILED`.

### Decisiones tomadas (no replantear)

- **Wake-word**: ambas frases "gemma" y "hey gemma" siempre activas, Vosk
  small es-0.42 (~40 MB) con vocabulario restringido. Debounce 2 s para
  evitar falsos positivos en cadena.
- **STT**: faster-whisper `small` int8 en CPU + Silero VAD. language="es"
  fijo. beam_size=1 default, 5 si audio >5 s. condition_on_previous_text=False.
- **Endpoint**: VAD detecta silencio 400 ms tras hablar -> final. Techo
  absoluto 15 s desde inicio de habla. Timeout 5 s pre-habla.
- **Auto-fallback**: si la primera transcribe de >=1 s tarda >3 s, baja a
  `base`. Persiste via `GEMMA4_VOICE_STT_MODEL`.
- **TTS**: Piper VITS+ONNX CPU, voz default `es_MX-claude-high`. Sentence-
  chunking del stream del LLM (`.!?;¡¿\n\n` cierra oracion). Worker thread
  FIFO; productor LLM no bloquea.
- **Follow-up window**: 5 s tras TTS (configurable 0/5/10 s) donde se puede
  hablar sin wake-word. HUD muestra cyan suave. Close phrases: "gracias",
  "listo", "ya esta", "cancelar", "stop" (normalizadas case + accents).
- **Feedback wake**: beep 80 ms 600 Hz + HUD parpadeo cyan brillante. TTS "si"
  como toggle opcional (default OFF).
- **Voz por perfil**: PERF y BAL -> voice on (si usuario lo habilito en
  Settings). LIGHT y STANDBY -> voice off, modelos liberados de RAM.
- **No es_AR oficial**: Piper no tiene voz rioplatense. Default es_MX-claude-high
  (acento neutro latino). Usuario puede fine-tunear o agregar voz custom en
  `~/.gemma4/models/piper/`.

### Modulos nuevos

| Modulo | Responsabilidad |
|---|---|
| `voice/audio_io.py` | sounddevice wrapper + ring buffer 5 s. 16 kHz mono int16 chunks de 30 ms. |
| `voice/wake.py` | WakeDetector Vosk con descarga consensuada del modelo. `model_exists()`/`download_model()` para la UI. |
| `voice/stt.py` | StreamingSTT con faster-whisper + Silero VAD. transcribe_stream() yields STTEvent (partial/final/timeout/error). Auto-fallback a base. |
| `voice/tts.py` | StreamingTTS con Piper. feed_text() acumula y encola oraciones a worker thread; sentence splitter respeta signos invertidos espanoles. `installed_voices()` para el dropdown. URLs hardcoded a HuggingFace. |
| `voice/controller.py` | VoiceController con state machine completa + callbacks. Componentes en threads dedicados, comunicacion via Queue/callbacks. enable()/disable()/trigger_manual()/set_tts_muted(). |

### Pre-requisito implementado: SSE en `llm_client.py`

Nuevo metodo `chat_stream()` que devuelve Iterator de:
- `{"type": "delta", "content_delta": str, "tool_call_delta": dict|None}`
- `{"type": "final", "finish_reason": str, "content": str, "tool_calls": list}`

Acumula tool_call fragments (id/name/arguments) que llama-server envia en
pieces. agent.py sigue usando `chat()` no-stream — el unico consumer de
`chat_stream` por ahora es el TTS de la GUI (Fase W). Migrar `agent.py` a
streaming es Fase posterior fuera de scope.

### GUI

- **Tab VOICE** nuevo en SettingsDialog: enable master, feedback (beep/HUD/TTS),
  input device, STT model, TTS voice, follow-up window, close phrases editables,
  TTS muted.
- **MainWindow**: auto-arranca el VoiceController 100 ms despues del primer
  paint si `voice.enabled` esta en gui.json y el perfil lo permite. Loading
  en QThread aparte para no bloquear GUI (carga 1-3 s).
- **HUD**: `IDLE_LISTENING` -> `IDLE`, `LISTENING/WAKE_DETECTED/FOLLOWUP` ->
  `LISTENING`, `TRANSCRIBING` -> `PROCESSING`, `THINKING` -> `THINKING`,
  `SPEAKING` -> `SPEAKING`, `FAILED` -> `ERROR`.
- **Input placeholder** durante transcripcion muestra el partial gris.
- Al recibir Final del STT, llama `_on_send(text)` igual que tipear manualmente.

### Lifecycle por perfil

`_apply_profile` (Fase V) ahora tambien orquesta voz:
- PERF/BAL + `voice.enabled` -> `voice_controller.enable()`
- LIGHT/STANDBY -> `voice_controller.shutdown()` (libera modelos de RAM,
  no solo pausa).
- Override manual del usuario en Settings se respeta hasta que lo cambie.

### Dependencias agregadas

- `vosk` 0.3.45 (wake-word)
- `faster-whisper` 1.2.1 (STT)
- `silero-vad` 6.2.1 (VAD)
- `piper-tts` 1.4.2 (TTS)
- `sounddevice` (ya estaba)

Lazy import por modulo. Si una falla, el subsistema correspondiente queda en
FAILED pero el resto sigue funcionando.

### Validacion

- **66/66 tests passing**. 9 nuevos Fase W: W-SSE deltas, W1 wake matching,
  W2 state machine wake->listening->transcribing, W3 listening timeout 5 s,
  W4 followup close phrase, W5 disable() unloads, W6 sentence chunker,
  W7 auto-fallback to base, W8 normalization.
- **pyright 0 errors** en archivos nuevos y tocados.
- **Imports en runtime real verificados** (vosk + faster_whisper + silero_vad
  + piper + sounddevice cargan limpio en Windows Python 3.10).

### Caveat documentado

Si el llama-server tarda >3 s en responder a la primera peticion (cold start
del KV cache, primera generacion), el TTS va a tener una pausa visible entre
`THINKING` y `SPEAKING`. **No es bug, es fisica del sistema**: el TTS no
puede arrancar a hablar hasta que el LLM emite el primer token, y ese first-
token depende de la latencia del servidor. Mitigaciones cuando se quiera:
- Pre-warm: hacer una request dummy al server tras arrancar (no implementado).
- Filler audio: el TTS dice "mmm" mientras espera (no implementado).
- Streaming del LLM (`chat_stream`): ya listo, falta que `agent.py` lo use.

### Limitaciones conocidas

- **agent.py todavia no usa streaming**: SSE existe en `llm_client.chat_stream`
  pero el loop del agente sigue siendo no-stream. Para que el TTS arranque al
  primer token hay que migrar el loop (fase posterior).
- **Voz es_AR no oficial en Piper**: usar es_MX-claude-high o fine-tunear.
- **Vosk small es-0.42 es lo mejor disponible para wake offline en espanol**:
  hay un small/big version, big es ~1.4 GB y no vale el ratio para wake-word.
- **TTS no soporta tono emocional**: Piper es de tono fijo. Para "Alexa tier"
  alcanza pero no es expresivo como Kokoro/XTTS (que estan fuera del budget
  CPU sub-segundo segun el INFORME).
- **Listening timeout fijo a 5 s** post-wake, no configurable en esta version.
  Si el usuario suele callarse, agregar slider en VOICE tab (futuro).
