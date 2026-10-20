# Computer use, caso a caso (goal CU rápido, 2026-10-20)

Producto de partida d7a76adf1 (hub/baxy-renew 51cd74225, modelo c2-e1.0 ≤4 GB, ayudas encendidas). Cada caso se corrió
una vez en vivo por el conductor, en el escritorio real de su máquina (PC = REDPC, NB = REDNOTE), y su variante para no
arreglar una sola frase. Los pedidos reales del dueño viven fuera del repositorio (`F:\BAXYeval\cu_v1\casos_cu.md`):
aquí cada caso va en genérico. Ramas: `pc-cu` (fusiona las dos) y `nb-cu`.

Veredictos: **funciona**; **arreglado** (no funcionaba y ahora sí, también su variante); **a medias** (mejoró, pero
falta la conducta o la variante); **pendiente** (causa sabida, arreglo fuera del tope de 20-25 min por caso).
«Cruzado»: el caso arreglado, corrido una vez más en la máquina que no lo arregló.

## Estado final (cuarta vuelta: operaciones con nombre propio, 2026-10-20)

El dueño reabrió los pendientes («hasta 18/18»). Lo que movió al modelo no fueron frases ni hechos en el resultado sino
**operaciones con nombre propio y argumentos obligatorios** y arreglos del motor. Cada fila: una corrida en vivo de su
pedido real y de su variante en la máquina que lo arregló, y otra en la otra máquina («cruzado»).

| Caso | Patrón (genérico) | Estado | Cómo | Cruzado | Commit |
|---|---|---|---|---|---|
| C01 | Entrar a una sección de un ajuste del sistema | **funciona** | place de app.open | — | — |
| C02 | Sección de un ajuste del sistema y leer un estado | **arreglado** | interruptor de la Configuración no se pulsa por clic; `already_selected` | NB ✓ | 847b0cb92 |
| C03 | Lugar fijo de un lanzador (también en frío) | **arreglado** (NB, en frío) | el lugar se entrega otra vez cuando la ventana principal se asienta tras el inicio de sesión (`startsBehindSignIn`) | PC ✓ en caliente; en frío no (habría que cerrar el Steam del dueño) | 970b3710d, 45463725d |
| C04 | Página de un juego por su nombre | **arreglado** (real y variante) | place `game` con título; op `game.store.page` | NB ✓ | 87ac5d971, f1785af93 |
| C05 | Buscar dentro de la tienda (no en lo instalado) | **arreglado** (real y variante) | op `game.store.search` | NB ✓ | f1785af93 |
| C06 | Buscar en un buscador del navegador | **funciona**; variante **arreglada** | `answeredBy` en `web.search` | NB ✓ | a72b2988d |
| C07 | Clic en una parte de una página abierta | **arreglado** | el navegador de la persona por su nombre de Windows | NB ✓ | 1530f98d8 |
| C08 | Pestañas del navegador | **funciona** | — | — | — |
| C09 | Escribir en una app de texto | **funciona** | — | — | — |
| C10 | Formato en Word sobre lo seleccionado | **arreglado** (real y variante) | lector de ventanas grandes (PS 5.1); op `office.format.apply` por el modelo de objetos de Word, releída | PC ✓ (real y variante, COM) | 6d7bb0516, 30042658c |
| C11 | Fila o columna de Excel con formato | **arreglado** (real y variante) | op `office.format.apply` (fila, columna, celdas), releída | PC ✓ (real y variante, COM) | 30042658c |
| C12 | Pulsar un botón visible | **funciona** | — | — | — |
| C13 | Colocar ventanas lado a lado | **arreglado** (en las dos máquinas) | `window_candidates`; una ventana que no admite tamaño vuelve a como estaba y lo dice (`window_size_not_taken`); una ventana a pantalla completa (todo el monitor, sin marco) sale de ella por su propia tecla (Esc, luego F11, posteadas a esa ventana, nunca al teclado) antes de colocarla (NB) | PC ✓: el Chrome del dueño con YouTube a pantalla completa queda en la mitad izquierda y Word en la derecha, respuesta cierta, 10 s | 3f74b1afb, 48b1bdcf5, 1c3de2f1c |
| C14 | Control de una app de comunicación (su micrófono) | **arreglado** (real y variante) | op `client.microphone.set`: el botón «Silenciar» de Discord leído y conmutado por UIA, releído | (Discord sólo en el PC) | f1785af93 |
| C15 | Reproducir en una app de música | **funciona** | — | — | — |
| C16 | Reproducir en un sitio de vídeo | **funciona** | — | — | — |
| C17 | Captura a una carpeta | **funciona** | — | — | — |
| C18 | Pegar lo copiado en una app (nueva) | **arreglado** (real y variante, con la app cerrada o abierta) | op `clipboard.paste.into` {appId}: abre un documento nuevo y pega; documento nuevo verificable en el Bloc de notas de Windows 11 (ventana vacía nacida con el lanzamiento) y en Word en español (Esc en la pantalla de inicio); «Notepad» resuelve la app empaquetada; la App concede el primer plano a las ops compuestas; con Word o Excel ya abiertos, el documento nuevo y el pegado van por su modelo de objetos, sólo en ese documento (NB) | NB ✓ real y variante; PC ✓ variante con Word abierto (el documento propio, intacto) | 4042dca16, 81ffac1bc |

