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

## Continuación — decisor recuperado y apertura de Steam honesta

- La mente sí estaba publicada. El bloqueo que capturaba cada entrada estaba en
  `%LOCALAPPDATA%\BAXY\dev-mente-v2\shell\planner-state.v1.bin`: un plan antiguo
  de `app.open` para Steam conservaba `pendingEffectMayHaveOccurred=true`, mission
  `a68179ed-14ac-4fa5-882f-56211ac2944b` e invocation
  `cb6a6bb9-b306-4c28-90ce-412eb90a6839`. Ninguna respuesta podía refrescar ese
  estado y `cancelar` volvía a persistirlo; por eso el plan sobrevivía y tomaba
  los turnos siguientes antes del decisor.
- Un efecto incierto sin desafío actualizable es ahora un fallo terminal honesto:
  el plan que no puede avanzar se borra, pero la invocación exacta continúa en el
  outbox durable como evidencia. Las conversaciones independientes vuelven a la
  mente con historial vacío mientras exista una recuperación; sólo las respuestas
  de control se entregan al plan pendiente.
- Una nueva petición equivalente sólo sustituye la identidad abandonada cuando la
  operación es `app.open`: el postcondition de abrir/enfocar y verificar la misma
  aplicación absorbe la incertidumbre anterior. No se generalizó a mensajes,
  borrados ni otros efectos. El reemplazo guarda atómicamente una mission e
  invocation nuevas antes de actualizar el registro en memoria.
- La falsa respuesta sobre Steam tenía una segunda causa: la narración de una
  misión de un paso anidaba sus hechos estructurados dentro de un string JSON. El
  compositor exigía después ese JSON literal, fallaba y podía intentar inventar
  otra causa. Una misión de un paso publica ahora directamente el resultado
  estructurado. La política visible conserva además la incertidumbre y exige que
  una pérdida de composición se nombre como tal; no acepta un «no pude
  encontrarlo» inventado. Las sondas de composición registran sólo causa, hashes,
  tamaños y conteos, nunca contenido.
- Corrida viva `steam-visible`, Release: `abre Steam` cruzó
  `decision.ready=action`, extrajo `app.open`, llamó al core durante ~180 ms y
  llegó a `response.final` en **1,585 s**. La UI mostró exactamente **«Steam ya
  está abierto.»**. La nueva invocation
  `6115856d-4ad1-433d-ad60-e457c608ef93` quedó journalizada con
  `verified=true`, `alreadyRunning=true`, `processId=28036` y `windowHandle=68200`;
  el outbox terminó vacío y el planner state siguió ausente.
- En la misma instancia, el turno posterior `¿Quién eres?` cruzó el bridge,
  terminó en `decision.ready=conversation` y `response.final` en **7,969 s**, sin
  core ni plantilla. Los parsers de memoria y selección ya tienen regresiones para
  no capturar esa pregunta. Sigue habiendo variación de latencia del decisor —se
  observó antes un timeout aislado de ~22 s—, que debe medirse durante la dosis y
  no ocultarse.
- Validación de esta tanda: filtro C# final **22/22**, filtro amplio de parsers
  **1772/1772** y contratos Python nuevos **5/5**. `test_planner.py` completo quedó
  en **138 pass + 101 subtests / 7 fail**: cuatro expectativas caducadas de
  prompt/cache, dos frases de prompt ausentes y la corrección de una misión parcial;
  son rojos reales a resolver antes del Full, no se ocultaron ni marcaron skip.
  `scripts/test_source_quality.ps1` pasó completo en modo Fast: PowerShell, Ruff,
  compileall, ESLint, ambos TSC, `dotnet format` y build Release con **0 warnings /
  0 errors**.

## Continuación — conversación separada del catálogo y sonda UIA fiable

