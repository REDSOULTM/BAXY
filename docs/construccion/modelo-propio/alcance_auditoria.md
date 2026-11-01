# Alcance fijo de la ronda final de auditoría (decisión 21 del autor, 2026-10-16)

Escrito el 2026-10-16 a las ~23:45 sobre c7699f276. Este documento es una lista cerrada y no se amplía después. Lo que
un auditor encuentre fuera de este alcance se anota, pero no cuenta para cerrar la ronda.

## Qué cuenta como ronda limpia

- 4 focos en el PC y 4 en el notebook, con estos focos fijos: mente y catálogo; App e interfaz; proveedores; bancos y
  honestidad.
- Ninguna violación de gravedad A dentro del alcance.
- Cada informe separa A y B. Los auditores clasifican y la sesión principal verifica la clase.

### Gravedad

- **A**: se arregla siempre, en la misma ronda.
  - Una ruta de uso normal que da por hecho algo no verificado.
  - Una doble pulsación, o un efecto en la ventana de la persona sin que lo haya pedido.
  - Una ayuda al modelo en código (regla 1).
  - Una descripción del catálogo que promete lo que el código no hace.
  - Recursos por encima de 4 GB.
  - Una cifra falsa en los informes.
- **B**: marginal, sólo bajo condiciones raras (un marco negro, un fallo de COM, una pantalla de PIN).
  - Se arregla si cuesta menos de 15 minutos y no cambia la conducta en rutas normales.
  - Si no, va a `metas.json` como tarea `pendiente`, con fecha, archivo:línea y escenario.

## a) Todo lo cambiado desde el congelado

`git diff ff863b47f..HEAD`, donde HEAD es el commit que audita cada ronda. Incluye código, catálogo, descripciones,
scripts de bancos e informes.

Sobre c7699f276 ese diff son 83 archivos (+1877 −435):

| Archivos | Carpeta |
|---:|---|
| 27 | `src/Baxy.Providers.Windows/External` |
| 15 | `tests/Baxy.Providers.Windows.Tests` |
| 7 | `src/Baxy.Core/Operations` |
| 7 | `src/Baxy.App` |
| 3 | `artifacts/renew` |
| 2 | `src/Baxy.Kernel/Operations` |
| 2 | `scripts/renew` |
| 1 | `tests/Baxy.Kernel.Tests` |
| 1 | `src/baxy_mind/data` (las descripciones) |
| — | El resto: `Providers.Windows/{Windows,Tasks,SystemStatus,Notes,Filesystem,Network,Capture,Applications}` y `Baxy.FieldUi` |

## b) Las rutas que ejercitan los bancos

Son las operaciones que aparecen en los campos de operación de los resultados de los bancos y el código que las sirve:
su `Descriptor` en `ProductCatalog.cs`, su descripción en `tool_descriptions.en.v1.json`, su handler en `Baxy.Core`, su
adaptador en `Baxy.Providers.Windows` y su proyección hacia el modelo.

Bancos de los que salen:

- `renew_v3/runs`: decisión, escenas, latido y e2e;
- `renew_v1`: práctica y brazos de la decisión 20.

Ningún `sealed.json` se abrió para sacar la lista. Son 144 de las 172 operaciones (143 en la primera versión; la ronda
final 20 encontró `memory.correct` en las escenas de práctica de la decisión 20, P035, y la pasó a esta lista):

app.close, app.installed, app.open, audio.app.volume.adjust, audio.app.volume.set, audio.microphone.mute, audio.mute,
audio.status, audio.volume, audio.volume.adjust, backup.known.create, backup.known.list, backup.known.restore.latest,
backup.list, bluetooth.device.list, bluetooth.device.pair, bluetooth.radio.set, bluetooth.radio.status, browser.control,
browser.navigate, browser.navigate.named, browser.page.read, browser.tabs.list, calculator.expression.evaluate,
calendar.event.create, calendar.event.list, capture.active.window, capture.screenshot, client.channel.locate,
clipboard.copy, clipboard.paste, clipboard.read.text, clipboard.write.text, desktop.wallpaper.set, display.status,
document.presentation.create, email.latest.read, email.latest.reply, email.send, file.compress, file.edit, file.find,
file.open, file.read, file.write, filesystem.create.directory, filesystem.explorer.count, filesystem.file.open.latest,
filesystem.folder.open, filesystem.known.duplicates, filesystem.known.trash.named, filesystem.list,
filesystem.sandbox.diff.named, filesystem.sandbox.move.named, filesystem.search, game.catalog.list,
game.entitlement.named, game.install.cancel.active, game.install.named, game.install.status, game.installed.named,
game.launch, game.uninstall.named, input.key.press, input.keyboard.layout, input.keyboard.open, input.pointer.control,
input.select.all, input.text.type, input.visible.click, input.visible.controls, media.control, media.play.exact,
media.play.query, media.play.youtube, media.seek.relative, media.status, memory.correct, memory.disable, memory.enable, memory.export,
memory.forget, memory.list, memory.recall, memory.save, memory.sensitive.save, memory.session.clear, memory.status,
message.draft, message.send.test, network.dns.status, network.ip.list, network.port.list, network.status, note.create,
note.list, note.read, note.search, note.trash, note.update, ocr.read, office.document.create, package.uninstall,
peripheral.list, schedule.alarms, shell.command.run, software.python.package.status, software.python.status,
storage.removable.list, streaming.play.named, system.application.crash.diagnose, system.power, system.process.list,
system.process.terminate.named, system.recyclebin.empty, system.settings.adjust, system.settings.set,
system.settings.status, system.status, system.time, task.complete, task.create, task.delete, task.list, task.search,
vision.describe, weather.current, web.download, web.fetch, web.search, wifi.connect.named, wifi.disconnect,
wifi.profile.list, wifi.radio.set, wifi.scan, window.active, window.application.status, window.close.all, window.focus,
window.maximize, window.minimize, window.minimize.all, window.resolve, window.snap.

