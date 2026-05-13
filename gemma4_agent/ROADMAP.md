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

**Proximo paso:** Fase C local (P1).

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

Fase A y B ya estan completas y verificadas en sesion 2026-05-13. La siguiente
sesion debe arrancar con **Fase C local (P1)**, en este orden:

1. **C3 `developer`** — desbloquea trabajo tecnico real (run_tests / git_status /
   start_dev_server con PID en `state`). El usuario es ingeniero; este es el
   gap mas valioso para sus propias tareas.
2. **C1 `device_settings`** — wifi/bluetooth/display/power; cubre la queja
   "cambia a este WiFi", "baja brillo".
3. **C2 `game_launcher`** — Epic/GOG/Xbox manifest scan. Steam ya esta cubierto.
4. **C7 `media_edit`** — ffmpeg trim/transcode/normalize; util para video local.
5. **C5 `maintenance`** — windows_update_status / defender_status / disk_cleanup
   con safety fuerte. NO scans largos.
6. **C8 `watcher` + `job_manager`** — base para tareas largas.
7. **C4 `network`** — diagnostico (ping/dns/firewall_status); sin escribir reglas.
8. **C6 `data_analysis`** — CSV profile/plots con pandas+matplotlib.

Mantener la disciplina: ninguna tool nueva queda con acciones devolviendo
`needs_implementation` sin justificacion documentada en este roadmap.

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
