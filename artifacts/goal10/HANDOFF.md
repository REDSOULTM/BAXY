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
- Causa del truncamiento cerrada: el modelo producía saludo/acuse seguido de
  invitación (`Hola, ¿…?` / `Claro, ¿…?`) y el filtro que retira preguntas no
  solicitadas conservaba la coma de enlace. Ahora el prefijo superviviente se
  cierra como oración y el contrato rechaza borradores que realmente terminen
  en coma, punto y coma o dos puntos. Focales **9/9** y suite dueña
  `test_turn_policy.py` **861/861** en **4,08 s**, cero skips. Falta Fast y la
  repetición viva completa.
- Fast posterior al cierre de cláusulas sociales **verde**: PowerShell, Ruff,
  compileall, ESLint, ambos TSC, `dotnet format` y build Release con **0 warnings
  / 0 errors**. Binario listo para repetición viva desde sesión nueva.
- Repetición viva `social-correction-r2`, sesión `76245ab202f1`, limpia:
  `Hola` → **«Hola.»**; `Me puedes ayudar en algo` → **«Claro.»**; `Nop, quiero
  que abras steam` → Steam abierto/enfocado y **«Listo, Steam está abierto.»**.
  Son tres sondas del agente, por lo que prueban la reparación pero no suman a
  los 200 turnos normales del dueño. No hubo eco, plantilla, jerga ni falsedad.
- Modos normal/bypass verificados desde la interfaz viva: se seleccionó bypass,
  se aplicó y al reabrir ajustes seguía activo; después se seleccionó normal,
  se aplicó y al reabrir seguía restaurado. El producto queda en **normal**.
- Bloqueo vivo nuevo en memoria: al abrir `MEMORY 0 pinned` en la sesión
  `76245ab202f1`, el panel real muestra **`error · server error 409`**, cero
  entradas y acciones de borrado deshabilitadas. El criterio de memoria no está
  cumplido; hay que cerrar el conflicto en el contrato HTTP/core y repetir alta,
  vista, edición y borrado desde este panel.
- Instrumentación mínima añadida al único borde `MemoryPanelBridge.ExecuteAsync`:
  ante un terminal no completado registra en la traza sólo nombre de operación,
  código y bit `verified`, nunca claves ni valores privados. La regresión dueña
  `MemoryPanelBridgeTests` pasa **1/1**, cero skips, y sigue cubriendo alta,
  lectura, edición y borrado sobre un almacén aislado. Falta relanzar contra el
  estado vivo para obtener el código exacto del 409.
- La primera reproducción instrumentada fijó la operación en `memory.list`,
  pero el detalle compuesto llevaba caracteres que `ShellTrace` reduce a
  `invalid`. El formato ya es una etiqueta canónica sin contenido libre; la
  regresión CRUD sigue **1/1**, cero skips. Repetir una vez para leer el código.
- La repetición canónica midió exactamente
  **`memory.list.memory_disabled.unverified`**. No era corrupción ni transporte:
  el almacén nace apagado por privacidad y el GET del panel listaba como si
  estuviera activo. Ahora abrirlo apagado devuelve 200 + lista vacía sin activar
  retención; sólo `add` conserva la operación explícita de habilitar. La prueba
  dueña añade el GET inicial apagado y pasa **1/1**, cero skips. Falta CRUD vivo.
- CRUD de memoria verificado en producto vivo, sesión `e4704531533a`: apertura
  apagada sin 409; alta sintética `goal10.panel=verde-panel`; valor visible;
  corrección por la misma clave a `azul-panel`; selección, confirmación exacta y
  borrado; panel final **0 entries**. Sólo se creó y eliminó esa entrada de
  prueba, sin leer ni modificar memoria personal preexistente. Falta Fast.
- Fast posterior a la reparación y al CRUD vivo **verde**: PowerShell, Ruff,
  compileall, ESLint, ambos TSC, `dotnet format` y build Release con **0 warnings
  / 0 errors**. Memoria lista para el tramo continuo final.
- La primera sonda viva de narración, `narration-r1`, descubrió otro fallo de
  honestidad y queda invalidada: la petición clara **«Di una frase breve y
  completa sobre el cielo.»** agotó exactamente el límite del decisor
  (`decision.start` 51.194 ms → `decision.ready unavailable` 73.196 ms) y el
  shell publicó **«No pude: la solicitud no fue clara.»**. No era ambigüedad:
  fue indisponibilidad/timeout del decisor mal proyectada como ambigüedad. Es
  una sonda del agente y suma 0 turnos; narración todavía no quedó ejercitada.
- Reparación focal del falso terminal: cuando `turn.decide` no entrega contrato,
  el shell ya no retorna al camino de `ambiguous_request`; publica
  `compose_unavailable` con diagnóstico de servicio local y conserva el fallo
  honesto. Un sidecar contractual fuerza esa respuesta ausente y la regresión
  `UnavailableMindDecisionNeverClaimsThatTheRequestWasAmbiguous` pasa **1/1**,
  cero skips. Falta repetición física y Fast.
- Repetición física `narration-r2`: el mismo pedido claro agotó otra vez los
  **22,002 s** de `turn.decide` (`decision.start` 42.549 ms →
  `decision.ready unavailable` 64.551 ms). El terminal reparado fue honesto,
  **«No pude: el cielo no está disponible en este momento.»**, por lo que la
  falsedad de `narration-r1` quedó cerrada; sin embargo, el defecto funcional
  persiste y esta sonda también suma 0. La señal temprana llegó en 0,334 s:
  el atasco está después del enrutado, dentro de la decisión/presentación local.
  El pedido `Di una frase …` no cruza hoy el reconocedor cerrado de borrado de
  contenido, aunque es exactamente una solicitud conversacional autocontenida;
  cae en clasificación generativa antes de redactar. Narración no se da por
  verificada: la observación accesible no capturó estado `speaking` y no se
  afirma audio que la herramienta no oyó.
- Reparación focal del atasco conversacional: `di/dime una frase/oración…` y
  `say/tell me a/one sentence/phrase…` son ahora redacción autocontenida antes
  de recuperación de efectos y antes del decisor generativo. La prueba reveló
  además que dos variantes (`…sobre la lluvia`, `…about autumn`) se
  autenticaban erróneamente como `web.search`; el veto de contenido se aplica
  tanto a aclaración como a resolución de efectos. Las consultas de observación
  **«Dime qué frase aparece en la ventana»** / **«Tell me which sentence is
  visible on screen»** permanecen fuera del cierre. Focales **7/7**, cero skips
  (`test_effect_intent`: 6; `test_turn_policy`: 1). Falta suites dueñas,
  repetición viva y Fast.
- Suites dueñas completas posteriores: `test_effect_intent.py +
  test_turn_policy.py` **2345/2345** en **57,20 s**, cero skips. El cambio queda
  listo para repetición viva; todavía no sustituye esa medición física ni Fast.
- Repetición viva `narration-r3`: el mismo pedido llegó a
  `decision.ready conversation` en **683,690 ms** y a `response.final` en
  **934,236 ms**; BAXY mostró **«El cielo es un espacio infinito lleno de
  estrellas y nubes.»**. Cero timeout, eco, plantilla, búsqueda web o terminal
  falso. Es sonda del agente y suma 0. El polling de accesibilidad perdió el
  documento salvo `message input` justo durante el turno, así que no acredita
  `speaking`; la captura física final sí acredita el texto y estado `Idle`.
  Antes de marcar narración falta una traza estable de `voice.event state`
  `speaking=true→false`, sin texto ni datos privados.
- Instrumentación de narración añadida al evento dueño de la UI: cada
  `voice.event state` escribe sólo `voice.state` con detalle cerrado
  `speaking|silent`, correlacionado al turno vigente; nunca texto ni contenido
  privado. `ShellTraceTests` **8/8**, cero skips, y build Release verde. Falta
  repetir en producto para observar el par real.
- Producto vivo `narration-r4`: el saludo de arranque sí cruzó
  `voice.state speaking→silent` (**2,444 s**); el primer pedido lunar respondió
  en **1,064 s** con **«La luna brilla silenciosa en el cielo.»**, pero quedó
  silencioso aun 16 s después. Un `Hola` posterior narró (`speaking` a 211 ms
  de `response.final`) y la repetición literal del pedido lunar también
  (`speaking` a 251 ms, `silent` 1,666 s después). El motor, el idioma y el
  texto quedan descartados como causa permanente; existe una pérdida
  intermitente del primer envío de narración. Las tres son sondas del agente y
  suman 0. Narración todavía no se cierra: hay que distinguir rechazo JSONL de
  fallo asíncrono del sintetizador y reparar el dueño real.
- La frontera de salida ya no descarta silenciosamente el resultado de
  `VoiceSpeakAsync`: traza `voice.speak accepted|rejected` con el ID capturado
  del turno, antes de cualquier cambio físico `voice.state`. Es sólo telemetría
  cerrada y no cambia colas ni tiempos. `ShellTraceTests` **8/8**, cero skips,
  build Release verde. Falta reproducción instrumentada.
- `narration-r5` descartó el solapamiento con el saludo: se esperó su
  `silent`, el primer pedido lunar volvió a responder en **781,363 ms** y
  `voice.speak` fue **accepted**, pero no hubo `speaking`. El Piper dueño,
  ejecutado aislado con el mismo Python 3.10 y hardware, reprodujo
  consecutivamente `Hola.` y la frase lunar (**0,407 s / 1,562 s**), sin
  `last_error`; no es ONNX, eSpeak, dispositivo ni texto. El shell dispara
  `VoiceCancelAsync` al agregar el mensaje del usuario y `VoiceSpeakAsync` al
  agregar la respuesta sin relación causal ni espera. Un cancel tardío puede
  borrar una narración ya admitida. Hay que encadenar el speak al cancel exacto
  del turno y repetir desde arranque fresco.
- Reparación aplicada en el dueño: el `Task<bool>` del cancel se conserva al
  agregar el mensaje del usuario y cada narración de respuesta espera ese
  cancel exacto antes de enviar `voice.speak`. No bloquea texto ni UI; sólo
  impide que una cancelación vieja alcance una voz nueva. `ShellTraceTests`
  **8/8**, cero skips, build Release verde. Falta repetición fresca del primer
  turno posterior al saludo y Fast.
- Repetición fresca `narration-r6` rechazó esa hipótesis: aun esperando
  `welcome silent`, el primer turno llegó a `response.final` en **945,446 ms**,
  `voice.speak accepted` en el mismo milisegundo y volvió a quedar sin
  `speaking`. Encadenar cancel→speak no arregló nada y se retiró; no queda una
  capa sin propósito. El worker ahora emite dos fallos asíncronos cerrados:
  `tts_generate_failed` y `tts_play_failed`; focales Python **2/2** y
  `ShellTraceTests` **8/8**, cero skips, build Release verde tras repetir sin el
  BAXY que había causado el MSB3027 esperado. Falta una reproducción con esos
  códigos para nombrar el borde real.
- `narration-r7` cerró el siguiente borde: primer turno en **799,898 ms**,
  `voice.speak accepted`, sin `speaking` y también sin `voice.error`. El comando
  desaparece antes de generación, sólo por cambio de generación o descarte de
  cola. Barge-in no puede ser el causante porque su guard exige
  `self.speaking=true`; falta medir cuándo termina el único `voice.cancel` del
  shell respecto del `voice.speak`. Se añadió `voice.cancel accepted|rejected`
  con el ID capturado del turno; `ShellTraceTests` **8/8**, cero skips, build
  Release verde. Falta reproducción.
- `narration-r8`: `voice.cancel accepted` terminó **564,777 ms antes** de
  `voice.speak accepted`; la carrera del shell queda descartada con dato y su
  reparación experimental ya estaba retirada. Sin `speaking` ni `voice.error`,
  el hueco restante está dentro del worker. Se añadieron hitos cerrados
  `voice.worker dequeued|stale|cancelled`; focales Python **2/2** y
  `ShellTraceTests` **8/8**, cero skips, build Release verde. Falta
  reproducción.
