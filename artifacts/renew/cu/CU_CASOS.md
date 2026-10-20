# Computer use, caso a caso (goal CU rápido, 2026-10-20)

Producto de partida d7a76adf1 (hub/baxy-renew 51cd74225, modelo c2-e1.0 ≤4 GB, ayudas encendidas). Cada caso se corrió
una vez en vivo por el conductor, en el escritorio real de su máquina (PC = REDPC, NB = REDNOTE), y su variante para no
arreglar una sola frase. Los pedidos reales del dueño viven fuera del repositorio (`F:\BAXYeval\cu_v1\casos_cu.md`):
aquí cada caso va en genérico. Ramas: `pc-cu` (fusiona las dos) y `nb-cu`.

Veredictos: **funciona**; **arreglado** (no funcionaba y ahora sí, también su variante); **a medias** (mejoró, pero
falta la conducta o la variante); **pendiente** (causa sabida, arreglo fuera del tope de 20-25 min por caso).
«Cruzado»: el caso arreglado, corrido una vez más en la máquina que no lo arregló.

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
| C18 | Pegar lo copiado en una app nueva | NB | no funciona: pega en la ventana del frente sin abrir la app y lo atribuye a la app pedida | **pendiente** (conducta); veracidad arreglada en el NB | PC: **la falsedad vuelve** (recibo `sentTo: Steam`, respuesta «pegué … en el bloc de notas») | el modelo nunca abre la app antes de pegar (frase en `clipboard.paste` probada y retirada); el recibo de pegar no decía adónde fue | `protected_front_next` (el rechazo protected_window dice que nada se envió y cómo llegar a otra app) y `sentTo` en el recibo de `clipboard.paste` | 4a6a864fe, f2576277e |

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

1. 18 casos de computer use sacados de los pedidos reales del dueño, cada uno con una variante; una corrida en vivo por
   caso en el producto real (modelo de 4B, ≤4 GB), en dos máquinas, en unas tres horas.
2. Antes: el pedido real funcionaba en **9 de 18**. Después: en **14 de 18** (C02, C04, C07, C10 y C13 pasan a
   funcionar); C05 y C14 mejoran a medias y C11 y C18 quedan pendientes con su causa.
3. Las causas fueron más del producto que del modelo: un fallo del lector de ventanas en PowerShell 5.1 dejaba sin árbol
   toda ventana grande (Word, Excel), un nombre de navegador o de ventana que no casaba, un lugar de la app que sólo
   aceptaba un número, recibos que no decían lo que el modelo necesitaba.
4. Patrón general «abrir el elemento de una app»: un lugar con dirección propia que acepta el nombre (la página de un
   juego), y el resultado de abrir una app lista los lugares a los que va directo (ayuda `app_places`).
5. «Buscar dentro de una app»: la búsqueda del lugar con lo que dijo la persona; se separa lo instalado de la tienda.
6. «Entrar a una sección y leer un estado»: se llega por lugar y se lee la vista; un clic sobre lo ya elegido lo dice.
7. «Ventanas» y «controles de una app»: el nombre que da Windows a la app (el navegador de la persona, sus ventanas
   abiertas) se resuelve a su proceso; dar formato funciona en Word una vez arreglado el lector.
8. Seguridad: un clic en la Configuración llegó a apagar la radio Wi-Fi; desde ahora un interruptor de la Configuración
   de Windows no se pulsa por clic (se rechaza con su estado), además de las herramientas del sistema ya protegidas.
9. Veracidad: cuatro recibos dicen ahora la fuente o el alcance real (buscador que respondió, micrófono de Windows,
   ventana que recibió lo pegado, juego hallado); quedan falsedades del modelo sobre lo pegado (C18).
10. Lo que queda es elección del modelo: no pide `wanted` en hojas grandes (C11), no abre la app antes de pegar (C18),
    no pulsa el botón propio de una app (C14). Ninguna frase de descripción lo movió; el prefijo final no empeora la
    decisión (decision2 230/268 frente a 228-229).
