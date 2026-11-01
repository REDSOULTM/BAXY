# Revisión de la fase B del notebook (objetivo «BAXY Renew al máximo»)

Cuatro revisores de sólo lectura, uno por área, sobre `nb-maximo` (86991ca9d / 80a9ab97c): aplicaciones, Steam y medios;
ventanas, controles visibles y computer use; sistema, archivos y memoria; scripts de banco y de System One. Cada hallazgo
dice archivo:línea, el escenario, el invariante y la prueba que fallaría hoy. **Estado**: «verificado» = lo leí yo en el
código; «arreglado» = commit con su prueba que fallaba antes. **Autor** según los archivos (portátil providers; PC mente, App,
Core, Kernel). Lo ya listado en `PALANCAS-nb.md` (R6.x, R7.x, R10.x, R11.x, R12.x) no se repite.

## Graves

| Id | Qué pasa | Dónde | Invariante | Prueba que falla hoy | Autor | Estado |
|---|---|---|---|---|---|---|
| B-SYS-1 | `file.write`/`file.edit` con `folder: home` o ruta completa escribían `%LOCALAPPDATA%\BAXY\1\confirmation-mode` = `bypass` (LowReversible, sin preguntar) y el núcleo lo relee en cada invocación: el modelo encendía Bypass sin la interfaz. La papelera por nombre llegaba a reciclar la carpeta BAXY | `LocalFilesystemProvider.cs:501-517`; `WindowsKnownFileAdapter.cs` (Locate, SubdirectoryRoots, enumeraciones); `ConfirmationModeStore.cs:13-35`; `Core/Program.cs:224` | 1, 4 | `BaxysOwnStateIsNeverWrittenThroughAKnownFolderOrAFullPath`, `BaxysOwnStateIsNeitherReadEditedNorFound` | portátil | **arreglado** 0ff4df60f |
| B-SYS-2 | `sessions/*.json` en claro guardan el texto y los argumentos de `memory.sensitive.save` y sobreviven a `memory.forget all`; al reabrir la sesión el modelo recupera lo olvidado | `FieldSessionStore.cs:52-80`; `mind.py:610-621`; `NativeTurnLoop.cs:149,565-567` | «borrar entera», 6 | `"4831" not in json.dumps(mind.export_session())` | PC | lo toma el PC |
| B-CU-1 | Un clic por índice o `controlId` cae en la ventana de la **última mirada** (B) aunque el paso nombra otra (A): `_lastView` no compara `view.Hwnd` con `window`, y `Find-ById` usa la caché sin mirar `LastView.hwnd`; `Refuses(A)` nunca ve B (puede ser la de la persona o una protegida mirable) y el recibo dice A. Hermano: `input.scroll` con `index` | `WindowsVisibleControlAdapter.cs:1041-1052`; `DesktopUiaWorker.ps1:2701-2709`; `WindowsScrollAdapter.cs:114-121` (`input.text.type` sí lo rechaza, `WindowsDesktopInteractionAdapter.cs:950`) | no molestar, protección, 2 | `AnIndexOfAnotherWindowsViewIsNeverPressedInTheNamedWindow` | portátil | pendiente |
| B-CU-3 | Si se cancela el saludo del worker UIA, el `{"ok":true}` queda en la tubería y **todas** las respuestas siguientes llegan desplazadas una línea (permanente): un clic se da por inválido aunque se pulsó, la cascada OCR puede pulsar otra vez | `UiaWorkerHost.cs:193-219` (`SendAsync:114-120` ya trata el caso, el arranque no) | 2, 3 | `ACancelDuringTheWorkersHelloNeverLeavesItsAnswerForTheNextCommand` | portátil | pendiente |

## Altos y medios

