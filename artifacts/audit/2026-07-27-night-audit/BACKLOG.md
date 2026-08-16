# Backlog de defectos

## BAXY-AUD-001 — Un Steam AppID schema-válido termina todo el core

- Severidad: P1
- Estado: confirmado; no corregido
- Versiones: instalación BAXY 1.0.8 y build de desarrollo del commit
  `f23b23f064211154e954d82883ba6bee5c2c466c`
- Operaciones: `game.install.prepare`, `game.install.status`
- Reproducción: 8/8 (dos intentos por operación y por binario)
- Efecto externo: ninguno; ambas operaciones son `read_only`

### Pasos mínimos

1. Iniciar `baxy-core.exe` con un `BAXY_DATA_DIR` aislado válido.
2. Enviar una `operation.request` para `game.install.prepare` o
   `game.install.status`.
3. Usar `{"appId":"audit-missing-id"}`. El valor tiene 16 caracteres, no está
   vacío y satisface el schema publicado.

### Esperado

El core debe rechazar el argumento con una respuesta terminal estable, o el
provider debe devolver que el AppID no pertenece a la biblioteca. El proceso
debe seguir disponible.

### Observado

No llega ninguna `operation.response`. El core termina con código 70 y stderr:

`BAXY core stopped safely (InvalidDataException).`

### Causa raíz

1. `ProductCatalog` publica `appId` solo como string no vacío de máximo 16
   caracteres.
2. `SteamLocalAdapter.RequireAppId` aplica una condición adicional no
   representada por el schema: 1–10 dígitos ASCII y sin cero inicial.
3. Al incumplirse esa condición, `RequireAppId` lanza
   `InvalidDataException`.
4. La frontera `SteamLocalAdapter.InvokeAsync` captura `IOException`,
   `UnauthorizedAccessException` e `InvalidOperationException`, pero omite
   `InvalidDataException`.
5. La excepción cruza handler y loop JSONL; `Program.Main` la captura solo en
   el último nivel y apaga todo el core con código 70.

### Evidencia

- `steam_appid_crash_repro_installed.json`
- `steam_appid_crash_repro_development.json`
- `reproduce_steam_appid_crash.py`

## BAXY-AUD-002 — Preparar un paquete apaga el core si `winget` no está en PATH

- Severidad: P1
- Estado: confirmado; no corregido
- Versiones: instalación BAXY 1.0.8 y build de desarrollo del commit
  `f23b23f064211154e954d82883ba6bee5c2c466c`
- Operación: `package.install.prepare`
- Reproducción: 4/4 (dos intentos por binario)
- Efecto externo: ninguno; la operación es `read_only` y el ejecutable nunca
  llegó a iniciarse
- Entorno: `Microsoft.DesktopAppInstaller` 1.29.280.0 está instalado, pero
  `Get-Command winget.exe` y `where.exe winget.exe` no lo resuelven

### Pasos mínimos

1. Ejecutar BAXY en una cuenta donde `winget.exe` no esté resoluble mediante
   `PATH`.
2. Enviar `package.install.prepare` con
   `{"packageId":"Microsoft.PowerToys"}`.

### Esperado

Una respuesta terminal estable debe explicar que el adaptador de paquetes no
está disponible. El núcleo debe seguir atendiendo solicitudes.

### Observado

No llega ninguna `operation.response`. El núcleo termina con código 70 y:

`BAXY core stopped safely (Win32Exception).`

### Causa raíz

1. `ProductCatalog` publica la operación y acepta cualquier `packageId` no
   vacío de hasta 256 bytes.
2. `WindowsInventoryAdapter.PackagePrepareAsync` invoca directamente
   `RunAsync("winget.exe", ...)`.
3. `Process.Start` lanza `Win32Exception` cuando el alias no está disponible.
4. La frontera `WindowsInventoryAdapter.InvokeAsync` captura
   `IOException`, `UnauthorizedAccessException`, `JsonException` e
   `InvalidOperationException`, pero omite `Win32Exception`.
5. La excepción llega al último cierre de seguridad de `Program.Main` y apaga
   el proceso completo.

### Cobertura que falta

Las pruebas del adaptador usan procesos simulados o entornos donde la
resolución del ejecutable no falla. Falta un caso de frontera para ejecutable
ausente y una aserción de que el loop JSONL permanece vivo después del fallo.

### Evidencia

- `package_prepare_crash_repro_installed.json`
- `package_prepare_crash_repro_development.json`
- `reproduce_package_prepare_crash.py`

## BAXY-AUD-003 — El inventario Bluetooth puede bloquear indefinidamente el core

- Severidad: P1
- Estado: confirmado; no corregido
- Versiones: instalación BAXY 1.0.8 y build de desarrollo del commit
  `f23b23f064211154e954d82883ba6bee5c2c466c`
- Operación: `bluetooth.device.list`
- Reproducción: 5/5 antes de la sonda de proceso (20 segundos en el barrido
  inicial y dos intentos de 10 segundos por cada binario)
- Efecto externo: ninguno; solo inventario

### Pasos mínimos

1. Iniciar el core con un `BAXY_DATA_DIR` aislado.
2. Enviar `bluetooth.device.list` con `{}`.
3. Esperar 10 segundos.

### Esperado

El inventario debe responder con los dispositivos observados o fallar en un
tiempo acotado, y el loop JSONL debe continuar disponible.

### Observado

No llega respuesta ni error. El proceso continúa vivo, pero la solicitud no
termina y, al ser el loop secuencial, impide procesar las solicitudes
posteriores. Las reproducciones se cerraron desde el arnés al vencer el
timeout.

La misma consulta subyacente mediante:

`Get-PnpDevice -Class Bluetooth`

terminó directamente en 1,57 segundos y devolvió el inventario del equipo.

### Causa raíz

1. Dos adaptadores anuncian `bluetooth.device.list`.
2. El primero, `WindowsDeviceControlAdapter`, enumera secuencialmente cuatro
   selectores WinRT con `DeviceInformation.FindAllAsync`.
3. Esas esperas no usan `WaitAsync`, timeout ni cancelación. El token solo se
   comprueba después de completar las cuatro enumeraciones.
4. Durante la sonda no apareció ningún PowerShell hijo: el bloqueo ocurre
   antes de llegar al adaptador alternativo `WindowsInventoryAdapter`.
5. `WindowsExternalCapabilityProvider` prueba los adaptadores en serie; como
   el primero no retorna, nunca alcanza el fallback basado en PowerShell que
   sí funciona en este equipo.

### Cobertura que falta

Falta una prueba con una operación WinRT que no completa, que demuestre
timeout/cancelación y acceso al fallback sin bloquear el protocolo.

### Evidencia

- `bluetooth_list_timeout_repro_installed.json`
- `bluetooth_list_timeout_repro_development.json`
- `reproduce_bluetooth_list_timeout.py`

## BAXY-AUD-004 — Un saludo después de la bienvenida recibe una descripción en tercera persona

- Severidad: P2
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8 y runtime del commit
  `f23b23f064211154e954d82883ba6bee5c2c466c`
- Ruta: conversación social visible en BAXY Field
- Reproducción física: 3/3 saludos válidos, en dos procesos/sesiones
- Reproducción focalizada: 3/3 por la ruta contextual
- Efecto externo: ninguno

