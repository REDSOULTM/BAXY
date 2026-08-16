# Evidencia mínima — recuperación de tools

## Baseline

- Rama/commit: `codex/baxy-rebuild-v3` / `c5a12952f7960163766f19d09651f6153a69ba13`.
- Cambios preexistentes: ninguno (`git status --short --branch`).
- .NET: 1.787/1.787 verdes (46 Contracts, 75 Kernel, 241 Providers, 953 Integration, 472 Setup). Tres gates físicos omitidos por contrato de entorno.
- Python vigente: 118 pruebas + 176 subtests verdes.
- `pytest` sin scope falla en colección por el archivo archivado `legacy/legacy_export/vision_input/test_videos.py` y la dependencia histórica ausente `gemma4_agent`; el fallo existía antes de los cambios. La suite vigente es `python -m pytest tests -q`.
- `hello`: 22 operaciones/21 tools públicas; `app.status` interna.
- Gates por entorno ya declarados: instalación/purga en perfil limpio, `app.open` sin procesos preexistentes y probes físicos dependientes de hardware/cuentas.

## Arqueología ejecutable

- Snapshot v2: 94 contratos registrados; 91 autorizados y 3 en cuarentena.
- Comando de regresión histórica acotada: 529/529 verdes en 31,42 s. Incluye registro, windows control, UIA, filesystem, transferencias, tareas, recordatorios, rutinas, red, portapapeles, accesibilidad y matriz de misiones.
- Procedencia del corte ventana: `codex/tool-ecosystem-v2:tooling/providers/windows_control.py`, tests `test_tooling_windows_control_provider.py` y workflows exactos de escritorio; activo preservado también en `legacy/`.

## Corte 1 — ventanas

- Tools: `window.resolve`, `window.focus`, `window.minimize`, `window.maximize`, `window.restore`.
- Contratos: schemas cerrados; `windowId` opaco; resultados con PID/nombre/estado/foco, sin título ni ruta; riesgo read-only o low-reversible; verifier ID único.
- Seguridad: selector sin rutas; inventario acotado; handle de 5 minutos, máximo 512, un solo uso; identidad HWND+PID+creation-time; revalidación antes del efecto; verifier separado; cancelación propagada; journal/replay del core.
- Unit/contract/integration: 5 pruebas nuevas del provider; 15 pruebas del catálogo y 8 handshakes/E2E relevantes verdes.
- Gate físico read-only: core exit 0, `hello` publicó 26 tools, `window.resolve` resolvió 1 ventana BAXY y devolvió `completed`, `verified=true`, `count=1`, stderr vacío. No se ejecutó una mutación física de ventana.
- `app.close` reutiliza el mismo handle, exige confirmación por riesgo `work_loss`, envía `WM_CLOSE` (no termina el proceso por fuerza) y solo completa cuando el verifier observa ausencia; su prueba con doble quedó verde. No se cerró una ventana real en el gate.
- `network.status` recupera la primitiva read-only v2 como auxiliar de `wifi.manage`; dos pruebas con doble acreditan segunda lectura y fail-closed ante cambio.
- `system.time` recupera la primitiva read-only v2 para que calendario/recordatorios/rutinas consuman UTC y offset tipados; dos pruebas acreditan coherencia y rechazo de reloj regresivo.
- `note.update` completa el reemplazo transaccional por selección (ID+título+revisión), conserva replay de estado alcanzado y verifica por relectura. Provider unitario, contrato y E2E quedaron verdes.
- `note.search` añade búsqueda acotada por título/contenido, omite papelera por defecto y verifica cada resultado mediante relectura; unit, contrato y E2E quedaron verdes.
- `task.manage` porta las nueve primitivas del provider v2 (`legacy/tooling/providers/tasks.py`) sin su workflow: estado durable separado, due UTC como metadato, resolución exacta, CAS, borrado recuperable y postlectura. Pasaron 3 pruebas del store, 15 contractuales, handshake y un E2E real por `baxy-core`.
- `clipboard.manage` porta `legacy/tooling/providers/clipboard.py` a Win32 NativeAOT con un seam estrecho. Tres pruebas del provider, dos de handler y el catálogo acreditan snapshot doble, postlectura exacta y error fail-closed. No se tocó el portapapeles real por privacidad y pérdida de estado transitorio.
- `window.move` y `window.resize` completan el control de geometría con `MoveWindow`, la misma identidad efímera, conservación del eje no modificado y rectángulo verificado. La suite específica de ventanas quedó en 7/7.
- Catálogo después del corte: 45 operaciones/44 tools; `app.status` permanece interna.

