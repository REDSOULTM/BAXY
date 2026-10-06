# El navegador de la persona (M122, 2026-10-02)

## El pedido

El dueño, 2026-10-02: «haz que BAXY inicie las cosas en el navegador que el
usuario usa, y que pueda utilizarlo. Cuando le pido una canción de YouTube la
abre en Edge, que no es mi navegador predeterminado. Yo tengo Disney y HBO
iniciados en Opera; si lo abre en Edge no está iniciado.» Y después: los BAXY
anteriores ya controlaron Opera y otros navegadores; lo primero es heredar.

En este PC el navegador predeterminado es **Opera GX**:
`HKCU\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice`
→ `ProgId = Opera GXStable` → `HKCR\Opera GXStable\shell\open\command` =
`"C:\Users\usuario\AppData\Local\Programs\Opera GX\opera.exe" -noautoupdate -- "%1"`
(versión 136.0.6008.76).

## Qué hicieron los BAXY anteriores (herencia)

Buscado en la historia de este repositorio (todas las ramas), en
`D:\Programacion\BAXY`, `D:\Programacion\BAXY DEFINITIVO`,
`D:\Programacion\Probando Gemma 4` (el agente gemma4, el BAXY anterior que el
dueño usó a diario), `D:\Programacion\Carter OS AI` y la `biblioteca/`.

| Versión | Abrir | Controlar / verificar |
|---|---|---|
| gemma4 (`Probando Gemma 4/gemma4_agent`) | `web_open_url` → `webbrowser.open(url)`: el **navegador predeterminado** (Opera GX), con su sesión. `browser_youtube_play` abre la URL `watch?v=` directa igual. Con un navegador nombrado: abre la app y escribe la URL con `Ctrl+L`, texto y `Enter`. | Sin verificación real: `verified=False`, `playback_verified=False` y una captura de pantalla. Streaming: si Opera GX escuchaba en `127.0.0.1:9222`, Playwright `connect_over_cdp` y selectores (`domain_tools/__init__.py:_streaming_cdp_play`); si no, `webbrowser.open` y «haz clic en el título». Lectura de lo que suena por **SMTC** con `winsdk` (`domain_tools/media_now_playing_fast.py`). |
| gemma4, `scripts/launch_opera_cdp.ps1` | Para tener ese puerto **cerraba Opera GX** (`Stop-Process -Force`) y lo relanzaba con `--remote-debugging-port=9222 --user-data-dir=<perfil real de Opera GX>`. | Después se vio que **Chromium 136+ ignora el puerto de depuración sobre el perfil por defecto** (endurecimiento de 2025 contra el robo de cookies por CDP; `tools_pkg/ops_tools.py:_launch_cdp_instance`, `tools.py:verify_window_exists`). gemma4 pasó a una instancia CDP **dedicada** con su propio perfil, y para verificar un dominio en el navegador real se conformó con «hay una ventana de navegador abierta» y una advertencia. |
| Carter v2 (`Carter OS AI/Carter_v2/.../capabilities/web.py`) | `webbrowser.open(url)` | Playwright sobre `CARTER_BROWSER_CDP_URL` (`127.0.0.1:9222`) cuando el navegador ya lo exponía. |
| BAXY Definitivo desde su punto de partida (`96d284ef`) y `D:\Programacion\BAXY` | Edge con un perfil CDP privado del producto (`%LOCALAPPDATA%\BAXY\browser-session-v1\edge`); los navegadores nombrados (`browser.navigate.named`), con su propio perfil privado. | CDP: URL final, estado del `<video>`, avance del reproductor. |

**Lo que funcionaba «muy bien»** en los BAXY anteriores era abrir en el
navegador predeterminado: la persona ve la página en su Opera, con sus
sesiones de Disney+, HBO o YouTube iniciadas. **Lo que no funcionaba** era
verificar: nada (o una captura), o cerrar el navegador de la persona para
relanzarlo con CDP, que hoy además no sirve por Chromium 136.