### Pasos mínimos

1. Abrir BAXY y esperar la bienvenida
   `Hola. Estoy lista para ayudarte con este equipo.`
2. Escribir `Hola`.

### Esperado

Una respuesta directa y natural, por ejemplo:

`¡Hola! ¿En qué puedo ayudarte hoy?`

### Observado

La interfaz mostró respuestas como:

- `El usuario saludó al asistente.`
- `El usuario me saludó diciendo 'Hola'.`
- `El usuario me saludó.`

El mensaje habla *sobre* la persona y no *con* ella. La respuesta directa del
mismo modelo, sin historial, fue correcta 3/3.

### Causa raíz

1. `BuildMindHistory` incluye la bienvenida inicial como último mensaje del
   asistente.
2. `LlmRuntime.chat` activa `_resolve_contextual_answer` siempre que encuentra
   cualquier mensaje anterior del asistente, sin limitarlo a
   `conversation_kind == "followup"` ni comprobar que el turno actual sea
   elíptico.
3. Por ello, el primer saludo del usuario se procesa como resolución de
   referencia entre la bienvenida y `Hola`.
4. El schema de esa ruta pide `resolved_meaning` y `direct_answer`; en este
   caso el modelo devuelve de forma determinista la descripción
   `El usuario saludó al asistente.`
5. `UserMessagePolicy.IsSafeConversationReply` solo comprueba texto vacío,
   longitud y términos internos prohibidos. No rechaza metadiscurso ni tercera
   persona, así que el texto llega a la interfaz.

### Brecha de pruebas

`run_user_behavior_gate.py` llama `runtime.chat` con historial vacío. Esa ruta
respondió bien, por lo que el gate no cubre la condición real creada por la
bienvenida del escritorio.

### Evidencia

- `social_greeting_repro.json`
- `reproduce_social_greeting.py`
- `ui-hola-3.png`
- `ui-hola-baxy.png`
- `ui-hola-fresh-2.png`

## BAXY-AUD-005 — BAXY abre Calculadora pero no puede cerrar su ventana UWP

- Severidad: P2
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Operaciones: apertura directa seguida de `app.close`
- Reproducción: 2/2 ciclos
- Efecto externo: reversible; la ventana se cerró manualmente al terminar la
  sonda

### Pasos mínimos

1. Pedir `Abre la calculadora`.
2. Comprobar que Calculadora aparece y que BAXY responde
   `Abrí la Calculadora.`
3. Pedir `Cierra la calculadora`.

### Esperado

La misma ventana abierta por BAXY desaparece y el asistente confirma el cierre.

### Observado

BAXY responde `No pude cerrar la calculadora.` y la ventana
`ApplicationFrameWindow` con título `Calculadora` sigue visible. El proceso
`CalculatorApp` también permanece activo.

### Causa raíz

1. El pipeline resuelve correctamente la ventana hospedada por
   `ApplicationFrameHost` y consume su identidad opaca.
2. `WindowsWindowControlProvider.CloseAsync` solo llama
   `PostMessage(hwnd, WM_CLOSE, ...)`.
3. Windows acepta el post, pero la ventana UWP de Calculadora ignora ese
   mecanismo y permanece visible.
4. La verificación `VerifyClosed` realiza 20 lecturas cada 100 ms, observa la
   ventana todavía presente y devuelve `window_verification_failed`.
5. El fallo se narra honestamente, pero no existe una estrategia de cierre
   compatible con la ventana UWP que el propio catálogo permite abrir.

### Brecha de pruebas

Las pruebas del provider cubren una ventana Win32 controlada. Falta un caso
físico UWP/ApplicationFrameHost, al menos para Calculadora.

### Evidencia

- `ui-calculator-open.png`
- `ui-calculator-closed.png`
- `ui-calculator-close-fail-2.png`

## BAXY-AUD-006 — Órdenes inequívocas de abrir aplicaciones se convierten en preguntas ajenas

- Severidad: P1
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Ruta: política contextual del turno en la interfaz real
- Efecto externo: ninguno en las reproducciones fallidas

### Pasos mínimos y resultados

Con una sesión recién iniciada o una sesión normal de BAXY:

1. `Abre Opera`:
   - observado físicamente: `Which browser and URL would you like to navigate to?`
     o `¿A qué URL deseas navegar?`;
   - Opera no se inicia.
2. `Abre el Bloc de notas`:
   - observado: `Abre una carpeta conocida de Windows y verifica la ventana
     de Explorer observada?`;
   - Bloc de notas no se inicia.
3. `Abre Spotify`:
   - observado: `¿Qué quieres buscar en Spotify?`;
   - no aparece una ventana ni un proceso nuevo de Spotify.

La sonda de la misma ruta del modelo también produjo variación no válida para
`Abre la calculadora`: `¿Qué aplicación o calculadora específica deseas
abrir?`, aunque el nombre ya es suficiente y en otra corrida física sí se
ejecutó correctamente.

### Esperado

Cada petición contiene una acción y un objetivo completos. Debe resolverse a
una sola operación `app.open` con el identificador conocido y verificarse la
ventana; no hace falta una URL, una carpeta, una búsqueda ni otra
desambiguación.

### Causa raíz

1. La ruta de producto entrega todos los turnos públicos a
   `TryExecuteWithMindAsync` y la decisión del modelo contextual es la única
   política de producción.
2. En el shortlist compiten operaciones semánticamente próximas como
   `app.open`, `browser.navigate.named`, `filesystem.folder.open` y operaciones
   de medios. El modelo selecciona el dominio próximo pero pide un argumento
   que pertenece a otra intención.
3. El repositorio ya contiene `NaturalApplicationRequestParser` y aliases
   auditados para Opera, Bloc de notas, Calculadora y otras aplicaciones, pero
   `MainWindowViewModel` aclara que no existe una segunda clasificación basada
   en frases. Ese parser queda en la ruta de oracle de pruebas, no como
   resguardo del turno real.
4. La compuerta de política real solo exige como caso crítico simple
   `Abre Steam`; no cubre varios objetivos inequívocos ni comprueba que una
   aclaración pertenezca a los argumentos de la operación candidata.

La forma compuesta `Abre Opera y navega a https://example.com/` también falló
físicamente antes de emitir una operación. Con el mismo modelo, una sonda
aislada generó a veces el plan correcto de un paso
`browser.navigate.named`, pero con historial de recuperación generó un DAG
distinto basado en `browser.navigate` + `browser.page.read`. Esta sensibilidad
al historial y la variación entre acción/plan/conversación forman parte de la
misma brecha de política.

### Evidencia

- `live_turn_probe.json`
- `ui-opera-open-attempt.png`
- `ui-notepad-open-attempt.png`
- `ui-notepad-open-attempt-2.png`
- `ui-spotify-open.png`
- `ui-opera-compound-result.png`
- `live_turn_and_plan_probe.json`
- `opera_recovery_context_probe.json`

## BAXY-AUD-007 — La pregunta «Qué hora es?» no ejecuta la capacidad local de hora

- Severidad: P2
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Operación esperada: `system.time`
- Reproducción: confirmada por interfaz física y por la ruta real del modelo
- Efecto externo: ninguno; consulta de solo lectura

