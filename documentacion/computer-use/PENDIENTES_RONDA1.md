# Pendientes de la ronda 1 (computer use v3)

Notas que las ramas de la ronda 1 escribieron en `PROGRESO_V3.md`. Ese archivo es del líder: al integrar
(`fable/cu-v3-ronda1`) se dejó su versión y las notas de las ramas viven aquí, con lo que dejó abierto la integración.

## Pendiente explícito de `fable/cu-v3-pausa` (regla de pausa, punto 0 arreglo 3)

Cubiertos por el `ForegroundLease` (espera de pausa, ráfaga, restauración, `waitedMs`/`restored` en el recibo):
`DesktopKeyboard` (teclas y texto de misión, en ráfagas de 8 caracteres), `VisibleControlSurface.Click/PointAt`,
la rueda de `WindowsScrollAdapter` y los clics de OCR y visión (con relectura de la superficie dentro de la ráfaga).

**Sin envolver todavía** (mueven el cursor real o mandan teclas sin espera, sin ráfaga y sin devolver cursor ni
frente; todos llevan ya la marca): `ClickPoint` de `DesktopUiaWorker.ps1` (último recurso de la cascada UIA para
Chromium/Electron sin patrón), `FocusComposer`/`ClickAt`/`ClickAtRelative`/tecleo Unicode y teclas de
`DesktopMessagingAdapter`, `MoveCenter`/`MouseAction` y los acordes de `DesktopKeyPress.ps1`,
`SpotifyDesktopAutomation.ps1`, `SpotifyMediaControl.ps1`, `SteamLocalAdapter.SendKeyboard`, y los guiones de
calculadora y selector Ctrl+K de `WindowsDeviceControlAdapter`. Hace falta adquirir el lease en el host C#
alrededor de cada llamada (para el worker UIA, sólo cuando cae a `ClickPoint`, no en las vías por patrón).

**Sin hacer:** tragar con `WH_KEYBOARD_LL`/`WH_MOUSE_LL` el input sin marca durante una ráfaga (el detector sólo
observa: una tecla de la persona dentro de la ráfaga llega a la ventana de la misión). Las ráfagas cortas acotan
la exposición; el gancho necesita medirse en vivo junto al medidor de molestia, que también usa ganchos LL.

**Sin probar en vivo:** el envío marcado de la calculadora y del selector Ctrl+K (`BaxyMarkedKeys`, compilado en
PowerShell 5.1 pero no ejecutado contra las apps).

Tras la integración: `ClickPoint` del worker UIA ya no existe (rama clic); el puntero de OCR, visión y la ruta
`needs_pointer` del worker va dentro del lease (`ScreenPointer`). Siguen sin envolver los de `DesktopMessagingAdapter`,
`DesktopKeyPress.ps1`, Spotify, Steam y los guiones de calculadora y Ctrl+K.

## Decisiones y pendientes de la integración (`fable/cu-v3-ronda1`)

- **Clic con `window` (vista contra clic y pausa).** vista traía al frente la ventana de la misión antes de cada clic
  y de cada rueda (`FrontForActAsync`, sin pausa y sin devolverla). Se retiró: el árbol UIA pulsa la ventana detrás
  y sólo el puntero y la rueda toman el frente, dentro de una ráfaga del lease que lo devuelve. Cambia lo que el
  live_check 1 de vista esperaba: «abrí Configuración y buscá mouse» ya no deja Configuración delante tras el primer
  clic por patrón.
- **OCR y visión sobre una ventana ligada detrás:** `ForegroundTargetAsync` devuelve la ventana ligada aunque esté
  detrás y `CaptureAsync` la dibuja con PrintWindow. Falta medir en vivo cuántas ventanas devuelven negro (vista ya lo
  dejó pendiente) y que el OCR relocalice bien cuando la captura de dentro de la ráfaga (pantalla) difiere de la de
  antes (PrintWindow): visión, sin relocalización, rechaza siempre en ese caso.
- **Clic tras abrir una app:** el bucle por etiqueta con app recién abierta sigue llamando a `FrontOpenedAsync` con
  `bringToFront` (diseño de vista para actos), fuera de una pausa. Es un robo de foco en apps con árbol que queda
  por pasar a la ráfaga.
- **`target` de clic y `TextField` de texto:** las dos eligen el campo al que va un texto. Con texto fusionado,
  `target` sólo vale con la ventana delante y el foco ya puesto; queda ver en vivo si sobra.
- **Rueda:** la captura después de girar usa el delegado inyectable de pausa, no `selfDrawn` de vista; dentro de la
  ráfaga la ventana está delante y las dos capturas salen por el mismo camino salvo que aparezca una ventana
  siempre encima.