**Por qué este BAXY usa Edge**: el contrato de producto exige efectos
verificados (invariante 2) y el único modo de leer el DOM (URL final,
`video.currentTime`) era un navegador con CDP; con el perfil real imposible
desde Chromium 136, el producto lanzó su propio perfil. No hay decisión
escrita del dueño que elija Edge; es una consecuencia técnica. Lo que costó: el
perfil privado no tiene las sesiones de la persona.

## Diseño

Se hereda la apertura de los BAXY anteriores (el enlace va al navegador de la
persona, como un clic) y se le pone la verificación que les faltaba, sin
tomar el navegador.

1. **Detección.** `UserChoice` de `https` (y de `http` si falta) → `ProgId` →
   comando `shell\open\command` → ejecutable absoluto. Familia por `ProgId` o
   ejecutable: Opera GX, Opera, Chrome, Edge, Brave, Vivaldi, Firefox; otro
   cualquiera vale con su nombre de proceso.
2. **Abrir.** `ShellExecute` de la URL (`UseShellExecute=true`): lo mismo que
   un clic en un enlace. Pestaña nueva en la ventana que la persona usa, con su
   perfil y sus sesiones. Si Opera no estaba abierto, Windows lo abre. **Nunca
   se cierra ni se reinicia el navegador de la persona.**
3. **Verificar sin secuestrar.**
   - **Navegación**: antes de abrir se anotan los títulos de las ventanas del
     navegador; después, en la ventana cuyo título cambió, UI Automation lee el
     **campo de dirección** recorriendo sólo el marco del navegador (nunca
     entra en el `Document` de la página). Sólo se compara el sitio con el
     abierto (`www.` y subdominios incluidos). Una dirección de otro sitio no
     se reporta nunca. Sin lectura del sitio abierto, el resultado es
     **incierto** (`user_browser_navigation_unconfirmed`, efecto posible): se
     dice que se abrió y que la persona puede comprobarlo.
   - **YouTube**: la búsqueda HTTP de siempre da el id y el título del primer
     video; se abre `watch?v=`; la **sesión multimedia de Windows (SMTC)** con
     ese título en `Playing` es la verificación (`user_browser_smtc_postread`).
     Si aparece en pausa (el navegador frenó la reproducción automática) se
     pulsa **una vez** el `Play` de esa misma sesión. Nunca se pulsa otra
     sesión (lo que la persona tenía en pausa). Sin sesión que lo pruebe:
     incierto (`user_browser_playback_unconfirmed`).
   - **Streaming con recurso** (`streaming.navigate`): como la navegación, más
     una segunda lectura a los 2,5 s para ver si el servicio redirigió a
     iniciar sesión (`streaming_authentication_required`).
   - **Título en streaming** (`streaming.play.named`, Netflix y Disney+): se
     abre la búsqueda en la sesión de la persona (Netflix `search?q=`;
     Disney+ `es-419/browse/search` y el título escrito en su buscador con UI
     Automation `ValuePattern`), se pulsa con `InvokePattern` el elemento cuyo
     nombre es el título y luego el control «Reproducir / Ver ahora /
     Continuar / Play». Lo que prueba la reproducción es una sesión SMTC
     **nueva** del navegador en `Playing`, no lo que diga el guion. Si no:
     incierto (`user_browser_streaming_playback_unconfirmed`).
   - **Controlar lo que suena** (pausa, siguiente, volver, adelantar, «qué
     suena»): ya iba por SMTC (`WindowsMediaSessionAdapter`, primero en la
     cadena), así que controla la sesión de Opera sin cambios.
4. **CDP sobre el navegador de la persona: no.** Chromium 136+ (y Opera GX
   136, que va sobre un Chromium posterior) ignora `--remote-debugging-port`
   en el perfil por defecto. La única forma sería reiniciar Opera con el
   puerto y **otro** perfil (sin sus sesiones) o copiar su perfil (leer sus
   cookies): las dos van contra lo pedido y contra la privacidad. Nunca se
   hará sin un sí explícito del dueño.