- La primera dosis multitur no cuenta: encontró tres defectos visibles. «¿Quién
  eres?» agotó el presupuesto y mostró «No pude: entender la solicitud»; «¿Qué
  puedes hacer?» inventó que su nombre era «Resolvedor semántico de referencias
  conversacionales»; y «Respóndeme sólo con un saludo breve» se enrutó a
  `task.resolve.exact`. La recuperación de esa lectura reaparecía después como
  una pregunta sobre metadatos de una rutina. Se canceló por el camino público y
  `planner-state.v1.bin` quedó ausente antes de repetir.
- Causa: las preguntas sobre BAXY y el trabajo cuyo único resultado es texto no
  estaban cerradas frente a una retirada posterior por catálogo. Ahora son una
  decisión de conversación que sólo quita autoridad; no propone prosa ni concede
  operaciones. Incluye identidad/capacidades, saludo solicitado, redacción,
  traducción y resumen. «¿Sigues ahí?» / `Are you there?` son actos sociales.
- La respuesta contextual también copiaba literalmente instrucciones internas.
  El veto visible rechaza vocabulario de planner/catálogo/resolvedor semántico,
  signos españoles sin cierre y confusables cirílicos no pedidos. En la corrida
  R6 el primer borrador de identidad copió el prompt y `Síо.` terminó con una
  “о” cirílica; ambos fueron rechazados y el segundo borrador seguro fue el que
  llegó a pantalla. La auditoría cruda fue opt-in y local en `%TEMP%`; no se
  versionó ni publicó contenido.
- `goal10_dose_turns.ps1` vuelve a adquirir el campo UIA inmediatamente antes de
  cada envío. Si en 3 s no existe `submit.received`, lo adquiere de nuevo y sólo
  reenvía tras comprobar otra vez que el bridge no aceptó el turno; el resultado
  registra `bridgeAttempts`. La corrida ejerció el segundo intento sin duplicar
  turnos. `goal10_uia_dump.ps1` muestra ahora los últimos 50 textos, donde vive la
  conversación, en vez de los primeros 30 ocupados por telemetría.
- Repetición limpia `conversation-clean-r6`, Release, cuatro turnos: **3,112 s /
  4,752 s / 0,769 s / 1,006 s**, todos con `visible.text`, cero core y cero error.
  La UI mostró exactamente: «Soy BAXY, un compañero que vive en el PC.»; una
  descripción honesta de ayuda conversacional e idiomas; «Hola.»; y «Sí, estoy
  aquí.». No quedó plan pendiente. Ésta es una sesión válida de regresión, pero
  todavía no se suma a la dosis de 200 porque nació para repetir una sesión que
  había fallado honestidad.
- Validación de esta frontera: `test_turn_policy.py` completo **835/835**;
  regresiones focales de planner **58/58**; puntuación C# **10/10**; ambos scripts
  PowerShell parsean. `scripts/test_source_quality.ps1` pasó completo en modo
  Fast, incluido build Release con **0 warnings / 0 errors**.

## Continuación — soak iniciado y planner dueño verde

- El tramo continuo comenzó a **2026-08-24 18:08:53Z** con BAXY Release PID
  `37388`, wake permanente activo y el sampler dueño en
  `artifacts/goal10/soak.json{,l}` (wrapper `28956`, worker `37720`). Muestra
  inicial: app RSS **210,2 MiB**, GPU total en uso **4.360 MiB** y llama-server
  vivo. A 121,6 s / 3 muestras: app RSS **208,9 MiB**, pico 210,2 MiB, GPU
  **4.417 MiB**; no hay crecimiento inicial. Los ficheros siguen actualizándose
  cada 60 s y deben sobrevivir sin truncarse hasta el cierre del tramo.
- Los siete rojos de `test_planner.py` se resolvieron sin skip ni umbral menor:
  el prompt compacto recuperó primera persona, actor, no invención, idioma e
  internos; el prompt general recuperó hechos verificables y la prohibición de
  pregunta genérica/imperativos ingleses; el cache de composición continúa
  deliberadamente apagado por la repetición cruzada de Spotify ya medida y los
  tests reflejan ese contrato; una misión parcial puede publicar más de una
  frase cuando conserva sus hechos. Resultado dueño: **146 pass + 101 subtests**.
