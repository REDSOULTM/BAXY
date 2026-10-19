# Errores accionables: pistas «next» para el modelo

Relevamiento de solo lectura del worktree `BAXY-Renew-ay`, rama `nb-ayudas`, commit `c9b18e62b`. Se recorrieron los handlers de `src/Baxy.Core/Operations/*` y los proveedores y adaptadores de `src/Baxy.Providers.Windows/**`. El objetivo fue encontrar los fallos en los que el modelo recibe un código (y quizás un `observed`) sin saber qué hacer después, y proponer para cada uno una pista corta al estilo de `path_outside_sandbox` (`src/Baxy.Providers.Windows/Filesystem/LocalFilesystemProvider.cs:556-569`).

**Qué ve el modelo.** `OperationVisibleFacts.FromOutcome` (`src/Baxy.Kernel/Operations/OperationVisibleFacts.cs:76-110`) arma esto: `status`, `error`, `cause`, `pending`, `effectUncertain` y `observed` (el `Result` del outcome). En `mind.py`, `_outcome` lo resume como «falló (código)» o «sin confirmar: pudo o no ocurrir». Cuando la tabla dice «nada más», el modelo recibe solo `error` y, si corresponde, `effectUncertain: true`.

**Excluidos**, porque ya los trabaja otra máquina: `calculator_window_not_found`, el efecto del modo accesible, la carpeta de trabajo en `file.write` y dónde listó `file.find`. Tampoco se incluyen los `invalid_arguments` de esquema, porque el bucle ya devuelve `argumentProblems` (`OperationVisibleFacts.FromStatus`), ni los fallos de infraestructura raros (`state_corrupt`, `handle_capacity_reached`, `memory_*`).

**Convenciones de la pista.** El modelo ve las herramientas con guion bajo (`window_resolve`, `input_visible_controls`; ver `NativeTurnLoop.AskThePersonAbout`), así que las pistas las nombran así. Todas están en inglés, en imperativo, con ≤ 35 palabras, y nombran el argumento o la operación siguiente. «Parcial» indica que ya existe parte de la ayuda, sea en el `observed` o en `src/baxy_mind/data/tool_descriptions.en.v1.json`.

## Hallazgos transversales (afectan a cómo implementar las pistas)

1. **Los fallos externos no llevan `Result` por construcción.** `ExternalJson.Failure/FailureBeforeEffect/FailureAfterEffect` (`src/Baxy.Providers.Windows/External/ExternalJson.cs:53-73`) crean el recibo con `Result = null`. Hace falta un ayudante del tipo `FailureWithNext(operation, code, next, extra)` que devuelva `Verified = false` y un objeto `{ "next": … }`.
2. **El handler externo descarta el `Result` de un recibo con `Verified = true`.** En `src/Baxy.Core/Operations/ExternalCapabilityHandlers.cs:317` se lee `result: receipt.Verified ? null : receipt.Result`. Una pista solo llega si el recibo de fallo tiene `Verified = false`, como hacen `NamedWindowNotFound` y `NotNamed`.
3. **Los candidatos de aplicación se pierden fuera de `app.open`.** `InstalledApplicationResolver.Resolve` calcula los 5 nombres más cercanos, pero `ResolveApplicationWindowsAsync` (`src/Baxy.Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs:526-528`) devuelve `app_not_found` sin ellos. Tampoco los lleva `WindowResolveResult`, y `file.open` con `application` solo pasa `opened.ErrorCode` (`src/Baxy.Providers.Windows/External/WindowsFileToolsAdapter.cs:289`).
4. **Los `windowId` son de un solo uso.** `TryConsume` los borra al usarlos (`src/Baxy.Providers.Windows/Windows/WindowsWindowControlProvider.cs:1091`). Las descripciones dicen «caduca a los 5 minutos» y solo algunas añaden «each window action returns a fresh windowId».

## Ventanas