5. **Edge del producto, sólo de respaldo**: cuando no se resuelve navegador
   predeterminado, cuando no se puede lanzar, con `BAXY_BROWSER=product`, o
   cuando una medición apunta `BAXY_CDP_ENDPOINT` a su propio navegador
   (fixture). Un enlace ya abierto en el navegador de la persona no se repite
   en Edge.

### Qué se pierde en el navegador de la persona (y sigue en CDP)

- **2026-10-06 (dueño: «todo lo que sea abrir un navegador… con el navegador
  predeterminado»):** `browser.page.read` y `browser.tabs.list` leen **siempre**
  el navegador de la persona (antes sólo si BAXY acababa de abrir ahí una
  página; si no, caían al Edge del producto). UI Automation sobre la ventana
  de delante: las pestañas son `TabItem` con `SelectionItemPattern` (Opera GX:
  `TabViewGx`), la página es el `Document` con `AutomationId` `RootWebArea`
  (aparece tras la primera consulta) leído con `TextPattern`. Sin ventana:
  `user_browser_not_running`; sin lectura: `user_browser_page_unreadable`. Los
  guiones escriben UTF-8 (`[Console]::OutputEncoding`): antes las tildes
  llegaban rotas y las citas de la página no coincidían. Probado en vivo con
  Opera GX: «qué pestañas tengo abiertas» y «léeme lo que dice la página».
- `browser.control` (atrás, recargar, desplazar, nueva pestaña, cerrar
  pestañas, pantalla completa) responde `user_browser_tabs_not_automatable`
  (nada hecho) siempre que hay navegador predeterminado, nunca actúa sobre un
  Edge que la persona no mira. Con atajos de teclado funcionaría (en vivo:
  Ctrl+T y Ctrl+W llegaron a Opera GX desde segundo plano), pero el «toque de
  Alt» que da el primer plano abre el menú de Opera y, tras esa prueba, el
  árbol de accesibilidad de Opera GX quedó cortado (`LiveBackgroundView`,
  `ElementNotAvailable`) hasta cerrarlo. No se activa sin una forma fiable de
  recuperarse.
- La verificación por DOM (`video.currentTime` avanzando, recarga de un
  reproductor atascado) pasa a SMTC: prueba que algo suena con ese título, no
  el segundo exacto.
- Netflix con «¿Quién está viendo?»: no se elige perfil por la persona; la
  búsqueda queda abierta y el resultado es incierto.
- `browser.navigate.named` a la **misma familia** que el predeterminado (p. ej.
  «ábrelo en Opera GX») abre en la sesión de la persona; a otra familia sigue
  con el perfil privado de ese navegador.

### Privacidad

No se leen cookies, contraseñas, historial ni ficheros de perfil. La lectura
de dirección mira sólo el marco del navegador y sólo se usa para comparar el
sitio recién abierto; los guiones de streaming sólo pulsan elementos cuyo
nombre es el título pedido o una palabra de reproducir, y devuelven el nombre
elegido. Las sesiones SMTC se leen como ya hacía `media.status`.

## Implementación

- `src/Baxy.Providers.Windows/External/UserBrowserIdentity.cs` — detección
  (`UserChoice` → `ProgId` → comando → familia, tokens SMTC).
- `.../UserBrowserPlatform.cs` — `IUserBrowserPlatform` y su versión Windows:
  `ShellExecute`, ventanas por proceso (`EnumWindows`), SMTC (`Windows.Media.Control`),
  y los dos guiones UIA.
- `.../UserBrowserScripts.cs` — los guiones UIA en línea (PowerShell 5.1):
  lectura del campo de dirección y paso de título/reproducir.
- `.../UserBrowserSurface.cs` — navegación, YouTube, streaming y su
  verificación; `BAXY_BROWSER=product` y `BAXY_CDP_ENDPOINT` mantienen Edge.
- `.../YouTubeSearch.cs` — búsqueda de YouTube compartida (id y título).
- `.../WebBrowserAdapter.cs` — usa la superficie del navegador de la persona
  para `browser.navigate`, `media.play.youtube`, `streaming.navigate` y
  `streaming.play.named`; Edge sólo de respaldo; operaciones de pestaña
  honestas tras una página en el navegador de la persona.