- No se mata BAXY para repetir Fast durante el tramo continuo. Esta tanda sólo
  toca Python y su suite dueña está verde; la compuerta Fast se repetirá en la
  ventana de reinicio o en el cierre, sin sacrificar la continuidad medida.

## Continuación — la sonda visible detectó continuidad falsa

- `goal10_dose_turns.ps1` ya no acepta `response.final` como sustituto de la
  pantalla: exige `visible.text`, espera el `dom.applied` posterior y captura por
  UIA la prosa exacta que vio la persona. La prueba viva `visible-capture-r1`
  conservó «Sí, estoy aquí. ¿En qué puedo ayudarte?» en **1,393 s**.
- La repetición multitur encontró un defecto grave antes de empezar la dosis:
  después de esa pregunta genérica, `Hola.` se clasificó como `clarify` y mostró
  **«¿Quieres que te diga el volumen y el silencio actuales de la salida
  predeterminada?»** en 3,424 s. No hubo llamada al core, pero sí iniciativa no
  solicitada; `visible-capture-r1/r2` son sondas fallidas y no cuentan.
- Causa demostrada en el árbol: `_history_has_pending_clarification` infiere un
  efecto pendiente de cualquier último mensaje del asistente terminado en `?`.
  La app ya conserva la aclaración real en `_pendingMindClarificationObjective`
  y, cuando existe, consulta primero la nueva entrada con historial vacío para
  decidir si la reanuda o la sustituye. Por tanto, la puntuación del historial
  Python convierte preguntas conversacionales normales en autoridad espuria y
  no representa estado real. Se corrige en esa frontera y se repite desde una
  instancia limpia antes de contar turnos.
- La inferencia por `?` ya se retiró de los cierres sociales, de no comprensión
  y de conversación estable; no queda un segundo estado de aclaración en Python.
  La regresión extremo a extremo de la mente entrega `Hola.` como conversación
  aun si el historial termina en «¿En qué puedo ayudarte?» y demuestra que no
  rankea catálogo, no recupera evidencia y no concede efectos. Suite dueña:
  `py -3.12 -m pytest tests/test_turn_policy.py -q` **835/835**; la sonda
  PowerShell parsea sin errores. Falta repetir en producto tras reiniciar al
  árbol nuevo; el tramo de soak iniciado sobre el binario anterior queda
  invalidado por este defecto visible y no puede contar para las 24 h finales.
- La repetición viva `continuity-clean-r1` sobre `d3df14d` confirmó que la
  autoridad falsa desapareció: presencia, saludo y capacidades terminaron sin
  core en **1,379 s / 0,815 s / 1,061 s**. No cuenta todavía: las tres respuestas
  añadieron la misma coletilla **«¿En qué puedo ayudarte?»**, incluso aunque el
  prompt ya la prohibía. Es una frase de plantilla visible y la sesión se marca
  fallida. La causa es distinta: el validador global sólo rechazaba ofertas
  genéricas cuando `_conversation_presentation_shape` no era `None`; saludos y
  capacidades pasan deliberadamente con shape nulo. La prohibición debe vivir
  antes de ese gate y provocar la reescritura model-authored ya existente.
- `continuity-template-clean-r2` demostró que enumerar una coletilla tampoco
  basta: el primer veto produjo variantes de la misma plantilla —«¿Qué
  necesitas?», «¿Qué te pasa?» y «¿En qué puedo asistirte?»—. Los tres
  turnos siguieron sin core en **1,369 s / 0,820 s / 1,084 s**, pero la sesión
  vuelve a fallar y no cuenta. El contrato correcto no es una lista de frases:
  para los actos sociales cerrados y las respuestas directas de conocimiento,
  una pregunta final no solicitada se elimina conservando la declaración
  model-authored que la precede; si no hay declaración o queda otra pregunta,
  el candidato se rechaza. Borradores de contenido y role-play quedan fuera de
  esa regla porque una pregunta puede ser parte del resultado solicitado.