| código | archivo:línea | qué ve hoy el modelo | pista propuesta («next») | dato a añadir |
|---|---|---|---|---|
| `window_not_found` | `src/Baxy.Providers.Windows/Windows/WindowsWindowControlProvider.cs:194` (process), `:242` (applicationName); `src/Baxy.Core/Operations/ApplicationWindowCloser.cs:38` (app.close por appId) | nada más | "no open window matches; call window_resolve with process \"*\" to list every window and repeat with its exact process, or byTitle true with part of its title; if the app is closed, use app_open" | `candidates` [{title, process}] de las ventanas visibles, como `NamedWindowNotFound` |
| `invalid_or_expired_window_id` | `WindowsWindowControlProvider.cs:296` (focus/min/max/restore), `:596` (move/resize), `:678` (snap), `:881` (close) | nada más. Parcial: la descripción dice que caduca a los 5 min, pero no que es de un solo uso | "each windowId works once and for 5 minutes; use the windowId your last window call returned, or call window_resolve again and use its new windowId" | `reason`: `used` \| `expired` \| `malformed` |
| `window_identity_changed` | `WindowsWindowControlProvider.cs:307`, `:607`, `:691` | nada más | "that window closed or was replaced since you resolved it; call window_resolve again for the app and use the new windowId; if none is listed, the window is gone" | — |
| `action_failed` / `verification_failed` (acciones de ventana) | `WindowsWindowControlProvider.cs:332`, `:349`, `:372`, `:631`, `:644-658`, `:744-800`; fallback `window_action_failed` en `src/Baxy.Core/Operations/WindowControlHandlers.cs:77` | código; `effectUncertain` en algunos | "the window did not reach that state (Windows refused, or it was not seen); call window_resolve to read its current state and windowId before trying once more; do not repeat blindly" | `observedState` (estado leído después) y `windowId` nuevo si sigue viva |
| `app_not_found` / `app_ambiguous` desde `window.resolve` (applicationName) y `app.close` (appId) | `src/Baxy.Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs:526-528` → `WindowsWindowControlProvider.cs:236-237` → `WindowControlHandlers.cs:36`, `:154` | nada más, aunque `app.open` sí da `candidates` | "no installed app has exactly that name; repeat with one of candidates, or call window_resolve with process (for example \"chrome\") instead" | `candidates` (ya calculados por el resolvedor; hay que pasarlos por `WindowResolveResult`) |
| `invalid_selector` (window.resolve) | `WindowControlHandlers.cs:23`; `WindowsWindowControlProvider.cs:172`, `:228` | nada más | "pass exactly one selector: applicationName (installed name, alone) or process (process name, \"*\" for all, or part of a title with byTitle true); offset and byTitle go only with process" | — (en `window.move/resize` el mismo código significa «x+y o width+height»; conviene un `next` propio) |
| `application_window_not_found` | `src/Baxy.Providers.Windows/External/WindowsVisibleControlAdapter.cs:1588-1612` | Parcial: `candidates` [{title, process}], `candidateCount`, `truncated` | "that app has no window on this desktop; repeat with application set to one candidate's title or process exactly, or open it first with app_open" | solo `next` |

## Apps

| código | archivo:línea | qué ve hoy el modelo | pista propuesta («next») | dato a añadir |
|---|---|---|---|---|
| `verification_failed` (app.open) | `WindowsInstalledApplicationOpenProvider.cs:318`; `src/Baxy.Core/Operations/AppOpenHandler.cs:84-97` | código; `effectUncertain` solo si el proveedor dijo `Succeeded` | "the app was started but no window of it was seen in time; call window_application_status (or window_resolve with applicationName) before opening it again: it may still be loading or sit in the tray" | `launchIssued`, `reusedExisting` (ya están en el recibo del proveedor) |
| `place_not_opened` | `AppOpenHandler.cs:121` | código + `effectUncertain`; se pierde el resultado de la apertura (appId, windowId) | "the app is open but that section did not open; look with input_visible_controls (application set) and click the section, instead of calling app_open again" | el `OpenApplicationResult` ya armado (`appId`, `windowId`, `place`) |
| `launch_failed` | `WindowsInstalledApplicationOpenProvider.cs:204`, `:212` | nada más (`candidates` null) | "Windows refused to start this app; retry app_open once, and if it fails again tell the person it would not start (it may need repair or reinstalling)" | `launchIssued` |
| `app_ambiguous` (app.open) | `WindowsInstalledApplicationOpenProvider.cs:1314-1318` → `:113` | nada más (con ambigüedad no se dan candidatos) | "two different installed apps share that exact name and BAXY cannot choose; tell the person and ask them to open the one they mean from Start" | `candidates` con nombre y editor/AUMID (sirve solo si `appId` llega a aceptar el AUMID) |
| `app_not_found` / `app_file_not_accepted` / `app_file_activation_failed` (file.open con `application`) | `src/Baxy.Providers.Windows/External/WindowsFileToolsAdapter.cs:289` | solo el código del proveedor; `candidates` descartados | app_file_not_accepted: "that app does not open this type of file; call file_open again without application to use its default app, or name another app". app_not_found: "repeat application with one of candidates" | `candidates` (de `opened.Candidates`) |
| `new_document_not_created` | `WindowsInstalledApplicationOpenProvider.cs:842` | nada más | "the app opened but no new document was seen; look with input_visible_controls before writing, and do not type until an empty document shows" | `windowId` de la ventana abierta |

