# El navegador de la persona (M122, 2026-10-02)

## El pedido

El autor, 2026-10-02: «haz que BAXY inicie las cosas en el navegador que el
usuario usa, y que pueda utilizarlo. Cuando le pido una canción de YouTube la
abre en Edge, que no es mi navegador predeterminado. Yo tengo Disney y HBO
iniciados en Opera; si lo abre en Edge no está iniciado.» Y después: los BAXY
anteriores ya controlaron Opera y otros navegadores; lo primero es heredar.

En este PC el navegador predeterminado es **Opera GX**:
`HKCU\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice`
→ `ProgId = Opera GXStable` → `HKCR\Opera GXStable\shell\open\command` =
`"%LOCALAPPDATA%\Programs\Opera GX\opera.exe" -noautoupdate -- "%1"`
(versión 136.0.6008.76).

## Qué hicieron los BAXY anteriores (herencia)

Buscado en la historia de este repositorio (todas las ramas), en
`D:\Programacion\BAXY`, `D:\Programacion\BAXY DEFINITIVO`,
la carpeta de pruebas de Gemma 4 (el agente gemma4, el BAXY anterior que el
autor usó a diario), la carpeta del prototipo Carter y la `biblioteca/`.

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
escrita del autor que elija Edge; es una consecuencia técnica. Lo que costó: el
perfil privado no tiene las sesiones de la persona.

## Diseño

Se hereda la apertura de los BAXY anteriores (el enlace va al navegador de la
persona, como un clic) y se le pone la verificación que les faltaba, sin
tomar el navegador.

1. **Detección.** `UserChoiceLatest\ProgId` de `https` (Windows 11 desde 25H2 escribe ahí la elección y deja
   `UserChoice` con la anterior, que sólo cuenta si la nueva falta), y de `http` si falta → `ProgId` →
   comando `shell\open\command` → ejecutable absoluto. Familia por `ProgId` o
   ejecutable: Opera GX, Opera, Chrome, Edge, Brave, Vivaldi, Firefox; otro
   cualquiera vale con su nombre de proceso.
2. **Abrir.** `ShellExecute` de la URL (`UseShellExecute=true`): lo mismo que
   un clic en un enlace. Pestaña nueva en la ventana que la persona usa, con su
   perfil y sus sesiones. Si Opera no estaba abierto, Windows lo abre. **Nunca
   se cierra ni se reinicia el navegador de la persona.**