### Pasos mínimos

1. Abrir BAXY.
2. Escribir `Que hora es?`.

### Esperado

BAXY debe ejecutar `system.time` y narrar la hora observada del equipo.

### Observado

- Interfaz física:
  `¿Te refieres a la hora actual o a la hora de algún lugar específico?`
- Interfaz física bajo los dos soaks:
  `No pude formular una respuesta segura para esta petición. Puedes reformularla.`
- Sonda de turno contextual:
  `Como modelo de lenguaje, no tengo acceso a la hora en tiempo real.`

La primera respuesta pide aclarar algo que ya está determinado por el contexto
local del producto. La segunda afirma una limitación falsa: BAXY publica y
ejecuta `system.time`.

### Causa raíz

1. La frase exacta existe en `src/baxy_mind/data/intent_bank.jsonl` con la
   etiqueta `system.time`, y el parser determinista también la reconoce.
2. La interfaz no usa esos parsers como autoridad; el LLM contextual puede
   clasificar el turno como aclaración o conversación aunque `system.time`
   esté en los candidatos.
3. Las pruebas end-to-end del parser pasan por un oracle tipado inyectado. La
   compuerta crítica del modelo real no incluye una petición de hora, por lo
   que no detecta la divergencia entre el parser probado y la política usada
   por el producto.

### Evidencia

- `live_turn_probe.json`
- `ui-time-fail.png`
- `ui_time_under_soak_accessibility.json`

## BAXY-AUD-008 — Spotify termina verificado después del timeout y BAXY afirma que falló

- Severidad: P1
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Ruta: plan confirmado `media.play.query` seguido de pausa
- Reproducción: 1/1 física con efecto y journal verificados
- Efecto externo: Spotify se abrió y reprodujo la pista correcta; se dejó
  pausada y luego se cerró de forma limpia

### Pasos mínimos

1. Pedir:
   `Reproduce exactamente Beat It en Spotify y luego pausa la reproducción`.
2. Responder `confirmar` cuando BAXY lo solicite.
3. Observar la interfaz durante al menos 25 segundos y comparar con el journal
   autenticado del core.

### Esperado

La interfaz debe esperar el resultado terminal, continuar con el paso de pausa
y narrar el estado real. Si se agota un timeout, debe reconciliar la invocación
antes de afirmar fracaso o permitir una repetición.

### Observado

- Spotify se inició y mostró `Beat It` de Michael Jackson.
- El journal del core registró `media.play.query` como `completed`,
  `verified:true`, con autoridad `spotify_windows_uia_postread`.
- La operación tardó 21,7336368 segundos.
- A los 20 segundos, la interfaz mostró:
  - `No pude detener las acciones pendientes.`
  - `No pude hacer la acción solicitada.`
- Después de que el core certificara el éxito, la entrada
  `media.play.query` seguía en `retry-outbox.v1.json`.
- La interfaz quedó mostrando `starting agent · loading tools...` y no aceptó
  los dos intentos posteriores de cancelar el plan.

### Causa raíz

1. La confirmación del plan llama `CoreProcessClient.SendOperationAsync` con un
   timeout fijo de 20 segundos.
2. La automatización UIA real de Spotify necesitó 21,73 segundos, un tiempo
   razonablemente próximo pero superior a ese límite.
3. `CoreProcessClient` retira el request pendiente cuando el wait lanza
   `TimeoutException`; la respuesta verificada que llega aproximadamente
   1,73 segundos después ya no puede completar el flujo de la interfaz.
4. La excepción sale antes de ejecutar `CompleteMindPlanStep`, por lo que no
   se llama `MarkResolved`, no se avanza al paso de pausa y quedan persistidos
   tanto el plan como la identidad de recuperación.
5. La frontera del core sí realiza y certifica el efecto. El problema es la
   ausencia de reconciliación entre el timeout del cliente y el resultado
   durable tardío, lo que crea exactamente el estado peligroso
   «efecto ocurrido / usuario informado de fallo».

### Evidencia

- `spotify_plan_timeout_repro.json`
- `ui-spotify-compound-confirmed.png`
- `ui-spotify-compound-baxy-result.png`
- `ui-after-cancel-attempt.png`
- journal local autenticado, secuencias 121–122

## BAXY-AUD-009 — El modelo extrae `notepad`, pero el contrato solo acepta el identificador canónico

- Severidad: P2
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Ruta: turno real `abre notepad` → `app.open`
- Reproducción: 2/2 para el argumento crudo (`interfaz física` y core directo)
- Efecto externo: ninguno

### Pasos mínimos

1. Escribir `abre notepad` en BAXY.
2. Inspeccionar la operación emitida o repetir directamente:
   `app.open {"appId":"notepad"}`.

### Esperado

La extracción debe producir el identificador de catálogo
`windows.notepad`, o la frontera debe normalizar el alias auditado antes de
buscar la aplicación.

### Observado

BAXY respondió `No pude abrir notepad.`. El journal registró
`app.open` con `appId:"notepad"` y `app_not_found`. La reproducción directa
contra el core instalado produjo el mismo `app_not_found` sin iniciar ningún
proceso. Con `appId:"windows.notepad"`, el mismo core sí inició Bloc de notas.

### Causa raíz

1. `NaturalApplicationRequestParser` conoce el alias y lo proyecta a
   `windows.notepad`, pero no es la autoridad de la ruta pública.
2. El extractor LLM devuelve el texto superficial `notepad` como `appId`.
3. `ApplicationIds.Notepad` y el provider especializado usan exclusivamente
   `windows.notepad`; la resolución de aplicaciones instaladas tampoco
   encuentra el alias crudo.
4. No existe una validación post-extracción que compruebe el identificador
   contra los objetivos conocidos, por lo que una clasificación correcta
   termina como fallo falso de instalación.

### Evidencia

- `app_open_installed_raw_notepad.json`
- `ui-notepad-open-attempt-2.png`
- journal local autenticado, secuencias 119–120

## BAXY-AUD-010 — La compuerta física `app.open` ya no puede leer el catálogo de 168 operaciones

- Severidad: P2
- Estado: confirmado; no corregido
- Versión: script del commit
  `f23b23f064211154e954d82883ba6bee5c2c466c`
- Ruta: `scripts/test_app_open.ps1`
- Reproducción: 2/2 invocaciones (ruta unión y ruta física; la primera se
  detuvo antes por la política de reparse point y la segunda alcanzó el lector)
- Efecto externo: ninguno; la compuerta abortó antes de abrir Bloc de notas

### Pasos mínimos

1. Ejecutar la compuerta contra
   `artifacts/product/build/local-win-x64`.
2. Permitir que lea el primer mensaje JSONL del core.

### Esperado

La compuerta certificada debe consumir el catálogo que publica el build actual
y continuar hasta su prueba física de ventana/foco.

### Observado

Falla con:

`A protocol line exceeded the configured byte limit.`

El límite local del script es 65.536 bytes. La primera línea del build de
desarrollo mide 73.493 bytes UTF-8 (7.957 por encima); la instalación 1.0.8
mide aproximadamente 74.283 bytes.

### Causa raíz

