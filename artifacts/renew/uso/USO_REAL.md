# BAXY en uso real: errores del dueño, uno a uno

Sesión en vivo del 2026-10-20 en el PC (REDPC), rama `uso-real` desde `hub/baxy-renew` 51cd74225 (modelo c2-e1.0,
ayudas encendidas). El dueño usa BAXY, pasa cada error y lo vuelve a probar. Casos en genérico: las frases literales del
dueño no van a git.

## Arreglados

| # | Caso (genérico) | Causa | Arreglo | Commit | Segunda frase |
|---|---|---|---|---|---|

## En prueba (arreglados y compilados, falta la prueba del dueño)

| # | Caso (genérico) | Causa | Arreglo |
|---|---|---|---|
| 1 | Buscar algo en Google en un navegador con nombre (Opera GX) mientras otra app (Spotify) está delante: la página se abre detrás y el texto tecleado va a la otra app; el modelo repite «recargar + escribir» 7 veces | Proveedor: la navegación por el navegador de la persona abre el enlace con el shell y lo verifica, pero un proceso en segundo plano no puede pasarle el frente, así que el navegador queda detrás (`UserBrowserSurface.cs` NavigateAsync; recibo `input.text.type` → `sentTo: Spotify`) | Tras una navegación verificada, la ventana del navegador se pone delante con el mismo mecanismo que la concesión de frente (`IUserBrowserPlatform.BringToFrontAsync`: `FrontGate`, `LeaseFrontSignal`, `VisibleControlSurface.BringToFront`) |
| 2 | Pedir dos veces seguidas una canción de un artista en Spotify: la segunda vez suena «Tus Me Gusta» (otra canción) y el recibo dice verificado | Proveedor: si el buscador ya tiene la misma consulta (sin tildes ni mayúsculas), no se aparta la página de antes y el control «Reproducir …» de más a la izquierda de la ventana es el de la biblioteca lateral (`SpotifyDesktopAutomation.ps1` Select-BaxySpotifySearchResult) | Los candidatos se acotan a la vista de resultados («Spotify – Buscar»), que no contiene la barra lateral; sin esa vista, la ventana como antes |
| 4 | Abrir Epic Games e ir a su tienda o a la página de un juego: `app.open` queda incierto y «mirar la ventana» no la encuentra 7 veces | Proveedor + datos: el acceso directo apunta a `Binaries\Win32\EpicGamesLauncher.exe`, que arranca `Binaries\Win64\…` y sale, y la verificación sólo aceptaba la misma ruta o una carpeta versionada (`ExecutableIsLaunchedImage`); la ventana se titula «Iniciador de Epic Games» y su árbol de accesibilidad está vacío (0 elementos), así que pulsar no puede funcionar y no había lugares propios | Se acepta la copia `Win64` hermana de una carpeta `Win32`; Epic Games Launcher en `app_places.v1.json` con `store` y `results` (`…/store/browse?q=`), comprobados en vivo con captura de ventana (`…://library` no cambia de página y no se añadió) |

| 11 | Pedir que busque un juego en la tienda de Epic: el modelo llama a instalarlo (`game.install.named`), que no se verifica y no instala nada (Epic sin juegos instalados, sin descarga) | El modelo eligió mal: las dos frases de `app.open` que enumeran las apps con lugares (`tool_descriptions.en.v1.json`, descripción y argumento `place`) no nombraban a Epic, así que su búsqueda no existía para él | Epic Games Launcher en esas dos frases (palanca 4, prefijo ~+20 tokens), con decision2 s0 de control |

## Pendientes

| # | Caso (genérico) | Causa | Estado |
|---|---|---|---|
| 3 | Buscar un juego en la tienda de Steam: clics en «Buscar en la tienda» / «TIENDA» fallan (`visible_surface_changed_while_waiting`, `protected_window`, inciertos) hasta 7 veces | Límite conocido (app hecha con web) + el modelo no usa la vía directa que existe (`app.open` place `results`/`store`) | Ayuda de resultado propuesta; decidir cuándo se da (en `app.open` o sólo tras un clic fallido) por el riesgo de desviar `media.play.query` en Spotify |
| 5 | Pedir una suma sin decir cuál y responder «lo que quieras»: suma 1+1 (bien, recibo con el valor) y vuelve a preguntar qué sumar | Límite del modelo: con la conversación entera y el resultado delante, repite la pregunta | Sin arreglo |
| 6 | Una frase larga y confusa sobre que algo «tarda» y «apagar y encender» terminó cerrando Spotify (modo Bypass, sin confirmación) | El modelo eligió mal (`system.process.terminate.named`) | Anotado |
| 7 | Sumar con clics en la Calculadora: tras «2 +», pulsar «2» queda incierto y el modelo lo pulsa otra vez (sale 22) | Proveedor: la pantalla queda igual que antes de la pulsación (sigue mostrando 2) y la post-lectura da `visible_button_postread_unchanged` aunque el `invoke` llegó | Pendiente; la segunda vez el modelo usó `calculator.expression.evaluate` y salió bien |
| 8 | El tiempo de mañana: busca en noticias, lee artículos de Google News con URLs de ~500 tokens que copia mal (400, JSON cortado) y responde con el de hoy | El modelo copia URLs enormes (11 s cada una) y eligió la fuente `news` | Pendiente |
| 10 | Una pregunta de historia respondida con una búsqueda: la respuesta mezcla dos hechos de los fragmentos (un barco «hundido por la flota española» por la mención de otra guerra en el mismo fragmento) y atribuye a «historiadores modernos» lo que el resultado atribuye a una de las partes | Límite del modelo: falsedad al resumir fragmentos correctos (los resultados eran exactos; corrió en el checkout viejo, sin arreglos de esta sesión) | Sin arreglo con lo permitido |
| 9 | Tras leer una guía web, «ábrela en mi navegador»: pregunta qué archivo abrir y busca archivos | El modelo eligió mal (no usó `browser.navigate` con la URL que acababa de leer); antes había dicho «Abrí la guía» tras sólo leerla | Pendiente |
