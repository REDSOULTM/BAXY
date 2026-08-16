# Carter Agent Universal Tool Gap Map

Fecha: 2026-05-12

Objetivo: mapear los huecos para convertir Carter Agent en un asistente
tipo Alexa/Jarvis, pero orientado primero a control local de Windows. La regla
de diseno se mantiene: pocas tools compuestas por dominio, evidencia de
ejecucion, rollback/cleanup cuando toque estado, y honestidad cuando falte una
dependencia o cuenta.

## Resumen Ejecutivo

El agente ya tiene una base fuerte para PC local: apps, Steam, archivos,
terminal, navegador basico, Playwright, vision/OCR, UIA, audio simple, memoria,
estado, safety opcional, descargas, registro, env y RAG local.

Los huecos mas importantes que aparecieron en pruebas reales son:

1. `office`: crear/editar PowerPoint, Word, Excel y PDF.
2. `audio_device`: cambiar dispositivo predeterminado y routing por app.
3. `notification`: timers, alarmas, recordatorios locales con toast de Windows.
4. `routine`: automatizaciones tipo Alexa "cuando X, haz Y".
5. `smart_home`: integracion local con Home Assistant/Matter/MQTT.
6. `browser_real_visible`: controlar el navegador visible, tabs, descargas y estado real.
7. `media`: control unificado de YouTube/Spotify/VLC/local files con verificacion.
8. `device_settings`: WiFi, Bluetooth, pantallas, printers, power plans, game mode.
9. `document_ingest`: PDF/DOCX/XLSX con parsing real, no solo texto plano.
10. `skill_manager`: instalar/crear skills locales y exponerlas como tools.

Servicios externos quedan separados al final. Para ahora, el foco local deberia
ser P0/P1.

## Aplicacion En Codigo

### 2026-05-12: Primer Corte P0 Local

Implementado en el agente:

- `office`: `status`, `create_presentation`, `create_document`,
  `create_spreadsheet`, `inspect`, `open`; editing/export devuelven
  `needs_implementation` hasta tener manejo seguro por plantilla.
- `audio_device`: `status/list/snapshot` y `set_default` preparado para helper
  local SoundVolumeView. Si falta helper devuelve `needs_dependency`.
- `notification`: estado, notificacion inmediata y scheduling via Windows
  Scheduled Tasks para timers/alarmas/reminders locales.
- `routine`: crear/listar/enable/disable/delete/run_now de rutinas manuales
  con steps de tools.
- `media`: wrapper compuesto para YouTube/local files/media keys.

Verificado:

- Catalogo subio de 26 a 31 tools.
- `office(create_presentation)` creo un `.pptx` real en `data/generated`.
- `routine(create)` + `routine(run_now)` ejecuto una tool real (`system.time`).
- `eval_smoke` pasa con `missing=[]` y `duplicate_count=0`.

Pendiente del P0:

- `browser_real_visible`: ya existe `browser_real(headless=false)` y CDP, pero
  falta una experiencia pulida para adjuntarse al navegador visible del usuario.
- `audio_device`: falta instalar/configurar helper local para que `set_default`
  cambie realmente AUX/Focusrite.
- `notification`: falta historial completo y UI de administracion.
- `routine`: faltan triggers persistentes/event-driven; ahora `run_now` es real.

### 2026-05-12: Lote De Tools Pequenas Locales

Implementado en el agente:

- `source_manager`: guardar/listar/buscar/leer/borrar fuentes y snapshots de
  archivos locales.
- `dependency`: diagnostico de modulos/binarios locales y hints de instalacion.
- `contacts`: contactos locales basicos.
- `notes_tasks`: notas y tareas locales.
- `local_calendar`: eventos offline y export ICS.
- `habit_tracker`: habitos con logs locales.
- `local_search`: busqueda local por nombre y contenido pequeno.
- `printer_scanner`: discovery de impresoras, default y cola con PowerShell.
- `desktop_layout`: snapshot de ventanas/monitores.
- `backup_sync`: backups ZIP locales registrados en state.

Verificado:

- Catalogo subio de 31 a 41 tools.
- `source_manager(snapshot_file)`, `contacts(create)`, `notes_tasks(note_create)`,
  `notes_tasks(task_create)`, `local_calendar(event_create)`,
  `habit_tracker(create)`, `local_search(search)` y
  `backup_sync(backup_create)` pasaron smoke funcional.

Pendiente de estas tools:

- Import/export vCard completo.
- Import ICS y update robusto de eventos.
- Restore/dedupe de backups.
- Restore de desktop layout.
- Print/scan real, no solo discovery/cola.
- Instalacion automatica de dependencias, si se decide permitirla con safety.

## Fuentes Base

- Alexa Built-in Intent Library: categorias Books, Calendar, Cinema Showtimes,
  General, Local Search, Music, Video, Weather y Standard Intents.
  <https://developer.amazon.com/en-US/docs/alexa/custom-skills/built-in-intent-library.html>
- Alexa Smart Home API: discovery de dispositivos, capability interfaces,
  routines, estado consultable y actualizaciones proactivas.
  <https://developer.amazon.com/en-US/docs/alexa/smarthome/understand-the-smart-home-skill-api.html>
- Alexa Music, Radio and Podcast Skill API: busqueda, playback y cola de audio.
  <https://developer.amazon.com/en-US/docs/alexa/music-skills/api-reference-overview.html>
- Alexa Reminders API: create/list/get/update/delete reminders con permisos.
  <https://www.developer.amazon.com/en-US/docs/alexa/smapi/alexa-reminders-api-reference.html>
- Home Assistant REST API: control local via HTTP con token.
  <https://developers.home-assistant.io/docs/api/rest/>
- Home Assistant WebSocket API: estado/eventos en tiempo real.
  <https://developers.home-assistant.io/docs/api/websocket>
- Windows app notifications/toasts: notificaciones locales y programables.
  <https://learn.microsoft.com/en-gb/windows/apps/develop/notifications/app-notifications/>
- Windows ScheduledTasks module: crear/modificar/iniciar/detener/eliminar tareas.
  <https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/>
- python-pptx: crear y modificar presentaciones `.pptx`.
  <https://python-pptx.readthedocs.io/en/latest/user/presentations.html>
- Microsoft Graph Calendar: eventos, reuniones, disponibilidad y asistentes.
  <https://learn.microsoft.com/en-us/graph/api/resources/calendar-overview>