- `continuity-shape-clean-r3` cerró las preguntas: presencia quedó en «Sí,
  aquí.» y capacidades en una declaración útil. El saludo, sin embargo, mostró
  otra vez «Sí, aquí.». El volcado UIA confirmó la secuencia completa y descarta
  una lectura atrasada: era un eco exacto del mensaje anterior del asistente.
  La sesión tampoco cuenta. La validación general sólo comparaba contra el pedido
  actual; el turno social permitía espejar a la persona, pero no distinguía ese
  espejo legítimo de repetir la propia respuesta previa. Se conserva el espejo
  social del usuario y se rechaza por separado cualquier eco del historial del
  asistente; el retry ya existente no lleva ese historial.
- La repetición `continuity-history-clean-r4` probó que el eco se rechazaba,
  pero agotaba los dos intentos y caía en la recuperación semántica, que hizo
  visible otra pregunta de plantilla: «¿En qué puedo ayudarte hoy?»
  (`decision.ready=clarify`, 2,611 s). Presencia y capacidades fueron limpias;
  el saludo invalida otra vez la sesión. La causa restante es que `chat` todavía
  entregaba historial al modelo para un acto social que el clasificador ya
  demostró autocontenido. Los actos sociales cerrados dejan de cargar historial,
  igual que el aviso de idioma cerrado; así no hay continuidad que inventar. El
  veto de eco se conserva para respuestas de conocimiento, donde sí puede haber
  historial legítimo.
- `continuity-social-clean-r5` dejó presencia y saludo limpios («Sí, aquí.» /
  «Hola.», 1,388 s / 0,805 s), pero capacidades terminó su frase útil con
  **«Si necesitas algo específico, avísame.»** (1,102 s). Es la misma plantilla
  convertida en invitación declarativa y la sesión tampoco cuenta. La regla se
  generaliza a un cierre no solicitado por forma: pregunta final o invitación
  condicional genérica. Si hay una declaración model-authored anterior, sólo se
  retira la coletilla; si la coletilla ocupa toda la respuesta, se rechaza.
- Repetición `continuity-closing-clean-r6` sobre `cbb08d0`, limpia en producto
  vivo: **«Sí, aquí.» / «Hola.» / «Puedo ayudarte con preguntas,
  explicaciones y charlas.»**, en **1,657 s / 1,065 s / 1,517 s**. Los tres
  turnos tuvieron `visible.text`, cero core, cero error y un solo cruce del
  bridge. Esta corrida demuestra la reparación, pero no suma a los 200 porque es
  la repetición obligatoria de las sesiones fallidas R1–R5.
- Suites dueñas tras la frontera final: `test_turn_policy.py` **848/848** y
  `test_planner.py` **146/146 + 101 subtests**. El segmento de soak invalidado se
  conserva por separado como `soak-invalid-visible-continuity.json{,l}`: terminó
  en 605,7 s / 11 muestras, sobre un proceso anterior y con carga interactiva;
  no se usa como evidencia idle ni como parte de las 24 h.
- `scripts/test_source_quality.ps1` pasó en modo Fast sobre el árbol de esta
  frontera: PowerShell, Ruff, compileall, ESLint, ambos TSC, `dotnet format` y
  build Release con **0 warnings / 0 errors**.
- El tramo definitivo se reinició desde cero a **2026-08-24 18:34:40Z** sobre
  `cad6d09`, con BAXY Release PID `4432`, wake permanente y sampler wrapper
  `32892` / worker `35296`. La primera muestra es app RSS **171,2 MiB**, GPU
  total **5.283 MiB**, llama-server vivo. `artifacts/goal10/soak.json{,l}` vuelve
  a pertenecer exclusivamente a este tramo; no matar ni recompilar BAXY mientras
  corra, salvo que un defecto obligue honestamente a reiniciar las 24 h.

## Continuación — hechos públicos sin verificar invalidan el tramo

- Durante uso real concurrente de la persona, la pregunta `Quien es batman?`
  mostró: **«Batman es un personaje de ficción de cómic y animación, creado por
  Bob Kane y William Marovich en 1939. Es un detective que vive en GOTHAM y
  lucha contra el crimen con su identidad secreta. Su boda con la detective
  Barbara Gordon lo convierte en un personaje de serie.»**. Es una afirmación
  factual no verificada con falsedades visibles; el trace confirma
  `decision.ready=conversation`, sin core.