`test_app_open.ps1` conserva un máximo fijo de 64 KiB para una línea JSONL,
pero el mensaje inicial contiene los schemas completos de las 168 operaciones.
El catálogo creció sin que la compuerta se actualizara ni contara con una
prueba que compare el tamaño real con su límite. El runtime de escritorio sí
consume ese catálogo; la regresión está en el arnés físico.

### Evidencia

- `artifacts/product/audit-2026-07-27-app-open.json`
- medición independiente: 73.493 bytes en el build de desarrollo

## BAXY-AUD-011 — La primera apertura canónica de Bloc de notas puede quedar como efecto ambiguo

- Severidad: P2
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Operación: `app.open {"appId":"windows.notepad"}`
- Reproducción observada: 1/7; las seis repeticiones posteriores aprobaron
- Efecto externo: Bloc de notas sí se abrió; la sonda cerró únicamente su
  ventana auditada

### Observado

En la primera corrida aislada, el core devolvió `verification_failed` con
`effectMayHaveOccurred:true`, aunque apareció un proceso nuevo y una ventana
visible de Bloc de notas. Las seis corridas siguientes devolvieron
`completed`, `verified:true`.

La ventana restauró una pestaña existente del Bloc de notas, pero esto por sí
solo no explica el fallo: corridas aprobadas también restauraron archivos con
títulos distintos.

### Causa raíz acotada

La señal queda acotada al tramo frío de lanzamiento/verificación:

1. el provider inicia correctamente el paquete;
2. el verificador exige en una misma observación identidad exacta de proceso,
   handle visible y foco;
3. durante el primer arranque, la transición del bootstrap al proceso
   empaquetado o la adquisición de foco no convergió dentro de la ventana de
   observación;
4. el provider retuvo correctamente la ambigüedad en vez de afirmar éxito.

No se atribuye el fallo al título restaurado. Falta telemetría de cada
observación del primer arranque para distinguir transición de PID/handle de
fallo de foco, y la compuerta física que debía aportar esa evidencia está
bloqueada por `BAXY-AUD-010`.

### Evidencia

- `app_open_installed_windows_notepad.json`
- `app_open_installed_windows_notepad_2.json`
- `app_open_installed_windows_notepad_3.json` a `_7.json`
- `reproduce_app_open.py`

## BAXY-AUD-012 — BAXY afirma que navegó aunque el core solo pidió confirmación

- Severidad: P1
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Operación: `browser.navigate.named`
- Reproducción física: 1/1 con journal, procesos y outbox observados
- Efecto externo: ninguno; Opera no se inició y no hubo navegación

### Pasos mínimos

1. En una sesión normal, escribir:
   `Navega Opera a https://example.com/`.
2. No confirmar nada porque la interfaz no ofrece la confirmación.
3. Observar mensajes, procesos, journal y outbox.

### Esperado

Como `browser.navigate.named` tiene riesgo `external_communication`, BAXY debe
mostrar la confirmación emitida por el core. Solo después de una respuesta
válida debe navegar y afirmar éxito.

### Observado

La interfaz mostró, para un único turno:

1. `No pude navegar a https://example.com/.`
2. un segundo después: `Navegué a https://example.com/`

No apareció proceso de Opera, el journal permaneció en la secuencia 124 y el
outbox conservó una entrada `browser.navigate.named`. Una invocación directa
aislada del mismo core demostró que el provider funciona: primero devuelve
`confirmation_required` y, al suministrar el token, navega y verifica
`finalUrl:https://example.com/`.

### Causa raíz

1. El turno se clasifica correctamente como acción
   `browser.navigate.named` y los argumentos se extraen.
2. `ExecutePreparedOperationAsync`, usado por acciones simples, solo reconoce
   una selección ambigua de notas. No llama
   `PendingOperationConfirmation.TryCreate`.
3. El `confirmation_required` del core se proyecta como un fallo y luego se
   conserva la identidad durable, pero no se guarda el token ni se crea un
   estado de confirmación que el usuario pueda contestar.
4. El segundo mensaje fuente es el estado de recuperación
   `Conservé la identidad...`. El compositor LLM lo reformula como
   `Navegué...`.
5. `UserMessagePolicy.IsSafe` limita texto y términos internos, pero para
   mensajes de estado no comprueba que una afirmación de éxito esté respaldada
   por `verified:true`; su detector de inversión solo protege fuentes que ya
   describen un resultado exitoso. Por eso acepta un efecto inventado.

La ruta de planes sí maneja `PendingOperationConfirmation` explícitamente;
la divergencia está entre esa ruta y la ruta de acción simple.

### Riesgo

Además de la afirmación falsa, la invocación queda durable pero sin una vía de
confirmación/cancelación en la sesión. Repetir la frase puede acumular o
reconciliar de manera confusa una acción que nunca fue autorizada.

### Evidencia

- `ui-opera-navigate-explicit.png`
- `ui-orphan-outbox-restart.png`
- `browser_navigate_named_installed.json`
- `opera_false_success_context_probe.json`
- outbox local observado con una sola entrada auditada

Al reiniciar, BAXY no anunció esa entrada ni ofreció recuperarla, confirmando
que el pending era invisible. Después de capturar la evidencia, la auditoría
cerró BAXY y retiró exclusivamente esa entrada creada por la prueba para
devolver el perfil a su baseline vacío. Esto fue limpieza del efecto del
arnés, no una corrección del producto.

## BAXY-AUD-013 — Navegar en Opera y leer la página usan sesiones CDP incompatibles

- Severidad: P1
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Cadena: `browser.navigate.named` → `browser.page.read`
- Reproducción directa: 1/1
- Efecto externo: navegación reversible a `https://example.com/`; el proceso
  aislado terminó al cerrar el core de prueba

### Pasos mínimos

1. En el mismo core, ejecutar y confirmar
   `browser.navigate.named {"browser":"opera","url":"https://example.com/"}`.
2. Tras el `completed/verified:true`, ejecutar y confirmar
   `browser.page.read {"maximumCharacters":2000}`.

### Esperado

La segunda operación debe leer la página que acaba de abrirse en Opera,
permitiendo misiones como «abre Opera, entra a una página y busca en ella».

### Observado

La navegación nombrada verificó URL y target. La lectura inmediatamente
posterior falló con `browser_page_snapshot_invalid`.

Control positivo: al iniciar la cadena con `browser.navigate` genérico, el
mismo core completó y verificó navegación, lectura (`Example Domain`), listado
de pestañas, scroll, reload, segunda navegación y back.

### Causa raíz

1. `NamedBrowserAdapter` mantiene su propia `CdpBrowserSession` en
   `opera-browser-profile`.
2. `WebBrowserAdapter` mantiene otra sesión independiente en
   `browser-profile`.
3. Solo el primero maneja `browser.navigate.named`; solo el segundo maneja
   `browser.page.read`, `browser.tabs.list` y `browser.control`.
4. El provider no comparte target, endpoint ni identidad entre ambos
   adaptadores, y `browser.page.read` tampoco acepta el `targetId` observado
   por la navegación nombrada.
5. El planner sí propone esta composición, pero el contrato público no tiene
   una forma de mantener continuidad con Opera.

### Evidencia