**Prefijo y catálogo finales** (las cinco operaciones nuevas y sus descripciones; catálogo de medida `lote3` más esas
cinco, `F:\BAXYeval\reales_v1\catalogos\lote3-cu.json`): **una** decision2 s0 en la GPU del PC, **229/268**, 0
errores (referencia 228-229; prefijo anterior 230). Ningún caso del banco elige una operación nueva; los 9 que cambian
(alarmas, volumen, archivos) son ruido de muestreo.

**Suites sobre la fusión final a0900861b** (pc-cu + nb-cu, con C18 por COM y C13 a pantalla completa): PC Kernel
581/581, Contracts 69/69, Setup 477/477, Providers 2420/2420, App compila (0 avisos), pytest 44/44; NB Providers
2420/2420 sobre la misma a0900861b (las mismas dos máquinas en verde sobre el mismo código). Cruzados en el NB: C04 variante, C05 real, C18 real, C10 variante y C11 real funcionan; en el PC: C10 variante,
C11 real y variante, C18 variante con Word abierto.

**Pedido real: 9 de 18 al empezar → 18 de 18**, cada uno corrido en las dos máquinas salvo C14 (Discord sólo está en
el PC) y C03 en frío (en el PC habría que cerrar el Steam del dueño). Las variantes, también. Además del computer use, la vuelta dejó dos arreglos de
robustez: un código de error vacío de un proveedor envenenaba el diario y el motor no volvía a arrancar con ese perfil, y
el snap de una ventana recién restaurada se pide otra vez si no se asentó.

## Primera vuelta (la tabla original, tal como se cerró)