- `.../NamedBrowserAdapter.cs` — el navegador nombrado que es el
  predeterminado abre en la sesión de la persona.
- `src/baxy_mind/llm.py` — hechos de causa para los cuatro códigos nuevos.

## Verificación

- `tests/Baxy.Providers.Windows.Tests/UserBrowserTests.cs` (24, con
  plataforma falsa): detección por `ProgId`, apertura y lectura del sitio,
  dirección de otro sitio nunca reportada, incierto sin lectura, respaldo
  Edge (fallo de lanzamiento, sin predeterminado, `BAXY_BROWSER=product`,
  `BAXY_CDP_ENDPOINT`), YouTube por SMTC, pulsar `Play` sólo en la sesión del
  título, no tocar la sesión en pausa de la persona, operaciones de pestaña
  honestas, Netflix y Disney+ (búsqueda escrita), inicio de sesión pedido,
  `streaming.navigate`, navegación nombrada a la familia predeterminada.
- `tests/test_m122_user_browser_facts.py`: hechos de causa.
- Manual, 2026-10-02, con un Edge **propio y desechable** (perfil temporal,
  cerrado después por su PID): el guion de dirección leyó
  `https://example.com` en 1,2 s; el guion de página pulsó por UIA el enlace
  «Learn more» del contenido y la dirección pasó a
  `https://www.iana.org/help/example-domains`. Prueba que UIA lee el
  omnibox de Chromium y pulsa elementos de la página.
- **Opera GX real, 2026-10-02 01:20** (Opera estaba cerrado; ningún `Baxy.exe`
  en marcha; video silencioso para no sonar de madrugada), con
  `UserBrowserLiveCheck` (lo que corre `scripts/check_user_browser.ps1`):
  - Primera vuelta: YouTube **verificado** por SMTC (sesión
    `OperaSoftware.OperaGXWebBrowser.1732473326`, título del video, `playing`)
    y **pausado** por SMTC (`paused`, verificado). La navegación quedó
    **incierta**: el campo de dirección de Opera GX (`AddressTextfieldView`,
    «Campo de dirección») está a profundidad 15 del árbol y el recorrido
    paraba en 14. Arreglado (profundidad 24, 1500 nodos; el primer campo,
    `AddressBarViewGx`, tiene valor vacío y se salta).
  - Segunda vuelta: navegación **verificada**
    (`finalUrl https://example.com/`, `user_browser_uia_address_postread`,
    lectura ~1 s), YouTube verificado y pausado otra vez.
  - Paso de página en Opera GX, sobre pestañas propias: «Learn more» pulsado
    por UIA en example.com (la dirección pasó a iana.org); en duckduckgo.com
    el título se escribió en su buscador, que es un `ComboBox` (rol
    combobox), no un `Edit`: el guion acepta los dos. Opera GX expone sus
    paneles laterales como documentos en la vista cruda; en la vista de
    control sólo aparece el de la pestaña, y el guion elige el documento cuyo
    nombre empieza el título de la ventana.
  - Quedó abierto Opera GX con las pestañas de la comprobación (example.com,
    iana.org, duck.ai y dos videos de YouTube en pausa); no se cerró nada.

## Pendiente

- Netflix/Disney+ en Opera con la cuenta del dueño: los nombres accesibles de
  fichas y botones están tomados de lo medido por CDP en VIDEO1947/1919, no
  comprobados por UIA en Opera.
- HBO Max no es servicio del catálogo de `streaming.play.named` ni de
  `streaming.navigate`; cuando el pedido llega como `browser.navigate` ya abre
  en Opera, con la sesión. Añadirlo al catálogo es decisión aparte (catálogo,
  mente y decisor entrenado).
- Pestañas del navegador de la persona (atrás, recargar, cerrar pestaña) por
  teclado a su ventana, verificadas por la lectura de dirección.
- Instrumentos de medición que dependían de Edge: deben exportar
  `BAXY_BROWSER=product` (o su `BAXY_CDP_ENDPOINT`) para conservar el
  aislamiento.
