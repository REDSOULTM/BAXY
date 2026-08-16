# Contratos, flujos y datos

## Principio de autoridad

BAXY usa una cadena de autoridad cerrada:

```text
lenguaje natural
  → propuesta
  → operación/plan del catálogo
  → validación determinista
  → política y confirmación
  → identidad durable
  → efecto
  → postlectura
  → outcome
  → narración
```

Cada flecha reduce ambigüedad; ninguna concede una operación que no exista en
el catálogo compilado.

| Capa | Puede | No puede |
|---|---|---|
| FieldUi | recoger input y mostrar estado | ejecutar tools o providers |
| App | coordinar, preparar, confirmar, recuperar y presentar | inventar una operación pública |
| Mind | conversar, extraer, proponer acción/DAG y operar voz | decidir riesgo, confirmar, ejecutar o declarar éxito |
| Contracts | representar y validar wire data | contener conducta de producto |
| Kernel | validar catálogo/schema/policy/identidad/estado | usar APIs de Windows |
| Core | componer y conducir el engine | interpretar libremente lenguaje |
| Provider | leer/aplicar/postleer plataforma | redefinir policy o outcome visible |
| Setup | verificar y mutar instalación | compartir autoridad con runtime de usuario |

## Fronteras de proceso

### App ↔ Core: `baxy.local.v1`

Transporte: stdin/stdout JSONL UTF-8. Core limita a 1 MiB las solicitudes que
lee y el `hello` que escribe; App limita a 1 MiB cada respuesta que consume.
El writer de `operation.response` en Core todavía no valida el envelope
serializado completo antes de escribirlo. App rechaza una respuesta mayor, pero
eso no convierte la frontera en simétrica: el gap está registrado como deuda.

Mensajes:

| Tipo | Dirección | Rol |
|---|---|---|
| `hello` | Core → App | versión, PID, capabilities y catálogo de aplicaciones |
| `operation.request` | App → Core | operación, argumentos, mission/invocation y confirmación |
| `operation.response` | Core → App | outcome, código, mensaje, datos y metadata de efecto |
| `protocol.error` | Core → App | framing/JSON/contrato inválido |

App resuelve y lanza el core local esperado, comprueba el PID comunicado y
compara los 168 descriptores públicos completos y ordenados contra el catálogo
que compiló. Core también exige igualdad de registry y catálogo, incluyendo su
operación interna. Esta es validación/pinning del hijo y del contrato, no firma
criptográfica del hello ni autenticidad de editor.

Algunos identificadores y comentarios históricos del source llaman
`authenticated catalog` a esta frontera. En ese contexto significa catálogo
cerrado validado/pinned. Reserva “autenticación criptográfica” para mecanismos
que realmente usan MAC, AEAD, firma o una sesión autenticada.

La interacción es serial por perfil. Core toma una sola instancia por data root
y `MissionEngine` permite una ejecución a la vez para preservar orden,
idempotencia y efectos. “Escalar BAXY” no significa paralelizar mutaciones del
mismo perfil sin rediseñar esas garantías.

### App ↔ Mind: `baxy.mind.v1`

Transporte: stdin/stdout JSONL UTF-8, máximo 1 MiB por línea.

Secuencia de arranque:

```text
App lanza python -X utf8 -m baxy_mind
  → Mind crea el LLM opcional e inicia su warmup
  → Mind emite hello
  → App valida proceso/protocolo
  → App envía catalog.configure una sola vez
  → Mind publica planner lexical
  → encoder/evidencia se preparan en background
  → catalog.ready espera readiness del LLM si existe runtime
  → voz permanece lazy hasta que se solicita
```

El warmup empieza antes del saludo, pero `catalog.configure` es quien espera su
readiness: 120 s es la ventana de transporte de startup, 105 s el presupuesto
de catálogo y 90 s el máximo dedicado al warmup.

Solicitudes anunciadas actualmente por `hello.requests`:

| Solicitud anunciada | Resultado | Regla |
|---|---|---|
| `catalog.configure` | `catalog.ready` | una vez por proceso; catálogo cerrado |
| `turn.decide` | `turn.result` | única decisión contextual pública |
| `plan` | `plan.result` | solo tras un turno de tipo plan |
| `plan.ground` | argumentos anclados | solo observaciones estructuradas verificadas |
| `narrate` | texto natural | outcome tipado a lenguaje humano |
| `voice.start/stop/status` | acuses/estado | direct o wake según disponibilidad |
| `voice.speak/cancel` | aceptación/cancelación | SAPI y barge-in |
| `shutdown` | `shutdown.ack` | acuse terminal de transporte |

Implementadas y consumidas actualmente por App, pero omitidas del anuncio:

| Solicitud no anunciada | Resultado | Uso actual |
|---|---|---|
| `arguments` | extracción/abstención | App extrae contra schema y evidencia literal |
| `message.compose` | mensaje natural | App compone texto desde hechos acotados |

`turn.evidence.status` también está implementada y omitida del anuncio, pero la
consume tooling de gates, no el flujo normal de App. La omisión ya afecta a dos
consumidores existentes; no es solo un riesgo futuro. Corregir el contrato
público exige coordinar App, sidecar, tests de handshake y compatibilidad.

Los únicos mensajes no solicitados son `voice.transcript` y `voice.event`; los
subtipos como parcial/estado viven en el campo `event`, no en tipos
`voice.*` inventados. `voice.started`/`voice.stopped` son acuses del handler, no
prueba de que todo cleanup retenido haya terminado. `shutdown.ack` puede
publicarse antes de `lifecycle.close`, así que certifica cierre del transporte,
no reap físico exitoso.

Plano de control:

- un único reader acotado recibe stdin;
- la cola de entrada normal tiene capacidad finita;
- un coordinador decide prioridad;
- `_SerialRequestLane` serializa catálogo, lenguaje/planner y
  `voice.start/stop/status/speak`;
- el build de evidencia y la promoción del planner sí corren en threads de
  background con ownership explícito;
- cancelación de voz y shutdown pueden eludir la lane cuando existe trabajo
  bloqueante; fuera de esa condición siguen el dispatch normal;
- un writer terminal único serializa stdout;
- un resultado tardío del worker de router retirado no se reutiliza.

Esto evita carreras y sobrecarga del notebook. No paralelices generaciones o
planificaciones sin un contrato de correlación, cancelación y presupuesto.

### FieldUi ↔ App: `baxy.field.v1`

`Baxy.App/Assets/field-native-bridge.js` adapta los `fetch` y WebSocket
históricos a mensajes WebView2. `FieldUiBridge.cs` valida origen, método,
route, shape y límites.

Familias de rutas:

- estado: `/agent/status`, `/model`, `/metrics`, `/hardware`;
- superficies: `/surfaces`;
- voz: `/voice/status`, `/voice/start`, `/voice/stop`, `/voice/trigger`;
- turnos y actividad: `/turn`, `/activity`, `/log/clear`;
- sesiones: `/sessions`, `/sessions/new|load|rename`;
- memoria, triggers y tools: interfaces acotadas, no proxy genérico;
- perfil/accesibilidad/settings: estado administrado por App;
- inventory/restart/recycle: acciones explícitamente soportadas;
- upload: rechazado mientras no exista contrato tipado de adjuntos.

El bridge bloquea navegación externa, ventanas nuevas, red arbitraria y
ejecución JSON directa de tools. Cambiar una route es un cambio de contrato
entre JS versionado, bridge C# y pruebas.

## Flujo de un turno de texto

### 1. Ingreso

El compositor o una ruta nativa crea `MissionInput`. App agrega historial
acotado y estado de interacción, pero no transforma texto en autoridad.

### 2. Decisión

Con mind disponible, App usa `turn.decide`. El resultado puede ser:

- `conversation`: respuesta sin operación;
- `clarify`: pregunta necesaria antes de continuar;
- `action`: una operación exacta del catálogo;
- `plan`: una secuencia DAG de hasta 16 pasos.

Sin mind, App conserva rutas deterministas acotadas App → Core para slices
privadas soportadas. No existe un router general de lenguaje en Core: el
lenguaje libre degrada sin ejecutar. Estas rutas no deben crecer como un
inventario de frases para imitar al LLM.