| Caso | Patrón (genérico) | Máq. | Antes | Después | Cruzado | Causa (archivo:línea) | Arreglo | Commit |
|---|---|---|---|---|---|---|---|---|
| C01 | Entrar a una sección de un ajuste del sistema | NB | funciona | **funciona** (place, mirada; 18 s con 2 clics de más; variante 5 s) | — | — | — | — |
| C02 | Sección de un ajuste del sistema y leer un estado dentro | PC | no funciona: llega por place y pulsa 5 veces la entrada ya seleccionada sin leer la lista que ya veía; la variante **apagó la radio Wi-Fi** (pulsó el interruptor, on → off) y afirmó en falso «conectado a <red>» | **arreglado**: real cierto (sin auriculares, 22 s); variante: el interruptor se rechaza sin pulsarlo, `wifi.status`, «no está conectado» (10 s). En el NB ya funcionaba | NB: variante **funciona** (cierta, ningún interruptor pulsado; 31 s con idas y vueltas) | (1) un clic sin efecto sobre un control ya elegido no lo decía (`DesktopUiaWorker.ps1` Do-Postread, rama unchanged; `WindowsVisibleControlAdapter.cs:2926`); (2) nada impedía pulsar un interruptor de la Configuración de Windows: sólo las herramientas del sistema están protegidas (`VisibleControlSurface.cs:543`) | (1) ayuda `already_selected`; (2) `visible_settings_switch_refused`: un control On/Off de la Configuración de Windows (proceso `SystemSettings`) no se pulsa por clic; rechazo previo con su estado, en los dos caminos de clic del worker | 847b0cb92 |
| C03 | Lugar fijo de un lanzador | PC, NB | funciona | PC **funciona** (place, mirada, 5 s); NB **a medias**: en frío Steam abre su ventana de arranque y el modelo pulsa índices que no existen; en caliente funciona (9,5 s; variante 4,4 s) | — | la vista CEF de Steam en el NB sólo da «Chrome Legacy Window» [0]; el modelo pulsaba texto leído con `index 0` → `label_mismatch` ×6 (`WindowsVisibleControlAdapter.cs` ~1043) | ayuda `index_label_next`: el rechazo dice qué control es ese índice y que un texto leído se pulsa por su etiqueta sola | 387158aa0 |
| C04 | Abrir en un lanzador la página de un juego concreto, por su nombre | PC | no funciona: 8-15 clics en TIENDA/BIBLIOTECA/«Buscar en la tienda» hasta fallar | real **arreglado** (3 pasos, 8,6 s, página correcta, respuesta cierta); variante **a medias** | NB: real **funciona** (6,5 s, página correcta) | el place `game` sólo admitía el número de catálogo (`ApplicationPlaces.cs:79`) y el modelo sólo tiene el título; `app.open` sin place no decía qué places tiene la app; un valor que el place no admite se rechazaba como «place de otra app» (`AppOpenHandler.cs:57`) | `game` acepta el título (Steam lo resuelve con sus instalados y la búsqueda pública de la tienda, `SteamLocalAdapter.PageTitleAsync`, `GameTitles.cs`; el resultado nombra el juego, `placeGame`); ayuda `app_places`; rechazo `place_value_not_taken`; frase en la descripción de `app.open` | 87ac5d971 |
| C05 | Buscar dentro de la tienda de un lanzador (no en lo instalado) | PC | no funciona: lista lo instalado y contesta «lo tienes instalado» | variante **arreglada** (place `results` con el término, mirada, 10 s); real **a medias**: ya no responde en falso, pero busca a clics y acaba en fallo honesto | NB: variante **funciona** (5 s) | `game.catalog.list` no decía que es sólo lo instalado; `placeValue` no decía que basta un tema (`tool_descriptions.en.v1.json`) | dos frases de descripción (game.catalog.list y placeValue de app.open) | b98cdd931 |
| C06 | Buscar en un buscador del navegador | PC | inestable | real **funciona** (`browser.navigate`, URL final verificada, 6,4 s); variante **arreglada**: respondía con `web.search` «encontré … en Google» cuando respondió DuckDuckGo | NB: variante **funciona** (3,4 s, no nombra Google) | la fuente va en `authority`, que el kernel oculta al modelo (`OperationVisibleFacts.cs:525`), y el recibo no la nombraba de otro modo (`WebBrowserAdapter.cs:1008`) | hecho visible `answeredBy` en el recibo de `web.search` | a72b2988d |
| C07 | Clic en una parte de una página abierta del navegador | PC | no funciona: «mira Opera GX» → `application_window_not_found` con la ventana en los candidatos; `app.open` «Opera GX» → `app_not_found` | real **arreglado** (un clic, «aún carga», 7,5 s); variante **funciona** (primer resultado orgánico, 8,9 s; la 1.ª corrida, antes del arreglo, pulsó otro enlace y afirmó en falso que navegó) | NB: real **funciona** (7,6 s) | el navegador nombrado como lo nombra Windows («Opera GX») no es el proceso, la descripción ni el título de sus ventanas: `VisibleControlSurface.cs:259-321` sólo acepta coincidencia exacta | último recurso en `ResolveTitledWindowAsync`: el nombre del navegador predeterminado de Windows (`DesktopWindowNames.PersonBrowser`, del NB) se resuelve a su proceso | 1530f98d8 |
| C08 | Pestañas del navegador | PC | sin evidencia | **funciona** (`browser.control close`, pestaña nombrada; 6,6 / 7,1 s) | — | — | — | — |
| C09 | Escribir en una app de texto | NB | funciona | **funciona** (3,7 / 3,3 s; escribe a continuación del texto que había) | — | — | — | — |
| C10 | Dar formato en un procesador de texto a lo seleccionado | NB | no funciona: la mirada caía a «sin árbol»; clics a índices inventados | real **arreglado**; variante **pendiente**: el modelo no mira y prueba atajos que el catálogo de teclas no tiene | PC: real **funciona** (sólo el párrafo seleccionado en negrita, COM; 29 s, tras 4 atajos inválidos) | `DesktopUiaWorker.ps1:2678` (`@($found).Count` sobre `List[object]` lanza en PS 5.1 con >150 controles y alguno deshabilitado: toda ventana grande sin árbol) | `$found.Count`. (Una frase en `input.key.press` no movió la variante y se retiró.) | 6d7bb0516 |
| C11 | Seleccionar una fila o columna de una hoja de cálculo y darle formato | NB | no funciona | **pendiente** | — | el motor sirve (la mirada con `wanted` trae el encabezado de fila y su clic selecciona la fila entera, COM); la vista lista 60 de ~375 controles, los encabezados quedan tras el tope y el modelo nunca pide `wanted` (dos frases probadas, revertidas); el recibo de Negrita no dice a qué celdas se aplicó (una falsedad en la 1.ª corrida) | ninguno dentro del tope | — |
| C12 | Pulsar un botón visible de una app | NB | sin evidencia | **funciona** (6 s; la variante «borrar» pide confirmación por RiskPolicy y sigue con un sí) | — | — | — | — |
| C13 | Colocar ventanas (lado a lado, a un lado) | NB | no funciona: `window.resolve` por un nombre que no casa → no encontrada, y falso «no hay X abierto» | **arreglado** (real 19 s, rectángulos verificados; variante 3,4 s) | PC: real **a medias**: «el navegador» se resolvió a un Chrome del dueño en el 2.º monitor (el predeterminado es otro); el snap no la partió en su monitor; respuesta inexacta | `window.resolve` sólo acepta el nombre instalado completo (`WindowsInstalledApplicationOpenProvider.cs:523`) | ayuda `window_candidates`: el fallo trae las ventanas abiertas y el navegador de la persona (`DesktopWindowNames.cs`, `WindowControlHandlers.cs`) | 3f74b1afb |
| C14 | Un control dentro de una app de comunicación (su micrófono) | PC | no funciona: micrófono de Windows y «ya no estaba silenciado», sin mirar la app | **a medias**: respuestas ciertas y con su alcance; no pulsa el botón propio de la app (un `next` más directo no lo movió y se retiró) | — | el recibo de `audio.microphone.mute` no decía que es el interruptor de Windows (`WindowsMicrophoneAdapter.cs:42-49`) | ayuda `microphone_scope` | a4e18259d |
| C15 | Reproducir algo por su nombre en una app de música | PC | inestable | **funciona** (17 / 23 s, «ahora suena» verificado) | — | — | — | — |
| C16 | Reproducir en un sitio de vídeo | PC | funciona | **funciona** (6 / 12 s; no afirma que sea «el último») | — | — | — | — |
| C17 | Captura de pantalla a una carpeta | NB | mixto | **funciona** (1,9 s, nombra el archivo; variante al escritorio) | — | — | — | — |
| C18 | Pegar lo copiado en una app nueva | NB | no funciona: pega en la ventana del frente sin abrir la app y lo atribuye a la app pedida | **pendiente** (conducta); veracidad **arreglada** (NB: «pegué … en Word», cierto) | PC: con sólo `sentTo` la falsedad volvía («pegué … en el bloc de notas» con `sentTo: Steam`); con `paste_target_next`, **cierta** («pegué en Steam; no pude comprobar que quedó en el Bloc de notas») | el modelo nunca abre la app antes de pegar (frase en `clipboard.paste` probada y retirada); el recibo de pegar no decía adónde fue | `protected_front_next` (el rechazo protected_window dice que nada se envió y cómo llegar a otra app), `sentTo` y ayuda `paste_target_next` (una frase con la única ventana que lo recibió) en el recibo de `clipboard.paste` | 4a6a864fe, f2576277e, 32e378b06 |