- `browser_chain_installed.json`
- `browser_chain_generic_installed.json`
- `browser_chain.py`
- `opera_recovery_context_probe.json`

## BAXY-AUD-014 — Cerrar la última pestaña funciona pero devuelve `web_adapter_unavailable`

- Severidad: P2
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Operación: `browser.control {"action":"close"}`
- Reproducción: 1/1 al final de la cadena CDP genérica
- Efecto externo: la pestaña y el navegador aislado desaparecieron

### Observado

Después de siete operaciones verificadas sobre la misma sesión, el cierre de
la única pestaña devolvió `failed`, `verified:false`,
`web_adapter_unavailable`, sin marcar `effectMayHaveOccurred`.

### Causa raíz

1. `CdpBrowserSession.ControlAsync` envía correctamente
   `/json/close/{targetId}`.
2. Para verificar, consulta repetidamente `TargetExistsAsync`.
3. Al ser la última pestaña, el proceso/endpoint CDP puede terminar antes de
   la postlectura. La consulta lanza una excepción de transporte en lugar de
   devolver simplemente «target ausente».
4. `WebBrowserAdapter.InvokeAsync` captura esa excepción fuera de
   `ControlAsync` y la reduce a `web_adapter_unavailable`, perdiendo el hecho
   ya observado de que se emitió el cierre.

La respuesta es por tanto falsa respecto del efecto y además declara
implícitamente que no pudo haber ocurrido.

### Evidencia

- `browser_chain_generic_installed.json`

## BAXY-AUD-015 — `audio.volume` considera cumplido un nivel exacto distinto por ±2 puntos

- Severidad: P2
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Operación: `audio.volume`
- Reproducción: 1/1 en la restauración; control posterior confirmado
- Efecto externo: reversible; el volumen inicial de 3 % quedó restaurado

### Pasos mínimos

1. Tener el volumen en 5 %.
2. Ejecutar `audio.volume {"level":3}`.

### Esperado

El contrato dice «fija el volumen absoluto»; el endpoint debe quedar en 3 % o,
si el dispositivo cuantiza el valor, el resultado debe expresar esa
limitación sin afirmar que ya estaba en el valor pedido.

### Observado

La operación devolvió `completed`, `verified:true`, `applied:false`, con
baseline y final en 5 %, y narró:

`Listo, el volumen del sistema ya estaba en 5 %.`

Para restaurar el baseline real fue necesario ir de 5 % a 0 % y luego a 3 %.
La lectura final certificó 3 % y `muted:false`.

### Causa raíz

`WindowsAudioControlProvider` usa `VolumeTolerancePoints = 2` tanto para
decidir que la petición ya está satisfecha como para verificarla. Una
diferencia de exactamente dos puntos evita por completo `SetVolumeScalar`.
Esa tolerancia puede ser razonable para la postlectura de hardware, pero no
para omitir la mutación de una orden absoluta ni para narrar equivalencia.

### Evidencia

- `audio_status_baseline.json`
- `audio_volume_set_7.json`
- `audio_volume_adjust_down_2.json`
- `audio_volume_restore_3.json`
- `audio_volume_bridge_0.json`
- `audio_volume_restore_3_second.json`
- `audio_status_restored_second.json`

## BAXY-AUD-016 — `web.search` verifica resultados sin comprobar relación con la consulta

- Severidad: P2
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Operación: `web.search`
- Reproducción: 4/4 consultas devolvieron resultados estructurados; al menos
  dos conjuntos fueron manifiestamente ajenos
- Efecto externo: solo consultas HTTPS de lectura

### Ejemplos observados

- Consulta `BAXY assistant audit` → tres resultados de `Soldier Field`.
- Consulta con token único
  `baxy-audit-7f9e3d2c-unique-token` → páginas francesas de consumo, un foro de
  DVD y Amazon Haul.
- `OpenAI` → resultados exclusivamente de Microsoft/Office.
- `Windows 11 calculator` → resultados al menos relacionados con Windows.

Todos se devolvieron como `completed`, `verified:true`.

### Causa raíz

1. El adapter llama Bing RSS con la query correctamente escapada.
2. La verificación solo valida XML acotado, título no vacío y URL HTTP(S).
3. No exige que el proveedor refleje la consulta, que el conjunto contenga
   términos relacionados ni que una búsqueda sin coincidencias devuelva cero.
4. Por ello, cualquier feed RSS estructuralmente válido se certifica como
   resultado de la consulta aunque sea un fallback, contenido genérico o
   resultados irrelevantes.

### Evidencia

- `web_search_installed.json`
- `web_search_0.json`
- `web_search_1.json`
- `web_search_2.json`

## BAXY-AUD-017 — La activación por palabra clave está instalada como dependencia pero sin modelo runtime

- Severidad: P1
- Estado: confirmado; no corregido
- Versión: instalación/runtime BAXY 1.0.8
- Ruta: voz manos libres / wake word
- Reproducción: compuerta física 1/1
- Efecto externo: micrófono y loopback se abrieron y cerraron; no se guardó
  audio

### Observado

La sonda reportó:

- `wakeWord:false`
- `wakeBackend:"unavailable"`
- `wakeWordError:"wake_word_manifest_missing"`

Las distribuciones `livekit-wakeword`, Silero, Sherpa/Parakeet y audio están
instaladas con las versiones esperadas. Sin embargo, no existe
`D:\BAXYRuntime\assets\wake\baxy-wakeword-v1.json` ni otro activo wake bajo el
runtime. El manifest general `mind-runtime-v1.json` tampoco configura una ruta
alternativa.

### Causa raíz

`resolve_wakeword_manifest` usa `BAXY_VOICE_WAKE_MANIFEST` o una ruta fija
externa. El paquete/repositorio no contiene un modelo acústico calibrado —por
diseño de licenciamiento/tamaño— y la instalación activa no aprovisionó ese
activo. La dependencia Python está disponible, pero no puede crear backend sin
manifest, modelo y reporte de calibración validados.

El modo directo mediante botón sí abre entrada/loopback; el fallo afecta la
activación manos libres prometida por la arquitectura.

### Evidencia

- `artifacts/product/voice_system_gate.json`

## BAXY-AUD-018 — Parakeet no recupera «Spotify» en la muestra histórica física

- Severidad: P1
- Estado: confirmado; no corregido
- Versión: runtime de voz activo de BAXY 1.0.8
- Ruta: STT final + corrector de entidades
- Reproducción: 2/2 decodificaciones (gate y diagnóstico redacted)
- Efecto externo: ninguno

### Observado

La muestra canónica `test_open_spotify.wav`:

- existe y dura 1,789 s;
- produce un transcript no vacío de 10 caracteres / dos tokens;
- no contiene la entidad `spotify` antes ni después del corrector;
- el mejor token queda a distancia de edición 3 de `spotify`;
- el inventario de corrección sí contiene exactamente `spotify`.

El transcript no se persistió ni publicó; la evidencia guarda solo hash y
métricas.

### Causa raíz

1. Parakeet produce una hipótesis demasiado distante para el umbral textual
   conservador de 82 %.
2. `FuzzyCorrector` solo permite la rama fonética débil cuando una alternativa
   n-best aporta apoyo independiente.
