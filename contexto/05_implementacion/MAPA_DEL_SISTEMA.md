# Mapa del sistema

Estado: cuerpo determinista de BAXY 1.0 cerrado en la frontera Codex → Fable;
Fable ya implementa IA, planner durable, composición y voz local completa.
Solo quedan calibraciones que exigen al usuario/perfil limpio. Los cortes bajo
`experiments/technology_tournament/` siguen siendo evidencia del torneo, no el
runtime productivo.

Base aprobada por `../04_arquitectura/ADR/ADR-0001-arquitectura-base-baxy-1.md`:

usuario → BAXY Field React congelado → bridge nativo WebView2/WPF → frontera JSONL local `baxy.local.v1` →
core .NET 10 NativeAOT → operaciones tipadas → efecto local → verificación →
journal/replay → respuesta acotada.

La extensión vigente añade: host WPF ↔ `baxy.mind.v1` ↔ router/LLM/planner y
micrófono → Silero → Parakeet → `MissionInput`; la salida vuelve por la misma
respuesta mostrada y SAPI. La mente propone, pero no adquiere autoridad del
core.

## Cortes implementados

La solución `Baxy.slnx` separa cinco proyectos productivos:

- `Baxy.Contracts`: contratos JSONL, validación y serialización compatible con
  NativeAOT;
- `Baxy.Kernel`: registro de operaciones y superficie de tools, ejecución de
  misiones, resultados tipados, huellas, journal y replay;
- `Baxy.Providers.Windows`: persistencia local de notas, apertura/verificación
  acotada de aplicaciones permitidas, medición read-only del estado local y
  control verificado del audio global, provider GPU DXGI+PDH, memoria privada y
  exportación local;
- `Baxy.Core`: proceso NativeAOT que publica el saludo de protocolo, atiende
  peticiones y verbaliza resultados tipados mediante un narrador separado;
- `Baxy.App`: host WPF que administra core/mind mediante sidecars JSONL con Job
  Object, hospeda WebView2 y adapta el contrato de la GUI histórica sin darle
  autoridad directa;
- `Baxy.FieldUi`: exportación React/Vite literal de la interfaz de `4a83f2d`.

El catálogo congelado contiene 22 operaciones totales y expone 21 tools
públicas. `app.status` es la única operación interna. Las once operaciones
`memory.*` son `correct`, `disable`, `enable`, `export`, `forget`,
`list`, `recall`, `save`, `sensitive.save`, `session.clear` y `status`. El parser
de texto de WPF reconoce frases acotadas
ES/EN/spanglish para todo el ciclo de notas, apertura directa o cortés de Bloc
de notas, consultas locales de CPU, RAM, disco del sistema, batería y Windows,
y consultas de identidad/uso puntual de GPU, órdenes de volumen absoluto o mute
explícito del audio global, además de
memoria explícita local. `app.open` solo
puede producir `appId=windows.notepad`. Los scopes combinados de status son una
sola operación read-only y cada orden de audio es una operación independiente;
estos cortes no implementan conversación general ni composición multioperación.

## Costuras Codex → Fable

- `MissionInput` unifica `Text` y `VoiceTranscript`; la procedencia no cambia
  parser, riesgo, confirmación ni ejecución. Las regex de idioma permanecen en
  la capa interina delimitada por test.
- `OperationOutcome` transporta estado, resultado y error tipados, sin texto
  público. `ProductOperationNarrator` es la única capa productiva que convierte
  esos datos en respuesta natural.
- `OperationRegistry` conserva 22 definiciones y proyecta 21 descriptores de
  tool públicos completos. El wire no exporta la salud interna `app.status`.
- `LocalJsonlSidecarProcess` hospeda el core y deja la misma frontera lista para
  un segundo proceso local, sin incorporar todavía Python ni un modelo.

Evidencia: `artifacts/product/architecture_seams_gate.json`.

Las acciones naturales por título nunca convierten texto en una ruta o comando.
El provider normaliza Form C y compara títulos exactos con
`OrdinalIgnoreCase`: lectura requiere una coincidencia activa; papelera y
restauración requieren una sola coincidencia en todos los estados. Búsqueda y
mutación comparten el lock del store, y un estado objetivo ya alcanzado se
reconcilia sin aumentar revisión. Los duplicados devuelven una shortlist
inmutable; la GUI pagina cinco elementos, acepta una selección contextual y
envía una ruta exacta enlazada a UUID, título, revisión y estado. El provider
rechaza un candidato obsoleto con `note_selection_stale`, sin contenido ni
efecto. UUID y JSON permanecen fuera de la experiencia visible.