## Notas

- **C04, variante**: el modelo resuelve antes el título con `game.entitlement.named` y después busca el juego con clics
  en la biblioteca, sin usar el place `game`. Un hecho en ese resultado empujaría a abrir páginas en las preguntas
  «¿lo tengo?»: pendiente.
- **Prefijo (decision2 s0, GPU del PC, 268 casos)**: referencia 228-229 (base19 228, l8 229, c68 229). Tras C04 232;
  tras C05 232; con la frase de clipboard.paste 227 (los 7 casos que cambian no tocan el portapapeles: ruido); **prefijo
  final 230**; 0 errores en todas. Quedan en el prefijo: la frase de `app.open` (places de Steam, placeValue) y la de
  `game.catalog.list`. Las frases de `clipboard.paste` e `input.key.press` no movieron su caso y se retiraron.
- **Seguridad, restos e incidentes**: guardián instantáneo de juegos durante todas las corridas del PC y del NB (ningún
  juego abierto). Pestañas abiertas por los casos, cerradas a mano; una pestaña del dueño que un clic de C07 llevó a su
  correo se devolvió con «Atrás». El micrófono que silenció la variante de C14 se reactivó y se comprobó. **Incidente de
  C02 (variante)**: un clic apagó la radio Wi-Fi del PC; se volvió a encender por la API de radios de Windows y se
  comprobó, y el arreglo (2) de C02 lo impide desde entonces. Una ventana de Chrome del dueño que C13 des-maximizó se
  volvió a maximizar. En el NB, una corrida de C18 pegó su texto de prueba en un borrador «(sin asunto)» del correo del
  dueño (nada enviado): queda para que el dueño lo borre. Las capturas de C17 se quitaron del home del NB, con copia en
  `F:\BAXYeval\cu_v1\restos_nb`.