3. Esta ruta del recognizer entrega una única hipótesis, por lo que no existe
   esa evidencia secundaria y el corrector se abstiene correctamente según su
   política.
4. El resultado seguro es no inventar la marca, pero funcionalmente la orden
   histórica pierde el proveedor cerrado y no puede ejecutar la intención.

### Evidencia

- `voice_clip_diagnostic.json`
- `diagnose_voice_clip.py`
- `artifacts/product/voice_system_gate.json`

## BAXY-AUD-019 — `filesystem.hash` termina el proceso del core con una excepción

- Severidad: P1
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8 y build de desarrollo del commit auditado
- Operación: `filesystem.hash`
- Reproducción: 3/3, con un `resourceId` recién emitido y válido
- Efecto externo: ninguno fuera del sandbox aislado; cada data root fue eliminado

### Pasos mínimos

1. Crear un archivo mediante `filesystem.write.text`.
2. Conservar el `resourceId` devuelto por esa operación.
3. Invocar `filesystem.hash {"resourceId":"<id recién emitido>"}` en el mismo
   proceso del core.

### Esperado

La operación debe devolver una entrada verificada con el SHA-256 del archivo,
o un fallo estructurado si la identidad hubiera caducado.

### Observado

Las operaciones previas `filesystem.create.directory`,
`filesystem.write.text` y `filesystem.read.text` terminaron
`completed/verified:true`. Al pedir el hash, el core cerró la tubería sin
respuesta, terminó con código 70 y escribió:

`BAXY core stopped safely (InvalidOperationException).`

El resultado fue idéntico dos veces en el binario instalado y una vez en el
build de desarrollo.

### Causa raíz

1. El provider calcula y devuelve correctamente un `FilesystemEntry`.
2. `FilesystemResultJson.Entry` llama a `Write`, que ya abre el objeto JSON
   raíz y escribe `version`.
3. A continuación llama directamente a `WriteEntry`; esta función intenta
   abrir un segundo objeto con `WriteStartObject()` sin haber escrito antes un
   nombre de propiedad ni estar dentro de un array.
4. `Utf8JsonWriter` lanza `InvalidOperationException`.
5. `FilesystemHandler` solo captura `FilesystemProviderException`, por lo que
   el error de serialización escapa hasta el límite fatal del core.

La misma función `WriteEntry` sí es válida dentro del array que construye
`filesystem.list`; el defecto está específicamente en el envoltorio singular.

### Evidencia

- `filesystem_chain_installed.json`
- `filesystem_hash_crash_installed_2.json`
- `filesystem_hash_crash_development.json`
- `filesystem_chain.py`

## BAXY-AUD-020 — `input.select.all` no puede completar su verificación UIA

- Severidad: P1
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Operación: `input.select.all`
- Reproducción: 3/3 superficies de texto (Notepad moderno, TextBox WinForms y
  TextBox WPF)
- Efecto externo: solo texto sintético en ventanas de auditoría; todas cerradas

### Observado

- Notepad moderno: `select_all_uia_failed`.
- TextBox WinForms: `focused_control_has_no_text_pattern`; la operación ni
  siquiera envía Ctrl+A.
- TextBox WPF: `select_all_uia_failed`, aun cuando el control sí expone
  `TextPattern`, tiene una sola selección y el Ctrl+A ya fue emitido.

La escritura previa mediante `input.text.type` sí fue aceptada y verificada en
las tres superficies.

### Causa raíz

Hay dos rutas sin salida funcional:

1. Si el control no expone `TextPattern` —caso común en WinForms—, el script
   falla sin intentar un fallback verificable.
2. Si sí lo expone, `DesktopSelectAll.ps1` llega a comparar los extremos de la
   selección usando `TextPatternRangeEndpoint`, pero solo carga
   `UIAutomationClient`. En un PowerShell limpio el tipo del enum no está
   disponible porque falta cargar `UIAutomationTypes`; la referencia lanza
   una `RuntimeException`.
3. El `catch` reemplaza la excepción y el paso exacto por
   `select_all_uia_failed`, ocultando la causa a la respuesta pública.

El diagnóstico redacted observó exactamente:
`step=compare_start`, `textPatternAvailable=true`, `selectionCount=1` y
`No se encuentra el tipo [Windows.Automation.TextPatternRangeEndpoint]`.

### Evidencia

- `window_input_chain_installed.json`
- `window_input_safe_chain_installed.json`
- `window_input_wpf_chain_installed.json`
- `window_input_wpf_diagnostic_installed.json`
- `diagnose_select_all.ps1`

## BAXY-AUD-021 — Maximizar, minimizar y restaurar ventanas reportan fallo antes de que el estado converja

- Severidad: P1
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Operaciones: `window.maximize`, `window.minimize`, `window.restore`
- Reproducción: 7/7 transiciones inicialmente fallidas sobre ventanas WPF y
  WinForms; 7/7 estados pedidos presentes 500 ms después
- Efecto externo: solo ventanas sintéticas de auditoría, cerradas al terminar

### Observado

Cada orden devolvió inmediatamente `failed`, `verified:false`,
`verification_failed`. Una nueva resolución 500 ms después certificó el
efecto real:

- maximizar → `state:"maximized"`;
- restaurar → `state:"normal"`;
- minimizar → `state:"minimized"` y sin foreground.

`window.move`, `window.resize`, `window.focus` y el cierre de esas mismas
ventanas sí terminaron verificados.

### Causa raíz

1. `WindowsWindowControlProvider.ExecuteAsync` emite la transición mediante
   Win32.
2. A diferencia de `app.close`, no contiene ningún bucle de convergencia.
3. Observa y verifica exactamente una vez, de inmediato.
4. WPF y WinForms procesan de forma asíncrona el cambio de estado; esa primera
   lectura todavía refleja el estado previo.
5. El provider consume la identidad efímera y devuelve fallo, sin
   `effectMayHaveOccurred`, aunque la transición solicitada completa instantes
   después.

Es un falso negativo determinista para estas superficies y puede provocar que
la interfaz o un retry repita una acción ya realizada.

### Evidencia

- `window_input_wpf_after_select_installed.json`
- `window_input_wpf_full_installed.json`
- `window_input_winforms_full_installed.json`
- `window_input_safe_chain.py`

## BAXY-AUD-022 — BAXY abre el teclado en pantalla pero `app.close` no puede cerrarlo

- Severidad: P2
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Operaciones: `input.keyboard.open` → `window.resolve` → `app.close`
- Reproducción: 1/1 cadena BAXY; control de cierre alternativo 3/3
- Efecto externo: el teclado de auditoría fue cerrado al finalizar

### Observado

1. `input.keyboard.open` abrió y verificó `osk.exe`.
2. `window.resolve {"process":"osk"}` resolvió exactamente el PID recién
   creado.
3. `app.close` devolvió `failed`, `action_failed` y el teclado siguió visible.
4. El mismo HWND aceptó inmediatamente `WM_SYSCOMMAND/SC_CLOSE`, desapareció y
   no quedó ningún `osk.exe` creado por la auditoría.

### Causa raíz