## Entrada y clics

| código | archivo:línea | qué ve hoy el modelo | pista propuesta («next») | dato a añadir |
|---|---|---|---|---|
| `visible_button_not_found` | `WindowsVisibleControlAdapter.cs:1345` (sin result); `:3131-3135` (con `candidates` solo si hay nombres que contienen la etiqueta) | Parcial: a menudo nada; a veces `candidates` | "no control has that exact label; call input_visible_controls on that window and repeat input_visible_click with a label (and its index) copied from the view" | `visibleLabels` (los primeros ~20 nombres de la ventana) cuando `candidates` está vacío |
| `visible_button_postread_unchanged` | `WindowsVisibleControlAdapter.cs:2926` (también `:1242`) | código + `effectUncertain` | "the click went in but nothing visible changed; look again with input_visible_controls and choose another control or manner (double, menu) rather than pressing the same one again" | `label`, `method` (invoke/pointer) |
| `visible_click_postread_unread` / `visible_click_handoff_uncertain` | `WindowsVisibleControlAdapter.cs:2919`, `:2923` | código + `effectUncertain` | "the click was sent but its effect was not confirmed (another window may have appeared); call window_active or input_visible_controls to see before clicking again: a repeat may do it twice" | `arrivedWindow` {title, process} en handoff |
| `visible_control_identity_stale` | `WindowsVisibleControlAdapter.cs:1040`, `:2228`; `src/Baxy.Providers.Windows/External/WindowsDesktopInteractionAdapter.cs:951`; `src/Baxy.Providers.Windows/External/WindowsScrollAdapter.cs:120` | nada más | "that index or controlId comes from an older look; call input_visible_controls on the window again and use the new index" | — |
| `input_window_not_in_front` | `src/Baxy.Providers.Windows/External/ForegroundLease.cs:290`, `:303`, `:431`, `:441`; `WindowsVisibleControlAdapter.cs:276` | nada más | "Windows did not bring that window to the front (closed, minimized or blocked); call window_resolve to check it is still open, repeat once, and if it fails again tell the person" | `windowAlive` (bool) y `frontProcess` |
| `input_user_not_paused` | `ForegroundLease.cs:303`, `:429`; `WindowsVisibleControlAdapter.cs:314` | nada más | "the person kept using the mouse or keyboard and BAXY never acts over them; repeat the same call once in a moment, and if it fails again tell them you need a short pause" | `waitedMs` (ya lo tiene la ráfaga) |
| `input_user_interrupted` / `input_effect_not_verified` / `input_window_changed` (al escribir) | `src/Baxy.Providers.Windows/External/LeasedInput.cs:13-16`; `WindowsDesktopInteractionAdapter.cs:657-671` (`SentFailure`), `:685-694` | Parcial: `sentTo`, `charactersTyped`, `charactersAsked`, `effectUncertain` | "typing stopped or was not seen landing; check the field with input_visible_controls (includeText true) and type only the characters still missing (charactersAsked minus charactersTyped)" | solo `next` (en clics: añadir `pressed` bool) |
| `protected_window` | `src/Baxy.Providers.Windows/External/WindowsExternalCapabilityProvider.cs:371-378`; `WindowsVisibleControlAdapter.cs:236`, `:2202`; `WindowsScrollAdapter.cs:125` | Parcial: a veces `refusedProcess`; mencionado en la descripción | "BAXY never acts in this window; for an editor or terminal, look at it first with input_visible_controls naming its application; for a system tool or BAXY itself, tell the person to do it" | `reason`: `system_tool` \| `baxy` \| `unnamed_developer_window`; `refusedProcess` siempre |
| `active_window_not_found` | `WindowsVisibleControlAdapter.cs:1692`, `:2194`; `WindowsDesktopInteractionAdapter.cs:978`; `WindowsScrollAdapter.cs:174` | nada más | "no window was in front to act on; pass window (the number from your last look) or set application in input_visible_controls, or bring the app up with window_focus first" | — |
| `input_field_not_replaceable` | `WindowsDesktopInteractionAdapter.cs:395`, `:427` | nada más | "replace needs a field from a look; call input_visible_controls on the window and repeat input_text_type with window, the field's index and replace true" | — |
| `desktop_interaction_argument_invalid` | `WindowsDesktopInteractionAdapter.cs:390`, `:406` | Parcial: la descripción dice «no line break or tab» | "text cannot hold line breaks or tabs nor pass 4,096 characters, and index needs window; type each line separately and press enter with input_key_press between them" | `problem`: `line_break` \| `too_long` \| `index_without_window` \| `unknown_key` |