- GAIA: benchmark de asistentes generales con razonamiento, multimodalidad,
  web browsing y tool use.
  <https://arxiv.org/abs/2311.12983>
- OSWorld: benchmark de agentes usando computadoras reales, apps de escritorio,
  file I/O y workflows multi-aplicacion.
  <https://arxiv.org/abs/2404.07972>
- WebArena: tareas web realistas como e-commerce, foros, desarrollo y CMS.
  <https://arxiv.org/abs/2307.13854>
- Mind2Web: agentes web generalistas sobre sitios diversos.
  <https://arxiv.org/abs/2306.06070>
- TheAgentCompany: tareas profesionales de empresa con web, codigo, programas
  y comunicacion con coworkers.
  <https://arxiv.org/abs/2412.14161>
- SWE-bench: tareas reales de software engineering desde issues de GitHub.
  <https://arxiv.org/abs/2310.06770>

## Estado Actual Del Agente

Tools compuestas actuales:

- `system`: hora, procesos, CPU/RAM/GPU, disco, bateria, brillo, power.
- `audio`: volumen, mute, dispositivos, media keys.
- `app`: buscar, abrir, cerrar, desinstalar apps dinamicas.
- `steam`: biblioteca, tienda, juegos, AppID, launch/install.
- `window`: listar, foco, cerrar, minimizar/maximizar/restaurar, mover.
- `gui`: screenshot, click, type, hotkeys, scroll, drag, OCR click text.
- `vision`: OCR local y puente a vision nativa de Gemma via screenshot.
- `browser`: abrir, buscar, YouTube play, media pause, titulo activo.
- `web`: buscar, leer paginas, investigar con fuentes.
- `uia`: arbol UI Automation, find/click/focus/set_value.
- `filesystem`: list/read/write/search/delete/copy/move/rename/mkdir/diff/archive.
- `package`: winget list/search/install/uninstall.
- `clipboard`: read/write.
- `terminal`: run.
- `memory`: save/recall/list/delete.
- `verify`: app_opened/file_exists/window_exists/clipboard_contains.
- `state`: recursos abiertos, cleanup, checkpoints, rollback.
- `input`: idioma/layout de teclado.
- `env`: variables de entorno process/user/machine.
- `registry`: query/export/import/add/delete/backup.
- `download`: fetch/hash/signature.
- `email`: status/draft/send via Graph si hay token.
- `reminder`: local state o Graph si hay token.
- `browser_real`: Playwright headless/CDP.
- `knowledge`: SQLite FTS5 local.
- `safety`: confirmaciones opcionales.

## Metodo De Priorizacion

- P0: Hueco que ya bloqueo un caso real o una expectativa comun tipo Alexa.
- P1: Control local importante para tareas diarias de PC.
- P2: Expansion local avanzada o vertical especializada.
- P3: Servicios externos, cloud o integraciones con cuentas.

Cada tool propuesta es compound. No se propone crear 100 funciones sueltas.

## P0 Local

### 1. `office`

Problema detectado: el usuario pidio "puedes hacerme un PowerPoint?" y el
agente respondio que no tenia herramienta. Esto es un hueco grande para un
asistente generalista.

Tool compuesta:

```text
office(action=...)
```

Acciones:

- `create_presentation`: crear `.pptx` desde tema, outline, imagenes y tablas.
- `edit_presentation`: modificar slides, texto, imagenes, orden y notas.
- `export_pdf`: convertir a PDF si hay Office/LibreOffice disponible.
- `create_document`: crear `.docx`.
- `edit_document`: editar `.docx`.
- `create_spreadsheet`: crear `.xlsx`.
- `edit_spreadsheet`: hojas, formulas, tablas, charts.
- `open`: abrir archivo creado.
- `inspect`: resumen de documento existente.

Implementacion local:

- `.pptx`: `python-pptx`.
- `.docx`: `python-docx`.
- `.xlsx`: `openpyxl`.
- PDF export: LibreOffice headless o Office COM si existe.

Evidencia:

- Ruta creada.
- Hash SHA256.
- Numero de slides/hojas/paginas.
- Screenshot opcional si se abre.

Rollback/cleanup:

- Borrar archivo creado si fue generado por el agente.
- Backup antes de editar un documento existente.

Estado: faltante.

Prioridad: P0.

### 2. `audio_device`

Problema detectado: el agente puede listar dispositivos y volumen, pero no
puede cambiar default device. En Alexa esto equivale a salida de audio/musica
en dispositivo correcto.

Tool compuesta:

```text
audio_device(action=...)
```

Acciones:

- `list`: playback/recording, default actual, status.
- `set_default`: cambiar dispositivo predeterminado.
- `set_default_communications`: comunicaciones.
- `set_app_route`: routing por app si Windows lo permite.
- `get_app_routes`: mixer/routing actual.
- `snapshot`: guardar estado actual.
- `restore`: restaurar snapshot.

Implementacion local:

- Preferible: helper local instalado y verificado, por ejemplo SoundVolumeView
  o AudioDeviceCmdlets.
- Alternativa: WASAPI policy config via modulo propio, con pruebas fuertes.

Evidencia:

- Default antes/despues.
- Device ID y nombre friendly.
- Exit code del helper.

Rollback:

- Snapshot del default anterior antes de cambiar.

Estado: parcialmente cubierto por `audio`, pero `set_default` falla sin helper.

Prioridad: P0.

### 3. `notification`

Alexa cubre timers, alarmas y reminders. Tenemos `reminder` local basico en
state, pero falta una capa real que avise al usuario aunque el chat no este
activo.

Tool compuesta:

```text
notification(action=...)
```

Acciones:

- `timer_start`, `timer_cancel`, `timer_list`.
- `alarm_create`, `alarm_cancel`, `alarm_list`.
- `reminder_create`, `reminder_update`, `reminder_delete`, `reminder_list`.
- `toast_now`: notificacion inmediata.
- `toast_schedule`: notificacion programada.
- `notify_sound`: sonido local opcional.

Implementacion local:

- Windows Toast/App Notifications para avisos visibles.
- Scheduled Tasks para persistencia y ejecucion aun si el agente se cerro.
- Archivo state para ownership y cleanup.

Evidencia:

- Task Scheduler task name.
- Toast payload.
- Proxima ejecucion.