| Id | Qué pasa | Dónde | Prueba | Autor |
|---|---|---|---|---|
| B-SYS-3 | Recibos de idempotencia de la memoria de por vida: a los 4096 cambios la memoria queda «llena» con 0 recuerdos y `forget all` no lo libera; guardan el `Selector` de lo olvidado (= R11.2/R11.3) | `LocalMemoryStore.cs:21,213,269,386,1026-1051` | `maximumReceipts:2`, save, forget all, save → hoy lanza | portátil (Providers/Memory) |
| B-SYS-4 | `doubt_ask` escribe en `turns.jsonl` el texto de un pedido de memoria (`private` se marca después) y el archivo no rota ni vive en la raíz privada (= R11.6) | `mind.py:897-901,1015`; `__main__.py:34` | `test_mind_doubt_policy.py` con `memory_save` | PC |
| B-APP-1 | Un mpv en pausa sigue contestando `media.*` y tapa a la sesión que suena (Spotify): «pausa la música» dice «ya estaba» y Spotify sigue | `YouTubeMpvAdapter.cs:354-378,436-449`; orden en `WindowsExternalCapabilityProvider.cs:74-83` | `APausedLocalPlayerStandsAsideWhenAnotherSessionPlays` | portátil |
| B-APP-2 | Plazos propios de yt-dlp (45 s) y del pipe de mpv (15 s) salen como `OperationCanceledException`: `external_provider_failed` ambiguo, sin pasar al navegador, yt-dlp vivo (= R6.3) | `YouTubeMpvAdapter.cs:102-111,167-169,233-235` | `AResolverTimeoutIsNotAnAmbiguousEffect` | portátil |
| B-APP-3 | Valor de lugar que no encaja se dice «lugar de otra app» (= R6.4) | `AppOpenHandler.cs:51-66`; `ApplicationPlaces.cs:72-91` | `APlaceValueThatDoesNotFitIsSaidAsSuch` | PC (Core) / Kernel |
| B-APP-4 | Steam: una descarga en pausa (StateFlags 1538) se dice «downloading»; rama `not_installed` muerta | `SteamLocalAdapter.cs:931-937,694` | `APausedDownloadIsNotSaidDownloading` | portátil |
| B-APP-5 | Fallo de red en la búsqueda de Steam se dice «título no resuelto» | `SteamLocalAdapter.cs:527-536,562-565` | `AStoreSearchThatFailedIsNotAnUnresolvedTitle` | portátil |
| B-APP-6 | `game.entitlement.named` saca el título a la tienda de Steam aunque su descripción dice «local» | `SteamLocalAdapter.cs:207,550-571`; `ProductCatalog.cs:670-671` | `EntitlementNeverSearchesTheStore` | portátil (+ descripción PC) |
| B-APP-7 | mpv escribe un log por reproducción con la URL de googlevideo (incluye `ip=`), sin retención | `YouTubeMpvAdapter.cs:205-221` | argumentos de mpv sin `--log-file` | portátil |
| B-APP-8 | `game.launch` con el juego abierto: 35 s y fallo ambiguo (= R6.2) | `SteamLocalAdapter.cs:787,860-904` | `AGameAlreadyRunningIsTheStateReached` | portátil |
| B-APP-9 | Un `Win32Exception` al leer el catálogo de apps (PowerShell bloqueado) tumba el bucle del Core sin estado terminal | `WindowsInstalledApplicationOpenProvider.cs:99-104,826-833,1446` | `AnUnstartableCatalogReadIsInventoryFailed` | portátil |
| B-APP-10 | Proveedor de la Calculadora y alias `windows.calculator` vivos (ley 2, app nombrada en código) | `ApplicationOpenContracts.cs:5,150-161`; `WindowsCalculatorOpenProvider.cs`; `Core/Program.cs:110-112`; `ProductCatalog.cs:55` | aserción de catálogo sin alias | portátil + PC |
| B-APP-11 | Reutilizar una ventana que desaparece antes del foco cuenta como reutilización; `RequestForeground` sin presupuesto | `WindowsInstalledApplicationOpenProvider.cs:145-185,231,315-320,949` | `AReusedWindowGoneBeforeFocusIsALaunch` | portátil |
| B-CU-2 | «La ventana de BAXY» se compara con el PID del Core (sin ventanas): con el chat de BAXY al frente, `input.visible.controls {}` lee la ventana de BAXY | `VisibleControlSurface.cs:261,655,675,1983`; `.Traspaso.cs:108`; `.Family.cs:232,292,362` | `TheProductsOwnWindowInFrontGivesWayToThePersonsWindow` | portátil |
| B-CU-4 | Escribir 4096 caracteres a 35 ms pasa los 100 s de la App: el Core muere a mitad, el frente no se devuelve, el modelo reintenta y duplica | `WindowsDesktopInteractionAdapter.cs:310`; `DesktopKeyboard.cs:72,108-128`; `NativeTurnLoop.cs:57`; `CoreProcessClient.cs:18-19` | `ALongTextStopsWithWhatWasTypedBeforeTheAppsBudget` | portátil |
| B-CU-5 | Ruta de depuración muerta que guarda capturas y OCR de chats en disco si existe una variable | `DesktopMessagingAdapter.cs:1707-1758,1313` | regla «ningún adaptador escribe capturas fuera del almacén» | portátil |
| B-SYS-5 | `display.mode.set` guarda el modo con `CDS_UPDATEREGISTRY` sin «¿conservar?»: un modo que el monitor no muestra queda negro y persiste | `WindowsDisplayModeAdapter.cs:85,278-281` | primer `Apply` sin `UpdateRegistry` | portátil |
| B-SYS-6 | `system.process.terminate.named` aborta entero si una instancia es de SYSTEM (`StartTime` lanza) | `WindowsProcessTerminationAdapter.cs:30-45,211-216` | `deniedCount` con `terminatedCount>0` | portátil |
| B-SYS-7 | Texto fijo visible «BAXY confirmó el reinicio…» (invariante 5, y nadie confirmó en Normal); descripción de `shell.command.run` no dice `home` ni rutas absolutas | `WindowsPowerTransitionAdapter.cs:83-85`; `ProductCatalog.cs:1346`; `ShellCommandAdapter.cs:58-78` | — | portátil + PC |