### 3. Argumentos

Para una acción, la extracción:

- usa el JSON Schema del catálogo;
- conserva strings abiertos como evidencia literal del mensaje;
- valida tipos cerrados de forma determinista;
- pregunta si falta un requerido;
- se abstiene si el valor no puede anclarse a evidencia verificable.

Un plan conserva `expectedOperations` en orden. El modelo puede completar
argumentos y dependencias, pero no sustituir u omitir efectos explícitamente
reconocidos.

### 4. Preparación

App crea una `PreparedOperation` con:

- operación;
- argumentos;
- `missionId`;
- `invocationId`;
- challenge/confirmación cuando corresponde.

Los IDs sobreviven al retry. Cambiar argumentos con el mismo invocation ID
produce `idempotency_conflict`.

### 5. Validación y política

Kernel valida:

1. contrato;
2. existencia exacta en registry;
3. schema;
4. frontera privada;
5. riesgo;
6. challenge ligado al fingerprint;
7. confirmación.

El LLM no decide ninguno de esos puntos.

### 6. Durabilidad antes del efecto

El journal reserva capacidad terminal y persiste `started` antes de llamar al
handler. Si no puede garantizar esa transición, rechaza antes del efecto.

### 7. Provider y postlectura

El handler llama al provider. El provider:

- liga el target;
- evita fallback después de efecto observado o ambiguo;
- conserva receipt/intención cuando el dominio lo requiere;
- postlee estado real;
- diferencia “solicitud enviada” de “resultado verificado”.

En providers externos puede haber varios adapters ordenados. Se prueba el
siguiente únicamente mientras no exista `Verified`, `EffectObserved` ni
`EffectMayHaveOccurred`.

### 8. Outcome

Estados wire:

| Estado | Terminal | Reintento | Significado |
|---|---:|---:|---|
| `completed` | sí | no | postcondición comprobada |
| `failed` | sí | no automático | fallo honesto; puede incluir efecto ambiguo |
| `rejected` | sí | no | policy, contrato o confirmación rechazados |
| `pending` | no | sí, mismo ID/fingerprint | precondición reintentable sin terminal |

`effectMayHaveOccurred:true` significa que repetir podría duplicar un efecto.
Debe conservarse la operación y pedir reconciliación o intervención; no se
convierte en `pending` ni en éxito.

Replay:

- un terminal con el mismo fingerprint devuelve el terminal registrado;
- un ID nuevo es otra invocación;
- mismo ID y distinto fingerprint falla;
- un `started` incompleto conserva identidad y recovery conservador;
- no se afirma exactly-once más allá de la evidencia específica del provider.

### 9. Narración

App proyecta el resultado y pide narración al mind cuando está disponible. El
usuario recibe lenguaje breve y humano. JSON, nombres de clases, estados del
router y trazas quedan como diagnóstico opcional, nunca como respuesta normal.

## Flujo de un plan

```text
turn.decide → plan
  → skeleton DAG ≤ 16
  → validación de operaciones y dependencias
  → checkpoint cifrado
  → para cada paso listo:
       ground con observaciones estructuradas
       preparar/confirmar
       ejecutar por Core
       guardar outcome/observación/checkpoint
  → completar, aclarar, replanificar acotadamente o detenerse
```

Reglas:

- las dependencias solo apuntan a pasos anteriores;
- no hay ciclos ni más de 16 pasos;
- `memory.*` queda fuera del planner general;
- grounding no recibe texto libre de web, OCR o documentos;
- un paso fallido no se salta como si hubiera producido su observación;
- un efecto ambiguo pausa el plan;
- el checkpoint se escribe antes de avanzar;
- recovery no genera una identidad nueva para ocultar una invocación incierta.

## Flujo de voz

Entrada directa:

```text
voice.start direct
  → micrófono
  → VAD
  → audio del turno
  → Parakeet final + AEC
  → voice.transcript
  → MissionInput
```

Entrada con wake:

```text
KWS ONNX «Baxy»
  → pre-roll
  → VAD
  → Nemotron parcial opcional
  → Parakeet final + AEC
  → voice.transcript
```

Reglas:

- el wake acústico es opcional; sin modelo calibrado sigue disponible el botón
  directo;
- el fallback lexical está apagado salvo migración explícita;
- Nemotron solo publica parciales después de abrir un turno autorizado;
- Parakeet produce la transcripción final que entra al flujo;
- los términos de corrección se derivan del catálogo y no conceden autoridad;
- `voice_output.py` posee un único worker/cola SAPI y su cancelación;
- `AudioDucker` vive en `voice_aec.py` y `VoiceEngine` coordina su uso con TTS,
  AEC, loopback y `voice.cancel`/barge-in;
- el owner de cada job de cleanup se conserva hasta que termina o se reporta.

El gate sintético no prueba micrófono, altavoz, sala o voz del usuario. Los
gates físicos se ejecutan por separado y con presencia/precondiciones.

## Cancelación, deadlines y ownership

Un deadline no es solo un timeout de UI:

- se calcula con reloj monotónico;
- cada suboperación recibe el presupuesto restante;
- un timeout de protocolo retira/marca el worker cuando su contrato lo exige;
- un timeout HTTP del LLM descarta/reintenta dentro del presupuesto, pero no
  mata `llama-server` por cada request;
- no se reutiliza una respuesta tardía;
- el proceso LLM se reapea en cierre o muerte de startup, y el worker de router
  se retira/reapea ante fault o timeout de su protocolo;
- shutdown cancela lanes, voz, LLM, evidencia y router en orden;
- un fallo secundario de cleanup no puede sobrescribir el terminal principal.

Operaciones nativas no interrumpibles pueden terminar después de una señal de
cancelación; por eso el owner y la semántica de efecto potencial deben
permanecer vivos. “Cancelar” no significa fingir que nada ocurrió.

## Persistencia

Data root normal:

```text
%LOCALAPPDATA%\BAXY\1
```

`BAXY_DATA_DIR` no es una ruta arbitraria: `WindowsPrivateStorage` exige un hijo
directo permitido bajo `%LOCALAPPDATA%\BAXY` y valida ACL, owner, handles, ADS y
reparse points.

### Matriz de stores

| Datos | Owner/ruta relativa | Protección | Recovery y límites relevantes |
|---|---|---|---|
| Journal de invocaciones | Core/Kernel: `journal/missions.jsonl` + `.anchor` | HMAC-SHA256 encadenado; clave protegida DPAPI | fsync, compactación, 64 MiB, reserva terminal de 2 MiB |
| Clave journal | Security: `security/journal-hmac.v2.key` | DPAPI CurrentUser | ausencia incompatible falla cerrado |
| Estado de plan | App: `shell/planner-state.v1.bin` + key | AES-GCM, purpose binding, clave DPAPI | 1 MiB; checkpoint/recovery |
| Retry outbox | App: `shell/retry-outbox.v1.json` | texto plano + checksum SHA-256 | 128 entradas, 1 MiB; detecta corrupción accidental, no MAC |
| Memoria privada | Provider: `memory-store/` | envelopes AES-GCM, purpose binding, clave DPAPI | 512 registros, 4.096 receipts, recovery |
| Notas | Provider: `notes-store/` | JSON en claro con SHA-256 y backup atómico | 512 notas, 96 KiB por documento |
| Tareas | Provider: `tasks-store/` | JSON en claro con integridad/backup del store | límites de texto y páginas |
| Recordatorios | Provider: `reminders-store/` | mismo store base de tareas | misma semántica |
| Rutinas | Provider: `routines-store/` | mismo store base; payload en claro | lifecycle explícito |
| Audio | Provider: `audio/control-state/` | intent/receipt durable, no prometer cifrado | store propio: 64 KiB/archivo, 16.384 entradas y 64 MiB totales |
| Apertura de apps | Provider bajo data root | estado de invocación durable | store propio: 1 MiB/archivo, 16.384 entradas y 64 MiB totales; scan O(n) |
| Capturas | Provider: `captures/` | archivo local acotado | postlectura y path safety |
| Filesystem sandbox | Provider: `filesystem-sandbox/` | confinamiento de ruta | no escape/reparse |
| Runtime mind | `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json` | manifest validado; no secreto | reemplazo controlado por scripts |
| Modelos/caches | candidatos de `assets.manifest.json` y caches declarados | hashes/manifests por componente | fuera del paquete/repositorio |
| Versiones instaladas | `%LOCALAPPDATA%\Programs\BAXY` | paquete/content-id/hashes | versiones inmutables, current/previous, recovery |