El shell solo habilita entrada si el saludo contiene una vez cada una de sus 21
tools públicas, en orden, y coinciden exactamente nombre, schema cerrado,
riesgo, contrato verificador y descripción. El catálogo total contiene 22
porque `app.status` es salud interna. `app.status` usa schema vacío estricto y
el core valida al arrancar que ProductCatalog y OperationRegistry coincidan en
identidad y orden. `note.read` se proyecta como título/contenido en lenguaje
natural, nunca como JSON; la vista se trunca explícitamente a 16.384 caracteres
sin dividir un par surrogate.

## Estado local read-only

`system.status` acepta `summary`, `cpu_memory`, `os_memory`, `cpu`, `memory`,
`disk`, `battery`, `os`, `gpu_identity` y `gpu_usage`. El uptime se recopila
únicamente dentro de `summary`; `uptime` no es scope público. El provider legado
solo consulta las secciones pedidas: CPU mediante dos muestras separadas por
150 ms, RAM total/disponible, capacidad y espacio del disco del sistema,
batería/alimentación, versión/build/arquitectura de Windows y tiempo activo.

No hay campos ni probes de procesos, IP, hostname o usuario. Una
batería ausente es una medición válida y un estado totalmente desconocido no se
convierte en presencia inventada. Un summary puede conservar mediciones válidas
y nombrar fallos parciales saneados. El summary conserva su JSON/provider legado
y no sondea GPU. El handler rechaza evidencia contradictoria o fuera del scope
antes de publicar éxito.

El oráculo runtime congela 113 IDs de producto —50 literales, una misión y nueve
rutas `source`—, no las 306 filas globales `system.status`. Resumen genérico,
`os` standalone y spanglish solo tienen contrato sintético. El E2E atraviesa
ViewModel→core→Win32 y oculta JSON/nombres internos en la respuesta.

## Estado GPU local

`gpu_identity` enumera adaptadores y capacidades mediante DXGI sin abrir
contadores de uso. `gpu_usage` añade una fotografía puntual de porcentaje,
memoria gráfica dedicada usada y RAM compartida usada mediante PDH. Ambos usan
un contrato JSON separado compatible con NativeAOT y conservan el catálogo en
21 operaciones totales/20 interactivas. La decisión está congelada en
`../04_arquitectura/ADR/ADR-0002-estado-gpu-local.md`.

No hay subprocess, red ni dependencia de fabricante. Las frases con
`nvidia-smi` son únicamente alias naturales de `gpu_usage`; ninguna respuesta
afirma haber ejecutado la herramienta. Temperatura, energía, ventilador, clocks,
procesos y monitoreo continuo quedan fuera.

El provider conserva orden y multiplicidad de adaptadores y correlaciona DXGI
con PDH sin publicar LUID/PID. La respuesta visible desambigua con ordinales
uno-based; el JSON interno usa `AdapterIndex` cero-based. Para uso, los tres
campos de medición aparecen juntos o quedan `null`. Un adaptador no medido puede
producir `unsupported` indexado junto a otros medidos; si no existe evidencia de
ninguno, hay un solo fallo global. Evidencia inválida o contradictoria falla
cerrada y no se convierte en uso cero.

El oráculo GPU congela 77 casos: 7 de identidad, 19 de uso, 17 composiciones y
34 negativos duros. Una ejecución física managed y la compuerta NativeAOT
observaron tres adaptadores, dos medidos y uno no disponible con fallo indexado.
`scripts/test_gpu_status.ps1` corroboró hello 21, identity/usage verificados,
un `unsupported` indexado, cero fallos globales, correlaciones, warmup
`malformed_json`, stderr vacío y exit 0. Publicó schema
`baxy-gpu-status-gate-v1` en `artifacts/product/gpu_status_gate.json`. El core
AOT de esa evidencia del octavo corte mide 7.376.384 bytes y tiene SHA-256
`17b88aed29af5d4cc9dffb3931b73ce13791b304e4f1a7692d2f9eb588550fe9`.

La frontera JSONL aplica un máximo de 1 MiB en ambas direcciones: el core acota
su entrada y la GUI acota la salida que recibe antes de asignarla; la captura de
stderr también queda limitada. El core continúa atendiendo después de una
entrada malformada o rechazada. `note.list` usa paginación explícita: `limit`
vale 50 por defecto, se limita a 100 y se combina con `offset`; el provider
devuelve resúmenes sin contenido y el store admite un máximo de 512 notas.
La snapshot ambigua comparte ese máximo, limita cada preview a 128 bytes UTF-8
y, en el caso adversarial automatizado, su respuesta completa queda bajo
700.000 bytes y el límite de 1 MiB. El protocolo transporta UUID internamente;
solo la proyección de la GUI los oculta.