- En la misma sesión, `Cual es el ultimo mortal kombat que salio?` terminó en
  plan/aclaración sin core y mostró **«¿Cuál es el nombre del último Mortal
  Kombat lanzado en el mercado?»**. Ante `Dimelo tu`, mostró **«No puedo decir
  cuál fuerió el último kombat que salió.»**. La entrada llegó por `key.enter`:
  no fue un falso positivo de wake. Los tres son turnos reales, pero esta sesión
  no cuenta porque violó honestidad y plantillas; se repetirá completa tras la
  reparación.
- El tramo iniciado a 18:34:40Z queda invalidado y detenido. Se conserva como
  `soak-invalid-public-facts.json{,l}`: **182,2 s / 4 muestras**, RSS inicial
  **171,2 MiB**, última/pico **271,5 MiB** durante carga interactiva; no es
  evidencia idle ni suma a las 24 h. Se detuvieron app y ambos samplers. No se
  inicia otro tramo hasta que preguntas factuales públicas crucen `web.search`,
  el kernel verifique el resultado y la repetición viva sea limpia.
- La evidencia acumulada confirmó que no era un caso especial: el holdout
  versionado de mensajes reales contiene **456** filas `qa_factoid` dentro de
  9.172 turnos. La nueva frontera sintáctica reconoce **357/456 (78,3 %)** sin
  etiqueta ni modelo: personas, capitales, fechas, cantidades, biografías,
  estado civil y lanzamientos. Los restantes incluyen deliberadamente datos de
  contacto, posesivos/localización personal, opinión, deícticos sin referente y
  formas corruptas del corpus que no deben convertirse automáticamente en una
  consulta saliente.
- `web.search` se selecciona después de los reconocedores específicos: las
  lecturas de batería, GPU, ventana, portapapeles, aplicaciones, calendario y
  audio conservan su operación dueña. La búsqueda pública queda cerrada antes
  del decisor, conserva el texto literal como `query` y no acepta identidad de
  BAXY, contenido creativo, datos personales o estado de este PC. Suites dueñas
  completas: `test_effect_intent.py + test_turn_policy.py` **2327/2327** en
  49,07 s. Falta compuerta Fast y repetición viva del proveedor/narración.
- Compuerta `scripts/test_source_quality.ps1` **Fast verde** sobre `0a2c270`:
  PowerShell, Ruff, compileall, ESLint, ambos TSC, `dotnet format` y build
  Release; compilación **0 warnings / 0 errors**. Ya puede repetirse en producto
  desde binario limpio.
- `public-facts-r1` confirmó el enrutado pero encontró otra frontera: ambos
  turnos fueron `action -> web.search` (Batman: core **465 ms**, visible **1,72
  s** desde decisión; Mortal Kombat: core **239 ms**), pero la consulta enviada
  era la pregunta entera. Bing devolvió cinco resultados sobre el pronombre
  «quien» y BAXY mostró su definición; Mortal Kombat falló honestamente con
  `web_search_results_irrelevant` y después el compositor mostró un error
  genérico. R1 no cuenta y el soak sigue detenido.
- La corrección siguiente no toca el proveedor ni relaja relevancia: el grounding
  transforma sólo factoids públicos ya autorizados en una consulta centrada en
  el sujeto (`Batman biografia`, `Mortal Kombat ultimo lanzamiento`, `capital of
  Nigeria`, `Mariah Carey age`). Identidad, estado local y privacidad siguen
  fuera; las consultas web explícitas conservan su literal. Suites dueñas tras
  el cambio: **2327/2327** en 56,80 s. Falta Fast y repetición viva.
- Fast del grounding centrado **verde**: toda la estática multilenguaje y build
  Release **0 warnings / 0 errors**. El commit `19c4527` está local; dos pushes
  fallaron por conexión a `github.com:443`, no por rechazo, y se reintentará.