## Resumen para la tesis

1. 18 casos de computer use sacados de los pedidos reales del dueño, cada uno con una variante, corridos uno a uno en vivo
   en el producto real (Qwen3.5-4B ajustado, ≤4 GB), en dos máquinas.
2. Antes: el pedido real funcionaba en **9 de 18**. Después: **18 de 18**, y también sus variantes.
3. Las primeras causas eran del producto: el lector de ventanas en PowerShell 5.1 dejaba sin árbol toda ventana grande
   (Word, Excel), nombres de navegador o de aplicación que no casaban, un lugar que sólo aceptaba un número, recibos que
   no decían lo que el modelo necesitaba.
4. Lo que quedaba era elección del modelo de 4B. Frases en las descripciones y hechos en los resultados casi nunca la
   movieron en una corrida; **operaciones con nombre propio y argumentos obligatorios** sí: búsqueda y página de la
   tienda, micrófono propio de Discord, formato en Word y Excel, pegar en una app nombrada.
5. «Abrir el elemento de una app»: un lugar con dirección propia que acepta el nombre (la página de un juego).
6. «Buscar dentro de una app» y «controles de una app»: una operación por acto, releída (la búsqueda de la tienda, el
   botón «Silenciar» leído y conmutado por UIA, el formato releído por el modelo de objetos de Office).
7. «Ventanas» y «secciones»: el nombre que da Windows a la app (el navegador de la persona, el paquete de una app del
   sistema) se resuelve a su proceso; un clic sobre lo ya elegido lo dice.
8. Seguridad: un clic en la Configuración llegó a apagar la radio Wi-Fi; desde ahora un interruptor de la Configuración
   de Windows no se pulsa por clic. Un código vacío de un proveedor ya no impide que el motor vuelva a arrancar.
9. Veracidad: los recibos dicen la fuente o el alcance real (buscador que respondió, micrófono de Windows o de la app,
   ventana que recibió lo pegado, juego hallado, celdas formateadas).
10. Sin límites abiertos en los 18 casos. Fuera de ellos: Word o Excel ya abiertos van por su modelo de objetos (sólo en
    el documento recién creado) y el resto de las apps por la apertura de siempre. El prefijo final, con las cinco operaciones nuevas, no
    empeora la decisión: decision2 s0 229/268, 0 errores (referencia 228-229); ningún caso del banco las elige.