El teclado en pantalla corre como proceso UIAccess. `app.close` usa
`PostMessage(WM_CLOSE)`, que devuelve falso para esa ventana bajo UIPI, y no
intenta el comando de sistema `SC_CLOSE` que la propia ventana sí acepta. La
operación de apertura tampoco devuelve un `windowId`, por lo que el usuario
necesita una resolución adicional aun si el cierre fuera compatible.

### Evidencia

- `window_input_osk_close_installed.json`
- `window_input_safe_chain.py`

## BAXY-AUD-023 — La política LLM pierde la intención en la mayoría de órdenes básicas y compuestas

- Severidad: P1
- Estado: confirmado; no corregido
- Versión: BAXY 1.0.8, Gemma-4 E2B QAT y catálogo de 168 operaciones
- Ruta: `turn.decide` y `plan` de producción
- Reproducción: matriz amplia 39/60 fallos semánticos; subconjunto sin
  historial 18/20 fallos; soak repetitivo 317/522 fallos
- Efecto externo: ninguno; la sonda solo decidió y planificó, sin ejecutar

### Metodología

Cada petición se envió al sidecar real con el catálogo autenticado del core,
modelo/runtime instalado y el mismo mensaje de bienvenida que recibe la
interfaz. Para una acción simple se aceptó tanto `kind:"action"` como un plan
de un paso con la operación esperada; es decir, el conteo no penaliza una
diferencia meramente estructural.

Resultado: 21/60 intenciones correctas y 39/60 incorrectas. La media fue
6,434 s y el máximo 16,838 s.

### Ejemplos representativos

- Hora, fecha, estado del equipo, procesos, red, volumen, ventana activa,
  música actual, Bluetooth, periféricos y Wi-Fi se contestaron como charla,
  a menudo afirmando que el modelo «no tiene acceso» a capacidades que sí
  existen y que el core verificó directamente.
- `Lee el portapapeles` → `note.read`.
- `Copia la selección` → `filesystem.copy`.
- `Crea una tarea llamada Auditoría` → `note.create`.
- `Recarga la página` → `browser.page.read`.
- Un volumen absoluto de 8 % pidió dirección «subir o bajar».
- Captura de pantalla pidió confirmación semántica innecesaria o afirmó no
  poder capturar.
- Listar notas, tareas, recordatorios y rutinas se trató como conversación
  sin acceso a datos personales.

Las cinco misiones compuestas finales fallaron 5/5:

- Opera + navegar + leer produjo solo la navegación;
- captura + OCR terminó en una aclaración sobre qué app abrir;
- crear + leer nota produjo `note.create` dos veces;
- volumen + postlectura pidió un porcentaje que ya estaba presente;
- Spotify exacto + pausa volvió a preguntar qué canción buscar.

También hubo desacuerdo interno: para hora y estado, `turn.decide` devolvió
`plan`, pero la llamada `plan` devolvió `kind:"conversation"` y cero pasos.

### Aislamiento del historial

Se repitieron 20 fallos con historial completamente vacío. Solo 2/20 se
recuperaron (`reminder.list` y `browser.control`); 18/20 persistieron. La
bienvenida agrava saludo/metadiscurso, pero no explica el fallo sistémico de
herramientas.

### Causa raíz

1. La shortlist E5 de producción sí contenía la operación correcta en 18/20
   ejemplos fallidos, por lo que la causa principal no es ausencia del
   catálogo. Solo `network.status` y `wifi.status` quedaron fuera.
2. El LLM de política selecciona conversación, aclaración o un candidato
   léxicamente próximo aun cuando el candidato correcto está visible.
3. `validate_turn_decision` comprueba forma, conteos y pertenencia al
   shortlist, pero no puede comprobar que la decisión cubra el efecto humano.
4. `apply_turn_action_relevance_veto` puede quitar autoridad a una acción poco
   relevante, pero por diseño ningún componente determinista puede promover
   una orden inequívoca que el LLM degradó a conversación.
5. `ProcessIntentRouter.route` está explícitamente deshabilitado; el parser
   determinista que sí conoce muchas de estas frases tampoco es fallback de
   autoridad en producción.
6. La segunda llamada `plan` vuelve a inferir desde cero y puede contradecir a
   `turn.decide`; no hay una invariante que obligue a conservar todos los
   efectos ya declarados por el turno.

El resultado es seguro en el sentido de que suele abstenerse, pero la
experiencia principal de BAXY no puede alcanzar gran parte del core disponible
y, en varios casos, selecciona otra operación válida pero incorrecta.

La compuerta oficial de planificación + ejecución corroboró el problema:
3/9 misiones aprobaron, 6/9 fallaron y solo seis pasos llegaron a ejecución
verificada. Entre los DAG incorrectos:

- crear un archivo se convirtió en `note.create`;
- captura + OCR se convirtió en `browser.page.read`;
- crear + leer documento omitió la lectura;
- streaming + búsqueda quedó solo en `browser.navigate`;
- Spotify exacto + pausa produjo
  `media.play.query → media.status → media.status`.

El sexto fallo fue ambiental y correctamente explícito:
`calendar.event.list` alcanzó el provider pero no había perfil Outlook.

### Repetición prolongada

Un soak de 8,713 horas reinició el worker y `llama-server` cada dos horas,
reconfiguró las 168 operaciones y repitió 13 órdenes simples/compuestas sin
ejecutar las propuestas. Terminó 522 decisiones sin anomalías de proceso o
protocolo: 205 conservaron la intención y 317 no (39,27 % de acierto).

- Estado del equipo, estado de audio, búsqueda web, tareas, captura + OCR y
  volumen + postestado fallaron 40/40.
- Notas acertó 9/40; Spotify exacto + pausa, 1/40.
- Opera + navegar + leer acertó 34/40, por lo que también es intermitente.
- Opera simple acertó 40/40, Calculadora 39/40, y saludo/hora sin historial
  41/41. La hora siguió fallando desde la UI con la bienvenida contextual,
  como registra `BAXY-AUD-007`.
- Latencia media 5,998 s, p95 11,138 s y máxima 15,461 s.

### Evidencia

- `extended_turn_probe_installed.json`
- `extended_turn_cases.json`
- `routing_failed_subset_empty_history.json`
- `routing_failed_subset.json`
- `routing_shortlist_diagnostic.json`
- `diagnose_shortlist.py`
- `llm_plan_execution_gate_installed.json`
- `mind_overnight_soak_installed.json`
- `soak_summary_final.json`

## BAXY-AUD-024 — La memoria deshabilitada se presenta como un error 500 opaco

- Severidad: P2
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Ruta: interfaz real → `memory.save` / `memory.recall`
- Reproducción: 2/2 peticiones con memoria deshabilitada
- Efecto externo: ninguno; data root sintético, posteriormente eliminado

### Observado

Con la memoria local deshabilitada:

1. `recuerda que mi color favorito es azul` alcanzó `memory.save`.
2. `qué color me gusta` alcanzó `memory.recall`.
3. El core devolvió correctamente `failed`, `verified:false` y
   `memory_disabled` en ambos casos.
4. La interfaz no explicó que había que habilitar la memoria. Mostró dos veces
   `No pude hacerlo. (500: "accion_no_completada")`.

El control positivo posterior aprobó el ciclo completo desde la misma interfaz:
habilitar con confirmación, guardar, consultar, listar, borrar con confirmación,
confirmar ausencia, deshabilitar y consultar estado.