3. **Verificar sin secuestrar.**
   - **Navegación**: antes de abrir se anotan los títulos de las ventanas del
     navegador y la dirección de la del frente (vacía en una pestaña nueva; si
     esa lectura falla deprisa, se repite una vez);
     después, en la ventana cuyo título cambió, UI Automation lee el
     **campo de dirección** recorriendo sólo el marco del navegador (nunca
     entra en el `Document` de la página). Llega la dirección pedida (ruta y
     cada parámetro pedido, con las grafías del navegador normalizadas;
     `UserBrowserArrival.cs`). Otra dirección del mismo sitio (`www.` y
     subdominios incluidos) vale sólo como redirección: no es la misma ruta
     con otra consulta (uso real v3 t4, c10) y es nueva en esa ventana (ventana
     nueva, o la del frente cuando antes mostraba otra cosa). Si el campo de
     la ventana cuyo título cambió sigue mostrando la página de antes (Opera GX
     tarda en ponerlo al día), se lee una vez más a los dos segundos aunque el
     título no se mueva; esa lectura no gasta ninguna de las tres que esperan
     a un título nuevo (noche r7, R7-portátil-5). Una
     dirección de otro sitio no se reporta nunca. Sin lectura que valga, el
     resultado es **incierto** (`user_browser_navigation_unconfirmed`, efecto
     posible) y dice qué se comprobó: `linkSent` (el enlace se entregó al
     navegador), `windowChanged` (alguna ventana suya cambió después) y
     `addressSeen` (`not_read`, `unreadable`, `no_address`, `page_from_before`,
     `other_page` o `same_site_not_known_new`), nunca la dirección leída de una
     pestaña. `streaming.navigate` y `streaming.play.named` siguen devolviendo
     su incierto sin esos datos. Se
     dice que se abrió, que no se pudo comprobar y que la persona puede
     comprobarlo: es honesto; dar por comprobada la página no lo es.
   - **YouTube**: la búsqueda HTTP de siempre da el id y el título del primer
     video; se abre `watch?v=`; la **sesión multimedia de Windows (SMTC)** con
     ese título en `Playing` es la verificación (`user_browser_smtc_postread`).
     Si aparece en pausa (el navegador frenó la reproducción automática) se
     pulsa **una vez** el `Play` de esa misma sesión. Nunca se pulsa otra
     sesión (lo que la persona tenía en pausa). Sin sesión que lo pruebe:
     incierto (`user_browser_playback_unconfirmed`). La espera es de 15 s con
     el navegador abierto y de 30 s si el pedido lo arrancó (Opera GX en frío
     tardó 9–16,5 s en `Playing`, tandas de PC 2026-10-12).
   - **Streaming con recurso** (`streaming.navigate`): como la navegación, más
     una segunda lectura a los 2,5 s para ver si el servicio redirigió a
     iniciar sesión (`streaming_authentication_required`).
   - **Título en streaming** (`streaming.play.named`, Netflix, Disney+ y HBO
     Max): ver «Streaming en la sesión de la persona» más abajo.
   - **Controlar lo que suena** (pausa, siguiente, volver, adelantar, «qué
     suena»): ya iba por SMTC (`WindowsMediaSessionAdapter`, primero en la
     cadena), así que controla la sesión de Opera sin cambios.
4. **CDP sobre el navegador de la persona: no.** Chromium 136+ (y Opera GX
   136, que va sobre un Chromium posterior) ignora `--remote-debugging-port`
   en el perfil por defecto. La única forma sería reiniciar Opera con el
   puerto y **otro** perfil (sin sus sesiones) o copiar su perfil (leer sus
   cookies): las dos van contra lo pedido y contra la privacidad. Nunca se
   hará sin un sí explícito del autor.
5. **Edge del producto, sólo de respaldo**: cuando no se resuelve navegador
   predeterminado, cuando no se puede lanzar, con `BAXY_BROWSER=product`, o
   cuando una medición apunta `BAXY_CDP_ENDPOINT` a su propio navegador
   (fixture). Un enlace ya abierto en el navegador de la persona no se repite
   en Edge.

### Streaming en la sesión de la persona (Disney+ y HBO Max, 2026-10-06)

El autor: «Disney y HBO deberían de funcionar». Tiene las dos sesiones
iniciadas en Opera GX; Netflix no tiene sesión en este PC.

| Servicio | Se abre | Título | Reproducir |
|---|---|---|---|
| Netflix | `netflix.com/search?q=<título>` | elemento cuyo nombre es el título | «Reproducir / Play…» |
| Disney+ | `disneyplus.com/browse/search` (sin `es-419`: redirige al idioma de la cuenta) y el título escrito en su buscador (`ValuePattern.SetValue`) | tarjeta «Coco Clasificación: 0+. Estreno: 2017…» (`Hyperlink` a `/browse/entity-<uuid>`) | «VER AHORA» o «CONTINUAR» (`Hyperlink` a `/play/<id>`) |
| HBO Max | `play.hbomax.com/search/result?q=<título>` (la URL que escribe su propio buscador) | tarjeta «The Last of Us. Fila 1 de 9…» (título entre aislantes bidi U+2066–2069) | «Ver The Last of Us, Temporada 1…» o «Reanudar Superman…» (`Button`) |

- **Elegir la tarjeta** (guion `PagePlay`, igual en cualquier Chromium: sólo
  nombres accesibles de la página): se quitan los caracteres de formato, se
  pliegan tildes y mayúsculas y se ordena: el nombre (o su primer tramo
  aislado) **es** el título; empieza por el título seguido de espacio, coma o
  punto; empieza por él y sigue como otro título («Daredevil: Born Again»,
  «Cocoon»); sólo lo contiene («Menú de Superman»). Gana la primera de la
  mejor clase.