Rollback:

- Unregister scheduled task.
- Marcar reminder/timer como cancelado.

Estado: `reminder` local existe, pero no notifica de forma robusta.

Prioridad: P0.

### 4. `routine`

Alexa tiene routines: "cuando pase X, haz Y". Para un Jarvis local esto es
critico.

Tool compuesta:

```text
routine(action=...)
```

Acciones:

- `create`: crear rutina con trigger y acciones.
- `list`, `enable`, `disable`, `delete`.
- `run_now`: ejecutar rutina manual.
- `simulate`: dry-run.
- `history`: eventos y resultados.

Triggers locales:

- Hora/fecha.
- App abierta/cerrada.
- Ventana activa.
- Archivo cambiado.
- CPU/RAM/GPU/temperatura si disponible.
- Red conectada/desconectada.
- Dispositivo USB/audio conectado.
- Evento Home Assistant/MQTT.

Acciones:

- Ejecutar cualquier tool compound con args.
- Secuencias con compensacion/cleanup.

Evidencia:

- Definicion JSON.
- Ultima ejecucion.
- Resultado de cada step.

Rollback:

- Deshabilitar/eliminar rutina.
- Ejecutar compensaciones de cada accion si existen.

Estado: faltante.

Prioridad: P0.

### 5. `browser_real_visible`

Tenemos `browser_real` headless y CDP, pero falta control consistente del
navegador visible del usuario: tabs reales, pagina activa, descargas, clicks,
formularios y lectura del DOM.

Tool compuesta:

```text
browser_real(action=...)
```

Acciones a fortalecer:

- `attach_visible`: conectar a Chrome/Edge/Opera con remote debugging.
- `active_tab`: URL/titulo/DOM de la tab visible.
- `tab_open`, `tab_close`, `tab_focus`.
- `download_wait`: esperar descarga y devolver ruta/hash.
- `click_text`, `click_selector`, `fill`, `press`.
- `extract`: main text/readability.
- `screenshot_visible`.

Implementacion local:

- Playwright/CDP.
- Perfil separado para no tocar sesion personal por defecto.
- Modo visible opcional cuando el usuario quiere ver lo mismo.

Evidencia:

- URL real.
- Titulo real.
- Selector/texto encontrado.
- Screenshot.
- Archivo descargado con hash.

Rollback:

- Cerrar tabs/contextos creados por el agente.
- Borrar descargas temporales si fueron temporales.

Estado: parcialmente cubierto.

Prioridad: P0.

### 6. `media`

Tenemos `browser(youtube_play)` y media keys, pero falta un controlador unico
para musica/video/radio/podcasts/local media. Alexa separa busqueda, playback
y cola de audio.

Tool compuesta:

```text
media(action=...)
```

Acciones:

- `play`: reproducir por query en proveedor elegido.
- `pause`, `resume`, `stop`, `next`, `previous`.
- `queue_add`, `queue_clear`, `queue_list`.
- `now_playing`.
- `volume_for_app`.
- `open_local`: reproducir archivo local.
- `search_local_library`.
- `cast_lan`: DLNA/Chromecast si esta disponible.

Backends locales:

- Media keys de Windows.
- Session info si se puede leer por Windows media session APIs.
- VLC/MPV CLI para archivos locales.
- YouTube via browser visible/headless.
- Spotify local via app, externo via API despues.

Evidencia:

- URL o archivo.
- Titulo elegido.
- App/window activa.
- Estado `now_playing` cuando se pueda.

Rollback:

- Detener playback iniciado por el agente.
- Restaurar volumen si se cambio.

Estado: parcial.

Prioridad: P0.

## P1 Local

### 7. `smart_home`

Alexa destaca en smart home: luces, switches, sensores, termostatos, escenas,
routines y estado. Para mantener el foco local, la mejor base no es cloud sino
Home Assistant y/o Matter/MQTT.

Tool compuesta:

```text
smart_home(action=...)
```

Acciones:

- `status`: conexion y backend.
- `discover`: entidades/dispositivos.
- `get_state`: estado de entidad.
- `set_state`: control simple.
- `call_service`: servicio Home Assistant.
- `scene_run`: escenas.
- `area_control`: controlar area/habitacion.
- `subscribe_events`: escuchar eventos.
- `automation_run`: correr automatizacion.

Backends locales:

- Home Assistant REST API.
- Home Assistant WebSocket API.
- MQTT.
- Matter/Thread via controller local si existe.

Evidencia:

- Entity ID.
- Estado antes/despues.
- Response HTTP/WebSocket.

Rollback:

- Snapshot de estado anterior cuando sea reversible.

Estado: faltante.

Prioridad: P1, P0 si el usuario tiene Home Assistant.

### 8. `device_settings`

Control local de PC mas alla de apps.

Tool compuesta:

```text
device_settings(action=...)
```

Acciones:

- `wifi_list`, `wifi_connect`, `wifi_disconnect`, `wifi_status`.
- `bluetooth_status`, `bluetooth_toggle`, `bluetooth_pair`.
- `display_list`, `display_set_resolution`, `display_set_scale`.
- `display_arrange`, `night_light`.
- `power_plan_list`, `power_plan_set`.
- `game_mode_get`, `game_mode_set`.
- `default_apps_get`, `default_apps_set`.
- `startup_apps_list`, `startup_apps_enable_disable`.

Evidencia:

- Estado antes/despues.
- Comando usado.
- Config actual.

Rollback:

- Snapshot de configuracion previa.

Estado: parcialmente cubierto por `system`, pero no por dominio.

Prioridad: P1.

### 9. `printer_scanner`

Alexa no es fuerte aqui, pero un asistente de PC si debe imprimir, escanear y
manejar colas.

Tool compuesta:

```text
printer_scanner(action=...)
```

Acciones:

- `printers_list`.
- `printer_default_get`, `printer_default_set`.
- `print_file`.
- `print_queue`.
- `cancel_job`.
- `scanners_list`.
- `scan_document`.

Implementacion local:

- PowerShell printer cmdlets.
- WIA para scanner si disponible.

Evidencia:

- Job ID.
- Printer/scanner name.
- Archivo generado.

Rollback:

- Cancelar job si sigue en cola.

Estado: faltante.

Prioridad: P1.

### 10. `local_calendar`

No sustituye Graph, pero permite calendario/reminders offline.

