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

## Continuación 2026-08-24 — diagnóstico de la mente en curso

- El árbol ya traía una instrumentación sin commit en
  `MainWindowViewModel.InitializeMindAsync`; se completaron los cinco estados que
  terminan en `Failed`/`NotConfigured`, incluidos cancelación de discovery y
  `Ready` sin cliente vivo.
- Corrida `trace-mind-handshake.jsonl`, Release, árbol de procesos limpio: el
  sidecar llegó a `catalog_ready` a las `00:53:57`, unos 8 s después del launch.
  Una segunda sonda dentro del caller observó `client_published` y
  `voice_status=True`. Por tanto el bloqueo anterior no es manifiesto, discovery,
  saludo ni catálogo: la mente sí se publica viva.
- Aun así, el turno UIA real `¿Quién eres?` no produjo `response.final` dentro de
  más de dos minutos y dejó la máquina sin capacidad práctica de planificar ni
  `echo`/`taskkill`. La sonda de recursos muestra que el defecto aparece al entrar
  el primer turno, no en el handshake; no cerrar ni dosificar hasta encontrar qué
  trabajo neural/encoder está monopolizando el equipo.
- Las llamadas de diagnóstico permanentes aún están sin decidir: conservar la
  causa terminal en `last-mind-failure.txt`; retirar los hitos temporales de
  `last-mind-handshake.txt` después de localizar el atasco.
- Antes de seguir, recuperar/terminar exclusivamente el árbol de la instancia
  `Baxy.exe` PID `51480` y sus hijos. Varias sesiones de consola quedaron en espera
  porque Windows no les asignó CPU; preservar los traces del directorio
  `%TEMP%\baxy-goal10` después de recuperar el equipo.
- La terminación selectiva se intentó por PowerShell, `taskkill /T /F` y un runtime
  Node independiente; ni siquiera `cmd /c echo` consiguió ejecutarse durante más de
  15 min. Se dejó emitido `shutdown.exe /r /t 5 /f` (el reboot también es parte del
  criterio de cierre), pero el comando seguía sin recibir CPU al último control. Si
  esta tarea reaparece después de un reinicio físico, el árbol/diff/handoff están en
  disco: comprobar primero `git status --short --branch` y preservar los traces antes
  de volver a lanzar BAXY.

## Continuación tras reboot — 2026-08-24 10:23

- Windows volvió a arrancar a las `10:08:00`; `Baxy.exe --tray` apareció a las
  `10:09:10` y publicó `last-mind-handshake.txt = initialize_complete` a las
  `10:10:01`. UIA mostró el input habilitado. El autostart/reboot funciona.
- En idle durante 5 s: App/Core consumieron 0 CPU; `llama-server` 0,06 s. Working
  set: App 173,3 MiB, Core 67,3 MiB, llama 2.814,5 MiB, mente Python 1.114,6 MiB,
  encoder Python 842,5 MiB y wrappers 18 MiB. Es baseline, no cierre de fuga.
- El trace preservado `trace-mind-caller.jsonl` prueba el bloqueo anterior: 2.439
  filas en 82 min, con **542 `compose.start` + 542 `compose.end`** y 1.320
  `visible.indication`; 2.404 filas pertenecen al welcome/recovery `t0` y la
  mayoría son intentos `confirmation` cada ~8 s. El data root de desarrollo sí
  contiene `shell/planner-state.v1.bin`; el root normal no. La cola
  `PendingModelMessageQueue` reintenta sin límite cualquier confirmación que el
  compositor nunca acepta. Ésta es una causa demostrada de saturación, no una
  hipótesis de encoder.
- En el root normal sin recovery pendiente, el turno UIA real `¿Quién eres?`
  terminó visualmente en **3,956 s** y respondió exactamente «Soy BAXY, un
  compañero que vive en el PC.»: el decisor sí funciona y ya no hubo eco ni
  plantilla visible.
- Inmediatamente después de `response.final`, Windows volvió a quedar sin
  planificación durante al menos 6 min: ni `cmd /c echo`, `git diff` ni
  `taskkill /PID 24952 /T /F` avanzaron. Esto separa un segundo defecto vivo en
  la fase posterior a la respuesta visible (narración/TTS o reanudación de wake).
  El watchdog inicial se desactivó al ver texto, por lo que no cubrió esta fase.
  Tras recuperar/reiniciar, instrumentar voz post-turn y usar un watchdog que
  exija también idle estable después de `response.final`.