- **Reproducir**: «reproducir, ver ahora, continuar, reanudar, play, watch
  now, resume, continue watching», o un verbo de ver seguido del título («Ver
  The Last of Us, …»); nunca un nombre con «tráiler/avance/teaser/mi lista».
- **Verificación**: Opera tiene **una** sesión SMTC para todo el navegador
  (`OperaSoftware.OperaGXWebBrowser…`), que cambia de título según lo que
  suena. Prueba = esa sesión con el título pedido (Disney+ la titula «Bluey |
  Disney+», HBO Max «The Last of Us») o con un título que no tenía, en
  `Playing`. Lo que ya estaba igual antes (mismo título, mismo estado: algo
  que la persona tenía en pausa en otra pestaña) no cuenta ni se pulsa. HBO
  Max tardó 12–15 s desde el botón hasta `Playing`: la espera es de 30 s.
  Si el guion no llegó a pulsar reproducir, el resultado es incierto en el
  acto: lo que suene entonces (el tráiler de una ficha) no es lo pedido.
- **«¿Quién está viendo?»**: si la página muestra esa pregunta (o «Who's
  watching?»), el guion se para y el resultado es
  `user_browser_streaming_profile_choice` (efecto posible, nada reproducido):
  la página queda abierta y la persona elige su perfil. No se elige perfil por
  ella, tampoco cuando hay uno solo (no se puede contar perfiles de forma
  fiable por UIA en los tres servicios). En las cuentas del autor ni Disney+
  ni HBO Max lo mostraron.
- **Inicio de sesión**: la dirección se relee a los 2,5 s en cualquier host
  del servicio (HBO Max inicia sesión en `auth.hbomax.com`):
  `disney_authentication_required`, `hbo_max_authentication_required`.
- **HBO Max sin navegador predeterminado**: no se abre en el Edge del
  producto (no tiene la sesión de la persona ni ruta propia):
  `hbo_max_needs_default_browser`, nada hecho.
- **Árbol UIA «roto» de Opera GX** (tras abrir una pestaña de Acceso Rápido,
  `LiveBackgroundView` deja un primer hijo muerto y `FindAll` desde la ventana
  devuelve 0): `PagePlay` y `Address` recorren los hijos desde el último
  (`GetLastChild` + `GetPreviousSibling`) cuando `GetFirstChild` falla, y
  `PagePlay` busca el documento con ese recorrido y hace `FindAll` desde él.
  Probado en vivo en ese estado.
- **Ruta directa, descartada**: en Disney+ el `/play/<id>` de una película es
  el mismo uuid de su ficha, pero el de una serie es el del episodio, y los
  dos ids sólo se ven en la página. La API GraphQL de JustWatch da fichas sin
  sesión, pero no es oficial, manda el título a un tercero y la búsqueda del
  propio servicio ya acierta en 3–5 s; no se añade.
- **Mente**: «en HBO Max», «en HBOMax», «en HBO» → `hbo_max` (lectores de
  `semantic/media.py`, `semantic/arguments.py`, `streaming_service_named`, los
  alias del planificador y el catálogo llano del decisor). «Max» a secas
  **no**: «pon el brillo en max» sería un título en HBO Max.
  `streaming.navigate` acepta direcciones de `hbomax.com`/`max.com`.

**En vivo, Opera GX del autor, 2026-10-06** (App por `run_baxy_conductor.ps1`,
perfil nuevo por turno, sonido silenciado y restaurado, cada video pausado
por SMTC al acabar; turno = de la frase al final publicado):