- `public-facts-r2` verificó que `batman biografia` sí devuelve cinco resultados
  pertinentes (Wikipedia ES/EN, DC e IMDb) y el core los marcó verificados; la
  UI mostró una descripción de Batman como vigilante de Gotham. Mortal Kombat
  siguió fallando, ahora por proveedor: Bing RSS devolvió HVAC, White Sands y
  otros dominios ajenos incluso para tres variantes inglesas centradas. El gate
  `web_search_results_irrelevant` los rechazó correctamente. R2 no cuenta.
- Desde esta misma máquina, DuckDuckGo HTML devolvió resultados pertinentes para
  la misma consulta (Mortal Kombat 1, Definitive Edition y Legacy Kollection).
  El provider mantiene Bing y, sólo si no obtiene ningún resultado relevante,
  consulta DuckDuckGo, decodifica la URL final HTTPS, limita el cuerpo a 2 M de
  caracteres y aplica el mismo filtro de tokens. Regresión dueña focal:
  `StructuredWebSearch*` **4/4**, cero skips. Falta suite completa/Fast/vivo.
- Suite completa `Baxy.Providers.Windows.Tests` **452 pass** en 38 s según el
  resumen VSTest (`Omitido: 0`), aunque la salida también imprimió cuatro casos
  ambientales como «Omitidas» (NativeAOT CoreAudio, Wi-Fi real, DXGI/PDH e IP
  real). No se usan esos cuatro como cobertura ejecutada; el fallback HTTP sí
  corrió dentro de los 452. Falta Fast y repetición viva.
- Fast del fallback **verde**: PowerShell, Ruff, compileall, ESLint, ambos TSC,
  `dotnet format` y build Release; **0 warnings / 0 errors**. Binario listo para
  `public-facts-r3`.
- `public-facts-r3` cruzó limpio el bridge, UIA y core en ambos turnos, pero no
  cuenta: Batman quedó sin las falsedades originales; Mortal Kombat usó el
  fallback y recibió cinco resultados, incluidos `Mortal Kombat 1: Definitive
  Edition` (14-05-2025) y una fuente que aún decía «más reciente: Onslaught,
  octubre de 2023». El compositor eligió esa afirmación obsoleta y la mostró
  como actual. Es otra violación de honestidad; se conserva la corrida en
  `public-facts-r3.json` y se repite.
- La sonda también tenía una carrera real: `dom.applied` puede preceder por una
  posición a `response.final`. Ahora exige DOM después de `visible.text`, que es
  la publicación causal; R3 produjo el JSON de dos turnos en vez de un falso
  timeout. La consulta de recencia se cambia a “most recent release available
  now” y esos términos temporales dejan de puntuar relevancia: la entidad sigue
  siendo obligatoria, pero una etiqueta «latest» no convierte HVAC en pertinente.
- Focales de R4: grounding Python **4/4** y `StructuredWebSearch*` C# **4/4**.
  Fast verde completo, build Release **0 warnings / 0 errors**.
- `public-facts-r4` limpia en producto: Batman cruzó Bing verificado y mostró
  una descripción breve de su papel como vigilante de Gotham; Mortal Kombat
  cruzó DuckDuckGo verificado y mostró **«El último Mortal Kombat que salió es
  Mortal Kombat: Legacy Kollection, lanzado en 2025.»**. La evidencia incluyó
  Gematsu (lanzamiento 30 de octubre), PlayStation y la ficha de la compilación
  de 2025. Tiempos totales de sonda **5,307 s / 3,180 s**, un solo bridge,
  `visible.text`, DOM, cero `turn.error`. Es la repetición obligatoria de R1–R3:
  demuestra la reparación, pero no suma a los 200.
- Tramo continuo definitivo reiniciado a **2026-08-24 19:26:18Z** sobre
  `ef10aed`: BAXY PID `44880`, sampler wrapper `39580` / Python `47588`, wake
  permanente activo. Primera muestra: app RSS **274,8 MiB**, llama-server vivo,
  GPU reportada **6.392 MiB** en uso de 16.380 MiB totales. Desde aquí no matar
  ni recompilar; uso real y dosis se ejecutan sobre esta misma instancia.