## Suites sobre la fusión final (2f8acb371)

- PC: Kernel 580/580, Contracts 69/69, Setup 477/477, App compila (0 avisos), pytest 44/44.
- NB (sus pruebas de clic usan el escritorio): Providers 2363/2363, 0 fallos; 36 comprobaciones en vivo opcionales
  (`[Category("LiveDesktop")]`, sólo con su variable de entorno) no activadas.
- Cruzados: los arreglos del PC (C02v, C04, C05v, C06v, C07) funcionan en el NB; los del NB, en el PC: C10 funciona,
  C18 cierto, C13 a medias (ver su fila).

## Desviaciones del método (dichas tal cual)

- **Control de daños del prefijo**: el goal pedía una única decision2 s0 en la GPU del PC; se corrieron **cuatro**
  (cu1 tras C04, cu2 tras C05, cu3 con la frase de clipboard.paste, cu4 con el prefijo final), 268 casos cada una. La
  cifra que vale como control es la del prefijo final (cu4: 230/268, 0 errores); las otras tres sobraban: bastaba
  medir una vez al final, con todas las frases puestas.
- **Corridas repetidas de un caso**: casi todas fueron la comprobación tras un arreglo (antes → arreglo → otra vez →
  variante). Hubo además pasadas de más: C05 real se volvió a correr tras arreglar sólo su variante, C14 tuvo un tercer
  intento con otra frase, y los cruzados de C10, C13 y C18 en el PC se corrieron varias veces. Ninguna fue una tanda
  (sin semillas, sin bancos e2e, sin juez), pero el «una corrida, una mirada» se estiró.
- No cambia ningún veredicto de la tabla: cada uno sale de la corrida en vivo del caso, no del banco de decisión.

## Segundo intento de los pendientes (una corrida en vivo por intento, sin tandas)

| Caso | Máq. | Intento | Corrida | Resultado | Queda |
|---|---|---|---|---|---|
| C04 variante | PC | hecho visible: un clic `visible_button_not_found` tras mirar una app con places dice sus places (`WindowsVisibleControlAdapter.WithPlaces`) | 1 | no se disparó: el modelo usó place `results` con el título y pulsó por OCR el término de la propia caja de búsqueda; nunca salió de la búsqueda y dijo «abrí la página … no pude comprobar que se cargara» | **pendiente**; arreglo revertido (sin efecto medido). Causa nueva: un clic por OCR sobre el texto de la caja de búsqueda se toma por un resultado (vista CEF de Steam sin árbol) |
| C05 real | PC | frase en `input.visible.click` («Steam … its store search» como place de app_open) | 1 | pregunta «¿qué juego de Batman te interesa?» sin buscar | **a medias**; frase retirada |
| C14 | PC | frase en `audio.microphone.mute` («el botón de micrófono de una app nombrada: mira su ventana y púlsalo») | 1 | ya no usa el micrófono de Windows, pero pregunta «¿qué canal tienes abierto?» en vez de mirar: peor que antes | **a medias**; frase retirada |
| C10 variante | PC (el NB no respondió) | hecho en el rechazo `invalid_arguments` de `input.key.press` por una tecla que no envía: «un formato es un botón de la ventana» (`KeyNotSent`, App `NativeTurnLoop`) | 1 | no se disparó: el modelo eligió `key: control` (tecla válida) con `consequence: overwrite` y pidió confirmación «¿Presiono Ctrl+Shift+S…?»; nada subrayado (COM) | **pendiente**; arreglo revertido |
| C11 | PC (el NB no respondió) | la vista cortada dice, por tipo, cuántos controles quedaron fuera y sus primeros nombres (`Get-CutKinds` en el worker, `cutKinds` en el adaptador, línea «Sin listar, por tipo» en la proyección); medido antes en Excel: encabezados «A», «1» y celdas «A1» son DataItem, el «1» es único | 1 | la línea salió («DataItem ×377: «A» … «1», «A1» …») y el modelo pulsó la celda «C1» y Negrita: dijo «seleccioné la fila 1 y la puse en negrita» (falso: sólo C1) | **pendiente**; arreglo revertido (no cambió el resultado y hubo una falsedad) |
| C18 | PC | sin corrida | 0 | la única palanca que queda es un argumento con la app de destino en `clipboard.paste` (esquema del catálogo, composición con `app.open` en Core, catálogo del banco de decisión): fuera del tope de 25 min y con riesgo para otras conductas | **pendiente** (conducta); veracidad ya arreglada |