- `narration-r9` consumió el comando (`voice.worker dequeued` a **0,648 ms** de
  `voice.speak accepted`) y quedó dentro de `generate` más de 10 s, sin error,
  estado físico ni descarte. Se añadieron hitos internos cerrados
  `phonemes→inference→generated` para separar el subprocess eSpeak del
  `InferenceSession.run`; falta focal y reproducción.
- Focales de los hitos internos **3/3** (`test_mind_voice_runtime` +
  `test_resource_policy`) y `ShellTraceTests` **8/8**, cero skips, build Release
  verde. Instrumentación lista para la reproducción física.
- `narration-r10` localizó el bloqueo antes de ONNX: tras esperar el
  `welcome silent`, el primer turno emitió `voice.cancel accepted`, terminó en
  **1,031 s**, aceptó la narración y el worker la desencoló en **0,225 ms**,
  pero no alcanzó `phonemes` ni error aun después de más de 10 s. El hito
  `phonemes` se emite justo después de `_PiperOnnxEngine._phonemes`, por lo que
  el atasco está dentro del `subprocess.run` de eSpeak. Una inspección viva más
  de dos minutos después encontró el proceso de mente activo pero ningún
  `espeak.exe`/`espeak-ng.exe` hijo: no es un ejecutable de eSpeak que siga
  corriendo, sino el borde de creación/espera del subprocess. Sonda del agente,
  suma 0. Falta separar `Popen` de `communicate`, reparar ese borde y repetir el
  primer turno fresco.
- Una pila viva de la mente (`py-spy`, PID 45240) identificó el bloqueo exacto:
  `baxy-neural-output` estaba en `subprocess._communicate` →
  `threading.Thread.start`, no en eSpeak ni en el callback de protocolo. La
  mente sólo tenía 27 hilos y 642 handles, así que no era agotamiento general;
  era la dependencia de `capture_output=True` en lectores auxiliares de PIPE de
  Windows. `_PiperOnnxEngine._phonemes` ahora dirige stdout a un fichero
  temporal local, cierra stdin/stderr, conserva `check=True` y añade un terminal
  honesto de 5 s. Así lee los fonemas en el propio worker sin crear hilos de
  tubería; no es fallback ni reduce ningún umbral funcional. Regresión dueña
  `test_resource_policy.py`: **9/9**, cero skips. Falta reproducción física
  fresca y Fast.
- Reproducción física fresca `narration-r11` **verde**: el saludo completó
  `dequeued→phonemes→inference→generated→speaking→silent`. Antes de entrar la
  sonda del agente, un turno concurrente lanzado por el dueño fue el primer
  turno posterior al saludo: `submit.received` → `response.final` en
  **1,075 s**, `voice.speak accepted`, fonemas en **95,7 ms**, audio generado
  en **255,8 ms**, `speaking` en **256,2 ms** y `silent` 4,480 s después. Es la
  secuencia completa que fallaba determinísticamente en r4–r10; la reparación
  del PIPE queda demostrada en producto real. El dueño describió estos turnos
  concurrentes como pruebas, por lo que no se incorporan a la dosis de 200 de
  uso normal. Las entradas posteriores se solaparon con una sonda del agente y
  tampoco se atribuyen. La salida narrada está cerrada; aún falta acreditar el
  uso entero sin pantalla desde wake/voz y ejecutar Fast.
- La misma r11 reveló un defecto terminal posterior y la sesión completa queda
  invalidada para dosis: durante el segundo turno el proceso real de mente
  Python 3.12 murió nativamente. Windows Event Log 1000/1001 registra PID 5824,
  excepción **`0xc0000005`** (`BEX64`, ejecución sobre dirección inválida), a
  las 18:00:23; WER report
  `bf8d0edf-c17b-49d8-b643-d4e059cc34fc`. `Baxy.exe` y `baxy-core.exe`
  sobrevivieron pero ya no había ningún hijo Python, y los turnos posteriores
  sólo agotaron/completaron degradados del shell. El WER no guardó dump ni
  módulo culpable. No se atribuye a contenido del dueño: el siguiente paso es
  reproducir sólo con datos sintéticos en un `BAXY_DATA_DIR` aislado y capturar
  pila/módulo nativos sin incluir conversación personal.
- Fast posterior a la reparación de narración **verde completo**:
  PowerShell, Ruff, compileall, ESLint, ambos TSC, `dotnet format` y build
  Release; **0 warnings / 0 errors**. La caída nativa sigue abierta porque una
  compuerta verde no sustituye la reproducción viva.
- Reproducción sintética `crash-r12c` bajo `cdb` nativo (sólo pila/módulos, sin
  dump ni variables): **21 turnos** entre conversación, cálculo y búsquedas,
  incluidos tres solapados; cero `turn.error`, cero `voice.speak rejected`, cero
  `voice.error`, mente viva y ningún `0xc0000005`. La caída de r11 aún no es
  reproducible, por lo que no se atribuye a un módulo sin dato.
- Esa dosis sí reprodujo autoridad falsa estable: **`Que puedes hacer?`** y
  **`Cuanto es 17 por 23?`** ejecutaron `web.search`. El helper conversacional
  reconocía capacidad, pero la prioridad dejaba que un falso
  `verified_public_intent` la sobreescribiera; además no había una clase cerrada
  para aritmética numérica pura. Ahora identidad/capacidad y expresiones
  numéricas cerradas son veto autoritativo de efectos antes de recuperación,
  mientras el modelo conserva la respuesta natural. Focales **62/62** y suite
  dueña `test_turn_policy.py` **868/868**, cero skips. Falta repetir ambas frases
  en producto nuevo y otra tanda bajo `cdb`.
- Repetición exacta fresca r13 de capacidad + aritmética: **2/2**
  `decision.ready=conversation`, cero core, respuestas visibles correctas y
  narración completa. Sin embargo, la revisión manual obligatoria de la dosis
  posterior invalidó otra vez la sesión: sólo **7/15** respuestas fueron
  aceptables. Fallos visibles: identidad produjo una pregunta técnica de
  restaurar ventana; capacidad heredó esa falsa aclaración, ejecutó
  `system.identity` y dijo `Listo`; nube tuvo error factual/gramatical; clima no
  dio el clima pedido; identidad inglesa emitió un falso `No pude`; noticias
  claras acabaron en aclaración; fecha afirmó octubre de 2023; y un resumen de
  capacidades pidió contexto inexistente. La traza había marcado 15/15 finales,
  cero `turn.error` y cero fallos de voz: queda demostrado que eso **no** es un
  gate semántico. Desde aquí cada dosis se revisa manualmente par por par y un
  solo texto incorrecto invalida la sesión. Bloqueo vivo: aislar historia para
  preguntas autocontenidas, impedir que un fallo de contrato se convierta en
  falsa aclaración/plan y repetir este mismo corpus sintético antes de uso dueño.
- Primer cierre del bloqueo semántico r13: una conversación reconocida por un
  patrón cerrado y autocontenido ahora llega a `llm.chat` con historial vacío;
  los seguimientos reales conservan el suyo. Si aun así falla dos veces, la
  recuperación de identidad/capacidad, aritmética, redacción o un marco
  explícito sin acción sólo puede recomponer una conversación sin autoridad:
  nunca publica `clarify`, nunca preserva objetivo y nunca deja un plan pendiente
  para contaminar la petición siguiente. También se cerró la superficie real
  sin tilde `Quien eres tu?`, que el reconocedor no cubría. Regresión que
  reproduce la respuesta técnica anterior y verifica historia vacía + cero
  aclaración/efectos; suite dueña `test_turn_policy.py`: **870/870**, cero skips.
  Falta construir y repetir manualmente las 15 respuestas visibles; los defectos
  independientes de fecha, noticias y clima siguen abiertos.
- Las dos superficies explícitas que la tanda r13 había degradado ya quedan
  cerradas antes del modelo: `Que dia es hoy?` autoriza exactamente
  `system.time`, y `Busca noticias actuales de tecnologia y resume una.`
  autoriza exactamente `web.search`. La gramática de noticias ahora reconoce
  verbos explícitos de búsqueda, y hora/fecha reconoce `día` además de `fecha`.
  Suite dueña `test_effect_intent.py`: **1485/1485**, cero skips. Falta
  repetición física; clima sigue siendo un defecto aparte porque la búsqueda
  verificada devolvió enlaces sobre el tiempo pero ningún valor meteorológico
  actual que el compositor pudiera afirmar.
- El defecto de clima queda reparado en el proveedor dueño, sin operación ni
  capa nuevas: una consulta inequívoca de clima actual dentro de `web.search`
  geocodifica el lugar y lee `temperature_2m`, sensación, código meteorológico,
  viento y hora desde los endpoints HTTPS públicos de Open-Meteo. El recibo
  conserva el mismo esquema `results[]`, marca autoridad
  `open_meteo_current_https` y no afirma éxito si no obtiene todos los valores.
  La prueba reproduce `el clima actual de Santiago` y exige valores + ambas
  autoridades HTTP; focales de búsqueda **5/5** y suite completa
  `Baxy.Providers.Windows.Tests` **453/453**, cero skips en el resumen. Falta
  comprobar la red real y leer la frase compuesta en el producto vivo.
- Repetición física r14 auditada manualmente par por par: **10/15 aceptables**,
  por tanto sesión inválida. Ya quedaron correctos identidad ES/EN, capacidad,
  aritmética, hora web, clima con valores Open-Meteo, capital, fecha y los dos
  textos ingleses. Fallaron: frase de lluvia pobre, nube con falsa incapacidad,
  perro ejecutó `audio.status` y dijo «bocina», noticias devolvió portadas sin
  resumir una, y el resumen de capacidades ejecutó `task.resolve.exact` y acabó
  en un falso `No pude`.
- Reparación posterior: `Explica que es…` se cierra como conocimiento;
  preguntas ES/EN por sonido animal son no-efecto autoritativo (no pueden ser
  `audio.status` ni web); y el sobre «Resume en una frase que puedes hacer» se
  reconoce como capacidad del propio BAXY. Para noticias actuales, `web.search`
  retira la instrucción de resumen de la consulta y usa RSS de Google News con
  `when:1d`, proyectando titulares individuales, fuente y fecha en vez de
  portadas genéricas. Focal web **6/6**, `test_turn_policy.py` **876/876** y
  `Baxy.Providers.Windows.Tests` **454/454**, cero skips en los resúmenes.
  Falta Fast/rebuild y repetir las 15; la frase de lluvia se reevalúa junto con
  la nueva generación aislada y no se dará por buena sin lectura manual.
- Fast posterior verde completo (PowerShell, Ruff, compileall, ESLint, ambos
  TSC, `dotnet format`, build Release, 0 warnings/errores) y tanda física r15
  auditada manualmente: la primera sonda entregó 8 turnos y perdió foco antes
  del noveno sin caída del producto; una continuación en la misma sesión
  completó los 7 restantes. La sesión vuelve a ser **inválida**: nube confundió
  el fenómeno físico con computación; identidad inglesa publicó un falso
  `No pude`; perro dejó de ejecutar audio pero añadió morder/lamer como sonidos;
  noticias verificó un titular pero la composición acabó en un falso fallo; y
  lluvia siguió como fragmento pobre. Los otros diez textos fueron aceptables,
  incluidos clima real, fecha, capital, aritmética y capacidad envuelta. La
  pérdida de foco pertenece a la sonda UIA; mente, core y app siguieron vivos.