- La primera comprobación visual de modos encontró un bloqueo real: `/settings`
  ya leía y persistía `normal/bypass`, pero `field-native-bridge.js` ocultaba la
  pestaña `agent`, deshabilitaba el selector de confirmaciones y ocultaba
  `apply`; el bypass era imposible de activar desde el producto. La capa nativa
  ahora expone esa pestaña, mantiene administrados los demás controles y deja
  editables sólo `confirmation policy` y `apply`. Regresión dueña aislada (sin
  tocar el PID vivo): `NativeBridgePreservesTheHistoricalContractLocally`
  **1/1**, cero skips, build Release en salida temporal. El tramo de 19:26:18Z
  se invalidará al relanzar el binario reparado; no puede contar como las 24 h.
- Tramo inválido por control de modo cerrado y preservado como
  `soak-invalid-mode-control.json{,l}`: **545,8 s / 10 muestras**, RSS inicial
  **274,8 MiB**, final/mínimo **269,6 MiB**, pico **274,8 MiB**; no hubo alza,
  pero no suma a las 24 h. Fast posterior a la reparación **verde**: PowerShell,
  Ruff, compileall, ESLint, ambos TSC, `dotnet format` y build Release con **0
  warnings / 0 errors**. El siguiente lanzamiento ya contiene el selector vivo.
- La primera sesión del dueño tras ese lanzamiento tampoco cuenta. Turnos
  visibles: `Hola` → «Hola,»; `Me puedes ayudar en algo` → **«¿Quieres que
  resuelva un único título literal y emita autoridad CAS sin exponer
  detalles?»**; `Nop, quiero que abras steam` → **«¿Quieres que inicie un AppID
  poseído y verifique la identidad del proceso lanzado?»**. Las dos últimas son
  plantillas técnicas no solicitadas; cero efectos llegaron al core.
- Causas cerradas sin reabrir el planner: la protección de estado local decía
  que excluía turnos sociales, pero el código incluía `social` junto a
  `knowledge` y convertía una oferta de ayuda en confirmación del vecino de
  catálogo; además el prefijo correctivo puntuado `Nop, ...` no se retiraba, por
  lo que `quiero que abras Steam` no alcanzaba el reconocedor autenticado de
  `app.open`. `AppID` y «autoridad CAS» tampoco estaban en el veto de vocabulario
  interno para preguntas.
- Reparación focal: sólo `knowledge` puede entrar a la protección de recitado de
  estado; `No/Nop/Nope, ...` expone la solicitud sustituta sólo con puntuación
  obligatoria (la negación `No quiero...` sigue sin autoridad); toda aclaración
  rechaza `AppID` y «autoridad CAS». Focales **14/14** y suites dueñas completas
  `test_effect_intent.py + test_turn_policy.py` **2333/2333** en **64,73 s**,
  cero skips. Falta Fast y repetición viva completa de esta sesión.
- Fast de la reparación social/corrección **verde**: PowerShell, Ruff,
  compileall, ESLint, ambos TSC, `dotnet format` y build Release con **0 warnings
  / 0 errors**. Binario listo para repetir los tres turnos reales.
- Repetición viva `social-correction-r1`, sesión `2fa97ec19971`: la sesión sigue
  invalidada y suma **0 turnos**. `Hola` → **«Hola,»** y `Me puedes ayudar en
  algo` → **«Claro,»**: desapareció la jerga técnica, pero ambos actos sociales
  quedaron truncados en una coma. Es un defecto visible reproducible, no una
  preferencia de estilo.
- En esa misma repetición, `Nop, quiero que abras steam` sí alcanzó el efecto
  real: Steam se abrió/enfocó y BAXY mostró **«Listo, Steam está abierto.»**. La
  corrección de prefijo y el enrutado `app.open` quedan verificados en producto;
  falta cerrar el truncamiento social y repetir la sesión entera.