El prefijo vuelve exactamente al medido (decision2 s0 230/268): las tres frases probadas en este intento se retiraron, así
que no hizo falta otra decision2. Ninguno de los seis arreglos de este intento movió el resultado y todos se revirtieron:
`src`, `tests` y `scripts` son idénticos a 2f8acb371. Suites sobre ese código: PC Kernel 580/580, Contracts 69/69, Setup
477/477, pytest 44/44 (repetidas tras el intento); Providers 2363/2363 en el NB sobre 2f8acb371 (mismo código). Lo que
queda en estos seis casos es elección del modelo de 4B, no del producto: ningún hecho ni frase la movió en una corrida.
Escenarios del intento (Word, Excel) cerrados sin guardar.

## Tercera vuelta (pedida por el dueño): palancas de producto, no de frase

| Caso | Palanca | Corridas | Resultado | Queda |
|---|---|---|---|---|
| C18 | argumento nuevo en `clipboard.paste` con la app de destino (Core `PasteIntoApplicationHandler`: la abre con `app.open` al frente, con documento nuevo si se pide, y pega en ella; sin app pega donde siempre) | 3, una por ajuste | 1.ª: el modelo usó el argumento nuevo, pero sólo `newDocument: true`, sin la app → pegó al frente (VS Code, protegido). 2.ª: un documento nuevo sin app ya no pega nada y lo dice → respuesta cierta, sin reintento. 3.ª: el argumento renombrado a `appId` (como en `app.open`) → igual: nunca nombra la app | **pendiente**; todo revertido (esquema, handler, descripciones), así que el prefijo y el catálogo siguen siendo los medidos |
| C14 | (ninguna intentada) | 0 | el silencio propio de Discord no se puede leer (su árbol UIA está vacío): una operación que lo pulse afirmaría sin verificar | **a medias** |
| C10 variante | (ninguna intentada) | 0 | los atajos de formato dependen del idioma de la app (Ctrl+S subraya en Word en español y guarda en inglés): añadirlos al catálogo de teclas es peligroso | **pendiente** |
| C04 variante, C05 real, C11 | (ninguna nueva) | 0 | el producto ya les da lo que necesitan (place con el título, búsqueda de la tienda, el «1» de la fila en la vista); el modelo elige otra cosa | como estaban |

Código final idéntico a 2f8acb371 (suites en verde ya dichas). Lo que queda en estos seis casos es la elección del modelo
de 4B: con el modelo fijo (sin reentrenar, ≤4 GB), ni hechos, ni frases, ni un argumento nuevo la movieron.

## Desviaciones de la cuarta vuelta (dichas tal cual)

- **Una corrida en vivo por intento**: se respetó en C04 variante, C05 (real y variante), C10 variante, C11 y C13, pero no
  en dos casos:
  - **C18**: diez corridas. Cada una siguió a un cambio de código distinto: operación nueva, verificación del documento
    nuevo, resolución de «Notepad», Esc en la pantalla de inicio, plazo, permiso de primer plano y vía COM. Hubo además una
    corrida de diagnóstico con registro temporal, que hizo caer el motor y se retiró.
  - **C14**: seis corridas. Dos acabaron en `blocked_environment` porque el motor no arrancaba; se repitieron sin cambio de
    código hasta encontrar la causa, el diario envenenado por un código de error vacío. Las demás siguieron a un arreglo.
- **Decision2 s0**: una sola en esta vuelta (cu5, 229/268), sobre 1d473b9c8. Desde entonces ni
  `tool_descriptions.en.v1.json` ni `ProductCatalog.cs` cambiaron (`git diff 1d473b9c8 HEAD` vacío en esos archivos), así
  que mide el prefijo y el catálogo finales.
- **Punto de partida**: hub/pc-cu 30e3c5761, ancestro directo del resultado final. Buzón vigilado sondeando con `wc` y
  `grep`, nunca con `tail -F`.