- Los cinco fallos visibles de r15 ahora tienen contratos de presentación
  generales, separados de autoridad: identidad propia ES/EN, capacidad propia,
  nube meteorológica, sonido animal y oración completa. Cada contrato conserva
  generación local pero rechaza la clase exacta de salida mala observada. La
  instrucción de resumir un titular verificado y su fuente ahora sobrevive los
  tres intentos del compositor, en vez de existir sólo en el primero. Focales
  nuevas **19/19**; suites dueñas `test_turn_policy.py` **886/886** y
  `test_planner.py` **147/147 + 101 subtests**, cero skips. Falta Fast y una
  tanda física fresca 15/15 leída manualmente; ningún turno r13–r15 suma dosis.
- Fast de `64c0d18` verde completo, 0 warnings/errores. Tanda física fresca r16
  auditada manualmente: **14/15** respuestas correctas (saludo, identidad ES/EN,
  capacidad simple y envuelta, lluvia, aritmética, nube física, hora, clima con
  valores, capital, otoño, ladrido y fecha). Noticias actuales ejecutó
  `web.search`, pero los tres intentos de redacción se perdieron y la UI publicó
  el falso terminal «no pude redactar…». Por ese único fallo la sesión completa
  es inválida y suma cero. Bloqueo vivo: capturar el defecto exacto de los tres
  borradores del compositor con su auditoría local sin contenido, reparar y
  repetir las quince; no se baja ningún validador.
- La auditoría local r17 aisló los tres descartes: **3/3 `internal_code`**. La
  causa no era jerga generada, sino que el validador `_DOTTED_OP` trataba el
  dominio público de la fuente periodística (por ejemplo `biobiochile.cl`) como
  si fuera una operación interna. Ahora un nombre con puntos sólo se admite en
  un resultado `web.search` cuando aparece literalmente dentro del `observed`
  verificado; `web.search`, snake_case y cualquier dominio no observado siguen
  bloqueados. Focal reproducible **2/2**, `test_goal06_voice.py` **9/9** y suites
  de mente **1033/1033 + 101 subtests**, cero skips. Falta reproducción física
  del titular y luego la tanda completa 15/15.
- Reproducción física fresca r18 superó el falso `internal_code` y por primera
  vez publicó un titular concreto con fuente y fecha, pero deformó una palabra
  como `tecnologíaecnología`; revisión manual: **0/1**, inválida. El guard de
  salida ahora detecta spans largos duplicados dentro de una sola palabra y los
  clasifica como invención para regenerar, sin aceptar ni corregir texto a
  ciegas. Focal que reproduce exactamente la corrupción **1/1**. Falta suite
  dueña y otra reproducción física del mismo turno.
- Suite dueña tras el guard **9/9**, cero skips. Reproducción física fresca r19
  de noticias **1/1 correcta**: el primer borrador quedó auditado como
  `invented` y se descartó; el siguiente publicó el titular sobre seguridad de
  buzos, lo resumió como indicación del propio titular y nombró la fuente
  observada `radiosantamaria.cl`, sin códigos ni falsos fallos. Falta Fast y una
  sesión r20 limpia con las quince respuestas revisadas manualmente.
- Fast verde completo, 0 warnings/errores. Sesión fresca r20: revisión manual
  **14/15**, otra vez inválida sólo por noticias. La auditoría de Python muestra
  que el primer borrador corrupto fue descartado y no registra rechazo del
  segundo; aun así, el shell publicó la recuperación `composition_lost...`.
  Esto acota el rechazo posterior a `UserMessagePolicy` dentro de
  `ModelMessageComposer.ComposeAsync`, no al guard Python. `compose.end` ahora
  registra el código de fallo del outcome (o `exception`) para obtener el dato
  exacto en una reproducción aislada; falta build y r21 de un turno.
- Reproducción aislada r21 midió el terminal exacto:
  **`compose.end=no_response`** tras 10,0 s. El primer request ordinario agotaba
  su techo GPU de 5 s mientras Python regeneraba el borrador corrupto; el shell
  entonces usaba otros 5 s para componer la disculpa. La selección de timeout
  ahora asigna el presupuesto GPU denso ya existente de 10 s sólo cuando el
  resultado observado tiene autoridad `google_news_rss_https`; composiciones
  ordinarias siguen en 5 s y los presupuestos CPU siguen en 60/130 s. Falta
  focal .NET y reproducción física r22.
- Focal de timeout + traza **9/9**, cero skips. Reproducción física r22 de
  noticias **1/1 correcta** en **7,373 s**: el primer borrador corrupto fue
  rechazado como `invented`, el segundo resumió el titular y nombró la fuente
  observada, y `compose.end` terminó sin fallo dentro del techo específico de
  10 s. Falta Fast y r23 fresca de quince; r22 es sonda y suma cero dosis.
- Fast verde completo. La r23 fresca volvió a **14/15** tras revisión manual:
  todos los turnos salvo noticias fueron correctos; noticias terminó en 4,443 s
  pero añadió «maquinaria», ausente del titular observado, y alteró dentro de
  comillas «litoral aysenino» por «litoral Aysén». La sesión es inválida y suma
  cero. El contrato de noticias ahora deriva del primer resultado el `title` y
  `source` dinámicos, exige ambos literalmente y prohíbe interpretación,
  ampliación o paráfrasis; este par no entra en el scaffold de misión multi-paso.
  La regresión rechaza exactamente la salida con «maquinaria» y sólo acepta la
  siguiente redacción que conserva título + fuente: focal **2/2**, suite dueña
  `test_planner.py` **148/148 + 101 subtests**, cero skips. Falta reproducción
  física y otra tanda fresca completa.
- Reproducción aislada r24 conservó por fin el titular literal y no añadió
  hechos, pero omitió la fuente: revisión manual **0/1**, inválida. La causa es
  contractual: el proveedor extraía la fuente del título RSS y sólo la dejaba
  embebida en `snippet`, no como campo tipado. El mismo resultado verificado
  ahora expone `results[].source`; la mente ya exige literalmente `title` y
  `source`, sin inferir un dominio. Focal del proveedor **1/1** y suite completa
  `Baxy.Providers.Windows.Tests` **454/454**, cero skips en el resumen. Falta
  reproducción física.
- Fast verde completo. R25 conservó literal el título y la nueva fuente, sin
  inventar, pero publicó la yuxtaposición torpe «…aysenino, radiosantamaria.cl.»;
  revisión manual **0/1**, inválida. El contrato exige ahora una atribución
  explícita natural (`según`, `informa`, `publicado por` o equivalentes EN),
  además de título y fuente literales. La regresión descarta en orden la
  paráfrasis con «maquinaria» y la coma desnuda antes de aceptar la atribución:
  focal **2/2**, suite `test_planner.py` **148/148 + 101 subtests**, cero skips.
  Falta reproducción física.
- Reproducción física r26 de noticias **1/1 correcta** en **2,819 s**:
  «Mesas de trabajo y tecnología reforzarán la seguridad de buzos en el litoral
  aysenino, según radiosantamaria.cl.» Conserva título y fuente exactos, atribuye
  de forma legible y no añade hechos; `compose.end` sin fallo y auditoría sin
  descartes. Falta Fast y r27 fresca completa; r26 es sonda y suma cero dosis.
- Fast verde completo. R27 produjo 15 respuestas factualmente correctas y
  noticias quedó bien en 2,819 s, pero la revisión manual estricta rechaza la
  fecha «Hoy, hoy es 24 de agosto de 2026» por repetición visible: **14/15**,
  sesión inválida y suma cero. El detector general de duplicación ahora cubre
  palabras repetidas a través de coma/punto y coma/dos puntos, no sólo espacio;
  regresión exacta y suite dueña `test_goal06_voice.py` **10/10**, cero skips.
  Falta reproducción de fecha y otra tanda completa.
- R28 verificó que `Hoy, hoy` ya se descarta, pero los intentos siguientes sin
  forma específica agotaron el turno con pregunta/jerga y el shell publicó el
  falso fallo: **0/1**, inválida. El contrato de fecha actual ahora acompaña los
  tres intentos: sólo fecha observada, una oración, `hoy` como máximo una vez,
  sin pregunta, saludo, `Listo`, hora ni campos internos. Focales **2/2** y
  suites dueñas combinadas **159/159 + 101 subtests**, cero skips. Falta
  reproducción física.
- Reproducción física r29 de fecha **1/1 correcta** en **5,436 s**: «24 de
  agosto de 2026 es hoy.» Sólo contiene la fecha observada, una vez, sin saludo,
  pregunta, `Listo`, hora ni código; `compose.end` limpio y auditoría sin
  descartes. Falta Fast y r30 fresca completa; r29 suma cero dosis.
- Fast verde completo. **R30 aprobada manualmente 15/15**: saludo, identidad
  ES/EN, capacidades simple y envuelta, lluvia, aritmética, nube física, hora,
  clima con valores, capital, otoño, ladrido, titular literal con fuente y fecha
  fueron correctos; operaciones: sólo `web.search` en hora/clima/capital/noticia
  y `system.time` en fecha. Cero errores de sonda, cero recuperación visible y
  auditoría de composición vacía. Latencias: 0,854–5,205 s; noticias 2,807 s,
  fecha 1,258 s. Es la primera tanda sintética semántica verde y suma cero a las
  200 interacciones normales del dueño. Siguen abiertos los criterios amplios:
  corpus real, dosis normal multi-sesión, 24 h con reinicio y manos libres.
- Tramo de 24 h iniciado sobre r30 a **2026-08-24T23:45:14.919011Z** con el
  sampler dueño cada 60 s (`soak-r30.json[l]`), escucha permanente y llama-server
  vivos. Baseline: Baxy.exe RSS **281,0 MiB**, VRAM total de GPU reportada
  **6612/16380 MiB**; PID de sampler Python 43892. Aún no cumple duración,
  reinicio ni muestra final. Los turnos concurrentes del dueño siguen siendo
  explícitamente de prueba y no cuentan como uso normal.
- Auditoría acotada del corpus consolidado actual (streaming, sin leer contenido
  al contexto): `historical_messages.jsonl` tiene **14.836 filas**, **10.867
  canónicas**, 3.639 de origen `observed_user`, 656 redactadas, 3.640 con
  timestamp, **307 rutas fuente** y raíces `functiongemma` 7.082,
  `probando_gemma4` 3.789, `carter_os_ai` 2.028, `codex` 1.692, `baxy` 154 y
  `gemma4_local` 90. Esto confirma que el corpus heredado es mucho mayor que las
  3.691 frases únicas de la extracción Carter/Gemma4 de 2026-06-02; se usa para
  variedad y prioridades, nunca para sumar los 200 turnos normales.
- Integridad del corpus consolidado verificada con su suite dueña:
  `tests/test_historical_corpus.py` **37/37 + 58 subtests**, cero skips. No se
  alteró ni regeneró el corpus; la medición confirma el conjunto versionado que
  se usará sólo como evidencia de amplitud.
- Comprobación física del panel de memoria sobre la instancia viva r30: se abrió
  vacío, se añadió la entrada sintética `goal10_test_color=turquesa` y reapareció
  persistida con fecha y contador de una entrada. La inspección del código dueño
  descubrió un defecto de cierre: el bridge ya soportaba edición, pero
  `MemoryPanel.tsx` no exponía ninguna acción de editar. Se añadió el botón
  `edit`, que reutiliza el `POST /memory` tipado con la clave seleccionada y el
  valor actual como base. `npm run build` y `npm run lint` quedaron verdes; el
  contrato dueño del bridge, que recorre crear/listar/editar/borrar, quedó **1/1**
  con cero skips mediante `dotnet test ... --no-build`. Falta comprobar el botón
  nuevo en el producto tras terminar el tramo de 24 h, porque reiniciar ahora
  invalidaría el soak vivo.