## Archivos

| código | archivo:línea | qué ve hoy el modelo | pista propuesta («next») | dato a añadir |
|---|---|---|---|---|
| `version_conflict` / `expected_hash_for_missing_file` (file.write) | `src/Baxy.Providers.Windows/Filesystem/LocalFilesystemProvider.cs:174-175`, `:196` | Parcial: `exists`, `fullPath`, `append`; la descripción explica `expectedSha256` | version_conflict: "the file exists and was left as is; to replace it read it with file_read and pass its fileSha256 as expectedSha256, or set append true to add a line". missing: "the file does not exist yet; call file_write again without expectedSha256" | solo `next` (no conviene dar el hash: obliga a leer antes de sobrescribir) |
| `file_open_not_verified` | `WindowsFileToolsAdapter.cs:242` (con `processId`, `windowTitledWithFileSeen:false`), `:245`, `:289`, `:344` | Parcial en `:242`; nada más en el resto, con `effectUncertain` | "the file was handed to its app but no window titled with it appeared; call window_active or window_resolve to see whether it opened before calling file_open again" | `processId` también en `:245`/`:344` |
| `file_in_use` / `filesystem_access_denied` | `src/Baxy.Core/Operations/FilesystemHandlers.cs:94-97` | código; `effectUncertain` en las operaciones que cambian algo | file_in_use: "another program has that file open (for example Excel); ask the person to close it there, then repeat the same call". access_denied: "Windows denied access there; tell the person, or use another of their folders (desktop, documents, downloads)" | `fullPath` |
| `directory_not_found` (filesystem.list) | `LocalFilesystemProvider.cs:55` | nada más | "relativeDirectory is read only inside BAXY's work folder; for the person's folders use file_find with folder (desktop, documents, downloads or home)" | — |

## Navegador

| código | archivo:línea | qué ve hoy el modelo | pista propuesta («next») | dato a añadir |
|---|---|---|---|---|
| `user_browser_not_running` | `src/Baxy.Providers.Windows/External/UserBrowserTabs.cs:48` (const en `UserBrowserSurface.cs:326`) | nada más | "the person's browser has no open window; open the page with browser_navigate (or app_open the browser) before using browser_control" | `browser` (nombre del predeterminado) |
| `user_browser_tab_step_unconfirmed` | `UserBrowserTabs.cs:155`, `:302` | código + `effectUncertain` | "the step was sent but not seen; call browser_tabs_list or browser_page_read to check the tab before repeating it" | `action` |
| `user_browser_tabs_not_automatable` | `src/Baxy.Providers.Windows/External/WebBrowserAdapter.cs:178` (const `:1186`) | nada más | "that page is in the person's browser, which BAXY cannot drive right now; ask the person to do it, or open the page again with browser_navigate" | — |
| `web_adapter_unavailable` | `WebBrowserAdapter.cs:142`, `:152`, `:191` | código; `effectUncertain` si se abrió el navegador | "the browser or the network did not answer; retry once, and if it fails again tell the person the page could not be reached" | — |