## Medición y System One (B-MED)

| Id | Qué pasa | Dónde | Cifra afectada | Prueba / comprobación | Autor |
|---|---|---|---|---|---|
| B-MED-1 (grave) | «Laya corrige» ejecuta argumentos inventados: P252 «pon esta ventana en la mitad izquierda», Qwen elige `window_resolve` (correcto), Laya `window_snap` y `fill_call` escribe `windowId:"1"`, inventado, y se ejecuta; P253 `web_download` con una página de resultados como `url`. El juez sólo mira los argumentos que nombra el caso | `mind.py:950-961`; `bench_decision.py:65-72`; `forced_fill.py:212` | s1-corr-nb 233/268 (P252 es una de sus 3 ganancias, falsa); «forzados 14/15» ≤12/15; probablemente «140 → 148» | `Mind._corrected` con `fill_call` falso que da `windowId:"1"` tras `window_resolve` → hoy devuelve la llamada | PC |
| B-MED-2 | El analizador de la duda cuenta todas las decisiones; el producto sólo retiene acciones. Sólo acciones: AUROC 0,837 (no 0,902); bajo 0,4 se retienen 10 de 381 acciones buenas (2,6 %, no 0,65 %); bajo 0,5, 22/381 (5,8 %) | `analyze_signals.py:203-242`; `mind.py:337-339`; docstring de `doubt.py` | AUROC y fricción publicadas | recalculado sobre s1-ajuste-nb (1.839) | PC |
| B-MED-3 | Las opciones de Laya al servir no son las de su entrenamiento: la ficha elegida cuenta dentro del tope de 4 y p ≥ 0,02 (entrenamiento 0,01): ≤2 alternativas reales y una `complete_name` desperdiciada | `mind.py:969-976` frente a `qwen_signals.py:88-98`, `build_kev_data` | lo corregible por Laya sobreestimado ~20 % (20→16, 7→6, 4→3) | rivales `[_resolve .54, _active .41, _snap .03, _move .025]` con elección `_resolve` → hoy 3, deberían 4 | PC |
| B-MED-4 | Fuga entre el entrenamiento de Laya y «apartados»: 17 casos de dev con el mismo `state` y etiqueta que `kevdata-v4/laya_train.jsonl` (2 reales R0232.0, R0244.0 cortados a 1200; 15 sintéticos). `build_kev_data.py:29-37` agrupa por misión, no por texto | `build_kev_data.py:29-37` | «152 apartados 94,1 %» (hasta 2), recall@16 97,7 % | colisiones de `state` dev/train = 17 → 0 | PC |
| B-MED-5 | `bench_decision` no levanta S1 como el producto: con sólo `BAXY_S1_GGUF`, `BAXY_S1_VETO`=0 y Laya nunca se consulta; no espera a Laya; el resumen no guarda `BAXY_S1_*`, el GGUF, el md5 del catálogo; `--catalog` por defecto es el de `%LOCALAPPDATA%`, que reescribe cada arranque del producto (hoy md5 9466fc19, 266 apps, frente a 7fb060eb, 600) | `bench_decision.py:147-196`; `mind.py:510-513,934` | todo A/B S1 de decision2 sin `--catalog` explícito | exigir `--catalog`; resumen con S1 | PC |
| B-MED-6 | Escenas «S1 on/off» no miden nada: S1 no actúa en el latido (`mind.py:925-926`) y `bench_escenas.py:113` ni crea `SystemOne` | — | línea base de escenas on/off (diferencia = ruido) | correr una vez | PC |
| B-MED-7 | decision2 P251 y P252 esperan `window.maximize`/`snap` directo, pero el catálogo exige un `windowId` de `window.resolve`: Qwen acierta y cuenta como fallo (−2 por corrida), lo que B-MED-1 «recupera» de forma espuria | casos del banco | −2 en cada corrida | aceptar `window.resolve` como primer paso | ambas (banco) |
| B-MED-8 | La traza de un turno corregido lleva la duda de la llamada original | `mind.py:1032-1035` | análisis de la duda por operación | campo `doubt_of` | PC |
| B-MED-9 | `rescore_e2e.py:25-39` puede rejuzgar un caso con los eventos de otro (textos repetidos en `vivo_ft.json`, `limiteB.json`) (= R12.5) | — | rejuicios | buscar desde la posición del caso | portátil |
| B-MED-10 | Fase 4 de ayudas: `juzgar_fase4.py:115-124` junta pasos del historial con los del turno final (OTRA_OP 46 → ≤39, OK 130 → ≤137); `effect_ok` da `False` por `None`; `hacer_fase4*.py` contesta «sí» a cualquier confirmación; `e2e_pc2/3.sh` con `KIND=fal` sin guardián de juegos | `scripts/renew/notebook/*`, `ayudas/*` | cifras de la fase 4 del objetivo ayudas (cerrado) | — | portátil |