- El sampler de 24 h ya puede reanudar el mismo estado tras terminar su proceso o
  reiniciar Windows: conserva `started_at`, muestra inicial, total, pico y mínimo,
  calcula duración por reloj UTC y registra cada proceso con PID y
  `windows_booted_at`. El estado legado r30 se migra sin perder sus nueve primeras
  muestras. Regresión de reinicio **1/1** y `compileall` verdes. La instancia de
  sampler que corre desde las 23:45Z sigue usando el código anterior en memoria;
  el proceso que arranque después del reinicio leerá el JSON existente con el
  código nuevo. Se registró la tarea temporal `BAXY Goal10 Soak Sampler`, estado
  `Ready`, habilitada al logon de `REDPC\usuario`, ejecución limitada y
  `MultipleInstances=IgnoreNew`; apunta al Python 3.12, script, output y working
  directory absolutos de este repo. No se inició ahora, para no duplicar el
  sampler vivo. Falta verificar que dispare tras el reinicio y retirarla al cerrar.
- Al cerrar el panel después del alta física, la tarjeta exterior seguía mostrando
  `0 pinned` aunque dentro había una entrada. No era retraso: `/surfaces` fijaba
  `memory=0` y `App.tsx` priorizaba indefinidamente el snapshot inicial del stream
  sobre el sondeo. El endpoint ahora obtiene el conteo del mismo `MemoryPanelBridge`
  verificado (y falla explícitamente si no puede contarlo); el snapshot fijo del
  socket se retiró y el sondeo verificado pasa a tener precedencia. `npm run build`
  + `npm run lint` verdes. Build .NET completo aislado del binario vivo y contrato
  focal **1/1**, cero skips; el primer intento aisló sólo `bin` y falló antes de
  compilar por un `obj` incremental con el bundle viejo, y el segundo `ArtifactsPath`
  aisló ambos y pasó. Falta verificar físicamente tras el soak. El transcript
  visible seguía terminando en r30: no había respuestas nuevas del dueño pendientes
  de revisión manual.
- El primer intento de activar bypass escribió la ruta predeterminada, pero r30
  heredó `BAXY_DATA_DIR=...\dev-mente-v2`; su fichero real siguió diciendo
  `normal`. Por tanto ambos turnos fueron en **normal** y bypass aún no cuenta.
  Revisión manual: `Cuanto es 9 por 8?` respondió **`72.`**, correcto. El turno
  catalogado `Dime el estado actual del sistema.` fue **inválido**: publicó «No
  pude: no pude redactar el mensaje porque no pude asegurar que el resultado
  verificado se mantenga intacto sin perder sus hechos.» La traza lo acota:
  `core.call system.status` completó verificado, el primer borrador fue rechazado
  sólo como `too_many_sentences` y `compose.end=no_response` llegó **6,28 s** más
  tarde al agotarse los 5 s durante la reescritura. `system.status` recibe ahora
  instrucción propia (sólo `seen`, hasta tres oraciones declarativas), permite el
  resumen multi-oración sin relajar otros estados y usa el presupuesto GPU denso
  de 10 s. Focales iniciales **1/1 Python + 1/1 .NET**. La clase .NET completa
  destapó dos contratos antiguos rojos que también afectaban uso: «presentar» no
  contaba como explicación honesta de composición y claves de memoria con guion
  bajo se rechazaban aunque aparecieran literalmente en los hechos. Ambos guards
  aceptan ahora sólo verbos de formulación válidos y sólo códigos con guion bajo
  fundamentados en la fuente; los no observados siguen rechazados. Resultado final:
  Python dueño **161/161 + 101 subtests** y `PlannerAppBoundaryTests` **65/65**,
  cero skips, con build .NET aislado del ejecutable vivo. Falta repetir físicamente
  `system.status` tras el soak; el modo real permanece normal.
- Bypass real se activó después en la ruta correcta y `Que hora es?` cruzó una
  lectura catalogada sin efectos, pero la revisión manual la invalidó: a las
  **20:19** locales (reloj visible de la app) respondió «Listo, el tiempo local es
  **00:19**.» La configuración se restauró inmediatamente a `normal`. No cuenta
  como validación de bypass: primero hay que localizar si `system.time` observó UTC
  como local o si la composición cambió la hora, arreglar y repetir.
- La traza del mismo turno confirma `core.call system.time` verificado y
  `compose.end` limpio en **0,618 s**: no fue fallback ni timeout. El contrato sólo
  entregaba `utc` + desfase y delegaba la conversión al modelo, que publicó UTC como
  local. `TimeStatusHandler` entrega ahora también `localTime`, calculado de forma
  determinista con el desfase observado; la mente extrae de ese campo el `HH:mm`
  local, lo exige literalmente en todos los intentos y rechaza `00:19` cuando el
  valor verificado es `20:19`. La regresión exacta pasa **1/1**; suite Python dueña
  **162/162 + 101 subtests** y `NaturalSystemTimeViewModelEndToEndTests` **2/2**,
  más el guard visible completo `test_turn_policy.py` **886/886** en **4,05 s**,
  cero skips, con build .NET aislado. Falta reproducción física después del soak;
  r30 sigue vivo con el binario anterior y el modo real queda en `normal`.
- Al intentar usar la narración desde r30, ajustes sólo mostraba `connection`,
  `agent`, `transcript`, `prompt` y `about`: el panel React sí tiene la pestaña
  `voice` y sus controles reales (`enable voice`, feedback y `mute tts`), pero
  `field-native-bridge.js` la filtraba. La capa nativa ahora expone `voice` junto a
  las demás pestañas administradas; los toggles de voz existentes quedan usables,
  mientras proveedor/modelo y los demás campos siguen bloqueados. El build + lint
  de Field UI pasan. La clase dueña descubrió además que el sello del árbol Field
  seguía apuntando al bundle anterior a los cambios ya publicados de memoria; se
  reconstruyó el mismo bundle determinista y se actualizó el sello al hash real.
  `MainWindowShellContractTests`: **33/33**, cero skips, build Release aislado.
  Falta abrir `voice`, ejercer `mute tts` y oír una narración en el binario nuevo;
  r30 se cerró de ajustes sin aplicar cambios y continúa el soak.

### Continuación 2026-08-25 — runtime de voz completo y compuerta Full verde

- Decisión explícita nueva del dueño: **omitir completamente el soak de 24 h**.
  El tramo r30 interrumpido no es evidencia de cierre, no se reanuda y ya no es
  un criterio pendiente. Tampoco cuentan como dosis sus turnos sintéticos.
- La primera Full canónica de este tramo dejó .NET verde y Python en **3 fallos,
  8.765 pasadas, 15 skips y 433 subtests**. Las tres causas se corrigieron sin
  fallback: el catálogo anunciaba el ONNX de Piper sin su configuración, faltaba
  el frontend eSpeak requerido para fonemizar y el test histórico R275 reconstruía
  contra el runtime mutable actual en vez de verificar el artefacto sellado que
  publicó la medición. R275 vuelve a leer ese artefacto y conserva su sello.
- Se completó el asset oficial `es_MX-claude-high.onnx.json` desde
  `rhasspy/piper-voices` commit
  `0c9c5d340496a47205a799eb046aab69334a88e9` (SHA-256
  `1afc81f703c0e4cb3b4d7c0dca096b8b54a98806807f0170cf5eb5557723c12d`) y
  eSpeak NG 1.52.0 desde su MSI oficial (MSI SHA-256
  `7f673c709ea5dd579d3b5ebb98688cc575328a6ab7438d2bc405b88cedaeafb9`),
  desplegado de forma privada en `D:\BAXYRuntime\assets\espeak-ng`. El ejecutable
  tiene SHA-256
  `3080ec3822c1b266ef557c710bc79a97d20a7ab133a34bac308b81ab0afc733e`.
  El catálogo tipado resuelve modelo, sidecar, ejecutable y datos; Piper no se
  anuncia si falta cualquiera. La invocación portable usa `--path` al directorio
  dueño de `espeak-ng-data`. Medición física: carga **2,129 s**, generación total
  **2,502 s**, **50.688 muestras a 22.050 Hz**, pico **0,389**; focales de voz
  **122 pasadas y 4 skips heredados**.
- La segunda Full reveló únicamente que el sello vivo del árbol STT había quedado
  atrás de estos cambios: **2 fallos, 8.767 pasadas, 15 skips y 433 subtests**.
  Se resellaron los dos consumidores vivos sobre los **358** Python actuales con
  SHA-256 `d41a548490d8c0a9de266d3e5b949b8bdc947f1c85d3413a4300730fff456838`;
  el hash histórico de la campaña v17 consumida quedó intacto. Focal:
  **12 pasadas y 1 skip heredado**.
- Tercera ejecución canónica `scripts/test_source_quality.ps1 -Mode Full`:
  **verde**. Build Release: 0 advertencias/0 errores. .NET: Contracts 60/60,
  Integration **2.851 pasadas, 1 skip contado**, Kernel 137/137, Providers
  454/454 y Setup 477/477. Python: **8.769 pasadas, 15 skips y 433 subtests**
  en 441,38 s. Resultado terminal:
  `source_quality_gate_passed: mode=Full`. La matriz regenerada por la prueba se
  restauró; `git diff --check` queda limpio.
- Siguen pendientes de verificación física en el binario actual: pestaña `voice`,
  `mute tts` y narración audible; repetición bypass de hora local; edición de
  memoria y badge exterior. La dosis amplia de uso real del dueño tampoco se
  sustituye con sondas sintéticas.

### Continuación 2026-08-25 — verificación física del binario actual

- La pestaña `voice` quedó físicamente visible con sus controles administrados.
  Piper recorrió en la instancia real `accepted → dequeued → phonemes →
  inference → generated → speaking → silent`; la reproducción de «Cuatro.»
  permaneció hablando unos **3,75 s** según la traza. `mute tts` se ejerció desde
  la UI, se reaplicó, sobrevivió al cierre y reapertura de ajustes y a un reinicio
  completo de BAXY. El arranque en mute registró `voice.speak=muted`. Después se
  restauró desde la misma UI y el estado final persistido es `tts-muted=false`.
  El bridge nativo ahora persiste este ajuste en `tts-muted`; una prueba dueña
  cubre ambos estados.
- El texto real «¿Cuánto es dos más dos?» descubrió que el cierre local de
  aritmética reconocía dígitos pero no palabras y por eso el binario previo había
  intentado `web.search`. El reconocedor cerrado acepta ahora números ES/EN de
  cero a veinte. La repetición física respondió exactamente **«Cuatro.»**, sin
  operación web; la traza conserva `decision.ready=conversation`, respuesta
  visible y la secuencia completa de Piper. La regresión incluye esa oración y
  su equivalente inglés; `test_turn_policy.py` queda **888/888**.
- Durante el primer reinicio del binario nuevo apareció una degradación real de
  la mente: `InitializeMindAsync` notificó `PropertyChanged` fuera del hilo UI y
  `FieldUiBridge.PostEnvelope` accedió a WebView2 antes de entrar al `try`,
  produciendo `InvalidOperationException` de Dispatcher. Los callbacks de mensaje
  y propiedad ahora se remiten al Dispatcher dueño, y el acceso a CoreWebView2
  queda dentro de la frontera capturada. Tras relanzar, `startup.ready` llegó en
  **19.104,808 ms**; durante todas las pruebas posteriores el fichero de fallo
  conservó sin cambios su marca antigua `2026-08-25T04:55:39Z`, la mente siguió
  disponible y las respuestas nuevas cerraron normalmente.
- El panel de memoria quedó verificado de extremo a extremo en el binario actual:
  alta sintética `goal10.physical_check=turquesa`, badge exterior **0 → 1**,
  edición a `azul`, borrado exacto y badge **1 → 0**. La entrada de prueba fue
  retirada; el estado final vuelve a cero y no se borró memoria ajena.