Tool compuesta:

```text
local_calendar(action=...)
```

Acciones:

- `event_create`, `event_list`, `event_update`, `event_delete`.
- `ics_import`, `ics_export`.
- `availability_local`.
- `schedule_notification`.

Implementacion local:

- SQLite + ICS.
- Windows notifications + Scheduled Tasks.

Evidencia:

- Event ID.
- ICS file.
- Proximo aviso.

Rollback:

- Delete/update event.

Estado: faltante.

Prioridad: P1.

### 11. `document_ingest`

`knowledge` hoy soporta texto plano. Un usuario normal pedira "lee este PDF",
"resume este Excel", "busca en este Word".

Tool compuesta:

```text
document(action=...)
```

Acciones:

- `extract_text`: PDF/DOCX/PPTX/XLSX/HTML.
- `extract_tables`.
- `extract_images`.
- `ocr_pdf`.
- `summarize`.
- `ingest_to_knowledge`.
- `compare_documents`.

Implementacion local:

- PDF: pypdf/pdfplumber/poppler.
- DOCX/PPTX/XLSX: python-docx/python-pptx/openpyxl.
- OCR: Tesseract.

Evidencia:

- Numero de paginas/slides/sheets.
- Chunks ingested.
- Warnings de parsing.

Rollback:

- Eliminar chunks de knowledge si se pidio.

Estado: parcial via `knowledge` solo texto.

Prioridad: P1.

### 12. `game_launcher`

Steam esta bien cubierto, pero un usuario gamer pedira Epic, Xbox, Riot,
Battle.net, EA, Ubisoft, GOG, mods y actualizaciones.

Tool compuesta:

```text
game_launcher(action=...)
```

Acciones:

- `discover_games`: todos los launchers.
- `launch`.
- `install`.
- `uninstall`.
- `open_store_page`.
- `open_library_page`.
- `check_updates`.
- `close_launcher`.

Backends:

- Steam actual.
- Epic manifests.
- GOG Galaxy DB/manifests.
- Xbox app/Store URI.
- Battle.net/Riot/EA/Ubisoft installed shortcuts/manifests.

Evidencia:

- Launcher.
- App/game ID.
- Proceso/ventana.

Rollback:

- Cerrar launcher abierto por el agente.

Estado: Steam parcial, resto faltante.

Prioridad: P1.

### 13. `developer`

`terminal` existe, pero un agente universal necesita acciones de desarrollo
entendidas como dominio, no comandos crudos.

Tool compuesta:

```text
developer(action=...)
```

Acciones:

- `project_detect`.
- `run_tests`.
- `run_lint`.
- `run_format`.
- `git_status`, `git_diff`, `git_commit`.
- `package_install`.
- `open_ide`.
- `start_dev_server`.
- `stop_dev_server`.

Evidencia:

- Exit code.
- Resumen de tests.
- Archivos cambiados.
- URL del dev server.

Rollback:

- Detener procesos iniciados.
- No revertir cambios sin permiso.

Estado: parcial via `terminal/filesystem`.

Prioridad: P1.

### 14. `dependency_manager`

Cuando falta Playwright, Tesseract, SoundVolumeView, LibreOffice o python-pptx,
el agente debe diagnosticar e instalar o guiar, sin fingir.

Tool compuesta:

```text
dependency(action=...)
```

Acciones:

- `status`: dependencias conocidas.
- `explain_missing`.
- `install`: via winget/pip/npm si aplica.
- `verify`.
- `repair`.

Evidencia:

- Version detectada.
- Ruta binaria.
- Instalador/hash si aplica.

Rollback:

- Desinstalar paquete si fue instalado por el agente y es reversible.

Estado: parcial via `package`.

Prioridad: P1.

### 15. `windows_security_maintenance`

Para control total local faltan mantenimiento y seguridad del PC.

Tool compuesta:

```text
maintenance(action=...)
```

Acciones:

- `windows_update_status`.
- `defender_status`.
- `defender_scan`.
- `firewall_status`.
- `event_logs_query`.
- `startup_health`.
- `disk_cleanup`.
- `restore_point_create`.
- `backup_create`.
- `services_list`, `service_start_stop`.

Evidencia:

- Estado antes/despues.
- Logs relevantes.
- Restore point ID.

Rollback:

- Restore point o compensacion especifica.

Estado: parcial via `system/terminal`.

Prioridad: P1, con safety fuerte antes de acciones destructivas.

## P2 Local

### 16. `contacts`

Acciones:

- `contact_create`, `contact_search`, `contact_update`, `contact_delete`.
- `vcard_import`, `vcard_export`.
- `resolve_recipient`.

Uso:

- Necesario para email/messaging/reminders.

Estado: faltante.

### 17. `notes_tasks`

Acciones:

- `note_create`, `note_search`, `note_update`, `note_delete`.
- `task_create`, `task_complete`, `task_list`.
- `project_board_local`.

Backend local:

- Markdown folder.
- SQLite.
- Obsidian vault si existe.

Estado: memoria existe, pero no notas/tareas de usuario.

### 18. `local_search`

Alexa cubre local search como categoria. En PC local esto puede significar
buscar archivos, apps, configuraciones y contenido indexado.

Acciones:

- `search_everything`: si Everything SDK/CLI esta instalado.
- `search_windows_index`.
- `search_recent_files`.
- `search_settings`.

Estado: parcial via filesystem/app.

### 19. `peripheral`

Acciones:

- `usb_list`.
- `device_manager_status`.
- `keyboard_mouse_profiles`.
- `controller_status`.
- `rgb_profile_set` para Logitech/Corsair/Razer si API local existe.

Estado: faltante.

### 20. `capture_deferred`

Camara/mic quedan diferidos por decision de producto, pero el mapa debe
registrarlos.

Acciones futuras:

- `camera_list`, `camera_snapshot`, `camera_record`.
- `microphone_list`, `audio_record`, `transcribe_local`.
- `screen_record`.

Estado: diferido.

### 21. `accessibility`

Acciones:

- `magnifier_toggle`.
- `narrator_toggle`.
- `high_contrast`.
- `dictation_status`.
- `screen_reader_bridge` si se integra.

Estado: faltante.

### 22. `local_maps_offline`

Mapas/trafico suelen depender de servicios externos. Local solo seria limitado:

- abrir app Maps.
- abrir coordenadas/rutas guardadas.
- trabajar con mapas offline si el sistema los tiene.

Estado: bajo valor local, mejor P3 externo.

## P3 Servicios Externos

Estos no son prioridad inmediata, pero son necesarios para cubrir "lo que un
usuario cualquiera pida" al nivel de Alexa/Google Assistant.

### 1. `calendar_cloud`

Backends:

- Microsoft Graph Calendar.
- Google Calendar.

Acciones:

- crear/listar/modificar/cancelar eventos.
- disponibilidad.
- meetings.
- invites.

Estado: `email/reminder` Graph parcial, calendario cloud faltante.

### 2. `mail_cloud`

Backends:

- Microsoft Graph Mail.
- Gmail API.

Acciones:

- leer inbox.
- buscar correo.
- redactar.
- enviar.
- adjuntar.
- responder.

Estado: Graph send parcial si hay token.

### 3. `todo_cloud`

Backends:

- Microsoft To Do.
- Google Tasks.
- Todoist/Notion/Linear si el usuario usa esos servicios.

Acciones:

- crear/listar/completar tareas.
- proyectos/listas.
- fechas.

Estado: faltante.

### 4. `drive_cloud`

Backends:

- OneDrive/SharePoint.
- Google Drive.
 
Acciones:

- buscar/leer/subir/descargar/compartir archivos.
- Docs/Sheets/Slides.

Estado: faltante.

### 5. `music_cloud`

Backends:

- Spotify.
- YouTube Music.
- Apple Music.
- Tidal.

Acciones:

- search/play.
- playlists.
- now playing.
- devices.
- queue.

Estado: YouTube via browser parcial.

### 6. `smart_home_cloud`

Backends:

- Alexa/Google Home/HomeKit bridges.
- SmartThings.
- Tuya.
- Philips Hue cloud.
- Nanoleaf, Govee, etc.

Acciones:

- discovery.
- control.
- scenes.
- sensor state.

Estado: faltante. Preferir Home Assistant local primero.

### 7. `weather_news_search`

Backends:

- Weather API.
- News API/RSS.
- Search API.

Acciones:

- clima actual/pronostico.
- alertas.
- titulares.
- fuentes.

Estado: web search parcial, weather dedicado faltante.

### 8. `maps_traffic_places`

Backends:

- Google Maps.
- Bing Maps.
- OpenStreetMap/Nominatim.

Acciones:

- rutas.
- trafico.
- lugares cercanos.
- ETA.

Estado: faltante.

### 9. `communications`

Backends:

- Telegram.
- Discord.
- Slack.
- Teams.
- WhatsApp via desktop UI o API cuando aplique.

Acciones:

- leer/buscar mensajes.
- enviar mensaje.
- abrir chat.
- resumir conversaciones.

Estado: faltante.

### 10. `commerce`

Backends:

- Amazon/MercadoLibre/supermercados.
- listas de compra.
- price tracking.

Acciones:

- buscar producto.
- comparar precios.
- agregar a lista.
- comprar solo con confirmacion fuerte.

Estado: faltante.

### 11. `finance`

Backends:

- bancos.
- brokers.
- crypto exchanges.
- presupuestos.

Acciones:

- consultar balances.
- gastos.
- alertas.
- pagos solo con confirmacion fuerte.

Estado: faltante y high-risk.

### 12. `travel`

Backends:

- aerolineas.
- hoteles.
- rideshare.
- transporte publico.

Acciones:

- buscar vuelos.
- check-in.
- reservas.
- estado de viaje.

Estado: faltante.

### 13. `health_fitness`

Backends:

- Google Fit.
- Apple Health export.
- Garmin/Fitbit.

Acciones:

- leer metricas.
- crear recordatorios.
- resumir actividad.

Estado: faltante y sensible.

## Matriz De Cobertura Alexa-Like

| Dominio Alexa-like | Local necesario | Externo necesario | Estado Gemma |
|---|---|---|---|
| Stop/cancel/help/navigation | command router, progress, interruption | ninguno | parcial |
| Timers/alarms/reminders | notification + scheduled tasks | Graph/Google/Alexa reminders | parcial |
| Lists/shopping | notes_tasks/local lists | Amazon/AnyList/Todoist | faltante |
| Music/radio/podcasts | media local + browser visible | Spotify/YouTube Music/etc | parcial |
| Video | browser_real_visible + media | YouTube/Netflix/etc APIs/UI | parcial |
| Weather | none real local | weather API | faltante |
| Calendar | local_calendar/ICS | Graph/Google | faltante |
| Email | Outlook local optional | Graph/Gmail | parcial |
| Smart home | Home Assistant/MQTT/Matter | SmartThings/Tuya/etc | faltante |
| Local search | filesystem/app/Everything | maps/business search | parcial |
| Books/audiobooks | local files/library | Audible/Kindle | faltante |
| Calls/messages | desktop app UI | Telegram/Discord/Slack/Teams/etc | faltante |
| PC control | system/app/window/gui/uia/audio | vendor APIs | parcial fuerte |
| Documents | office/document_ingest | Drive/Office cloud | faltante |
| Games | Steam | Epic/Xbox/Riot/etc | parcial |
| Routines | local scheduler/event engine | cloud automations | faltante |

## Mapa Universal No Limitado A Alexa

Alexa es buena referencia para voz, casa inteligente, timers, musica y
consultas simples. Pero un usuario real de PC pide mucho mas: trabajo,
estudio, juegos, programacion, archivos, compras, cuentas, investigacion,
edicion multimedia, automatizaciones largas y tareas ambiguas. Para cubrir ese
universo conviene pensar en niveles de dificultad y dominios.

### Escala De Dificultad L0-L10

