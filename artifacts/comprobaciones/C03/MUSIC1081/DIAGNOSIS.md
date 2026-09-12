# MUSIC1081 — selección Spotify UIA existente

Diagnóstico de lectura, sin parche: la divergencia demostrada está en descubrimiento de resultados, antes del clic de reproducción. No hay datos suficientes para decidir cuál de los predicados de descubrimiento rechazó la UI real. No se ejecutó Spotify, UIA, Core, HTTP, pruebas ni cambios de fuente/registro.

## Recibo y primera frontera

MUSIC_TAIL962/ROOT_ADJUDICATION.json y el journal del perfil enlazan H0068, «pon música de daft punk», a inv88672a39-9448-4096-accb-10d3f48873f8, mission526382df-b843-40b2-8e65-111795d67a11:21:12:37.6304015Z→21:12:52.0457414Z,14.415s. La preparación/confirmación exacta admitió media.play.query {provider:spotify,query:daft punk}. Resultado failed, spotify_exact_result_not_found, verified=false, result=null, replayed=false, effectMayHaveOccurred=true. No hubo reproducción verificada. Los17 casos posteriores de962 no se ejecutaron.

La captura propia muestra petición, confirmación y respuesta honesta por ruta error; no muestra resultado/UIA crudo del hijo. shell-trace: seq50 inicia ejecución confirmada en t2,ms13843.831; seq65 termina,ms28276.708. El perfil/captures está vacío; launch.stderr está vacío y launch.stdout sólo contiene arranque. En los archivos propios examinados no está preservado el árbol UIA, stdout JSON del hijo, nombre/rectángulo de candidatos ni valor de la búsqueda. No abrir planner-state cifrado ni sus claves para intentar suplir esa evidencia.

La rama única que emite ese error en SpotifyDesktopAutomation.ps1:201–202 exige playCandidate=null y candidate=null al concluir el sondeo. Se alcanza antes de InvokeElement(candidate):205 y antes de effect=true/InvokeElement(playCandidate):242–244. Con ese error no se llegó a la postlectura de reproducción. El padre SpotifyDesktopAdapter.cs:59–65 cruza ExternalEffectBoundary antes de lanzar PowerShell; ExternalJson.cs:70–88 conserva incertidumbre desde esa frontera, aunque el hijo indique effectObserved=false. Antes del fallo el script ya ejecutó spotify:, foreground y spotify:search. Por eso el recibo incierto no demuestra que pulsara Play; tampoco puede reinterpretarse como garantía global de cero efecto.

Los dos owners Spotify son idénticos al commit962 c1c796096ce81319cdd9fe8419282171f5eeb3c1 (git diff acotado vacío). La base de la lectura actual es9cae1d673beb0f630001541bf4211d387f893d07; no se atribuye una reparación Spotify a cambios SMTC1079.

## Predicados actuales que raíz debe distinguir

1. Script:92–131 localiza el primer proceso Spotify con ventana, ComboBox cuyo nombre contiene play/reproducir; exige foreground y envía spotify:search: + EscapeDataString(query). El error final no fue window_missing/search_box_missing/foreground_not_verified. No demuestra que la página correcta hubiese terminado de cargar.
2. Script:143–189 lee ValuePattern del ComboBox/Edit y el árbol de la ventana. Busca botón visible cuyo nombre empiece play/reproducir más espacio; en query el texto tras ese prefijo no se liga a la consulta. Alternativamente exige un elemento cuyo nombre plegado sea exactamente query. Ambos usan geometría: debajo del searchRect.Top+20 y antes de+600, dentro del ancho de ventana. El botón elegido es el más a la izquierda; el candidato nominal es el más alto. No hay snapshot para saber si había artista, overlay, carga, control genérico Play, resultado fuera de banda o nombre accesible distinto.
3. Script:181–199 exige querySearchValueMatches para terminar antes de6s, pero al horizonte acepta searchSnapshotReady aunque ValuePattern falte/no coincida. Ese fallback no explica por sí mismo el error962 porque allí faltaron ambos candidatos. Sí impide proponer simplemente aceptar cualquier Play o aumentar espera: podría seleccionar otra página.
4. Script:247–275, si alcanzara reproducción, query verifica Pause presente y now-playing no vacío/diferente del anterior; no acredita por sí solo pertenencia a artista/género solicitado. La selección relevante y la relación entre candidato y pista requieren hechos, no sólo cambio de canción. Es limitación estática adicional, no causa ejecutada de962.

## Inspección/reconciliación mínima por raíz, sin reintento implícito