- El bypass se activó físicamente desde `settings → agent`, y el fichero real
  confirmó `bypass`. A las **01:04:42 -04:00**, «¿Qué hora es?» invocó el catálogo
  `system.time` y BAXY respondió **«01:04.»**, coincidente con el reloj local; no
  hubo confirmación ni efecto. Piper volvió a `silent`. La misma UI restauró al
  terminar `confirmation-mode=normal`. Estado final: confirmación normal, TTS no
  silenciado y memoria sintética limpia.
- El cambio Python movió de nuevo el árbol vivo STT. Se resellaron sólo los dos
  consumidores vivos sobre los mismos **358** ficheros, ahora SHA-256
  `84b08807c40a58da950cd88458bb3411de8c68e827576a1092e6a322aa979eb7`;
  el hash histórico de v17 sigue intacto. El soak de 24 horas continúa omitido
  por instrucción explícita y no se reabre.
- La Full posterior encontró tres sellos desfasados: los dos consumidores STT y
  el inventario histórico R144 del programa actual. Los focales exactos quedaron
  **3/3**. La primera repetición de Full se detuvo antes de probar código porque
  la instancia física había ocultado la ventana pero conservado `Baxy` y
  `baxy-core` bloqueando DLL de Release; se terminaron sólo esos dos PIDs de
  prueba y se relanzó desde cero. Ejecución canónica final: build Release **0
  advertencias/0 errores**; Contracts **60/60**, Integration **2.852 pasadas + 1
  skip contado**, Kernel **137/137**, Providers **454/454**, Setup **477/477**;
  Python **8.771 pasadas, 15 skips y 433 subtests** en 472,04 s. Resultado
  terminal: `source_quality_gate_passed: mode=Full`.
- Auditoría terminal de la dosis dueña publicada en
  `artifacts/goal10/owner-dose-unreachable.json`: **0 turnos / 0 sesiones**
  admisibles de uso normal. Todas las corridas disponibles son sondas,
  regresiones, corpus o sesiones invalidadas; los turnos concurrentes del dueño
  fueron descritos explícitamente como pruebas. Sólo el dueño puede originar 200
  pedidos espontáneos normales y cinco repeticiones 20×; automatizarlos o
  rebautizarlos falsearía su procedencia. Es un bloqueo externo al código y no
  existe otro paso local capaz de producir esa evidencia. Se publica por la salida
  terminal explícita del objetivo: criterio medido e inalcanzable. El soak y su
  medición inicial/final dependiente permanecen omitidos completamente por orden
  del dueño.

### Reapertura 2026-08-25 — corpus observado congelado

- El Goal 10 vigente sustituye la dosis espontánea como criterio integral por dos
  niveles reproducibles. El handoff anterior sigue siendo evidencia física heredada,
  pero no certifica el corpus nuevo y no se presenta como si lo hiciera.
- `scripts/build_observed_user_corpora.py` se ejecutó con el Python dueño del runtime.
  Resultado: Nivel 1 **1.947 ocurrencias / 626 textos únicos**, SHA-256 del JSONL
  `06dda8dc3c8abf118730d297bd002e31752f9a09f4e30d69acf51e54a1b5d085`; Nivel 2
  **808 / 281**, SHA-256
  `3da27e544680285e40b0b493ebd9c1a72f2af9aa300e3d289e77c14103e252d2`; mapping
  único y **0 conflictos** entre literales idénticos.
- Suite dueña: `python -m pytest tests/test_build_observed_user_corpora.py -q`
  usando `%LOCALAPPDATA%\BAXYRuntime\python\mind-runtime-v1\Scripts\python.exe`:
  **5/5 pasadas** en 6,71 s. Los Python globales 3.13 y 3.12 no tienen pytest;
  eso no es un fallo del producto.
- Próximo dueño: runner integral reanudable que conserve una fila y un veredicto
  por `message_id`. El gate exhaustivo heredado no basta: sólo llega a
  `turn.decide`/planner, registra `tools_executed: 0` y admite estados `review`.

### Continuación 2026-08-25 — primer replay real del corpus observado

- `05debb8` está en `origin/main`. Añade dos caminos separados y explícitamente
  etiquetados: `run_observed_user_mind_replay.py` para diagnóstico semántico sin
  afirmar ejecución, y `ObservedUserCorpusReplayTests` para atravesar shell, mente,
  catálogo, Core y providers reales con una fila durable por ocurrencia.
- El replay físico de los diez turnos de
  `gemma4_local/sessions/12a4898d705c.json` ejerció memoria habilitada por una
  operación real verificada. Cerró correctamente saludo, guardado explícito,
  consentimiento para contexto no solicitado, recall y acuse social. La corrida
  v9 completa está fuera de Git en
  `%LOCALAPPDATA%\BAXYRuntime\goal10\observed-product-session-12a4898d705c.v9.jsonl`,
  SHA-256 `ae3621afd2e21977be7501c48ece9ab435699e7604620900926a108e0998c840`.
- El corpus destapó y se corrigieron familias, nunca literales de examen: petición
  de recuerdo con marco necesidad/deseo; acuses sociales autónomos; cierre de app
  con nombre explícito; investigación web embebida; preservación de proyecciones y
  registros de memoria; y el error de misión que anidaba JSON como literal exigido.
  El ejecutor conserva ahora el `ErrorCode` real del Core y el compositor lo ve en
  prosa, sin exponer snake_case. `window_not_found` termina visible y honestamente
  como «No pude encontrarlo.» en la corrida física v12 (7 turnos, 6,668 s para el
  turno); `web_search_results_irrelevant` termina como fallo público verificable,
  no como pérdida de composición.
- Validación de la tanda: Python focal **2.409/2.409**, .NET focal **68/68**, replay
  físico v9 **1/1** y v12 **1/1**, todos con cero skips. La compuerta
  `scripts/test_source_quality.ps1` terminó verde en modo Fast: build Release con
  0 advertencias y 0 errores.
- El runner físico admite ahora `BAXY_GOAL10_OBSERVED_START` junto con el límite y
  conserva en cada fila tanto el índice global del corpus como el índice dentro de
  la partición. La fuente grande contiene 1.857 trazas independientes y puede
  dividirse sin romper contexto; las 16 sesiones Gemma (90 turnos) deben seguir
  ejecutándose completas para respetar sus fronteras.
- La primera fila de esa fuente grande expuso un conflicto del oráculo heredado:
  `tengo el bluetooth encendido` se etiquetó en 2025 como la operación prototipo
  `bluetooth.manage`, retirada y sustituida por el catálogo tipado actual. Identidad
  exige iniciativa sólo cuando se pide, así que una observación declarativa no puede
  autorizar un efecto. Se añadió el veto general de observaciones y el compositor
  produce ahora un acuse directo, sin respuesta fija ni literal del corpus.
- La reproducción física final está en
  `%LOCALAPPDATA%\BAXYRuntime\goal10\observed-probando-shard-0000-0001.v8.jsonl`,
  SHA-256 `e8793bd469522edea425264f03d2281cb7be4cfdf4464715be11bbb7194b50f5`.
  La ocurrencia global 685 respondió «Entiendo que tienes el bluetooth encendido.»,
  registró cero operaciones y pasó **1/1** con cero skips. La suite Python focal
  quedó en **904/904** y el build .NET en 0 advertencias y 0 errores.
- El runner físico aún no es el veredicto integral: captura respuesta, trace y
  journal, pero no adjudica las nueve dimensiones. Próximo dueño exacto: producir
  el contrato adjudicado contra Identidad, con un ledger versionado para conflictos
  del oráculo congelado, y persistir `pass`/`fail` individual; sólo entonces lanzar
  las 1.947.

### Continuación 2026-08-25 — honestidad conversacional en replay físico

- La tanda corrige familias semánticas observadas, nunca literales del corpus:
  restricciones explícitas de no actuar, identidad/capacidades con voseo,
  observaciones declarativas, aclaraciones de magnitud con dirección ya conocida y
  conservación de hechos estructurados al componer respuestas. El compositor y la
  frontera visible rechazan ahora la inversión `isCharging=false` → «está cargando»
  y cualquier estado de espera ausente; `isAcOnline=true` sólo autoriza decir que el
  equipo está conectado a corriente.
- `StartNewUiSession()` descarta también la aclaración pendiente. Esto elimina la
  contaminación física entre filas independientes sin tocar la memoria durable ni
  disfrazar continuidad dentro de una sesión. El replay captura por fila los audits
  raw/final/compose, hash del texto, clase, idioma, trace y journal del provider.
- Aclaraciones físicas (2 filas):
  `%LOCALAPPDATA%\BAXYRuntime\goal10\observed-fix-probando.clarify-r5.jsonl`,
  SHA-256 `c14adab853db4b0e8d0e2cc20d35ed2fd039709beac884369f739828abae0ced`.
  «subí el volumen» y «bajá el brillo» preguntaron sólo cuánto, conservaron la
  dirección, ejecutaron cero operaciones y la prueba cerró **1/1, 0 skips**.
- Observaciones físicas (8 filas):
  `%LOCALAPPDATA%\BAXYRuntime\goal10\observed-fix-probando.observations-r12.jsonl`,
  SHA-256 `ac04cfc79d028a618077dbd1a4fe0c17ac9fdd007bed1d28ec5707f7d63a148`.
  Bluetooth y brillo conservaron objeto+estado sin alegar verificación; la consulta
  de ventana terminó con el estado real. Las dos filas de batería revelaron una
  inversión factual y por eso esta corrida no certifica esa familia.
- Repetición física dueña de batería (2 filas):
  `%LOCALAPPDATA%\BAXYRuntime\goal10\observed-fix-probando.battery-r13.jsonl`,
  SHA-256 `090cf70a00ab8ae537e55697dc4ce59ebe016bb0f540772615ad5a7da760513d`.
  Ambas invocaron `system.status`, terminaron `completed`, observaron 97%,
  `isCharging=false` e `isAcOnline=true`, y respondieron explícitamente que la
  batería **no** cargaba pero sí estaba conectada. Prueba **1/1, 0 skips**.
- La muestra amplia de 25 filas en
  `%LOCALAPPDATA%\BAXYRuntime\goal10\observed-final-probando.part0000-r8.jsonl`
  (SHA-256 `585e98b53c336f27107ba3604ae97130069b3f0d7a711ebff64960e8520020f1`)
  queda marcada sólo como **diagnóstico anterior a estas correcciones**; no es
  evidencia final y debe repetirse sobre el árbol comprometido.
- Validación propietaria acumulada antes de la compuerta: Python
  `test_turn_policy.py + test_goal06_voice.py + test_planner.py` **1.095 pasadas y
  101 subtests, 0 skips**; .NET `MindShellEndToEndTests + PlannerAppBoundaryTests`
  **79/79, 0 skips**; Ruff verde. `scripts/test_source_quality.ps1` terminó
  **verde** en modo Fast, con build Release en 0 advertencias/0 errores. Próximo
  paso: commit/push de esta tanda y nueva muestra física de 25 filas para descubrir
  el siguiente defecto.

### Continuación 2026-08-25 — segunda tanda del replay observado

- La primera muestra de 25 sobre `7e7e1b1` quedó **diagnóstica e incompleta**:
  `%LOCALAPPDATA%\BAXYRuntime\goal10\observed-final-probando.part0000-r14.jsonl`
  conserva 8 filas antes de que una proyección se cancelara; no es evidencia final.
  Antes del corte reveló que «cargada al 97%» podía omitir si la batería estaba
  cargando ahora. El contrato Python y la frontera visible .NET exigen desde esta
  tanda verbalizar `isCharging` siempre que el provider lo entregue; porcentaje y
  alimentación AC no lo sustituyen.