## Control global de audio

`audio.volume` acepta un entero absoluto de 0 a 100 y `audio.mute` un estado
booleano explícito. Ambas operaciones apuntan solo al endpoint de salida
predeterminado `eRender`/`eMultimedia` y tienen riesgo `low_reversible`. No hay
control relativo, por sesión/aplicación, de micrófono, de otros dispositivos ni
consulta pública de estado; el parser rechaza negaciones, condicionales y mezcla
con otra operación.

El oráculo ejecutable fija 143 mensajes históricos —109 literales, 14 fuentes y
dos misiones—. Es una slice de 529 filas de audio y 397 filas de producto clase
`user_mission`.
Las dos misiones standalone reúnen 335 mensajes —248 de volumen y 87 de mute—;
quedan 192 mensajes de esas dos misiones standalone sin acreditar; además quedan
composiciones fuera de la slice.

El provider usa interfaces COM generadas compatibles con NativeAOT. Bajo un
mutex, toma una prelectura fresca, persiste una intención durable y recién
entonces llama al setter de Core Audio; después vuelve a leer volumen y mute y
comprueba tanto el objetivo como la dimensión que debía preservar. El endpoint
solo se conserva como SHA-256 en la evidencia. Un receipt reconciliado afirma
estado observado, no causalidad ni exactly-once.

Una intención sin receipt terminal produce estado `pending` y no completa el
journal. El shell bloquea otras rutas, conserva el mismo
`missionId`/`invocationId` y permite continuar con la orden exacta aun después
de reiniciar. No ejecuta rollback ni reaplica automáticamente un efecto
incierto. El store de audio falla cerrado antes de otro efecto si alcanza
16.384 entradas o 64 MiB; ese cap es deuda operativa P2.

El gate `artifacts/product/audio_control_gate.json` atravesó core NativeAOT y
JSONL en un equipo real: desde 0,98/98 %/no silenciado verificó 88 %, mute,
replay sin segundo efecto y restauración exacta. El gate mide estado del control
endpoint, no sonido audible; cubre un equipo y un device, no el parser WPF,
sesiones, otros endpoints ni modo exclusivo.

## Memoria privada explícita

La memoria está apagada por defecto. `memory.enable`, `memory.export` y
`memory.sensitive.save` requieren confirmación `privacy_sensitive`;
`memory.forget` usa `work_loss`; recall/list/status son `read_only`; correct,
disable, save y session.clear son `low_reversible`. La GUI separa el contenido
sensible de su proyección pública y conserva la identidad de misión/invocación
al confirmar o recuperar una operación pendiente.

La frontera App→Core no transporta argumentos ni resultados privados en texto
plano. `BoundProtectedJsonCodec` sella un envelope ligado a operación,
`missionId`, `invocationId` y `sessionId`; el Core lo autentica antes del handler
y vuelve a sellar los resultados privados exitosos. Challenge, expiración y
reconciliación viajan fuera del envelope; el bearer token queda en RAM,
redactado y sin persistir. Los fallos genéricos son metadatos públicos. La misma
protección cubre las entradas privadas del outbox y los payloads privados del journal. La
clave durable se guarda bajo DPAPI Current User; el ciphertext previo falla
cerrado ante pérdida o cambio de clave. El sentinel detecta key
ausente/cambiada solo si su contraparte original permanece y no detecta un
reemplazo coordinado bajo el mismo usuario.

`LocalMemoryStore` persiste snapshot, recovery, watermark e intención en sobres
autenticados/cifrados. Admite 512 registros, 4.096 receipts, valores de hasta
4.096 bytes UTF-8, 16 tags, recall de cinco resultados y listado paginado de
hasta 100. Distingue retención persistente, de sesión y temporal; una memoria
temporal no puede superar 30 días y la ruta natural actual usa 24 horas. El
watermark detecta rollback parcial/incoherente y la intención permite completar
o recuperar una mutación sin fabricar éxito. Un rollback coordinado de
current/recovery/watermark autenticados puede conservar coherencia y aceptarse.

La raíz productiva solo puede ser `%LocalAppData%\BAXY\<hijo-directo>`. El
directorio BAXY y la hoja se crean atómicamente con DACL protegida para usuario
y SYSTEM. Raíz, key, store y export validan por handle volumen local, ruta
final, owner y ausencia de reparse; los archivos validan además un solo hardlink.
Sus handles de directorio
niegan delete sharing durante la operación y el rename es relativo al directorio
ya validado. Outbox y journal residen bajo la raíz protegida, pero sus archivos
aún se abren por path/FileStream y no heredan esas garantías por handle.