- Conservar invocación/misión962 pendientes y recibo original. Una observación actual es reconciliación del estado presente, no una prueba retrospectiva de qué ocurrió el11/09. No reenviar confirmar/retry ni reutilizar inadvertidamente la confirmación restaurada de ese perfil.
- Observar sólo cliente existente: PID+creation, HWND y unicidad, título/estado visible y sesión SMTC identificada realmente como Spotify con pista/artista/playbackStatus. Si no hay Spotify visible o hay varias ventanas/clientes, registrar ese hecho actual y detener la inspección dirigida; no lanzar/cerrar para fabricar la precondición. Proceso Spotify solo no demuestra sesión, cola o contenido.
- Con la herramienta UIA/captura ya disponible y autorización de raíz, limitar lectura a esa ventana: Name, ControlType, IsOffscreen, BoundingRectangle y disponibilidad/valor del patrón de la búsqueda; controles/resultados visibles y now-playing. No credenciales, cookies, historial, claves ni árbol del escritorio. Registrar si la UI presenta login/intersticial, sin leer datos de autenticación. Una captura puede contener datos propios del cliente: mantenerla privada.
- Si todavía está la consulta correspondiente, comprobar su valor y los rectángulos/nombres contra los predicados anteriores sin invocar controles. Si está en otra página, no afirmar que reproduce el estado962: preparar únicamente una futura petición autorizada y observada tras reconciliar. Navegar a búsqueda es un efecto distinto de inspeccionar y no queda autorizado por este informe.
- Reparación condicional del owner existente: sólo con snapshot que demuestre el candidato pertinente rechazado, ajustar el predicado responsable de tipo/geometría/identidad manteniendo vínculo consulta→resultado→reproducción. Si la UI observada sólo demuestra loading/login/otra página, corregir esa precondición y conservar fallo honesto. No añadir nombres, umbrales difusos, elección arbitraria ni bypass de pertinencia. No parche especulativo aquí.

## Masa que habilitaría esa ruta

12 candidatos1078: H0068,H0163,H0213,H0237,H0250,H0282,H0388,H0454,H0548,H0552,H0579,H0598. Son consultas de artista, título y género/ambiente por media.play.query existente; requieren pares propios de cada conducta, no dos ejemplos universales. Sólo H0068 tiene la invocación incierta962; los otros11 no heredan ese estado. No hay12 pases prometidos ni necesidad demostrada de provider nuevo. Los WAV/SMTC propios de1069–1080 no sustituyen el contenido solicitado ni prueban Spotify.

## Evidencia exacta y SHA256
- D:\Perfil\Escritorio\ETC\Programacion\BAXY DEFINITIVO\artifacts\comprobaciones\C03\MUSIC_TAIL962\ROOT_ADJUDICATION.json — f01c22b8b5a50ff75d19d37dcfd0af849e56b9e89c3195067aa0644ddd384a4d
- D:\Perfil\Escritorio\ETC\Programacion\BAXY DEFINITIVO\artifacts\comprobaciones\C03\MUSIC_TAIL962\PREREG.json — 91f3b15d8304aad8263cd1ac97fe2ff57f1a99fc953049fdf01f8f7f68f11336
- C:\Users\usuario\AppData\Local\BAXY\C03-music-tail962-private\CANDIDATE_AUTHORIZED.json — 45f2109dc51b8dc3b478cefa17ce0edea520c8414229af9c020c4c074e21e2a5
- C:\Users\usuario\AppData\Local\BAXY\C03-music-tail962-private\run\shell-trace.jsonl — f00c8a7bad9ea6f8c8e10ff50f4983f8e9e1ff5c3a37703d92578cc5b64c7ccc
- C:\Users\usuario\AppData\Local\BAXY\C03-music-tail962-private\run\capture\events.jsonl — 268b732c6c49171131f3e40735bd57689ce7b2f0013011b3a3f48b50278bee72
- C:\Users\usuario\AppData\Local\BAXY\C03-music-tail962-private\run\launch.stdout.log — 6c5df29f0cddeda42dc9d8cb01df0f81aabfac7288d3b70df27613f498f7bbdd
- C:\Users\usuario\AppData\Local\BAXY\C03-music-tail962-private\run\launch.stderr.log — e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
- C:\Users\usuario\AppData\Local\BAXY\C03-music-tail962-profile\journal\missions.jsonl — c6c0e0b1efd9fd1b5608dfda260a0ad6ae98518b6d022561599c4f88560ec4f2
- D:\Perfil\Escritorio\ETC\Programacion\BAXY DEFINITIVO\src\Baxy.Providers.Windows\External\SpotifyDesktopAdapter.cs — 458dd061525e48f88969d50c6cacd918acebecd393ad7330e59bfee920489f14
- D:\Perfil\Escritorio\ETC\Programacion\BAXY DEFINITIVO\src\Baxy.Providers.Windows\External\SpotifyDesktopAutomation.ps1 — 4416b58568074dad789ae29740866adc684e834d2e9f94beacfd8a099d8d0916
- D:\Perfil\Escritorio\ETC\Programacion\BAXY DEFINITIVO\src\Baxy.Providers.Windows\External\ExternalJson.cs — 02f9a2fcfcc9261c600cddeb9f7fe4852fdac1f922e2b88a21c6cb7cccd88b01
- C:\Users\usuario\AppData\Local\BAXY\C03-music1078-eligibility\ROWS.json — 97872947994ab717ad8d33b8f43ffc73c7c4f911ec5d03b9576d111487f95df2