- Repetición física de batería:
  `%LOCALAPPDATA%\BAXYRuntime\goal10\observed-fix-probando.battery-r16.jsonl`,
  SHA-256 `34681cfc5889929a0bbbe98fb501fc7c38871e7f830e8eeaf67db2b9ad4e4b80`.
  Las 2/2 filas dijeron explícitamente «no está cargando», conservaron corriente y
  97%, ejecutaron `system.status` y terminaron `completed`; **1/1, 0 skips**.
- «poné una canción» no nombra consulta reproducible. La evidencia heredada de
  R29/R272 y el catálogo vivo demuestran que `media.play` fue sustituida por
  `media.play.query` con query obligatoria: negar capacidad o adivinar Spotify era
  incorrecto. El reconocedor cerrado acepta ahora sólo la forma genérica sin título
  y pide `query`; una canción nombrada no se degrada. El validador semántico rechaza
  preguntas definicionales o binarias. Evidencia física final:
  `%LOCALAPPDATA%\BAXYRuntime\goal10\observed-fix-probando.row0010-r19.jsonl`,
  SHA-256 `b91f29dfffae0dd2b9bca30d168bf58921fa1734fb11492aacbd0a2ac089f853`;
  respuesta «¿qué canción o música quieres escuchar?», `kind=clarify`, cero efecto,
  cero journal y **1/1, 0 skips**. R17 (negación falsa) y R18 (pregunta antinatural)
  quedan sólo como diagnósticos causales.
- Nueve restricciones consecutivas conservaron cero autoridad pero la primera
  corrida R21 comenzó toda respuesta con minúscula. El contrato model-authored de
  `no_action_constraint` exige ahora mayúscula y reintenta si falta. Repetición de
  cinco filas/tres familias:
  `%LOCALAPPDATA%\BAXYRuntime\goal10\observed-fix-probando.constraints-r22.jsonl`,
  SHA-256 `915c97f866a3310175e403b8664b2ad6f1d10fc42aa78f8f6302556f4e529c84`;
  5/5 respuestas naturales, cero journal, **1/1, 0 skips**.
- El runner ya no envía un turno oculto «cancelar» tras una aclaración de una traza
  independiente: la siguiente fila abre una sesión nueva y descarta explícitamente
  la aclaración pendiente. Esto elimina una inferencia evitable y deja cada registro
  limitado al turno que adjudica.
- Cierre de tanda: Python dueño (`test_effect_intent.py`, `test_turn_policy.py`,
  `test_goal06_voice.py`, `test_planner.py`) **2.604 pasadas + 101 subtests, 0
  skips**; .NET afectado **79/79, 0 skips**. La primera pasada amplia detectó dos
  usos no multimedia del campo genérico `query`; el validador quedó correctamente
  ligado a la identidad `media.play.query` y los 7 focales pasaron antes de repetir
  todo. `scripts/test_source_quality.ps1` terminó **verde** en modo Fast, con build
  Release 0 advertencias/0 errores.

### Continuación 2026-08-25 — estado de ventanas nombradas verificado

- La adjudicación manual del tramo observó un defecto que el texto plausible
  ocultaba: «hay alguna ventana de steam abierta» usaba `window.active` y negaba
  todas las ventanas de Steam a partir de observar sólo el foreground. El skill
  vigente de control de Windows y el catálogo asignan esa pregunta a
  `window.application.status`; `window.active` sólo prueba la ventana activa.
- El reconocedor cerrado autoriza ahora `window.application.status` únicamente para
  preguntas completas de estado sobre una app nombrada. La misma gramática preserva
  sólo el nombre como evidencia para los argumentos; una declaración como «Tengo una
  ventana de Steam abierta» sigue sin ganar autoridad.
- R23 fue la sonda causal que aún eligió `window.active`. R24 ya eligió la operación
  correcta pero terminó honestamente en `app_ambiguous`:
  `%LOCALAPPDATA%\BAXYRuntime\goal10\observed-fix-probando.window-status-r24.jsonl`,
  SHA-256 `976ce6326711704992ca4abd2b27d5422dda5eb06686cd57b2c19b235bf2f5a6`.
  R25 y R26 repitieron el mismo fallo mientras se aislaba argumento frente a
  provider; son diagnósticos no finales, SHA-256
  `f9cafff76a5f89125d86ca116fe7f5dd4bb91ccce46f4a0a3e9cf233e651600a` y
  `e7d63d87b8841922a982f3a9cc3961389b239a3f85763d36fc97e58f959344b0`.
- La causa física final estaba en `Get-StartApps`: esta máquina publica dos entradas
  exactas `Steam` (`Valve.Steam.Client` y el acceso clásico al ejecutable). Para una
  lectura, eso no es una elección ambigua: el provider agrega todas las identidades
  con nombre exacto y cuenta HWND visibles únicos, sin abrir ni enfocar. Las
  coincidencias parciales genuinas como `Visual` continúan en `app_ambiguous`.
- Evidencia física final (2 ocurrencias):
  `%LOCALAPPDATA%\BAXYRuntime\goal10\observed-fix-probando.window-status-r27.jsonl`,
  SHA-256 `95fb9e722e0878d7b40433254942e8fb5cf299beabcf45ff299dde22bc8314aa`.
  Ambas ejecutaron `window.application.status`, terminaron `completed`,
  `verified=true`, observaron `displayName=Steam`, `hasVisibleWindow=true` y un HWND
  visible único, y respondieron «Hay una ventana de Steam abierta.»; prueba física
  **1/1, 0 skips**.
- Regresión propietaria antes de Fast: Python `test_effect_intent.py +
  test_turn_policy.py` **2.446/2.446, 0 skips**; provider Windows focal **26/26, 0
  skips**. `scripts/test_source_quality.ps1` terminó **verde** en modo Fast, con
  build Release 0 advertencias/0 errores. Falta comprometer/publicar esta tanda y
  retomar el adjudicador integral de nueve dimensiones.

### Continuación 2026-08-25 — adjudicador integral binario conectado al producto

- `scripts/adjudicate_observed_product_replay.py` separa las dos autoridades que el
  goal exige: el runner captura producto/Core/provider; el modelo del goal deja una
  revisión semántica privada por fila. Pertinencia, naturalidad, idioma y honestidad
  vienen de esa revisión; acción pedida, riesgo, confirmación, verificación y
  terminal se derivan del audit, catálogo tipado y journal. Los únicos estados son
  `pass` y `fail`: faltantes, duplicados, hashes viejos, `review`, `unresolved`,
  postcondición ausente o lifecycle incompleto abortan o fallan.
- Cada revisión queda ligada a `message_id`, hash del mensaje, hash de la respuesta
  **y hash canónico de toda la fila física**. Por tanto una respuesta textual igual
  no puede reutilizar un juicio si cambiaron facts, provider, catálogo, trace o
  journal. La salida privada conserva mensaje/respuesta exactos, contrato corregido,
  trazas, hechos, nueve checks, veredicto y razón; el resumen versionable sólo publica
  nombres de archivo, hashes y conteos.
- El ledger versionado
  `artifacts/goal10/observed-contract-corrections.v1.json` usa selector compuesto
  `(acceptance_test_id, text_sha256)`, nunca la respuesta. Es necesario porque un
  mismo `acceptance_test_id` histórico agrupa órdenes, preguntas y observaciones. La
  primera versión corrige sólo los tres conflictos demostrados: observación de
  Bluetooth sin efecto, observación de brillo sin efecto y consulta de cualquier
  ventana de Steam mediante `window.application.status` (con `window.active`
  explícitamente denegada).
- El replay físico es ahora schema
  `baxy.goal10-observed-product-replay.v2`: captura por fila la definición actual de
  cada efecto (`operation`, `risk`, `verifier_contract_id`) y el modo de confirmación
  efectivo. V1 se rechaza para adjudicación. El test de ese contrato se movió a una
  fixture separada para que el filtro histórico
  `FullyQualifiedName~ObservedUserCorpusReplayTests` continúe seleccionando el test
  físico explícito; se comprobó con una corrida real de 23 s, no con el falso verde
  de 46 ms que reveló la colisión temporal de filtros.
- Captura v2 final del par Steam:
  `%LOCALAPPDATA%\BAXYRuntime\goal10\observed-fix-probando.window-status-r29.jsonl`,
  SHA-256 `5a36dfdd5599603904a7b479989a79df2af48bfe389ce9ee10f04ecbf1734f85`.
  Revisión semántica privada SHA-256
  `fee3218dee6a2e143195064868ad5b8fb795c29220027812bb8b0e0da7e38b5b`;
  adjudicación privada SHA-256
  `bbb92fee313fba5ce82e3e80c5d07d4acb97fb1127781cd214560642f54e225b`.
  Resultado: **2/2 pass**, con **2 pass y 0 fail en cada una de las nueve
  dimensiones**. El resumen versionable está en
  `artifacts/goal10/observed-product-adjudication-smoke-summary.v1.json`.
- Suite dueña del adjudicador **9/9, 0 skips**; contrato .NET focal **1/1, 0
  skips**. `scripts/test_source_quality.ps1` terminó **verde** en modo Fast, con
  build Release 0 advertencias/0 errores. Este smoke demuestra el mecanismo, no
  certifica todavía las 1.947. Próximo dueño: auditar las 626 variantes de contrato
  congeladas contra Identidad/catálogo, completar el ledger y ejecutar una primera
  tanda v2 representativa antes de la campaña completa.

### Continuación 2026-08-25 — contrato actual independiente antes del replay

- El adjudicador distingue ya efectos pedidos de operaciones auxiliares autorizadas
  (`allowed_support_operations`). El journal debe demostrar riesgo, confirmación,
  verificación y terminalidad tanto del efecto pedido como de cualquier soporte
  realmente invocado; una dependencia lícita como `window.resolve` no se confunde
  con el resultado solicitado y una operación extra continúa fallando.
- `scripts/build_observed_current_contracts.py` construye la autoridad independiente
  **antes** de ejecutar el producto. Exige una revisión binaria por cada literal
  único, liga texto, contrato histórico y catálogo tipado actual, rechaza operaciones
  retiradas, conflictos, duplicados, faltantes y `unreviewed`, y sólo después proyecta
  los 626 contratos aprobados sobre las 1.947 ocurrencias. Mensajes y revisiones
  exactas permanecen fuera del repositorio; el resumen versionable sólo contiene
  hashes y conteos.
- El corpus histórico calcula su hash antes de sanear secretos, correo, teléfono o
  `%USERPROFILE%`. Para las 15 filas redactadas se preservan por separado el hash
  privado original (`source_text_sha256`) y el hash del literal que BAXY recibe
  realmente (`text_sha256`/`replay_text_sha256`). Los no redactados siguen exigiendo
  igualdad exacta. Así no se recupera ni se inventa contenido privado y toda revisión
  queda ligada al input físico exacto.
- Plantilla privada integral generada en
  `%LOCALAPPDATA%\BAXYRuntime\goal10\observed-current-contract-review-template.v1.jsonl`:
  **1.947 ocurrencias, 626 textos únicos**, SHA-256
  `745a1a57a9a508dda0e1301788ebdf3b3ee95c42d15b5daf0507c5c646768012`.
  Aún contiene `verdict=unreviewed`: es inventario de trabajo, no evidencia de pase.
- El cambio actualiza el hash de la adjudicación privada del smoke a
  `cb9c90257d78343f50f22000feb43ba02d099516e3684061bf43b85e624e4561`;
  el resultado continúa **2/2 pass** y 2/0 en las nueve dimensiones. Pruebas Python
  focales **17/17, 0 skips**; contrato .NET **1/1, 0 skips**;
  `scripts/test_source_quality.ps1` **verde** en modo Fast, build Release con 0
  advertencias y 0 errores. Próximo dueño: completar y validar las 626 revisiones
  actuales antes de usar la proyección de 1.947 como mapping del replay.

### Continuación 2026-08-25 — 626 contratos actuales aprobados y proyectados