## Corte filesystem

- Procedencia: providers v2 `filesystem.py` y `filesystem_transfer.py`, y workflow prepare/commit/restore; no se reutilizó `filesystem.write_text` en cuarentena.
- Implementación: once tools sobre un sandbox privado; IDs `fs_*` de cinco minutos, revalidación de tamaño/mtime, bloqueo de rutas absolutas, escapes y reparse points, UTF-8 acotado, CAS SHA-256, transferencia con posthash y papelera privada con handles de un uso.
- Pruebas: 5/5 del provider, 15/15 del catálogo, handshake y E2E real del core para write/list/read/copy.
- Catálogo después del corte: 56 operaciones/55 tools públicas.

## Corte recordatorios y notificaciones

- Procedencia: provider v2 `reminders.py` y servicios D33; se conservó la separación histórica entre task metadata y reminder scheduling.
- Tools: `reminder.create/list/resolve.exact/delete/restore` y `notification.list.due/dismiss`, todas con estado durable, UTC, CAS y postlectura.
- Pruebas: catálogo y handshake verdes; E2E real create→resolve→list por `baxy-core`.
- Bloqueo restante: el protocolo stdin/stdout solo responde invocaciones y no tiene canal de eventos espontáneos hacia BAXY App; por ello no se simula un toast. Gate exacto: integrar una superficie receptora, crear un recordatorio a +60 s, mantener core y shell activos, observar una única presentación y ejecutar `notification.dismiss` con la versión recibida.
- Catálogo después del corte: 63 operaciones/62 tools públicas.

## Corte rutinas

- Procedencia: `legacy/tooling/providers/routines.py`; se conservaron sus seis operaciones y su prohibición explícita de creación/ejecución desde el catálogo del modelo.
- Implementación: store durable separado, metadata de workflow/trigger, resolución exacta, CAS, enable/disable, papelera y restore siempre deshabilitado. No existe runner ni llamada oculta a otras tools.
- Pruebas: lifecycle completo con seed confiable y catálogo/handshake verdes.
- Catálogo después del corte: 69 operaciones/68 tools públicas.

## Corte captura, backup y app.open

- `capture.screenshot`: GDI sobre escritorio virtual, BMP privado escrito atómicamente, `captureId`, dimensiones y SHA-256; prueba con frame falso y handler sin rutas.
- `backup.create/verify/restore`: backup privado por identidad de filesystem y hash exacto; restore solo a destino libre. Provider y E2E real del core quedaron verdes.
- `app.open`: Notepad se conserva; Calculadora añade adapter `calc.exe`→`CalculatorApp`, inventario antes/después, PID+creation-time+HWND y foco independiente. El resto de targets históricos usa las primitivas especializadas Steam/media/browser/Office/messaging/settings/capture.

## Contratos bloqueados y gates físicos

Todos estos contratos están publicados, tienen schema cerrado, riesgo, seam `IExternalCapabilityProvider`, provider de producción con probe y verificador fail-closed. Tres pruebas con doble demuestran éxito solo para evidencia estructurada, coincidente y `verified=true`; producción nunca afirma éxito sin adapter.