`memory.export` incluye los registros visibles, exige confirmación y escribe
JSON inspeccionable en `Documentos/BAXY`; redacta el contenido de registros
sensibles/secretos y nunca exporta sus valores originales. El recibo no expone
ruta ni hash en la experiencia pública. En replay, el Core vuelve a abrir el archivo y
verifica ruta determinista, schema, invocation ID, conteo y SHA-256; borrado o
alteración produce fallo honesto. La carpeta Documentos puede estar redirigida
o sincronizada por Windows y la GUI lo advierte antes y después.

El parser se apoya en el oráculo congelado de 100 positivos —60 literales—,
cinco correcciones y 34 negativos duros, con contratos de TTL, consentimiento e
inspección. No convierte contexto de conversación en una orden independiente y
no guarda por inferencia. Gate 10 está aprobado en el techo determinista v3 con
405/405 pruebas focalizadas y cero P0/P1. Usar memoria para personalizar notas,
audio, status u otras operaciones pertenece a la capa de IA de Fable.

## Distribución reproducible

`scripts/build_product.ps1` construye Release desde un snapshot Git detached y
publica un payload exacto de siete archivos: shell WPF autocontenido, cinco
bibliotecas nativas WPF adyacentes y core NativeAOT. El schema
`baxy-product-build-v4` fija rutas, tamaños, SHA-256, orden, TFM, runtime,
deployment y procedencia; un build sucio solo puede existir como override de
desarrollo marcado explícitamente.

`scripts/package_product.ps1` agrega el manifiesto y `SHA256SUMS` en un ZIP de
nueve entradas Stored con estructura canónica inspeccionada. El core NativeAOT
usa `/Brepro`; dos builds y dos paquetes limpios de `aac3e05` coincidieron byte
a byte. El ZIP mide 82.845.957 bytes y tiene SHA-256
`11971bc0501598009145506f815407ec42a7c8fde2e88996815c1d2eaf3e7ba9`.
La decisión está en
`../04_arquitectura/ADR/ADR-0003-paquete-release-reproducible.md` y la evidencia
en `artifacts/product/product_package_gate.json`.

Esta capa entrega bytes autocontenidos y atestados contra el manifiesto, pero
no instala ni modifica Windows. No crea acceso de Inicio, registro de
desinstalación o punteros de versión; tampoco implementa update, rollback o
uninstall. Los first-party carecen de Authenticode y la reproducibilidad
acreditada es same-host.

## Setup embebido y transaccional

`src/Baxy.Setup` consume esa capa sin cambiarla. Release inserta el ZIP y una
atestación canónica como recursos de un `WinExe` NativeAOT `win-x64`.
`EmbeddedPackageSource` vuelve a comprobar layout, CRC, SHA-256, manifiesto,
checksums, commit, epoch y `content_id` antes de abrir el payload.

`InstallationEngine` solo opera en `%LOCALAPPDATA%\Programs\BAXY`: publica
versiones inmutables, valida `.baxy-version.json`, conmuta punteros textuales
`current`/`current.previous` y usa journal para recovery. Reparse points, ADS,
hardlinks, paths ambiguos, downgrade SemVer y estados estables huérfanos o
duplicados fallan cerrados. El rollback del motor no se ofrece en `Program` por
la compatibilidad de datos aún pendiente.

`scripts/build_setup.ps1` reconstruye desde HEAD limpio, exige el paquete exacto
del mismo commit/epoch, compila con `/Brepro` y `PathMap`, inspecciona PE y
ejecuta `--verify-embedded`. El output contiene solo `Baxy.Setup.exe`,
`setup-manifest.json` y `SHA256SUMS`; el destino debe ser nuevo. Dos réplicas de
`5dad02a` fueron idénticas. Decisión: `ADR-0004`; evidencia:
`artifacts/setup/setup_package_gate.json`.

El release final vigente procede de `455243c`: predecesor 1.0.0 y candidato
1.0.1 A/B coinciden byte a byte por árbol. El Setup candidato mide 87.040.000
bytes/SHA-256 `68cfc301…30cd83`; el ZIP mide 83.121.455 bytes/SHA-256
`fdded6df…866978`. Los tres Setup aprobaron verificación embebida y permanecen
`NotSigned`. Evidencia: `artifacts/setup/final_release_gate.json`.