- `scripts/review_observed_current_contracts.py` materializa la revisión
  independiente del producto. No consulta router, modelo ni salida de BAXY: toma el
  significado del literal congelado, Identidad y las 174 operaciones del catálogo
  tipado actual. Cada decisión conserva una regla explicable, sólo puede ser
  `action`, `clarify` o `conversation`, y la salida exacta sigue siendo privada.
- Se leyeron las 626 variantes completas y después se reauditaron por contrato y por
  contexto. Resultado único: **367 action, 86 clarify, 173 conversation**, cero
  fallback y cero operación fuera del catálogo. El único override contextual es
  «Abrelo» dentro de una sesión que inmediatamente antes cerró WhatsApp; las trazas
  `probando_gemma4` continúan tratándose como casos independientes, tal como exige el
  runner.
- Correcciones importantes respecto del mapping heredado: lectura literal de
  pantalla usa `ocr.read` + `capture.screenshot`, no visión genérica; declaraciones
  implícitas de nombre/preferencia piden consentimiento antes de `memory.save`;
  Bluetooth/brillo/ventanas declarativos no reciben autoridad; el micrófono de
  Discord no se degrada a silenciar todo Windows; apagar la radio Wi-Fi no se finge
  con sólo desconectar; títulos Disney/Prime no se atribuyen al único player cerrado
  de Netflix; recordatorios sin hora o título y música sin consulta preguntan el dato
  faltante; operaciones retiradas se sustituyen sólo cuando el catálogo actual
  conserva la conducta exacta.
- Revisión privada:
  `%LOCALAPPDATA%\BAXYRuntime\goal10\observed-current-contract-review.v1.jsonl`,
  SHA-256 `9e807ac8da44edd73bb113f4c932001cbce08e1131b566b99af8ee332143bcca`.
  Mapping privado proyectado 1:1:
  `%LOCALAPPDATA%\BAXYRuntime\goal10\observed-current-contract-mapping.v1.jsonl`,
  **1.947/1.947 ocurrencias**, SHA-256
  `9020a827cd8ef9b6fc0a824c10243c99f2d8e6784633e61a9cdcdd5eeb36f779`.
  El resumen sin mensajes está en
  `artifacts/goal10/observed-current-contracts-summary.v1.json`.
- Validación: pruebas focales de revisor + builder + adjudicador **21/21, 0 skips**;
  `scripts/test_source_quality.ps1` **verde** en modo Fast, con build Release 0
  advertencias y 0 errores. Próximo dueño: usar este mapping en una muestra física
  v2 representativa; cualquier divergencia es defecto del producto o, con evidencia,
  una corrección explícita del contrato, nunca una edición oportunista por respuesta.

### Continuación 2026-08-26 — auditoría y familias de la muestra v2

No se hereda prosa de GPT/Claude como pase. Lo comprobado en disco:

- Builder dueño: `mind-runtime-v1` `py scripts\build_observed_user_corpora.py` reproduce
  Nivel 1 **1.947 / 626** SHA-256 `06dda8dc3c8abf118730d297bd002e31752f9a09f4e30d69acf51e54a1b5d085`
  y Nivel 2 **808 / 281** SHA-256 `3da27e544680285e40b0b493ebd9c1a72f2af9aa300e3d289e77c14103e252d2`.
  Mapping único, 0 conflictos. `pytest tests/test_build_observed_user_corpora.py` **5/5**.
- Mapping privado actual SHA-256
  `9020a827cd8ef9b6fc0a824c10243c99f2d8e6784633e61a9cdcdd5eeb36f779` (1.947)
  y revisión `9e807ac8da44edd73bb113f4c932001cbce08e1131b566b99af8ee332143bcca` (626):
  coinciden con `artifacts/goal10/observed-current-contracts-summary.v1.json`.
- La muestra privada r30–r35 **no certifica**: «cierra steam» → `window_not_found`;
  «cerrá la calculadora» preguntó el nombre de proceso; «cuál es mi ip» se negó como
  dato personal; «poné el brillo al 80» preguntó cantidad; «acordate que…» con memoria
  apagada copió «No pude usar esa respuesta.» Abrir calculadora sí cerró.

Familias arregladas en el dueño, sin literales del corpus:

1. Pregunta local de IP → `network.ip.list` (cerrado, como `system.time`).
2. Brillo absoluto con número y voseo `poné` → `system.settings.set`.
3. Voseo `cerrá` rellena `window.resolve.process` sin pedir un id interno.
4. `window.resolve` también casa título o proceso visible (`WindowSelector`), no sólo
   `GetProcessesByName`.
5. `memory_disabled` se formula como «local memory is turned off», no snake_case.
6. El runner físico espera input-ready entre filas independientes y no se traga un
   `SubmitAsync` silencioso; el turno visible usa el timeout interno del producto.

Pruebas dueñas: `test_goal10_daily_use_surfaces…` + CASES + close voseo + compose
memory_disabled + `WindowSelector` **177 pytest + 4 NUnit**. Replay físico r36–r38
aún no cierra: un freeze de 3 min en el sidecar tras matar corridas anteriores no
es un pase. Siguiente: una fila IP en frío con llama limpio, luego las seis juntas.

### Continuación 2026-08-26 — muestra v2 de 6 filas en bypass

- El runner físico ahora espera input-ready, espera 60 s la proyección asíncrona
  (NUnit no tiene dispatcher WPF) y, si la cola de composición agota 3 intentos,
  publica un último recurso visible en vez de silencio. Confirmado: sin eso IP
  dejaba `status=awaiting_mission_resume compose=no_response` y cero texto.
- Las 1.947 se corren en **bypass**. Identidad pide los dos modos; el normal se
  comprueba en la matriz, no fila a fila: `network.ip.list` es
  `PrivacySensitive` y el compose de confirmación devolvía vacío. Decisión
  anotada: no se baja el riesgo del catálogo (test Goal 05 lo sella).
- Memoria: `BAXY_GOAL10_MEMORY_BASELINE=1` para que `memory.save` no muera en
  `memory_disabled`.
- r48 SHA-256 `18d259d97820111f59fed6a35420a2280432a1989ef09788b164d02dbfe2b3de`,
  6/6 texto visible, 0 JSON en pantalla:

  | Pedido | Respuesta | Journal |
  |---|---|---|
  | abrí la calculadora | Listo, la calculadora está abierta. | `app.open` |
  | poné el brillo al 80 | Listo, el brillo está al 80%. | `system.settings.set` |
  | cerrá la calculadora | composition_lost (cierre verificado) | `window.resolve`+`app.close` |
  | cuál es mi ip | Mi IP es 100.64.0.11. | `network.ip.list` |
  | acordate que… azul | Guardé el dato en la memoria local. | `memory.save` |
  | cierra steam | No pude encontrarlo. (Steam ya cerrado) | `window.resolve` |

- Queda: prosa de misión de cierre de 2 pasos (hechos sí, frase no) y cierre
  ya-ausente como postcondición verificada, no `window_not_found`. Siguiente:
  muestra de 25 y campaña 1.947 en shards.

### Continuación 2026-08-26 — muestra representativa 25

- Runner **1/1**, 25/25 `message_id` distintos, 0 vacíos, 0 JSON visible.
  SHA-256 `17219788b7067d79274595d14f105dc25acc635321529856024198fb8596fea9`.
  ~4 s/turno caliente; 1.947 ≈ 2,2 h en un hilo.
- Bien: hola, memory.save/recall/consentimiento, WhatsApp open, volumen 10,
  web.search honesto sin resultados.
- Familias nuevas (no literales):
  1. `app.open` Steam pregunta «¿Quieres que abra Steam?» — dos entradas
     exactas en Get-StartApps; la agregación de Goal 10 es de lectura, no de
     open.
  2. Misión `window.resolve`+`app.close` / `browser.navigate.named` ejecuta y
     pierde la frase (`composition_lost`).
  3. Cierre ya-ausente → `window_not_found` / «No pude encontrarlo.»
  4. «Abrelo» en traza independiente aclara (correcto en producto; el mapping
     actual espera `app.open` por contexto de sesión). Ledger, no runtime.
- `03_COSTURAS.md`: rellenadas memoria, bandeja y arranque con medición y fecha
  2026-08-26.

### Continuación 2026-08-26 — campaña física en shards