| Familias | Tools | Bloqueo concreto | Gate de cierre exacto |
|---|---|---|---|
| media | `media.play.exact`, `media.control` | sesión Spotify/SMTC | iniciar sesión, seleccionar una sesión, invocar contra track/action de prueba y comparar now-playing antes/después |
| browser/streaming/web | `browser.navigate`, `streaming.navigate`, `web.search` | CDP, cuentas y proveedor search no configurados | inyectar adapter oficial, navegar una URL/URI de prueba y comparar URL final; search debe devolver IDs/URLs acotados |
| calendar/Office | `calendar.event.*`, `office.document.*` | cuenta y aplicaciones no autorizadas | cuenta de prueba, crear recurso marcado BAXY, reabrir por ID, verificar y eliminar manualmente el fixture |
| messaging | `message.recipient.resolve`, `message.send` | sesión y destinatario no autorizados | cuenta de prueba, resolver contacto fixture, confirmar contenido exacto, enviar una vez y comprobar receipt; nunca usar contactos reales |
| Bluetooth/WLAN/periféricos | `bluetooth.device.*`, `wifi.*`, `peripheral.*` | hardware/driver/perfiles ausentes del harness | hardware de prueba, resolver ID, aplicar una acción reversible y corroborar postlectura/job/capture |
| paquetes/juegos | `package.install.*`, `game.catalog.list`, `game.install.*`, `game.launch` | winget/Steam y propiedad no autorizados | VM limpia o cuenta fixture, prepare sin efecto, commit confirmado y comprobar job/proceso; desinstalar fixture al final |
| compra | `game.purchase.*` | dinero real prohibido | únicamente sandbox del proveedor con precio fixture; comprobar confirmationId, precio exacto y receipt sin cargo real |
| visión/OCR | `vision.describe`, `ocr.read` | VLM y language pack no configurados | captura fixture por `captureId`, adapter local/de prueba, verificar binding del hash y salida no vacía; no usar pantalla real |
| settings/power | `system.settings.set`, `system.power` | hardware y transición disruptiva | VM desechable: postlectura del ajuste; para power, intent durable antes de transición y receipt verificado al siguiente arranque |
| notificaciones | `notification.list.due`, `notification.dismiss` | shell sin canal de eventos salientes | shell receptor, reminder +60 s, observar una sola presentación y descartarla por versión CAS |

- Catálogo tras agotar el censo: 103 operaciones/102 tools públicas; las 43 familias están `cubierta-y-verificada` o bloqueadas con evidencia reproducible.

## Regresión del checkpoint

- .NET: 1.810/1.810 verdes (46 Contracts, 75 Kernel, 260 Providers, 957 Integration, 472 Setup); los mismos tres gates físicos quedaron omitidos por contrato de entorno.
- Python vigente: 120 pruebas + 176 subtests verdes en 98,18 s.
- `hello` real en perfil privado aislado: `type=hello`, 44 capabilities públicas ordenadas, desde `app.close` hasta `window.restore`; `app.status` no se publicó. Se comprobaron explícitamente `task.resolve.exact`, `clipboard.read.text` y `window.resize`.
- NativeAOT `win-x64`: publicación Release completada sin warnings ni errores; el ejecutable nativo respondió `hello` con las mismas 44 capabilities y sin publicar `app.status`.
- `git diff --check`: sin errores de whitespace; solo avisos de normalización LF→CRLF del checkout Windows.

## Validación final

- Censo congelado: 43/43 filas terminales — 22 `cubierta-y-verificada`, 9 `bloqueada-por-entorno` y 12 `bloqueada-por-dependencia-externa`; cero filas `crear`, `completar`, `adaptar` o `recuperar-y-portar`.
- .NET: 1.825/1.825 verdes (46 Contracts, 75 Kernel, 269 Providers, 963 Integration, 472 Setup). Tres gates físicos siguen omitidos por contrato: audio NativeAOT real, movimiento de instalación con ejecutable activo y DXGI/PDH físico.
- Python vigente: 120 pruebas + 176 subtests verdes; el test del censo acredita exactamente las 43 familias y la frontera sin planner.
- `hello` Debug en perfil privado aislado: 102 capabilities públicas ordenadas, `app.close`→`window.restore`; `app.status` no publicada. Se verificó presencia de captura, backup y contrato monetario gateado.
- NativeAOT Release `win-x64`: publicación completada sin warnings/errores; el ejecutable nativo emitió las mismas 102 capabilities y excluyó `app.status`.
- `git diff --check`: limpio, salvo avisos informativos LF→CRLF del checkout Windows.
- No se agregó planner, router de intención, parser conversacional, STT ni llamadas ocultas entre tools.