El lifecycle actual integra Inicio, registro de desinstalación, install, update,
rollback y uninstall keep/purge. El recorrido same-host ya demostró
install/update/rollback/keep-data; instalación desde cero, primer inicio
instalado y purge siguen `pendiente-por-entorno` para un perfil desechable.

## Persistencia y replay

Cada nota se guarda como un JSON UTF-8 independiente con SHA-256 de integridad.
Las mutaciones escriben un temporal en el mismo directorio, reemplazan el
documento y conservan una copia válida para recuperación. El store no cifra el
contenido y el hash no es una MAC.

El journal JSONL registra fases `started` y `completed`, enlaza y autentica cada
registro con HMAC-SHA-256 y reconstruye invocaciones al abrirse. La clave
dedicada está envuelta por DPAPI Current User. Tiene un tope duro de 64 MiB,
compacta de forma atómica y exacta todos los resultados terminados, y reserva
2 MiB para completar cada mutación admitida. Las reservas de registros
`started` incompletos se reconstruyen tras reiniciar. Una repetición con el
mismo identificador y la misma huella devuelve el resultado almacenado sin
repetir el efecto; reutilizar el identificador con otra petición se rechaza. Si
no hay capacidad, la petición se rechaza antes del efecto y conserva su
identidad durable para reintentar. Ausencia de anchor/clave, truncado, rollback,
cadena inválida o journal legado sin firma fallan cerrado.

El shell conserva el mismo par `missionId`/`invocationId` durante los reintentos
hasta recibir una respuesta terminal, para que el replay controle la
duplicación. Antes del envío persiste la petición en un outbox durable; este
sobrevive al reinicio completo del shell y elimina la entrada únicamente tras
una respuesta terminal. Cada entrada tiene un checksum SHA-256 canónico para
detectar corrupción accidental. El contenedor JSON general del outbox es texto
plano, no tiene HMAC, se limita a 1 MiB y 128 entradas, y falla cerrado ante
corrupción o rutas reparse; los argumentos `memory.*` contenidos en él sí son
envelopes cifrados y autenticados.

En una ambigüedad, la petición por título continúa en el outbox hasta cancelar,
reemplazarla por otra misión o elegir. La elección hace un reemplazo atómico:
mantiene `missionId`, genera otro `invocationId` y persiste la ruta exacta antes
del efecto. Tras reiniciar, se recupera esa ruta y nunca se vuelve a interpretar
el ordinal. La reconciliación mutante actual usa el caso exacto revisión
N+1/estado objetivo; todavía no existe un recibo de mutación schema v2.

Un fallo inesperado de almacenamiento o integridad durante una mutación deja la
invocación incompleta y reintentable con el mismo ID, en vez de publicar una
respuesta terminal falsa. En timeout, el shell señala la desconexión antes de
propagar el error, no conserva un estado `ready` falso y rechaza nuevos envíos.
El core se inicia mediante `LocalJsonlSidecarProcess`, el mismo host configurable
que admite otro ejecutable, argumentos y entorno. Cada instancia usa stdin,
stdout y stderr UTF-8 estrictos y un Job Object kill-on-close propio; si la
asociación al Job falla, el arranque falla y termina ese proceso.

El Job del shell conserva `KILL_ON_JOB_CLOSE` y permite breakaway explícito.
Solo el launcher confiado de Notepad usa `CREATE_BREAKAWAY_FROM_JOB`, sin
argumentos ni handles heredados; los demás hijos permanecen contenidos. La
aplicación final debe sobrevivir al core porque es el efecto solicitado, y su
identidad/ventana/foco se verifican de forma independiente antes del éxito.

Los fallos normales al iniciar o saludar al core no derriban la GUI: el estado
visible degrada a `No disponible`. Los scripts productivos validan cada ancestro
de sus rutas, ADS y puntos reparse; la limpieza se liga a handles de procesos
propios. La prueba hostil de junction preservó un centinela externo. Estas son
defensas locales acotadas, no una afirmación de disponibilidad ni autenticidad
adversarial completa del producto.

La expansión productiva todavía debe completar y separar explícitamente:

entrada → percepción/contexto → conversación → planner → shortlist general →
grounding → riesgo/autorización → ejecutor tipado → verificador → compensación
→ memoria → narrador → GUI/TTS. El shortlist especializado para duplicados de
notas ya existe; falta todavía el mecanismo general del producto completo.

`legacy/` es referencia de solo lectura, no base promovida por inercia.
WPF + core Rust estático es el fallback Pareto. Python y otros runtimes solo
entran como sidecars si ganan su subsistema con evidencia.