Ley 2 en S1: sólo restos menores (`system_one.KINDS` sólo lo usan los scripts de entrenamiento; docstrings de `doubt.py`
«nothing decides on it yet» y de `system_one.py` con el 94,1 % de layam-v1, no del GGUF que se sirve). No queda Kev,
pregunta lateral, sopa ni «Laya primero» en el producto. Dudosos de S1: USS de Laya con mmap quizá no cuenta sus ~340 MB;
`_ask` no captura `IncompleteRead`; con semilla 0 s1-l0-04-nb cambió acciones que la capa 0 no puede cambiar (ruido);
`arg_ok` por subcadena acepta «10» por «1».

## Dudosos (falta medir o decidir)

- Applets del Panel de control en `rundll32`/`explorer` sin proteger (`ncpa.cpl` «Deshabilitar» el adaptador de red).
- `display.mode.set` y `window.close.all` (consolas) en el latido o en Bypass.
- Valor de campos de contraseña leído antes de mirar `IsPassword` (`DesktopUiaWorker.ps1:1232-1244`).
- `web.download` sin Mark-of-the-Web; `memory.correct` y `schedule.alarms cancel` sin confirmación (decisión de diseño).
- DPI en `window.*` con monitores de escalas distintas; `ArgumentException` de `GetProcessById` en el proveedor de ventanas.
- Papelera llena (el conteo no sube), Papelera en unidades sin `$Recycle.Bin`.
