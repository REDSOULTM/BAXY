# Handoff — Goal 10 — 2026-08-24 — `2e69a34`

## Objetivo
BAXY se usa en una dosis real concentrada, no miente, se queda encendido barato, y
eso queda en `origin/main`.

## Lo que cambió respecto al handoff anterior

**El bloqueo de arranque está resuelto. BAXY arranca, el core se queda vivo, el
input acepta texto y hay turnos reales.** Todo lo demás del goal sigue abierto.

### Cadena de diagnóstico (no re-derivar)

1. `startup.ready` aparecía **aunque el arranque hubiera fallado**: la hipótesis
   del handoff anterior («si el handshake falla, sale `startup.failed`») era
   falsa. `MainWindowViewModel.InitializeAsync` captura la excepción y llama a
   `HandleStartupFailureAsync`, así que `MainWindow.OnLoaded` ve un `await shell`
   que completa bien y emite `startup.shell.ready` + `startup.ready`.
2. Ese `catch` era **el único sitio donde moría la causa**. Ahora la escribe en
   `%LOCALAPPDATA%\BAXY\presence\last-startup-failure.txt`. Sin eso no hay
   diagnóstico posible: la ventana sólo ofrece «reintentar».
3. Con la causa a la vista: `DurableRetryStore.Load()` lanzaba
   `InvalidDataException` leyendo `shell\retry-outbox.v1.json`. **Y «reintentar»
   vuelve a leer el mismo archivo: fallaba igual, para siempre.** Arreglado con
   cuarentena (`.unreadable-<ts>`), no borrado —puede contener operaciones cuyo
   efecto quizá ocurrió— y BAXY lo dice al arrancar
   (`TurnVisibleFacts.Failure("durable_retry_unreadable")`).
4. El core también moría antes, con `JsonException` enmascarada. `Program.cs`
   ahora deja el detalle en `<dataRoot>\diagnostics\last-core-fault.txt`.

### Datos de desarrollo incompatibles (decisión tomada)

Dos archivos del data root `dev-mente-v2` estaban escritos en **formatos que este
árbol no produce ni produjo nunca** (`git log -S` no los encuentra):

- `journal\missions.jsonl` — cada registro `completed` guardaba la respuesta como
  `{"type":"baxy.journal.protected-response.v1"}`, un sobre cifrado. El lector
  actual valida `operation.response` en claro → `JsonException` → core exit 70.
- `shell\retry-outbox.v1.json` — 70 bytes que empiezan por `BAXYPAY1`, el sobre de
  `WindowsProtectedPayload`. El `DurableRetryStore` actual es texto plano por
  diseño (lo dice su propio comentario de cabecera).