### Causa raíz

1. `MemoryHandlers` conserva el motivo estable `memory_disabled`.
2. `CreateMemoryFailureMessage` ignora `response.ErrorCode` y reduce cualquier
   `failed` de memoria al mismo texto genérico.
3. `AddMessage` intenta reformular todos los errores con el modelo local usando
   un timeout síncrono de 3,25 s.
4. En la matriz instalada el modelo tardó 6,434 s de media; cuando no entrega
   una reformulación válida a tiempo, `UserMessagePolicy.Create` descarta
   también el texto fuente.
5. El fallback de cualquier error es el literal único
   `No pude hacerlo. (500: "accion_no_completada")`.

Por eso se pierde tanto el motivo verificable del core como una instrucción
humana para recuperar el flujo.

### Evidencia

- `memory-ui-missions.jsonl`
- `memory-ui-final-outbox.json`
- `ui-memory-flow.json`
- `ui-memory-final-status.json`
- `capture_ui_accessibility.ps1`

## BAXY-AUD-025 — La reformulación LLM elimina el dato de respuestas de memoria correctas

- Severidad: P1
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Ruta: interfaz real → `memory.recall` / `memory.list`
- Reproducción: 2/2 consultas de preferencia y 1/1 listado de un solo registro
- Efecto externo: ninguno; memoria sintética aislada y eliminada

### Observado

La interfaz guardó `response_style: direct`, lo consultó, lo corrigió a
`technical_and_brief` y volvió a consultarlo. El core completó y verificó las
dos llamadas `memory.recall`, pero ambas respuestas visibles fueron solamente:

`Encontré esta memoria local.`

No mostraron ni la clave ni el valor pedido. Después de eliminar correctamente
un registro de sesión, `memory.list` volvió a omitir el único registro
persistente restante con la misma frase genérica.

El problema no es el almacén: un listado con dos registros sí mostró
`Carter` y `response_style technical_and_brief`, y la exportación privada
posterior contenía el valor corregido.

### Causa raíz

1. `MemoryOperationResponseProjection.CreateRecordsMessage` construye una
   proyección con cada `label: value`.
2. `AddMessage` no presenta esa proyección directamente: la entrega al modelo
   como un evento `status`.
3. Para mensajes de estado, `UserMessagePolicy` solo conserva mediante
   invariantes algunas acciones en primera persona. No extrae ni exige las
   claves y valores de memoria.
4. `UserMessagePolicy.IsSafe` valida longitud y términos prohibidos, pero no
   equivalencia factual ni cobertura de la proyección.
5. La respuesta abreviada del modelo supera esa validación y reemplaza el
   mensaje determinista completo.

Así, una operación privada verificada puede convertirse en una afirmación
correcta pero inútil que no responde qué dato fue encontrado.

### Evidencia

- `ui-memory-correction.json`
- `ui-memory-session-clear.json`
- `memory-extended-ui-missions.jsonl`
- `memory_export_ui_installed.json`

## BAXY-AUD-026 — Una navegación de streaming “verificada” aún no está lista para el paso siguiente

- Severidad: P1
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Cadena: `streaming.navigate` → `browser.page.read`
- Reproducción: fallo inmediato 3/3; control con espera 4/4 pasos
- Efecto externo: sesiones YouTube aisladas, cerradas al terminar

### Observado

En tres cores instalados independientes:

1. `streaming.navigate` a `https://www.youtube.com/` terminó
   `completed`, `verified:true`.
2. El siguiente paso `browser.page.read`, emitido inmediatamente como haría el
   ejecutor de un plan, falló 3/3 con
   `browser_page_snapshot_invalid`.
3. Repitiendo la misma cadena con una espera de 5 segundos entre pasos,
   navegar, leer, listar pestañas y recargar aprobaron 4/4.

No quedó ningún proceso de navegador de la auditoría.

### Causa raíz

1. `CdpBrowserSession.NavigateAsync` considera verificada la navegación en
   cuanto `location.href` deja de ser `about:blank` y coincide con una URL
   HTTP(S).
2. No exige `document.readyState` `interactive` o `complete`.
3. `StreamingAsync` hereda ese recibo y publica éxito inmediatamente.
4. `CdpBrowserSession.ReadPageAsync` sí exige esos estados, pero toma una sola
   instantánea y no contiene un bucle de convergencia.
5. El ejecutor de planes concatena pasos verificados sin una espera arbitraria,
   por lo que el contrato de salida de navegación es demasiado débil para su
   consumidor natural.

El resultado es un falso fallo determinista de las acciones compuestas de
navegar y después inspeccionar una página dinámica.

### Evidencia

- `streaming_navigate_chain_installed.json`
- `streaming_navigate_chain_installed_2.json`
- `streaming_navigate_chain_installed_3.json`
- `streaming_navigate_chain_delayed_installed.json`
- `browser_chain.py`

## BAXY-AUD-027 — La reproducción exacta de Spotify falla de forma intermitente al abrir

- Severidad: P1
- Estado: confirmado; no corregido
- Versión: instalación BAXY 1.0.8
- Ruta: `media.play.exact` con proveedor Spotify y título `Beat It`
- Reproducción: 2/5 fallos en cinco ciclos limpios; 3/5 controles positivos
- Efecto externo: Spotify se abrió y se cerró en cada ciclo; no quedó reproducción
  activa ni proceso creado por la auditoría

### Observado

En cinco cores instalados independientes, cada uno partiendo únicamente del
launcher de Spotify preexistente:

1. Tres ciclos encontraron `Michael Jackson - Beat It`, iniciaron reproducción
   exacta y aprobaron estado, salto de diez segundos, pausa y postestado:
   5/5 operaciones verificadas en cada ciclo.
2. Dos ciclos encontraron el resultado, pero tras unos 27 segundos devolvieron
   `spotify_exact_play_control_not_found`.
3. En ambos fallos el core terminó normalmente y no afirmó éxito ni dejó música
   sonando; el problema es de disponibilidad funcional, no un falso positivo.
4. La búsqueda no exacta del mismo tema aprobó antes 5/5, por lo que el fallo
   queda acotado a la selección exacta.

### Causa probable

1. `SpotifyDesktopAutomation.ps1` identifica la tarjeta del título exacto.
2. Si no encuentra su botón de reproducción, invoca la tarjeta y espera hasta
   doce segundos por un control en la vista de detalle.
3. Si esa UI transitoria no expone a tiempo el botón con el nombre exacto
   esperado, devuelve `spotify_exact_play_control_not_found`.
4. `SpotifyDesktopAdapter` solo reintenta
   `spotify_exact_result_not_found`; este segundo fallo transitorio se propaga
   inmediatamente y no tiene reintento de la operación completa.

La causa se registra como probable porque esta sesión es de auditoría y no se
instrumentó ni modificó el producto para capturar el árbol UIA interno durante
el fallo.

### Evidencia

- `media_exact_control_chain_installed.json`
- `media_exact_control_chain_installed_2.json`
- `media_exact_control_chain_installed_3.json`
- `media_exact_control_chain_installed_4.json`
- `media_exact_control_chain_installed_5.json`
- `media_control_chain.py`