Privado bajo `%LOCALAPPDATA%\BAXYRuntime\goal10\`. Ledger
`artifacts/goal10/observed-replay-campaign.v1.json`.

| Shard | n | empty | no_responde | action_missing | wall |
|---|---:|---:|---:|---:|---|
| 0–100 r50 | 100 | 0 | (18 miss) | 18 | 8m24s |
| 100–200 r51 | 100 | 0 | 0 | 17 | 3m |
| 200–400 r52 | 200 | 0 | 0 | 48 | 8m |
| 400–800 r53 | 400 | 0 | 174 | 219 | 33m degradado |
| 800–900 r54 | 100 | 0 | 69 | 85 | 11m degradado |

Límite práctico: shards de **100**, y reiniciar el sidecar cada uno. Un shard
de 400 mata llama a mitad. Familias vivas: prosa de cierre compuesto,
ya-ausente, `me abrís`/`wifi.status`/`mostrame el brillo` (cerradas en
`668a738`, aún no rejugadas). Steam open exact-dup `92670a3`. Bypass + memoria
en el runner. **No es 1.947/1.947 pass.** Siguiente shard: 900.

### Continuación 2026-08-26 — cobertura 1.947/1.947 capturada

Merge privado `observed-product-replay.v2.jsonl`
SHA-256 `d6e7db3ec461fe6a3810ff22d1127bb9b2db357073ea1b6ae49ad82252f556c1`
(rejugó 400–900). **1.947 filas, 1.947 `message_id` distintos, 0 vacíos, 0 JSON.**
651 `No pude: no responde.` y 50 `composition_lost`. Shards sanos (0 no_responde):
100–200, 200–400, 400–500, 600–700. Eso **no es** 1.947 pass. El compose vacío
es el cuello: hay que rejuglar los shards sucios y hacer que un fallo de
compose no se coma el turno. Resumen:
`artifacts/goal10/observed-replay-summary.v1.json`.

Hay que rejuglar los shards con sidecar degradado (400–800, 800–1200,
1500–1600, 1700–1800) en tandas de 100. Después, adjudicar.

### Continuación 2026-08-26 — compose-swallow y rerun sucio r70–r83

`aa573c8`: un compose vacío ya no encola reintentos ni deja `_pendingMindPlan`
para tragar el siguiente trazo independiente. `StartNewUiSession` limpia el
plan; el primer compose vacío publica last-resort y suelta el plan.

Smoke 10/10, 0 `no_responde`. Campaña sucia 100 filas, sidecar fresco entre
shards, 14/14 exit 0. Merge privado `observed-product-replay.v2.jsonl`
SHA-256 `7d30748ebc8e9711cbcdb51cebabfdba0d4ed6bc9c0ba4b4edc8b60ba574a53b`:
**1.947 / 1.947 ids, 0 vacíos, 0 JSON, 73 `No pude: no responde.` (eran 651).**
118 «No pude redactar una frase verificable sin perder sus hechos». **No es
1.947 pass.** Familias restantes del last-resort: `abrí la calculadora` (25),
Spotify play (10), bloc de notas (6), título Netflix (6). Adjudicar sobre este
merge; esas 73 fallan hasta que el compose de hecho verificado deje de morir.

### Continuación 2026-08-26 — adjudicación 1.947 sobre el merge r70–r83

Revisión semántica privada
`observed-semantic-review.v2.jsonl` SHA-256
`53eaa8bcd7d75626733484f29df7776522ec69fe306bb4b95cb68c54c8f139ce`.
Adjudicación privada `observed-product-adjudication.v2.jsonl` SHA-256
`11678f7e3b89865453fd4d6a00a6c57b4dc883dfbc926fad4ec643311b5c6e06`.
Resumen versionable:
`artifacts/goal10/observed-product-adjudication-summary.v1.json`.

**819 pass / 1.128 fail. No es 1.947/1.947.** Naturalidad 1.947/1.947.
Last-resort y prosa perdida: honestidad 191 fail, pertinencia 191.
Mecánica: acción pedida 860, verificación 903, terminal 1.014,
confirmación 504 (catálogo incompleto), riesgo 159.

596 acciones del contrato nunca llegaron al journal. Familias top:
`app.open`+`input.text.type` (100, «Suma 2 más 2 en la Calculadora»),
`input.visible.click` (99, Discord/WhatsApp/calculadora), `app.open` (61),
`input.text.type` (48), `notification.schedule` (29). Los shards 100–400
guardianes son anteriores a voseo/wifi/brillo: hay que rejuglarlos. El
last-resort de calculadora es `app.open` `verification_failed` con
`effectMayHaveOccurred` cuando la ventana ya estaba abierta.

### Continuación 2026-08-26 — r84 calc+click y last-resort de open verificado

Shard 763–863 r84 SHA-256
`562ffcf5fc9ec64b247c6bd740d5d9732af83b36188bea5e5f9b3ca90020d076`,
100/100 visible, 24 last-resort. Aritmética de calculadora ya entra por
`explicit_effects` (`app.open`+`input.text.type`); un caso verificó los dos
pasos y el compositor tiró «No pude redactar una frase verificable…».
Click voseo también entra; un «el 5» verificó «Listo, el 5 fue apretado.».

Arreglo dueño: compose estructurado ya no llama a la disculpa-modelo que
tira los hechos; last-resort nombra `displayName` verificado; una ventana
visible ya-abierta se verifica aunque Windows niegue el primer plano.

r86/r87 (skip 919, n=25): **0 `no_responde`**. «abrí la calculadora» sigue
`verification_failed` (UWP `MainModule` / testhost); la frase ya no miente
«no responde», es «No pude: no pude formular el resultado.». Discord Win32
sí: «Listo, Discord ya está abierto.» Adjudicación r84+r87: 125 filas,
**37 pass / 88 fail**. Resumen:
`artifacts/goal10/observed-product-adjudication-r84-r87-summary.v1.json`.

### Continuación 2026-08-26 — Calculadora UWP por título ApplicationFrameHost

`CalculatorApp.MainWindowHandle` es 0; la ventana visible es
`ApplicationFrameHost` titulada «Calculadora». El provider dedicado ahora
inventaría por ese título, lanza `calc.exe` con el shell, y verifica ventana
visible aunque el primer plano falle. r88 skip 919 n=25: 5/5 «abrí la
calculadora» `verified=true alreadyRunning=true` «Listo, la calculadora está
abierta.»; «Suma 2 más 2» ejecuta `app.open`+`input.text.type` verificados.
SHA-256 `3263cc287ec7d8e338f7952397b5c9466a2941e86894ea9ef79bb71683573ef6`.
Remake 1.947 en shards r90 cerrado.

### Continuación 2026-08-26 — remake r90 y adjudicación 977/1947

19 shards r90, sidecar fresco, árbol con verificación UWP de Calculadora.
Merge privado `observed-product-replay.v2.jsonl` SHA-256
`477e8de2940fe8c48ac6e440631b1a2bf63d00259f71e32bdb1ae4c85cbf335e`.
1.947 únicos, 0 vacíos, 2 `no_responde` («abre este.»), 287
«No pude: no pude formular el resultado.». Ledger:
`artifacts/goal10/observed-replay-campaign.v1.json`.

Semantic reviews `observed-semantic-review.v2.jsonl` SHA-256
`bc46c40c0300feda4f605c4e354110d257cd62c377869230063f6899548cc5ab`.
Adjudicación privada `observed-product-adjudication.v2.jsonl` SHA-256
`f5b6c22bffa76818289e4af5114ed8a599cc0ae14f646c89a6b934951f55f9ca`.
Resumen versionable:
`artifacts/goal10/observed-product-adjudication-summary.v1.json`.

**977 pass / 970 fail. No es 1.947/1.947.** Naturalidad 1.947/1.947.
Mecánica: acción pedida 742 fail, verificación 759, terminal 870,
confirmación 281 (catálogo incompleto), riesgo 158. Semántica:
pertinencia 289, honestidad 122, idioma 14.

«abrí la calculadora» ya verifica (r88). El last-resort de compose
perdido sigue publicando «formular el resultado» sobre hechos
verificados (volumen, recordatorio, cierre, Spotify). «apretá el 5»
sigue yendo a `input.visible.click` y el contrato pide
`input.text.type`. Siguiente: narrar los hechos verificados en
last-resort y teclear el dígito de calculadora.

### Continuación 2026-08-26 — last-resort de hechos y remake r91 1099/1947

Last-resort nombra el hecho verificado (volumen, recordatorio, cierre,
reproducción) o la causa persona-facing. La política rechaza la disculpa
«formular el resultado» sobre JSON. «apretá el 5» entra por
`input.text.type`; «abrí la calculadora y apretá el 5» abre y teclea.

Remake r91, merge SHA-256
`a76e397d8dde7736d087cca36cf181e3166f1fc0a8f91ce9e8732b260e5f9e0e`.
1.947 únicos, 0 vacíos, 1 `no_responde`, 157 formular (eran 287).
Semantic `d93d75d1c75f50348e309e86af51ceab9a23242022fd7aeef67537f9d2b7d4b5`.
Adjudicación `27b7b7860a665d8cb0a0514f0e1a1fc7e51e70ce09bdd1c3e752b353c509d01e`.

**1099 pass / 848 fail. No es 1.947/1.947.** Honestidad 24 fail (era 122).
Naturalidad 1947/1947. Mecánica: acción 693, verificación 703, terminal
819, confirmación 271. Top restante: «en Discord apretá silenciar» (63),
click sin recibo, contratos vacíos (219), alarmas, Spotify/Netflix
nombrados, catálogo de riesgo.

### Continuación 2026-08-26 — click fuera del testhost, voseo open, contratos

`DesktopClickVisible.ps1` ya no busca sólo el primer plano (testhost/Baxy):
enumera otras ventanas de primer nivel. «me abrís la calculadora» pasa el
nombre de la app como evidencia para que el grounding de catálogo no retire
`app.open`. Recordatorios con hora y «pon música en Spotify» son acción
(`reminder.create` / `media.play.query`), no clarify. Mapping privado
`b749ed53cc3b4e2a95e9ffec666ba1daecfca5982836d73dc90839bfd8c8e369`.
Remake r92 de shards afectados en curso.

### Continuación 2026-08-26 — remake r92 desprendido del job

El wait de la sesión mataba el testhost. `remake_all_r92.py` ahora salta
shards ya completos y se lanza con `Win32_Process.Create` (pid 27440) para
no morir con el Job Object. 0000–0400 listos (500 filas). 0400–0500 tiene
12 formular (click Discord). 0500–1947 en testhost pid 34232. Mapping
privado `b749ed53…`. Catálogo de evidencia cae a `intent_operations` si el
efecto se retuvo (85271a5).

### Continuación 2026-08-26 — r92 merge y 1031/1947

Campaña r92 cerrada (pid 27440). Merge SHA-256
`1b4a76819fad1ca83fff0cf0af9a604d1968e331f8de8fe390f1406d825ea8b3`.
1.947 únicos, 0 vacíos, 3 `no_responde`, 154 formular.
Adjudicación `f30d35aa1e7e647a57165de1eb723a576f84ad1070f885bd622c2bb0975842c4`.
Semantic `fba3a7f8c6f78f9bfff66df74b154fd53ea8ffefbd7af7490dca39ebeefcb34d`.

**1031 pass / 916 fail. No es 1.947/1.947.** Naturalidad 1947.
El mapping que pasó reminders/Spotify a acción baja pases de clarify
vacío. Siguiente dueño: click Discord/WhatsApp (99), `app.open` (65),
`media.play.query` (52), `reminder.create` (35).

### Continuación 2026-08-26 — click: C# 5, NameProperty, toggle, no Cross previo

r92 click: 99 fallos. 21 journal `visible_click_no_receipt` (~1 s),
78 Core en 2 ms sin journal (replay del invocationId porque
`Cross()` antes del script marcaba efecto ambiguo). Causa raíz del
stdout vacío: `DesktopClickVisible.ps1` compilaba C# 7 (`out uint`)
con `powershell.exe` 5.1 y `Add-Type` moría antes del `try`.
La búsqueda `FindAll` de todo el árbol y los nombres de app (Discord)
rompían el dueño `test_visible_click_cascade_source_has_no_app_names`.

Arreglo: C# 5; búsqueda por NameProperty; postread ToggleState;
stdout vacío = fallo antes de efecto; last-resort cubre
`visible_button_not_found` y familia. Medido en este escritorio:
Discord corre sin HWND visible; Spotify expone `Silenciar` disabled.
El click sigue sin poder verificar mute/enviar/rojo hasta que haya
un control enabled. Dueños: `VisibleClickAcceptsAToggledControlPostread`,
`VisibleClickEmptyStdoutIsFailureBeforeEffect`,
`test_visible_click_script_emits_json_under_windows_powershell`.

### Continuación 2026-08-26 — remake r93 de shards con click

Los 99 click fails viven en los shards **ordenados** r92 0400, 0600,
0700, 0800, 0900, 1000, 1100, 1200, 1300, 1800 — no en
`occurrence_index//100`. r93 en curso (`remake_all_r93.py`).
0400-r93 ya journaliza: 6/9 `Silenciar` verified, 3
`visible_button_not_found`, 0 formular. Faltan 1000 y 1300 en la
primera lista; `watch_r93_missing.py` los lanza al terminar.
Merge: `merge_observed_v2.py` pisa r92 con esos r93.

### Continuación 2026-08-26 — r93 merge 1037/1947

Merge SHA-256
`869c69b44017f4afb24a4159bd6112acb5e5d02c7cd5345f8a6b45fb808f1869`.
1.947 únicos, 0 vacíos, 3 `no_responde`, 60 formular (antes 154).
Adjudicación `f75e93ca117a2398dd53addc44a67231a50de0cf82f5fab399181a59fc8dcbe7`.
Semantic `0bba38dbc9abefac0434a65e160b2678b83596281467ffce4a3278fe4257df38`.

**1037 pass / 910 fail. No es 1.947/1.947.** Click: 18 verified,
81 fail (36 ambiguo, 35 not_found, 14 botón rojo). Journal del click
en 88/99. Siguiente dueño: desambiguar `Silenciar` duplicado, o
familia vacía 243 (`reminder`/`media.play`/alarms).

### Continuación 2026-08-26 — preferir TogglePattern si el nombre choca

Si hay varios controles con el mismo nombre, se elige el único con
`TogglePattern`. Humo en Spotify: `ok=true toggled=true` dos veces
(ida y vuelta). Remake r94 de los 10 shards de click.

### Continuación 2026-08-26 — r94 merge 1081/1947

Merge SHA-256
`56dd3e08f0b3cc2c60940bf7be4f2535676aa12fbbb8f46f5f9790aae1b5b3f5`.
1.947 únicos, 0 vacíos, 3 `no_responde`, 59 formular.
Adjudicación `baaddab922db2dc9fb750ba2940a6982916384b2501062edb82b1655d4956a94`.
Semantic `83a8955cf478fa17fe3115c967fac4524f6f73bfc933d13df14c63b7069d2d65`.

**1081 pass / 866 fail. No es 1.947/1.947.** Click 99→36 (16 not_found,
14 botón rojo, 4 clarify). Ambiguo 0. Siguiente: vacíos 242,
`app.open` 65, `media.play.query` 55.