| Turno | Resultado | Respuesta | Tiempo |
|---|---|---|---|
| «pon Bluey en Disney Plus» | verificado, sesión «Bluey \| Disney+» `Playing` | «No, Bluey ya está reproduciéndose en Disney+ en este momento.» (perfil con un turno anterior incierto) | 20 s |
| «pon Daredevil en Disney» | verificado, «Daredevil \| Disney+» (la serie de 2015, «CONTINUAR») | «Puse a reproducir en streaming «Daredevil»: se está reproduciendo.» | 22 s |
| «quiero ver Coco en Disney+» | verificado, «Coco \| Disney+» («VER AHORA») | «Ya estás reproduciendo Coco en Disney+ en tu navegador Opera GX.» | 21 s |
| «pon The Last of Us en HBO Max» | verificado, «The Last of Us» | «Ya está reproduciendo The Last of Us en HBO Max.» | 24 s |
| «ponme la película Superman en HBO» | verificado, «Superman» («Reanudar Superman…») | «Se ha iniciado la reproducción de la película "Superman" en HBO Max.» | 28 s |
| «pon Zorblax Quintavera en HBO Max» | incierto, nada suena | «No se pudo confirmar que Zorblax Quintavera esté reproduciéndose en HBO Max porque la página se abrió en tu navegador con tu sesión iniciada, pero no se verificó que el título comenzara a sonar.» | 41 s |

Cada turno deja su pestaña abierta en el Opera de la persona (no se cierran
pestañas por ella).

### Qué se pierde en el navegador de la persona (y sigue en CDP)