## Medios y audio

| código | archivo:línea | qué ve hoy el modelo | pista propuesta («next») | dato a añadir |
|---|---|---|---|---|
| `media_session_not_found` | `src/Baxy.Providers.Windows/External/WindowsMediaSessionAdapter.cs:355-359` | nada más | "nothing is reporting playback to Windows now; media_control only acts on something already playing: ask what to play and use media_play_query, or open the player with app_open" | — |
| `app_audio_session_not_found_on_default_output` | `src/Baxy.Providers.Windows/External/WindowsAudioAdjustmentAdapter.cs:170`, `:286` | Parcial: la descripción dice «only applications playing on the default output» | "no sound session of that app is on the default output; repeat with app set to one of sessions, or the app must play something first" | `sessions` (nombres de proceso con sesión en la salida predeterminada) |
| `smtc_postcondition_not_verified` | `WindowsMediaSessionAdapter.cs:580` | código + `effectUncertain` | "the command was sent but the player's state did not change; call media_status to read what is playing before sending it again" | `observedStatus` |
| `audio_reconciliation_required` (`pending`, `cause`) / `endpoint_changed` | `src/Baxy.Core/Operations/AudioVolumeHandler.cs:206-212`; `src/Baxy.Providers.Windows/Audio/AudioContracts.cs:24`, `:28` | `pending: true` + `cause` | "the volume change may or may not have applied (the output may have changed); call audio_status to read the real level and device before setting it again" | — |

## Juegos y Steam

| código | archivo:línea | qué ve hoy el modelo | pista propuesta («next») | dato a añadir |
|---|---|---|---|---|
| `steam_installed_game_not_verified` (game.launch) | `src/Baxy.Providers.Windows/External/SteamLocalAdapter.cs:779` | nada más | "that appId is not an installed game on this PC; take the appId from the installed games list or from game_installed_named with the title, never an invented one" | `appId` pedido |
| `steam_title_not_resolved` | `SteamLocalAdapter.cs:262` | Parcial: la descripción explica «exactly one game» | "no single Steam game has exactly that title; repeat with one of candidates, or ask the person for the exact store name" | `candidates` (títulos cercanos del snapshot local o de la búsqueda) |
| `no_steam_manifest_with_that_name` (game.uninstall) | `src/Baxy.Providers.Windows/External/SteamLocalAdapter.Uninstall.cs:35` | Parcial: mencionado en la descripción | "no installed Steam game has exactly that title; call game_catalog_list with a word of it as query and repeat with the exact title listed" | `candidates` |
| `steam_launch_process_not_verified` | `SteamLocalAdapter.cs:836` | código + `effectUncertain` | "Steam was asked to start it but no game process appeared in time (it may still load or show a dialog); look with window_active before launching it again" | — |

## Agenda, notas y tareas

| código | archivo:línea | qué ve hoy el modelo | pista propuesta («next») | dato a añadir |
|---|---|---|---|---|
| `schedule_time_invalid` | `src/Baxy.Providers.Windows/External/WindowsScheduledNotificationAdapter.cs:82` | Parcial: la descripción da los formatos | "give at as 24-hour local HH:mm or YYYY-MM-DDTHH:mm, or use inMinutes (1-525600) or inSeconds (10-86400) instead" | `at` recibido |
| `notification_clock_not_found` / `notification_clock_ambiguous` | `WindowsScheduledNotificationAdapter.cs:209-212` (resuelto en `:263-268`) | nada más | not_found: "no BAXY alarm or reminder of that kind rings then; call schedule_alarms with action list and cancel with the exact at and kind shown". ambiguous: "repeat cancel with kind alarm or reminder" | `upcoming` [{kind, at}] (las próximas) |
| `note_not_found` (`cause: by_title`) | `src/Baxy.Core/Operations/NoteHandlers.cs:36-40` | `cause` | "no note has exactly that title; call note_search with a word of it (or note_list) and repeat with the exact title shown" | `candidates` (títulos cercanos) |
| `note_selection_stale` / `task_version_conflict` | `NoteHandlers.cs:50`; `src/Baxy.Core/Operations/TaskHandlers.cs:51-53` | nada más | "it changed since you read it; read it again with note_read (or task_list) and repeat the change on the current version" | — |