Las 28 que no ejercitan los bancos de decisión, e2e, escenas y latido quedan **fuera** del alcance, salvo lo que de
ellas entre por a) o c). El banco de falsedades del v3 ejercita además dos de ellas: wifi.status (F303) y
package.install (F333). Corregido en la ronda final 20, que encontró falsa la frase «29 que ningún banco ejercita» y
`memory.correct` en un resultado de escenas:

backup.create, backup.known.verify.latest, backup.restore, backup.verify, filesystem.copy, filesystem.move,
filesystem.read.text, game.install.cancel, input.keyboard.status, input.scroll, network.ping,
note.restore, office.document.read, package.install, peripheral.print, peripheral.scan, streaming.navigate,
system.identity, task.reopen, task.restore, task.update, wifi.connect, wifi.ensure.connected, wifi.radio.status,
wifi.status, window.move, window.resize, window.restore.

## c) El núcleo

- **Kernel: riesgo y confirmación.** `src/Baxy.Kernel/Policy/` (RiskPolicy, WorldActs, ConfirmationMode*),
  `src/Baxy.Kernel/Mission/` (MissionEngine, InMemoryConfirmationAuthority, PrivateOperationBoundary,
  RequestFingerprint) y `src/Baxy.Kernel/Operations/OperationRisk.cs`.
- **Kernel: proyección.** `src/Baxy.Kernel/Operations/OperationVisibleFacts.cs` y `VisibleViewNumbering.cs`; en la App,
  `OperationResponseProjection.cs`, `TurnVisibleFacts.cs` y `ScreenViewProjection.cs`.
- **Journal.** `src/Baxy.Kernel/Journal/`.
- **App.** `src/Baxy.App/NativeTurnLoop.cs`, `Heartbeat.cs` y `HeartbeatMoment.cs` (el latido), y
  `PendingOperationConfirmation.cs` y `ConfirmationAsk.cs`.
- **Bucle de la mente.** `src/baxy_mind/mind.py` y `protocol.py`.

## d) W18 y W19

Se resolvieron en la ronda final 19.

- **W18: `dialectCountry` y `Namesakes` (weather.current).**
  - Antes, el significado del argumento estaba sólo en un comentario de C# que el modelo no ve.
  - Ahora llega al modelo en `arguments` de `tool_descriptions.en.v1.json`: «el país que marca el habla de la persona,
    sólo cuando es claro; sólo elige entre homónimos de tamaño comparable; el resultado dice namesakesElsewhere».
  - Decisión con su razón: `Namesakes` se queda. No interpreta a la persona: es la verificación del proveedor sobre la
    respuesta del geocodificador. Entre homónimos comparables no elige y los devuelve como candidatos, y el argumento
    lo pone el modelo.
- **W19: ipwho.is (weather.current sin location, web.search con nearby).**
  - La descripción de weather.current dice ahora que, sin location, «aquí» es la ciudad aproximada del PC según un
    servicio público y su dirección de internet, y que el resultado lo dice en `locatedBy`.
  - La descripción de web.search ya decía que nearby añade la ciudad y el país del PC, y que es sólo para lo que la
    persona pide cerca de ella.
  - Decisión con su razón: se queda, por dos motivos. Lo que sale del PC es sólo la consulta vacía a ipwho.is (por
    https), y después la ciudad que ese servicio dedujo, y sólo ante un pedido de «aquí» o «cerca».