Notas importantes:

- SHA-256 sin clave detecta corrupción, no manipulación hostil;
- DPAPI `CurrentUser` protege al usuario local, no sustituye aislamiento frente
  a código que ya ejecuta como el mismo usuario;
- `memory.*` cifra argumentos/resultados privados, pero metadata no sensible y
  challenges pueden permanecer en claro;
- exportar memoria a Documentos tiene una frontera de privacidad distinta;
- journal v1 sin firma se archiva como no confiable, no se adopta;
- un cambio de formato necesita versión, migración, recovery, límites y tests;
- nunca “arregles” un archivo persistido manualmente para hacer pasar una
  prueba.

## Límites que protegen disponibilidad

Selección de valores actuales que deben conservarse o cambiarse mediante
contrato:

| Frontera | Límite |
|---|---:|
| solicitud/hello Core y lectura de respuesta App | 1 MiB; writer de respuesta Core pendiente de precheck |
| solicitud/respuesta Mind | 1 MiB |
| startup / catálogo / warmup Mind | 120 / 105 / 90 s |
| `turn.decide` transporte / normal compartido por intentos / recovery | 22 / 17 / 2,5 s |
| `arguments` | 19,25 s |
| contexto LLM | 4.096 tokens |
| encoder E5 | batch de 4.096 textos / 4.096 caracteres por texto |
| skill | 32 KiB por archivo / 3 seleccionadas / 12.000 caracteres de prompt |
| TTS SAPI | 8.192 caracteres / cola de 16 |
| plan | 16 pasos |
| shortlist planner | 10 familias / 28 operaciones |
| catálogo de aplicaciones | 2.048 nombres / 262.144 bytes |
| outbox App | 128 entradas / 1 MiB |
| documento de nota | 96 KiB |
| notas | 512 |
| memoria | 512 registros / 4.096 receipts |
| estado de aplicaciones | 1 MiB por archivo / 16.384 entradas / 64 MiB |
| estado de audio | 64 KiB por archivo / 16.384 entradas / 64 MiB |
| journal | 64 MiB |
| cola normal del control plane Mind | 4 solicitudes |
| pendientes de lane serial Mind | 16 |

No conviertas un límite en truncamiento silencioso. Rechaza antes del efecto,
pagina o pregunta; si se cambia, actualiza productor, consumidor, tests y
documentación.

## Variables de entorno

Nombres principales:

| Familia | Variables |
|---|---|
| Core/App | `BAXY_DATA_DIR`, `BAXY_MIND_DISABLED` |
| Mind | `BAXY_MIND_PYTHON`, `BAXY_MIND_PYTHONPATH`, `BAXY_MIND_LLM_GGUF`, `BAXY_MIND_LLAMA_SERVER`, `BAXY_MIND_NGL`, `BAXY_MIND_STT_DIR` |
| Voz | `BAXY_VOICE_WAKE_ON_START` y variables detalladas en `src/baxy_mind/README.md` |
| Browser/vision | `BAXY_CDP_ENDPOINT`, `BAXY_VISION_ENDPOINT`, `BAXY_VISION_MODEL`, `BAXY_VISION_API_KEY` |
| Servicios | `BAXY_GRAPH_ACCESS_TOKEN`, `BAXY_SPOTIFY_ACCESS_TOKEN` |
| Tools | `BAXY_MPV_PATH`, `BAXY_YTDLP_PATH`, `BAXY_NODE_PATH` |

Documenta y registra solo nombres/estado redactado. Nunca imprimas tokens, API
keys, contenido privado ni rutas que expongan datos innecesarios.