- **2026-10-06 (autor: «todo lo que sea abrir un navegador… con el navegador
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
- `browser.control` actúa en el navegador de la persona (sección
  «Pestañas», abajo); nunca en un Edge que la persona no mira.
- La verificación por DOM (`video.currentTime` avanzando, recarga de un
  reproductor atascado) pasa a SMTC: prueba que algo suena con ese título, no
  el segundo exacto.
- «¿Quién está viendo?» (Netflix, Disney+, HBO Max): no se elige perfil por
  la persona; la página queda abierta y se dice (ver «Streaming en la sesión
  de la persona»).
- `browser.navigate.named` a la **misma familia** que el predeterminado (p. ej.
  «ábrelo en Opera GX») abre en la sesión de la persona; a otra familia sigue
  con el perfil privado de ese navegador.

### Pestañas (`browser.control` y `browser.tabs.list`, 2026-10-06)

El autor: «lo de mover pestañas y conteo de pestañas… que el Baxi no se limite».
Cada paso va a la ventana de delante del navegador predeterminado (la primera
en orden Z), sin teclado, sin menú y sin el toque de Alt —por mensaje de
ventana cuando el navegador lo atiende, si no por un patrón de UI Automation
(que puede traer el navegador al frente)—, y se verifica
**leyendo otra vez el marco** con UI Automation (guion `Frame`: pestañas con
su título, si está seleccionada y su centro como fracción de la ventana; botón
atrás habilitado o no; campo de dirección; el documento `RootWebArea` de la
pestaña activa con su `RuntimeId` y su desplazamiento). Lo que no se ve cambiar
queda **incierto** (`user_browser_tab_step_unconfirmed`, efecto posible).

| Acción | Cómo | Prueba de que ocurrió |
|---|---|---|
| `back` | `WM_APPCOMMAND` `BROWSER_BACKWARD` (1) | otro documento o dirección; con el botón atrás deshabilitado: `user_browser_history_start`, nada enviado |
| `reload` | `WM_APPCOMMAND` `BROWSER_REFRESH` (3) | `RuntimeId` del documento nuevo (medido: cambia al recargar, no entre lecturas) |
| `new_tab` | Chromium: `WM_COMMAND IDC_NEW_TAB` (34014); Firefox: `APPCOMMAND_NEW`; Opera: `Invoke` del botón de la tira (`GxAddTabButton`; Chrome `NewTabButton`) | una pestaña más |
| `close` | Chromium: `WM_COMMAND IDC_CLOSE_TAB` (34015); Firefox: `APPCOMMAND_CLOSE`; Opera: clic central publicado (`WM_MBUTTONDOWN/UP`) en el centro de la pestaña activa, sólo si sigue siendo la misma y está en pantalla | una pestaña menos (`closedTab`, `activeTab`) |
| `scroll_down`/`scroll_up` | `ScrollPattern` del documento (si no desplaza, su primer elemento que desplace en vertical), una pantalla (`LargeIncrement`) | el porcentaje leído después; en el borde: `user_browser_scroll_boundary`, nada movido |
| `fullscreen_video` | `Invoke` del botón de la página cuyo nombre empieza por «Pantalla completa»/«Full screen» (Blink lo toma como gesto de la persona) | la ventana cubre su monitor |
| `close_all` | con confirmación (`RiskPolicy` por el argumento): `close` de la pestaña activa una a una hasta dejar una (≤ 50, ≤ 40 s) | el marco releído tras cada cierre: una menos; `closedTabs`, `tabCount`, `activeTab`; parado a medias: `closedTabs` hasta ahí y efecto posible |

- **La última pestaña se conserva** (`user_browser_last_tab_kept`): cerrarla
  cierra la ventana de la persona.
- **`close_all`** (Fase 4, 2026-10-06): cierra la sesión entera de la persona,
  así que `RiskPolicy.LosesTheSession` lo confirma en modo normal, ligado a la
  invocación exacta (el argumento está en la huella). La última pestaña se
  conserva siempre.
- **Ir a una pestaña por su nombre** («ve a la pestaña de YouTube»): no es una
  operación nueva sino una misión del motor de computer use con aplicación
  «navegador» (la ventana delantera del navegador predeterminado): clic en la
  `TabItem` cuyo título contiene el nombre, verificado por la pestaña
  seleccionada (`documentacion/computer-use/CONTRATO_VISTA_ACCION.md` §6).
- **Conteo** (`browser.tabs.list`): la mente recibe `tabCount`, los títulos en
  orden, `activeTab` y `tabsPerSite` (cuántas pestañas comparten el sitio que
  el título nombra tras su último « - », « | » o « • », sin aislantes bidi ni
  espacios duros), contados por el código; una
  guarda (`_tab_listing_fact_defect`) rechaza un número que la lectura no dio
  («tres videos de YouTube» con dos), y si todo borrador cae se dicen la cuenta
  y los títulos leídos. Lo que lee CDP (Edge del producto) no cambia.
- **En la mente**, los lectores de `semantic/web.py` dan la acción sin pasar
  por el modelo: `browser_close_tab_arguments` («cierra esta pestaña»; «cierra
  la pestaña de YouTube» sigue siendo un límite) y `browser_page_step_arguments`
  («vuelve atrás», «recarga la página», «baja/sube la página», «pon el video en
  pantalla completa»). «Baja un poco» a secas sigue siendo la pregunta del
  volumen y «scroll down a bit» sin página, la rueda del puntero
  (`input.pointer.control`).

Lo específico de **Opera GX** (medido 2026-10-06 sobre el Opera de la
persona, sólo con pestañas abiertas por la prueba):
- Atiende `WM_APPCOMMAND` atrás/adelante/recargar, pero **no** `WM_COMMAND`
  ni `WM_SYSCOMMAND` con `IDC_*` ni `APPCOMMAND_NEW/CLOSE` (no usa el
  `BrowserView` de Chrome). Por eso la pestaña nueva es el botón y el cierre,
  el clic central; no se espera un mensaje que no llegará.
- Ids de vista de Chromium como `AutomationId`: atrás `view_1001`, adelante
  `view_1002`, recargar `view_1003` (el botón atrás de Opera sólo ofrece
  `ExpandCollapsePattern`; su estado habilitado sí sirve).
- **El árbol «roto» lo causa el Acceso Rápido** (la página de pestaña nueva
  con fondo vivo), no el toque de Alt: desde que se muestra, el primer hijo de
  `LiveBackgroundView` está muerto (`GetFirstChild` y `FindAll` desde la raíz
  fallan; `FindAll` da 0) aunque se cierre esa pestaña. El último hijo
  (`WindowDecoratorGx`) contiene la tira de pestañas, la barra y la página: los
  guiones `Address`, `Frame`, `Act` y `PageText` recorren los hijos desde el
  final cuando el recorrido hacia delante falla, y la lectura vuelve sin tocar
  el navegador. `PagePlay` (streaming) busca con `FindAll` desde la raíz y no
  tiene ese arreglo.
- Ese hijo muerto deja el marco leído a medias para siempre (E3, objetivo
  proveedores): `Frame` dice aparte el marco entero (`complete`) y la tira
  (`tabsComplete`, el nodo común más cercano de las pestañas recorrido de
  nuevo solo), y las pestañas se cuentan con la tira entera. Atrás/recargar
  en un marco a medias sólo se ven por el documento cuyo nombre empieza el
  título de la ventana (`page.matched`), nunca por la dirección, y el recibo
  lleva `frameComplete: false`. La ventana leída es la primera (de tres) cuyo
  marco tiene pestañas, no la ventanita del vídeo emergente de YouTube;
  `ListWindows` deja fuera ventanas con autor, de herramienta o encubiertas.
  `PageText` toma el documento nombrado como el título (hasta tres miradas en
  unos dos segundos) y la lectura se repite una vez.
- Las pestañas en «islas» (`TabGroupViewGx`) también son `TabItem` y cuentan.

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
- `src/baxy_mind/compose_situation.py` — hechos de causa para los códigos nuevos
  (`user_browser_*`, `hbo_max_*`); `data/operation_floor.v1.json`, las
  frases de suelo de `hbo_max_authentication_required` y
  `user_browser_streaming_profile_choice`.
- `.../UserBrowserTabs.cs` — `browser.control` en el navegador de la persona
  (mensajes de ventana, guiones `Frame`/`Act`, verificación por relectura);
  `UserBrowserPlatform.cs` publica `WM_APPCOMMAND`/`WM_COMMAND`, el clic
  central y mira si la ventana cubre su monitor. En la mente,
  `_project_tab_listing`, `_tab_listing_fact_defect` y `_tab_listing_final`
  (`listing_facts.py`) y los hechos de causa de los códigos de pestaña (`compose_situation.py`).

## Verificación

- `tests/Baxy.Providers.Windows.Tests/UserBrowserTests.cs` (37, con
  plataforma falsa): detección por `ProgId`, apertura y lectura del sitio,
  dirección de otro sitio nunca reportada, incierto sin lectura, respaldo
  Edge (fallo de lanzamiento, sin predeterminado, `BAXY_BROWSER=product`,
  `BAXY_CDP_ENDPOINT`), YouTube por SMTC, pulsar `Play` sólo en la sesión del
  título, no tocar la sesión en pausa de la persona, operaciones de pestaña
  honestas, Netflix y Disney+ (búsqueda escrita), inicio de sesión pedido,
  `streaming.navigate`, navegación nombrada a la familia predeterminada; y
  desde 2026-10-06 HBO Max (búsqueda en la dirección, sesión del título),
  inicio de sesión en `auth.hbomax.com`, HBO Max nunca en el Edge del
  producto, «¿Quién está viendo?» dejado a la persona y un título que la
  persona tenía en pausa no tomado por el pedido.
- `tests/test_m122_user_browser_facts.py`: hechos de causa.
- `tests/test_nav_hbo_max_service.py`: lectores de HBO Max en la mente.
- `tests/test_m122_user_browser_facts.py`: hechos de causa; conteo de
  pestañas (proyección, guarda «tres videos de YouTube», final de suelo,
  títulos de HBO Max), lectores de «cierra esta pestaña», «vuelve atrás»,
  «recarga la página», «baja/sube la página», «pon el video en pantalla
  completa», y que cada frase de suelo de pestañas pasa el juez de respuestas.
- `UserBrowserTests` (pestañas, plataforma falsa): atrás por `WM_APPCOMMAND`
  verificado por otro documento; sin historial no se envía nada; recarga por
  documento nuevo e incierta sin él; Opera pulsa su botón y Chrome recibe
  `IDC_NEW_TAB`; cierre por clic central en el sitio de la pestaña activa
  (Opera) o `IDC_CLOSE_TAB` (Chrome); una pestaña que cambió no se pulsa; la
  última se conserva; `close_all` cierra una a una y deja una; desplazamiento leído de
  vuelta y borde; pantalla completa por la ventana que cubre el monitor;
  lectura del marco con una sola pestaña (`ConvertTo-Json`).
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
- **Pestañas en el Opera GX de la persona, 2026-10-06 18:30–19:10**, App real
  (`run_baxy_conductor.ps1`, mente del worktree), Opera abierto por la persona
  con 15–16 pestañas; sólo se cerraron pestañas abiertas por la prueba
  (comprobado antes de cada cierre por el título de la pestaña activa):
  - «cuántas pestañas tengo abiertas» → «Tienes 15 pestañas abiertas en Opera
    GX, de las cuales 7 son de Disney+…» (contado aparte: 15 y 7, correcto).
  - «baja un poco la página» → «He bajado la página.» (iana.org: 0 → 100 %);
    «sube la página» → «He subido la página.» (100 → 0 %).
  - «recarga la página» → recargada (el `RuntimeId` del documento cambió).
  - «vuelve atrás» → volvió de iana.org a example.com; en una pestaña recién
    abierta: «No se pudo volver atrás porque la pestaña del navegador no tiene
    una página anterior…» (botón atrás deshabilitado, nada enviado).
  - «abre una pestaña nueva» → «Abrí una pestaña nueva en el navegador.»
    (16 → 17, Acceso Rápido delante); también tras «cuántas pestañas…» en la
    misma conversación.
  - «cierra esta pestaña» (tres veces, sobre pestañas de la prueba) → «He
    cerrado la pestaña de Acceso Rápido…» (17 → 16), «…de Example Domain…».
  - «cierra todas las pestañas» → «No pude cerrarlas todas: eso cerraría tu
    navegador entero con todas tus páginas. Puedo cerrar la pestaña que tienes
    delante.» (nada cerrado).
  - «pon el video en pantalla completa» (YouTube propio, sonido del sistema
    silenciado y restaurado a 60 %) → la ventana pasó de `-9,-9,1929,1029` a
    `0,0,1920,1080`, verificado. Se salió con Esc y se cerró la pestaña.
  - Opera estuvo en primer plano durante toda la prueba (el conductor no tiene
    ventana): que los mensajes no roben el primer plano está medido por la
    investigación en Chrome/Edge, no aquí; que las acciones UIA (botón de
    pestaña nueva, `ScrollPattern`, botón de pantalla completa) traigan Opera
    al frente, sin medir.

## Pendiente

- Netflix en Opera: sin sesión en este PC; sus nombres accesibles siguen
  tomados de lo medido por CDP en VIDEO1919, no comprobados por UIA.
- «¿Quién está viendo?»: no comprobado en vivo (las cuentas del autor no lo
  muestran); el guion lo reconoce por el texto de la pregunta.
- Un título que el servicio escribe distinto de como se pidió («house of the
  dragon» frente a «La Casa del Dragón») no se elige: queda incierto con la
  búsqueda abierta. El decisor entrenado no vio HBO Max al entrenarse; lo
  reciben los lectores y la línea de su catálogo.
- Pestañas: ir a una pestaña por su nombre y `close_all` con confirmación
  quedaron hechos en la Fase 4 (motor de computer use). El primer
  plano tras una acción UIA (botón de pestaña nueva en Opera, `ScrollPattern`,
  botón de pantalla completa) no está medido en Opera: la investigación lo vio
  traer Chrome/Edge al frente.
- Instrumentos de medición que dependían de Edge: deben exportar
  `BAXY_BROWSER=product` (o su `BAXY_CDP_ENDPOINT`) para conservar el
  aislamiento.
