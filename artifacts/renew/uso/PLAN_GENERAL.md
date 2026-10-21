# Plan general: apps que no exponen sus botones, identidad, foco y elección del modelo

2026-10-21, sesión de uso real. Pedido del dueño: dejar de arreglar a ciegas, investigar (documentación, estado del
arte, usuarios, papers) y generalizar, incluidos los arreglos de la sesión. Cinco investigaciones: evidencia interna
del proyecto, accesibilidad por familia de app, grounding visual, identidad de ventana y foco, y elección de
herramientas en modelos pequeños. Fuentes en cada sección.

## Diagnóstico

| Familia (se detecta por la clase de ventana) | Por qué falla | Qué funciona |
|---|---|---|
| Chromium, Electron, WebView2 (`Chrome_RenderWidgetHostHWND`), Qt (`Qt*QWindow*`), Flutter (`FLUTTER_RUNNER_WIN32_WINDOW`) | El árbol se construye al primer `WM_GETOBJECT` y se llena de forma asíncrona; una vista tomada antes de que se asiente está vacía o cambia ([Chromium a11y](https://www.chromium.org/developers/design-documents/accessibility/), [Qt](https://qt-project.org/doc/d7/d16/qwindowsuiaaccessibility_8cpp_source.html)) | Despertar el árbol en el hijo de render y esperar a que el número de nombres deje de cambiar |
| CEF con ventana dentro de una app (Steam, `steamwebhelper`) | La app decide; Steam da 3 nodos (medido, `DECISION_VISION_V3.md:65-66`) | `-cef-force-accessibility` (decisión del dueño, sin verificar en Windows), URI, teclado, OCR estable |
| CEF pintado en textura (Epic: Unreal + CEF OSR), juegos DirectX, dibujadas a mano (`UnrealWindow`, sin hijo de render) | No hay objetos de plataforma: 0 nombres (medido) ([CEF API](https://opendlang.org/library/arsd.webview.cef_browser_host_t.set_accessibility_state.html)) | URI propias, teclado, OCR con superficie estable, grounding visual |
| Java Swing (`SunAwtFrame`) | No va por UIA (Java Access Bridge) | OCR o visión |

Además:
- Los clics fallan sobre superficies que se mueven («la superficie cambió»).
- La identidad de ventana casa nombres exactos, y una ventana con título traducido o un lanzador que pasa a otro proceso no se encuentra.
- El foco se toma con `AttachThreadInput`, que puede colgar hilos.
- El modelo repite la misma llamada fallida, copia URLs enormes y no conoce los lugares de una app si la descripción no la nombra.

## Propuestas

### A. Motor de computer use, para cualquier ventana

| # | Propuesta | Coste | Riesgo |
|---|---|---|---|
| A1 | Clasificar la ventana por familia (clases de la ventana y de sus hijos) y decir la familia en el recibo de la mirada | Bajo | Nulo |
| A2 | Despertar el árbol (`ElementFromHandle` en el hijo de render, propiedades de contenido) y esperar a que el número de nombres se estabilice antes de la vista; repetir tras ocultarse | Bajo; +0,2-1 s en la primera mirada | Bajo |
| A3 | Antes de pulsar, esperar superficie estable (dos capturas iguales) y volver a ubicar la etiqueta justo antes del clic ([Playwright](https://playwright.dev/docs/actionability)) | Bajo, sin modelo | Bajo; tope para animaciones sin fin |
| A4 | Verificación genérica: captura con el puntero ya encima, clic, estabilidad y diferencia en la zona y en la ventana, más prueba de llegada | Bajo | Medio: efectos fuera de la ventana |
| A5 | Grounding visual de respaldo: Qwen3.5-4B con su `mmproj` en CPU sobre un recorte, sólo si UIA y OCR no encuentran la etiqueta (opción A de `DECISION_VISION_V3.md`, aceptada el 2026-10-08 y sin implementar) | +0,7 GB de RAM, 1,3-10 s por consulta, 0 VRAM | Medio: hay que medir antes si el ajuste fino degradó la visión |
| A6 | La frase de lugares de `app.open` generada desde `app_places.v1.json` (generaliza el arreglo de Epic de hoy) | Bajo; prefijo y banco | Bajo |
| A7 | Relanzar Steam con `-cef-force-accessibility`, sólo con confirmación | Bajo | Medio: cierra Steam; sin verificar en Windows |

### B. Identidad de ventana y foco

| # | Propuesta | Coste | Riesgo |
|---|---|---|---|
| B1 | Identidad por capas: AUMID de la ventana; app empaquetada; exe = destino del `.lnk`; mismo exe bajo la misma raíz de instalación; título sólo al final. Recordar el par catálogo ↔ exe real al abrir. Sustituye la regla Win32/Win64 de hoy ([appids](https://learn.microsoft.com/en-us/windows/win32/shell/appids)) | Medio | Medio en la capa de la raíz (falsos positivos), acotado |
| B2 | No teclear nunca sin comprobar que la ventana destino está delante: si no lo está, no se teclea y se dice | Bajo | Casi nulo |
| B3 | Navegador: `AllowSetForegroundWindow(pid)` del navegador antes de abrir el enlace, que es lo canónico ([Raymond Chen](https://devblogs.microsoft.com/oldnewthing/20090220-00/?p=19083), así lo hace Chromium); `AttachThreadInput` sólo como último recurso | Bajo | Medio |

### C. Elección del modelo, sin reentrenar

| # | Propuesta | Coste | Riesgo |
|---|---|---|---|
| C1 | Referencias cortas: el recibo da `ref: r3` y las herramientas la aceptan, en lugar de URLs de 500 tokens | Bajo; proveedor y recibos | Bajo |
| C2 | Ayuda «misma llamada, mismo resultado»: a la tercera, un hecho con alternativas; el tope duro sigue al final | Bajo | Medio: sondeos legítimos |
| C3 | Ayudas con la llamada ya escrita (`place=results placeValue=…`, búsqueda primero) | Bajo | Bajo |
| C4 | Frases «cuándo no usar» en descripciones (instalar: no para buscar en una tienda) | Prefijo; banco | Bajo |

Descartado con evidencia:
- Recuperar herramientas o subconjuntos dinámicos: rompe la caché del prefijo y los recuperadores son débiles.
- Ejemplos dinámicos: −5 en decision2.
- `SPI_SETSCREENREADER`: es global y Chromium no lo lee.
- CDP y puertos de depuración: agujero de seguridad.
- Renombrar herramientas: el modelo aprendió los nombres actuales.

## Estado (2026-10-21, todo en `uso-real`)

| Pieza | Estado | Medido o probado |
|---|---|---|
| A1 familia de la ventana | Hecho, 4118a7e45 | Epic `unreal`, Steam `cef`, Spotify/Opera/Discord/VS Code `chromium` (clases medidas en redpc); en el recibo de la mirada |
| A2 árbol despertado y asentado | Hecho, 4118a7e45 | Pruebas; falta verlo en uso real |
| A3 superficie quieta antes de pulsar | Hecho, 2d07b43cb | Pruebas; falta verlo en Steam |
| A4 verificación por diferencia | Ya existía en lo esencial (línea base justo antes del clic, ventanas que se animan solas descartadas); queda el refinamiento de capturar con el puntero encima | — |
| A5 visión de respaldo | Hecho, 293357a9a: el escalón `vision` heredado, apuntado al servidor de la mente con el proyector en CPU, pregunta en `bbox_2d` | Medido en Epic: c2-e1.0 10/10 (5 textos, 5 iconos) a ~8 s; en el servidor de BAXY 2/2 a ~10 s; VRAM sin cambio, +0,6 GB de RAM; el latido siguiente reevaluó 689 de 43.579 tokens (el prefijo vuelve de `-cram`) |
| A6 frase de lugares desde los datos | Hecho, 26d66733e | decision2 s0 230/268 (ref. 229) |
| A7 Steam con `-cef-force-accessibility` | Descartado | Medido: la opción llega a steamwebhelper y sus 4 ventanas internas siguen con 0 elementos con nombre; Steam devuelto a como estaba |
| B1 identidad aprendida y carpetas de arquitectura | Hecho, 3756acf93 | `app.open` de Epic ya verifica (antes «?») |
| B2 la página abierta recibe el teclado | Hecho, eb5274fc7 | Pruebas; falta el caso Opera con Spotify delante |
| B3 primer plano cedido por PID | Hecho, 2f19c8b8a | Pruebas |
| C1 referencias cortas | Hecho, cf29f2510 | Pruebas; falta el clima con Google News |
| C2 ayuda de la misma llamada | Hecho, cf29f2510 | Saltó en uso real (Epic, 01:48) |
| C4 instalar no es buscar | Hecho, 26d66733e | decision2 s0 230/268 |
| Espera del lugar dibujado (nueva, del uso real) | Hecho, c5be279bb | Causa medida: la búsqueda de Epic llegó 1-2 s después y la mirada leyó la página anterior |

## Arreglos de la sesión: cuáles son generales

| Arreglo | General | Generalización |
|---|---|---|
| Navegador al frente tras navegar | Sí, cualquier navegador y página | B3 lo hace por la vía canónica |
| Ayuda de lugares tras un clic o mirada fallida | Sí, cualquier app con lugares | C3 escribe la llamada |
| Spotify: sólo la vista de resultados | No, es de Spotify | A3 y A4 llevan la idea de zona de contenido estable al motor |
| Epic: copia Win64 hermana | No | B1 la sustituye |
| Epic en la descripción de `app.open` | No | A6 la genera desde los datos |