| Nivel | Tipo de pedido | Ejemplos | Estado actual | Gaps principales |
|---|---|---|---|---|
| L0 | Conversacion sin tools | "hola", "quien es Batman", "explicame X" | bueno | mejor identidad/estilo persistente |
| L1 | Estado simple del PC | hora, volumen, procesos, leer clipboard | bueno | normalizar encoding y defaults |
| L2 | Accion local simple | abrir/cerrar app, abrir URL, escribir archivo | bueno | mas verificacion por app |
| L3 | Accion local con seleccion | "abre Logitech", "cambia a AUX", "pon Billie Jean" | parcial | audio_device, media, app close robusto |
| L4 | Creacion local | PowerPoint, Word, Excel, PDF, zip, imagen simple | parcial | office, document, media_edit |
| L5 | Workflow multi-app | "abre Steam, busca X, luego Opera..." | parcial bueno | browser visible, planner mas fuerte |
| L6 | Web task con cuenta | comprar, reservar, cambiar datos, enviar formulario | parcial | browser_real_visible, auth/session policy |
| L7 | Investigacion verificable | comparar fuentes, tabla, citar, extraer PDFs | parcial | document_ingest, source manager |
| L8 | Trabajo profesional | coding, data analysis, reportes, emails, CRM | parcial | developer, data, office, cloud connectors |
| L9 | Automatizacion persistente | rutinas, triggers, tareas programadas | faltante | routine, notification, scheduler |
| L10 | Alto riesgo | dinero, contrasenas, borrado masivo, registry, compras | safety opcional | safety fuerte, approvals, audit, rollback |

### Principio Clave

Una tool universal no debe ser "hacer todo". Debe ser un conjunto pequeno de
tools compound con contratos claros. El LLM debe decidir el dominio; la tool
debe encargarse del detalle operativo y devolver evidencia.

## Dominios De Pedidos De Un Usuario Cualquiera

### 1. Conversacion, conocimiento y explicacion

Pedidos:

- "que es X?"
- "resumeme este concepto"
- "dame ejemplos"
- "traduceme esto"
- "hazlo mas simple"
- "ensename matematicas/programacion/ingles"

Local:

- Ya lo cubre el modelo sin tools.
- Falta `tutor` como modo/prompt, no necesariamente tool.
- Falta diccionario/traduccion offline si se quiere 100% local verificable.

Externo:

- Web/current facts.
- Wolfram/knowledge APIs si se quiere calculo simbolico fuerte.

Prioridad: P2, porque el modelo ya cubre bastante.

### 2. Informacion actual y verificacion

Pedidos:

- "que paso hoy?"
- "cual es el ultimo driver de Nvidia?"
- "investiga si este archivo es seguro"
- "compara precios actuales"
- "busca fuentes oficiales"

Local:

- `web` existe.
- Falta `source_manager`: guardar fuentes, citas, fechas, snapshots.
- Falta `fact_check`: comparar claims contra fuentes.

Externo:

- Search API.
- News API/RSS.
- Vendor APIs.

Prioridad: P1.

### 3. Archivos personales y organizacion

Pedidos:

- "encuentra el PDF que descargue ayer"
- "ordena mis capturas por fecha"
- "renombra estas fotos"
- "haz backup de esta carpeta"
- "encuentra duplicados"

Local:

- `filesystem` cubre parte.
- Falta `local_search` con Everything/Windows Index.
- Falta `backup_sync`: backups, snapshots, dedupe, restore.
- Falta `photo_library`: EXIF, agrupacion, thumbnails.

Externo:

- OneDrive/Google Drive/Dropbox.

Prioridad: P1.

### 4. Documentos, Office y PDF

Pedidos:

- "hazme un PowerPoint"
- "convierte esto a PDF"
- "rellena esta plantilla"
- "extrae tablas de este PDF"
- "haz un informe con portada, graficos y citas"

Local:

- Faltan `office` y `document`.
- `knowledge` solo cubre texto plano.
- Falta exportacion PDF confiable via LibreOffice/Office COM.

Externo:

- Microsoft 365/Google Workspace.
- Drive/SharePoint.

Prioridad: P0.

### 5. Comunicacion personal

Pedidos:

- "mandale un correo a X"
- "resume mis correos"
- "responde este mensaje"
- "manda esto por Discord/WhatsApp/Telegram"
- "avisame cuando contesten"

Local:

- `email` tiene Graph parcial, no local Outlook/Thunderbird.
- Falta `contacts`.
- Falta `communications` para desktop apps con UIA/browser/CDP.

Externo:

- Gmail/Graph/Telegram/Discord/Slack/Teams/WhatsApp.

Prioridad: P2 local, P3 externo.

### 6. Calendario, tareas, listas y recordatorios

Pedidos:

- "recuerdame en 20 minutos"
- "pon una alarma a las 7"
- "agrega leche a la lista"
- "agenda una reunion"
- "que tengo manana?"

Local:

- `reminder` es basico.
- Faltan `notification`, `local_calendar`, `notes_tasks`.
- Falta persistencia real con Scheduled Tasks/toasts.

Externo:

- Graph Calendar/To Do.
- Google Calendar/Tasks.
- Todoist/Notion/AnyList.

Prioridad: P0 local.

### 7. Apps, ventanas y escritorio

Pedidos:

- "abre X"
- "cierra Logitech G HUB"
- "mueve esta ventana al otro monitor"
- "haz click en aceptar"
- "configura esta app"

Local:

- `app/window/gui/uia/vision` cubren mucho.
- Falta app-specific profiles para apps dificiles.
- Falta `desktop_layout`: monitores, workspaces, posiciones guardadas.
- Falta interrupcion/cancelacion de acciones largas.

Externo:

- Ninguno normalmente.

Prioridad: P1.

### 8. Navegador y web interactiva

Pedidos:

- "compra esto"
- "rellena este formulario"
- "descarga el instalador correcto"
- "sube este archivo"
- "abre mi cuenta y cambia esta opcion"

Local:

- `browser_real` headless existe.
- Falta visible browser + tabs reales + download manager.
- Falta policy para credenciales/sesiones.

Externo:

- APIs de cada servicio si se evita UI.

Prioridad: P0/P1.

### 9. Multimedia, musica y video

Pedidos:

- "pon Billie Jean"
- "pausa el video"
- "sube el volumen de Spotify"
- "recorta este video"
- "convierte este audio a mp3"
- "haz subtitulos"

Local:

- `browser` y `audio` cubren simple.
- Falta `media` unificado.
- Falta `media_edit`: ffmpeg, thumbnails, transcode, trim, normalize.
- Falta now-playing verificable.

Externo:

- Spotify/YouTube Music/Apple Music.
- Speech-to-text si no se usa local.

Prioridad: P0 para media control, P2 para edicion.

### 10. Gaming

Pedidos:

- "abre Steam y busca X"
- "instala el juego"
- "optimiza para jugar"
- "graba los ultimos 30 segundos"
- "cambia perfil del mouse"
- "abre Discord con mis amigos"