**Decisión:** no se escribe migración para un formato que este árbol no produce
(ley 2). El journal se archivó a mano en
`%LOCALAPPDATA%\BAXY\dev-mente-v2\journal-incompatible-2026-08-24\` (con su
`journal-hmac.v2.key`); el outbox lo aparta ya el código. **No se tocó el
fail-closed del journal**: un journal ilegible sigue impidiendo arrancar el core,
y eso es la evidencia de manipulación, no un bug.

### Verificado en producto vivo (`2e69a34`, Release)

- `baxy-core.exe` **se queda vivo** (poll `Win32_Process` cada 200 ms, 30 s).
- Primer turno real del arranque: `core.call.start` detail `memory.status` →
  `core.call.end` en **332 ms**.
- UIA: `ControlType.Edit` name `message input` **`enabled=True`, `offscreen=False`**,
  árbol de 18 nodos. `scripts\goal10_dose_turns.ps1` lo encuentra y escribe en él.
- Turno «qué hora es» por UIA: aceptado, `submit.received` →
  `response.final` en **1,06 s**, con `visible.text`.

## Bloqueo vivo al cortar — LA MENTE NO SUBE

Es lo siguiente que hay que resolver, y bloquea la dosis entera.

`startup.shell.ready` llega a **14,7 s**: agota el `mindDeadline` de 12 s de
`InitializeAsync` y sigue sin mente. Consecuencia observada en la ventana (UIA,
sesión 00:40–00:41, turnos reales del dueño y uno mío):

| Pedido | Respondió | Veredicto |
|---|---|---|
| `Hola` | «Hola.» | pasa |
| `Quien eres` | «¿Qué tal?» | **no responde a lo pedido** |
| `aBRE STEAM` | «No pude: no pude encontrarlo.» | **falso**: goal 07 dejó Steam verificado |
| `qué hora es` | «¿Qué hora es?» | **eco de la pregunta** — plantilla, invariante 5 |
| (welcome) | «No pude: la composición se perdió y se verificaron hechos.» | plantilla |

El trace del turno confirma el mecanismo: `submit.received` → `queue.wait.end` →
`visible.indication understanding` → **`compose.start` detail `status`** →
`compose.end` → `visible.text`. **No hay `decision.start` ni `core.call.start`.**
Sin decisor, el compositor devuelve el evento de estado tal cual.

Esto no es «la mente tarda»: son **respuestas de plantilla y una afirmación falsa**,
que el goal define como defecto grave, no como anécdota.

Lo que **ya está descartado**: el manifiesto
`%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json` es correcto y **las seis rutas
existen** (python, gguf en `D:`, llama-server en `Programacion\BAXY\legacy\...`,
stt, wake, tts). No es un path roto.

**Siguiente medición, exacta:** `MainWindowViewModel.InitializeMindAsync`
(línea ~1696) fija `_mindStartupState` a `Failed` / `NotConfigured` en cinco sitios
distintos y **ninguno deja traza**. Es el mismo patrón que acaba de costar esta
sesión entera. Instrumentar ahí primero —una línea a
`CoreProcessClient.RecordPresenceFault("last-mind-failure.txt", …)`— y volver a
lanzar. La causa sale en una corrida.

## Sin empezar
Launch ×2 verificado, sampler idle 24 h, 200 turnos / 5×20, modos + narración +
panel de memoria + `web.search` en el producto vivo, reboot de Windows, idle final,
costuras, APLAZADOS de uso, compuerta Full.

## Commits en `origin/main`
1. `77537bf` — bandeja, `HKCU\...\Run\BAXY` → `"Baxy.exe" --tray`, X oculta, 2ª
   instancia muestra la 1ª, panel de memoria real.
2. `e787281` — `IsInputEnabled => IsReady && !_turnExecutionActive`.
3. `5b65951` — el WS `AgentEvent.ready` también sigue a `IsInputEnabled`.
4. `2dd5574` — `last-crash.txt` y `last-core-exit.txt`.
5. `2e69a34` — **esta sesión**: causa del arranque fallido escrita; cuarentena del
   outbox ilegible; `last-core-fault.txt` en el core.

## Decisiones — no reabrir sin dato nuevo
- WinForms `NotifyIcon` con `UseWindowsForms=true` **y**
  `<Using Remove="System.Drawing"/>`; si no, CS0104 en todo WPF.
- Panel de memoria: el `window.confirm` del Field **es** la confirmación de esa
  invocación. Enable va por `memory.configure`. Edit del mismo `key` =
  `memory.correct`; alta = `memory.save` kind `preference`.
- El fail-closed del journal **no se toca**.
- No se escribe migración de formatos que este árbol no produce.
- `Process.Exited` se levanta una sola vez y el core puede morir antes de que el
  manejador quede suscrito: por eso el fallo se registra también desde el `catch`
  de `CoreProcessClient.StartAsync`, no sólo desde `OnProcessExited`.

## Cómo se lanza y se mide (ya escrito, ya probado)
- Sonda de arranque + poll de procesos:
  `{SCRATCH}\goal10\launch_probe.ps1 -Seconds N -Tag X`. Mata lo vivo, borra las
  trazas previas, fija `BAXY_DATA_DIR`/`BAXY_APP_TRACE`/`BAXY_ASSET_DESCRIPTOR`,
  lanza `Baxy.exe` Release directo y vuelca trace + presencia.
- Volcado UIA: `{SCRATCH}\goal10\uia_dump.ps1` (edits con `enabled`/`offscreen` y
  los textos de la conversación — **así se lee lo que BAXY respondió**).
- Dosis: `scripts\goal10_dose_turns.ps1 -TracePath … -JournalPath … -OutputPath …
  -SessionId … -Turns @(…)`. Funciona.
- Sampler idle: `scripts\goal10_idle_sampler.py --output artifacts/goal10/soak.json
  --interval 60`. **Aún no se arrancó.**
- Compilar con BAXY vivo falla (`MSB3027`, `Baxy.exe` bloqueado): matar primero.
- PowerShell: `git commit -m @'…'@` **no funciona** aquí; usa `git commit -F` con
  el mensaje en un fichero.

## No hacer
No bajar umbral FAR. No skip/xfail. No soak sintético. No corpus como dosis. No
tocar el repo `BAXY` a secas. No inventar un HTTP extra para dosificar: el producto
se dosifica por UIA. No matar un BAXY vivo para inspeccionarlo si estás midiendo.