## Continuación — corrección de saturación ya integrada en `origin/main`

- La línea histórica relevante ya describía el mismo mecanismo: sesiones ONNX
  sin `SessionOptions` podían ocupar los 24 hilos y mantenerlos en *spin* tras
  la primera inferencia (`biblioteca/gemma4-agent/documentacion/03_voz_stt/research/plan_sherpa_parakeet_cpu_optimizacion.md:59-80,137-138`).
- Los commits de recursos que ya están en `origin/main` corrigieron los dos
  defectos demostrados por Goal 10: Piper/ONNX usa hilos acotados y no-spinning;
  la mente corre con prioridad/afinidad dura; y `PendingModelMessageQueue`
  terminaliza una composición fallida tras tres intentos en vez de reintentarla
  para siempre.
- La corrida física R6 del árbol vigente midió 60 muestras post-inferencia sin
  degradación: CPU BAXY promedio **0,73 %**, máximo **2,03 %**, RSS promedio
  **5.052,1 MiB**, GPU máximo **2 %**; el guardián terminó `completed`, sin matar
  procesos. Evidencia exacta en
  `artifacts/resource_optimization/physical_run_r6.json{,l}` y resumen en
  `artifacts/resource_optimization/HANDOFF.md`.
- La instrumentación temporal `last-mind-handshake.txt` ya cumplió su propósito
  y se retiró. Se conserva `last-mind-failure.txt` en todos los estados
  terminales `Failed`/`NotConfigured`, que es la traza operativa permanente.
- Validación dueña de esa frontera: los dos casos focales de
  `MindRuntimeDiscoveryTests` (cancelación fail-closed y orden discovery→factory)
  pasaron **2/2** en Release. Un filtro amplio de 36 tests dejó **29 pass / 7
  fail** de baseline: seis lecturas de trace chocan con el writer vivo y una
  prueba exige prosa fija frente al contrato estructurado vigente. No están
  atribuidos a esta instrumentación y siguen siendo rojos a reparar antes del
  Full final.

## Continuación — wake permanente sin dos CPUs en *spin*

- La corrida `aa82f95-live` aisló otra fuga que R6 no había ejercido con wake
  permanente: el Python de mente consumía **197,2 % de un core** mientras la UI
  mostraba `microphone always listening`; apagar el micrófono desde la propia UI
  lo llevó a **2,0 %** después de terminar la limpieza. No era carga útil ni
  TTS.
- Causa: `livekit-wakeword==0.1.0` crea tres `onnxruntime.InferenceSession`
  (mel, embedding y clasificador) sin `SessionOptions`. Eran las únicas sesiones
  ONNX del camino wake que todavía no pasaban por la política compartida
  no-spinning. `wakeword.py` construye ahora exactamente esos tres stages y los
  mismos pesos con un hilo, ejecución secuencial y spinning intra/inter apagado;
  no añade otro predictor ni cambia el umbral.
- Predictor real sobre silencio: carga **0,304 s**, inferencia p50 **17 ms** y
  p95 **18 ms**, score `0,005929`. Prueba de política: **8/8**.
- Corrida viva `wake-bounded`, 150,2 s y 269 muestras, con wake realmente activo:
  el proceso de mente promedió **10,47 % de un core** durante una ventana directa
  de 30 s (antes 197,2 %). En las últimas 50 muestras, BAXY completo promedió
  **1,13 % CPU del sistema**, máximo 2,25 %; el proceso de mente promedió 9,7 %
  de un core, máximo 17,1 %; RSS promedio 5.553,7 MiB y delta **−1,8 MiB**.
  `baxy_resource_guard` terminó `completed`, cero PIDs muertos y ninguna razón.
- Regresión física con el runtime dueño: **2/2** — BAXY sintetizado activa y
  ruido no; el ciclo PCM wake→STT llega a `open notepad please`. No hubo skips.
- `scripts/test_source_quality.ps1` pasó completo en modo Fast sobre este árbol:
  PowerShell, Ruff, compileall, ESLint, ambos TSC, `dotnet format` y build Release
  con **0 warnings / 0 errors**. Fue necesario reponer `node_modules` exactamente
  desde `pnpm-lock.yaml --frozen-lockfile`; no cambió ningún fichero versionado.