Local:

- `steam` fuerte.
- Falta `game_launcher` para Epic/Xbox/Riot/Battle.net/EA/Ubisoft/GOG.
- Falta `game_mode/peripheral` para perfiles.
- Falta captura local con Xbox Game Bar/OBS/ffmpeg.

Externo:

- APIs de tiendas, Discord, Xbox, Steam Web.

Prioridad: P1.

### 11. Sistema, mantenimiento y seguridad

Pedidos:

- "por que mi PC va lento?"
- "limpia temporales"
- "revisa virus"
- "actualiza drivers"
- "crea punto de restauracion"
- "arregla el audio"

Local:

- `system` parcial.
- Falta `maintenance`.
- Falta `driver_manager`.
- Falta diagnostico por logs/event viewer.

Externo:

- Vendor driver APIs/websites.

Prioridad: P1.

### 12. Red, WiFi, Bluetooth y dispositivos

Pedidos:

- "conectate al WiFi X"
- "enciende Bluetooth"
- "empareja mis audifonos"
- "cambia DNS"
- "abre puertos"
- "mira que usa mi red"

Local:

- Falta `device_settings`/`network`.
- Falta rollback de config red.

Externo:

- Router API/cloud.
- ISP account.

Prioridad: P1.

### 13. Audio avanzado

Pedidos:

- "cambia a AUX y luego vuelve a Focusrite"
- "usa este microfono en Discord"
- "baja solo Chrome"
- "mutea un programa"
- "aplica noise suppression"

Local:

- Falta `audio_device`.
- Falta app volume mixer/routing.
- Falta perfiles de audio por contexto.

Externo:

- Vendor apps Focusrite/Logitech/Voicemeeter APIs si existen.

Prioridad: P0.

### 14. Smart home y mundo fisico

Pedidos:

- "apaga la luz"
- "sube el aire"
- "cierra la puerta"
- "enciende escena cine"
- "si llego a casa, prende X"

Local:

- Falta `smart_home`.
- Base recomendada: Home Assistant REST/WebSocket, MQTT, Matter.

Externo:

- Alexa/Google/HomeKit/SmartThings/Tuya.

Prioridad: P1 local si hay HA; P3 cloud.

### 15. Compras y finanzas

Pedidos:

- "comprame X"
- "compara precios"
- "paga la cuenta"
- "mira mi saldo"
- "haz presupuesto mensual"

Local:

- Puede preparar comparativas y presupuestos offline.
- Falta `finance_local`: CSV de banco, categorias, presupuesto.

Externo:

- Bancos, brokers, tiendas, pagos.
- Requiere safety maxima.

Prioridad: P3, excepto presupuesto local P2.

### 16. Viajes, mapas y movilidad

Pedidos:

- "busca ruta"
- "cuando sale mi vuelo?"
- "reserva hotel"
- "pide Uber"
- "encuentra estacionamiento"

Local:

- Limitado: abrir mapas, guardar itinerarios, ICS.

Externo:

- Maps, aerolineas, hoteles, rideshare, transporte publico.

Prioridad: P3.

### 17. Salud, fitness y bienestar

Pedidos:

- "recuerdame tomar agua"
- "resume mis entrenamientos"
- "cuantas calorias?"
- "analiza sintomas"

Local:

- Timers, notas y habitos locales.
- Falta `habit_tracker`.

Externo:

- Garmin/Fitbit/Apple Health/Google Fit.
- Alto cuidado medico: no diagnosticar.

Prioridad: P2 local, P3 externo.

### 18. Educacion y estudio

Pedidos:

- "hazme flashcards"
- "tomame una prueba"
- "resume este libro"
- "explicame este paper"
- "crea plan de estudio"

Local:

- Modelo + `document` + `knowledge`.
- Falta `study`: flashcards, spaced repetition local, quizzes.

Externo:

- AnkiConnect, Notion, Google Classroom, LMS.

Prioridad: P2.

### 19. Programacion y trabajo tecnico

Pedidos:

- "arregla este bug"
- "corre tests"
- "crea un endpoint"
- "haz commit"
- "explica este repo"
- "levanta docker"

Local:

- Parcial via `terminal/filesystem`.
- Falta `developer` como tool de dominio.
- Falta `container` para Docker/compose.
- Falta `database` para SQLite/Postgres/MySQL local.

Externo:

- GitHub/GitLab/Jira/Linear/CI.

Prioridad: P1 si el usuario programa.

### 20. Datos, hojas de calculo y analisis

Pedidos:

- "analiza este CSV"
- "haz graficos"
- "limpia datos"
- "predice ventas"
- "haz dashboard"

Local:

- Falta `data_analysis`: pandas, plots, profiling, exports.
- `office` debe cubrir Excel basico.

Externo:

- Power BI, Google Sheets, BigQuery, databases cloud.

Prioridad: P1/P2.

### 21. Creatividad y generacion local

Pedidos:

- "haz una imagen"
- "edita esta foto"
- "crea un logo"
- "genera musica"
- "haz un video corto"

Local:

- Falta `creative_local`: conectar Stable Diffusion/ComfyUI, Krita/GIMP,
  ffmpeg, Blender.
- Gemma puede planear pero no generar assets pesados sin backend.

Externo:

- APIs de imagen/video/musica.

Prioridad: P2 local si hay modelos instalados.

### 22. Legal, burocracia y formularios

Pedidos:

- "rellena este formulario"
- "resume contrato"
- "prepara carta"
- "busca requisitos"
- "presenta tramite"

Local:

- `document` + browser visible + office.
- Falta `form_filler` con evidencia y revision antes de submit.

Externo:

- Portales de gobierno, firma digital, pagos.

Prioridad: P2/P3, con safety.

### 23. Memoria personal y contexto de vida

Pedidos:

- "recuerda que..."
- "que sabes de mi?"
- "organiza mis preferencias"
- "recomiendame segun mis gustos"

Local:

- `memory` existe.
- Falta memoria semantica mas rica con permisos: preferencias, personas,
  lugares, proyectos, equipos.

Externo:

- Cross-device sync opcional.

Prioridad: P1/P2.

### 24. Operaciones largas y delegadas

Pedidos:

- "investiga durante una hora"
- "monitorea esta pagina"
- "cuando baje de precio, avisame"
- "cada viernes genera un reporte"

Local:

- Falta `routine`, `notification`, `watcher`, `job_manager`.
- Falta pause/resume/cancel de jobs.

Externo:

- Cloud schedulers/notifications.

Prioridad: P1.

### 25. Casos de emergencia y seguridad personal

Pedidos:

- "llama a emergencias"
- "manda mi ubicacion"
- "bloquea el PC"
- "borra datos sensibles"

Local:

- Bloquear PC, alarma local, abrir contactos.
- Requiere confirmaciones y politicas.

Externo:

- Telefonia/SMS/localizacion.

Prioridad: P3 y high-risk.

## Nuevas Tools Detectadas Por El Mapa Universal

Ademas de las tools propuestas por el mapa Alexa-like, este barrido no-Alexa
agrega o refuerza estas:

- `source_manager`: fuentes, citas, snapshots, fechas de consulta.
- `fact_check`: claims vs fuentes.
- `backup_sync`: backup local, restore, dedupe.
- `photo_library`: EXIF, organizacion de fotos/videos.
- `communications`: apps de chat/mensajeria.
- `desktop_layout`: monitores, workspaces, layouts.
- `media_edit`: ffmpeg, transcode, trim, subtitles.
- `driver_manager`: drivers, vendor updates, rollback.
- `network`: WiFi, DNS, firewall local, router info.
- `finance_local`: CSV bancarios, presupuesto, categorias.
- `habit_tracker`: habitos locales.
- `study`: flashcards, quizzes, spaced repetition.
- `container`: Docker/compose.
- `database`: SQLite/Postgres/MySQL local.
- `data_analysis`: CSV/Excel/plots/dashboard.
- `creative_local`: ComfyUI/Stable Diffusion/GIMP/Blender/ffmpeg.
- `form_filler`: formularios con revision antes de submit.
- `watcher`: monitores de archivo/web/precio/estado.
- `job_manager`: tareas largas, cancelacion, reanudacion.

## Tool Catalog Propuesto Final

Para no inflar el prompt, el catalogo completo deberia quedar asi:

### Core ya existente

- `system`
- `audio`
- `app`
- `steam`
- `window`
- `gui`
- `vision`
- `browser`
- `web`
- `uia`
- `filesystem`
- `package`
- `clipboard`
- `terminal`
- `memory`
- `verify`
- `state`
- `input`
- `env`
- `registry`
- `download`
- `email`
- `reminder`
- `browser_real`
- `knowledge`
- `safety`

### Local nuevo recomendado

- `office`
- `audio_device`
- `notification`
- `routine`
- `smart_home`
- `media`
- `device_settings`
- `printer_scanner`
- `local_calendar`
- `document`
- `game_launcher`
- `developer`
- `dependency`
- `maintenance`
- `contacts`
- `notes_tasks`
- `local_search`
- `peripheral`
- `accessibility`
- `source_manager`
- `fact_check`
- `backup_sync`
- `photo_library`
- `communications`
- `desktop_layout`
- `media_edit`
- `driver_manager`
- `network`
- `finance_local`
- `habit_tracker`
- `study`
- `container`
- `database`
- `data_analysis`
- `creative_local`
- `form_filler`
- `watcher`
- `job_manager`

### Diferido local

- `capture`
- `voice_io`

### Externo futuro

- `calendar_cloud`
- `mail_cloud`
- `todo_cloud`
- `drive_cloud`
- `music_cloud`
- `smart_home_cloud`
- `weather_news`
- `maps_places`
- `communications_cloud`
- `commerce`
- `finance`
- `travel`
- `health_fitness`

## Orden De Implementacion Recomendado

1. `office`: resuelve el hueco PowerPoint inmediatamente.
2. `audio_device`: resuelve cambio AUX/Focusrite con snapshot/restore.
3. `notification`: timers/reminders/alarmas locales reales.
4. `routine`: base para automatizaciones.
5. `browser_real_visible`: control real del browser del usuario.
6. `media`: unificar YouTube/local/VLC/Spotify app.
7. `document`: PDF/DOCX/XLSX/PPTX parsing e ingestion.
8. `smart_home`: Home Assistant local.
9. `device_settings`: WiFi/Bluetooth/display/printer/power.
10. `game_launcher`: Epic/Xbox/Riot/Battle.net/etc.
11. `source_manager`: investigacion con citas, snapshots y fechas.
12. `data_analysis`: CSV/Excel/graficos/perfiles.
13. `developer`: tests/git/dev servers sin depender de comandos crudos.
14. `network`: WiFi/DNS/Bluetooth/router diagnostico.
15. `media_edit`: conversion, recorte, subtitulos con ffmpeg.
16. `backup_sync`: backups, restore y dedupe.
17. `watcher` + `job_manager`: tareas largas, monitores y cancelacion.
18. `communications`: mensajeria local/desktop primero.
19. `creative_local`: integracion con editores/modelos locales si existen.
20. `finance_local`: presupuestos desde CSV locales antes de bancos cloud.

## Reglas De Implementacion

1. Una feature nueva entra como tool compound, no como diez tools sueltas.
2. Todo resultado debe devolver `ok`, `status`, `verified`, `evidence`.
3. Si falta dependencia, devolver `needs_dependency`, no fingir.
4. Si falta cuenta/token, devolver `needs_user`, no fingir.
5. Toda accion reversible debe guardar snapshot/checkpoint.
6. Toda accion que abre recursos debe registrar cleanup en `state`.
7. Para GUI/web/media, no afirmar playback/lectura si no hay evidencia.
8. Para servicios externos, separar claramente auth, permisos y scopes.

## Conclusiones

El agente no esta lejos de ser un controlador local serio de Windows. Lo que
mas falta no es "mas LLM", sino capas de dominio:

- documentos Office,
- audio device routing,
- notificaciones/timers,
- rutinas,
- smart home local,
- browser visible real,
- media unificado,
- settings/perifericos,
- ingestion documental avanzada,
- analisis de datos,
- busqueda/verificacion con fuentes,
- workflows profesionales,
- jobs largos y watchers,
- backups,
- red/dispositivos,
- edicion multimedia.

Con esas tools locales, Gemma cubriria la mayoria de tareas tipo Alexa/Jarvis
sin depender de servicios cloud. Los servicios externos deberian venir despues,
porque agregan auth, permisos, privacidad, cuotas y riesgos transaccionales.