## Sistema y genéricos

| código | archivo:línea | qué ve hoy el modelo | pista propuesta («next») | dato a añadir |
|---|---|---|---|---|
| `external_provider_failed` / `external_verification_failed` / `external_effect_unobserved` | `src/Baxy.Core/Operations/ExternalCapabilityHandlers.cs:300`, `:316`, `:328-332` | código + `cause` (`external_provider_exception` \| `external_effect_ambiguous` \| `external_effect_unobserved`) | Con efecto incierto: "the result could not be confirmed; read the state with the matching status or list tool before repeating". Sin efecto: "it failed inside BAXY before acting; retry once, then tell the person" | `next` según `cause` (un solo lugar cubre ~100 operaciones) |
| `process_not_running` | `src/Baxy.Providers.Windows/External/WindowsProcessTerminationAdapter.cs:110` | nada más | "no running process has that executable name (or it already closed); call system_process_list to find its exact name, for example \"chrome\"" | `candidates` (nombres de proceso cercanos) |

**Total: 46 entradas** (contadas por fila; cuando una fila agrupa códigos hermanos, cuenta una vez).

### Otros detectados, de menor prioridad (sin fila)

`application_window_identity_unavailable` (`WindowsInstalledApplicationOpenProvider.cs:123`), `window_elevated` y `window_elevation_unread` (`WindowsVisibleControlAdapter.cs:680-683`, `:2200`; pista posible: «reopen with app_open forControl true or tell the person»), `visible_lookup_timeout` (`:751`), `visible_controls_unavailable` (`:1711`), `file_extension_not_openable` (ya explicado en la descripción), `invalid_resource_id`/`resource_changed` (`LocalFilesystemProvider.cs:458-465`; la caducidad de 5 min ya está descrita), `youtube_tab_not_found` (`WebBrowserAdapter.cs:604`), `wifi_profile_not_found` (`src/Baxy.Providers.Windows/External/WindowsDeviceControlAdapter.cs:1814`; convendría añadir `candidates` de `wifi_profile_list`), `no_default_output` (`AudioContracts.cs:20`), `task_not_found` (`TaskHandlers.cs:48`) y `close_prompted` (ya bien cubierto con `closePrompted` y la descripción).

## Prioridad (top 10)

1. **`visible_button_not_found`**: falla en cada clic con una etiqueta inexacta; añadir `visibleLabels` y el `next` hacia `input_visible_controls`.
2. **`window_not_found`**: es el primer paso de toda acción de ventana; añadir `candidates` y el `next` hacia `process "*"` y `byTitle`.
3. **`invalid_or_expired_window_id`**: el id es de un solo uso y eso no se dice; la pista evita reusar ids viejos.
4. **`input_window_not_in_front`**: es común en clics y escritura sobre ventanas de fondo; la pista lleva a comprobar con `window_resolve` y repetir una vez.
5. **`input_user_not_paused`**: aparece cada vez que la persona usa el PC; la pista dice que se repite una vez y luego se avisa.
6. **`visible_button_postread_unchanged`**: evita que el modelo apriete lo mismo en bucle.
7. **`visible_click_postread_unread` / `visible_click_handoff_uncertain`**: evita repetir un clic cuyo efecto pudo ocurrir (por ejemplo, una segunda pestaña).
8. **`visible_control_identity_stale`**: el índice viene de una vista vieja; la pista indica mirar otra vez.
9. **`verification_failed` (app.open)**: en la apertura de apps más frecuente, lleva a comprobar con `window_application_status` antes de reabrir.
10. **`app_not_found` sin candidatos en `window_resolve`/`app_close`/`file_open` con application**: los candidatos ya se calculan y se pierden; basta con pasarlos.

Le siguen de cerca `place_not_opened`, `app_audio_session_not_found_on_default_output` (con `sessions`), `steam_installed_game_not_verified` y `media_session_not_found`.
