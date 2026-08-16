# Resultados

## Validaciones iniciales

- Git BAXY: branch esperada, commit esperado, árbol limpio antes de cambios.
- Manifest de agentes: 322 registros; 303 completed; 19 interrupted;
  profundidades 302/19/1; cero IDs, posiciones o hashes duplicados; cero hashes
  mal formados.
- Cutoff: 17 fuentes lógicas; dos ejecuciones consecutivas con SHA-256
  `85929373646040f54771a7e3543a5ac3d022dbce688c55d17615ae35b7eb3fbd`;
  generador compila; manifiesto sin rutas absolutas ni contenido privado.
- Corpus v2: 122.744 ocurrencias → 14.836 mensajes → 2.083 misiones canónicas.
  Los mensajes se dividen en 12.036 de producto ES/EN/spanglish y 2.800 de
  trazabilidad `trace_only`; los tres registros adicionales frente al snapshot
  anterior son separaciones por alcance. Hay 4.650 misiones reales, cero
  misiones de producto sin operación, 79 restricciones de no-acción y 3.969
  duplicados exactos enlazados. El baseline schema 1 de 2.032/4.585 queda
  supersedido semánticamente, no borrado de la historia.
- Determinismo v2 confirmado mediante dos reconstrucciones finales A/B: los
  cuatro artefactos coincidieron byte a byte con el builder
  `857e1774825d336dd3446d08148e029711f9a9f12a5f3f9b84ddaf58011efeec`.
  Digests lógicos: mensajes
  `2cc440e274dc04137df1d48d3fe9e7d4356f99841476d64d4ab1010e06350322`,
  misiones `73ec1c32db9e32edcfab3769fae223fe2cc1c5b637633b27602fb5188104d53c`
  y mapeo `f9ef92da15fb0cd57b0e399e62e021f02ad1e3ad0a4ab8aef5c016c91b0c2c09`.
  Digests físicos: reporte `831862b5eec63bfa8a2d797cb48562589aca19066c17e173bb6fb61a6bae75a0`,
  mensajes `d9789574b41ff44fb057f17db696fd07140b299eb362a6b2636d86459bb804be`,
  misiones `0e48678f5a23b14f8e1d8cb509cba3aace0fbfb9beb3546aa8d5bfd5fefd10bf`
  y mapeo `5fccac4f7f5c2f2870400eae77dafa18b403dd600be24da9ef8d2650880e5b69`.
- Suite específica del cutoff/corpus/genealogía: 36/36 pruebas aprobadas;
  incluye schema/alcance, polaridad, oráculos exactos de juegos, mapping
  uno-a-uno, hashes recalculados, privacidad y 36 regresiones estructurales.
- Corrida completa vigente: 110/110 pruebas Python y 1.270/1.270 pruebas .NET
  —37 Contracts, 44 Kernel, 61 Setup, 232 Providers y 896 integración—: 1.380
  pruebas
  principales. El
  gate Python canónico es `python -X utf8 -m pytest -p no:cacheprovider tests -q`;
  la carpeta `legacy/` no forma parte de esa colección de entrega.

## Torneo tecnológico — Ronda B cerrada

- Ronda A: Python, .NET y Rust aprobaron 48/48 casos cada uno; Rust ocupó la
  frontera estricta de rendimiento y .NET avanzó por la regla congelada de
  promoción. Evidencia: `artifacts/technology_tournament/round_a_scorecard.json`.
- Los shells WebView2 quedaron descartados por red observada en sus hashes. La
  repetición corregida de los dos WPF ejecutó T16 por transporte real, hizo
  fail-closed la observación de red y ligó la procedencia de cada raw.
- Cada finalista aprobó 102/102 puntos acumulados: T01–T15 por compositor y T16
  por frontera raw del mismo core. Cada corrida tuvo 18 snapshots UI y uno de
  T16; además pasaron 7/7 arranques fríos, 30 operaciones calientes, lifecycle
  y 8/8 gates de paquete. La suite aprobó 41/41.
- Dos builds aislados reprodujeron por SHA-256 el shell WPF autocontenido, core
  .NET NativeAOT y core Rust estático. Todos los gates de
  `round_b_reproducibility.json` aprobaron.
- El score final eligió WPF + .NET NativeAOT con 82,004484/100. WPF + Rust
  obtuvo 79,992351/100 y queda como fallback; ambos están en Pareto.

| Métrica | WPF + .NET | WPF + Rust |
|---|---:|---:|
| Arranque frío p95 | 1.593,82 ms | 1.539,73 ms |
| Misión caliente p95 | 256,37 ms | 273,34 ms |
| Throughput | 4,64/s | 4,46/s |
| Memoria privada idle mediana | 111,93 MiB | 109,92 MiB |
| Memoria privada pico mediana | 122,88 MiB | 118,39 MiB |
| GPU dedicada pico mediana | 26,52 MiB | 26,52 MiB |
| Paquete interno | 67,61 MiB | 66,23 MiB |

Evidencia canónica:

- `artifacts/technology_tournament/round_b_scorecard.json`;
- `artifacts/technology_tournament/raw/round_b_*_runNN.json`;
- `artifacts/technology_tournament/raw/round_b_lifecycle_*.json`;
- `artifacts/technology_tournament/raw/round_b_package_*.json`;
- `artifacts/technology_tournament/raw/round_b_reproducibility.json`;
- `artifacts/technology_tournament/raw/round_b_supply_chain.json`;
- `artifacts/technology_tournament/round_b_sbom_*.cdx.json`.

## Primer corte productivo — hardening funcional

- La solución real combina un shell .NET 10 WPF con un core .NET 10 NativeAOT
  y usa JSONL local `baxy.local.v1`.
- El core implementa seis operaciones tipadas: `app.status`, `note.create`,
  `note.read`, `note.list`, `note.trash` y `note.restore`. La GUI de texto solo
  reconoce creación y listado de notas; no se probó ni se declara conversación
  general.
- Tras el hardening final, la solución Release aprobó 101/101 pruebas .NET:
  Contracts 23, Kernel 26, Provider 16 e integración 36. La suite histórica
  Python aprobó 41/41; la corrida conjunta suma 142 pruebas. Este resultado no
  cierra por sí solo Must 13 ni sustituye los gates pendientes.
- `artifacts/product/product_notes_slice.png` registra el shell y el flujo de
  notas en una captura de 980×680. La captura demuestra esa instancia visual,
  con `core_ready=true`, `mission_completed=true`, una nota, cero procesos
  residuales y cero entradas del outbox tras el terminal; no demuestra
  accesibilidad física ni toda la GUI objetivo.
- `artifacts/product/build/local-win-x64/build-manifest.json` enumera 14
  archivos de carga, 48.396.888 bytes en total y el SHA-256 individual de cada
  archivo, más el propio manifiesto.
  El directorio incluye el shell y el core, pero no es MSI/MSIX, instalador ni
  evidencia de instalación en una máquina limpia.
- Las pruebas de hardening cubren máximos de 1 MiB en ambas direcciones JSONL y
  una captura de stderr acotada, sin asignar primero entradas excesivas. Cubren
  también `note.list` paginado en el provider (`limit` 50 por defecto, máximo
  100 y `offset`) mediante resúmenes sin contenido, y el máximo de 512 notas
  del store.
- La GUI reintenta con `missionId` e `invocationId` estables hasta una respuesta
  terminal. Su outbox se persiste antes del envío, sobrevive al reinicio completo
  del shell y se vacía tras el terminal. Cada entrada lleva un checksum SHA-256
  canónico contra corrupción accidental. El contenedor y sus metadatos siguen
  siendo JSON en texto plano, sin HMAC; los argumentos `memory.*` internos sí
  son envelopes cifrados y autenticados. Tiene máximos de 1 MiB y 128 entradas
  y falla cerrado ante corrupción o rutas reparse. Los scripts validan cada ancestro, ADS y
  puntos reparse, y ligan la limpieza a handles de procesos propios. La prueba
  hostil de junction preservó el centinela externo.
- El store de notas valida SHA-256 y usa reemplazo atómico con backup. El
  journal encadena y autentica registros con HMAC-SHA-256 y sustenta replay
  idempotente. Su clave dedicada está envuelta por DPAPI Current User y su tope duro es
  64 MiB; la compactación conserva exactamente todos los resultados terminados,
  y reservas de 2 MiB reconstruidas al reiniciar aseguran capacidad para cerrar
  mutaciones ya admitidas. La saturación se rechaza antes del efecto y conserva
  la identidad durable. Ausencia de clave/anchor, truncado, rollback o tamper
  fallan cerrado. Las notas no están cifradas; los payloads privados `memory.*`
  sí están protegidos.
- Un fallo inesperado durante una mutación deja `started` y outbox incompletos
  para reintentar con el mismo ID, sin publicar un terminal falso. Las pruebas
  cubren además conflicto sobre `started` incompleto sin matar el core, timeout
  que desconecta y evita disponibilidad falsa, rechazo de envíos posteriores y
  limpieza del hijo aun si falla su asociación al Job de Windows.

## Segundo corte productivo — `app.open` acotado

- El catálogo incorpora `app.open` con riesgo `low_reversible`; el único
  destino es `windows.notepad`. La entrada natural cubre 13 registros
  históricos/siete literales y rechaza destinos, rutas, argumentos, URLs,
  negaciones, estado/how-to y composiciones fuera del allowlist.
- El provider usa inventario fail-closed, identidad exacta de System32 o paquete
  Microsoft, handles/creación estables, lanzamiento sin argumentos ni handles
  heredados y verificador independiente de PID, ruta, paquete, HWND visible y
  foco. El receipt durable impide relanzar el mismo `invocationId` después de
  crash, ambigüedad o desaparición del PID.
- La frontera core/provider exige evidencia coherente y ligada a la invocación;
  14 clases de recibo contradictorio fallan como `verification_failed` con
  divulgación de posible efecto.
- Release aprobó 230/230 pruebas .NET: Contracts 23, Kernel 26, Provider 56 e
  integración 125. En ese checkpoint Python aprobó 41/41; total histórico: 271.
  Formato y diff quedaron limpios, y dos auditorías independientes terminaron
  sin P0/P1. La revisión posterior del corpus llevó el snapshot documental a
  289; la corrida completa actual se registra en Validaciones iniciales.
- El build de ese checkpoint enumera 14 archivos de carga y 50.546.916 bytes,
  más el manifiesto. `Baxy.exe` tiene SHA-256 `a531f1c9…c08e0c` y `baxy-core.exe`
  `e9a7a393…c98d51`.
- `artifacts/product/app_open_gate.json` conserva el resultado físico:
  `skipped/preexisting_notepad`, exit 2, una instancia preexistente preservada.
  Por eso lanzamiento fresco, replay, supervivencia tras core/Job y E2E GUI no
  están aprobados. El gate cubre directamente core/provider bajo un Job
  equivalente; no atraviesa WPF ni `CoreProcessClient`.
- El corpus canónico v2 registra 329 etiquetas `app.open`, 98 mensajes con
  efectos denegados y 2.083 misiones. La corrección derivada está cerrada y no
  amplía el runtime ni los gates físicos del segundo corte.

## Tercer corte productivo — ciclo natural de notas

- El parser expone `note.create`, `note.list`, `note.read`, `note.trash` y
  `note.restore` mediante gramáticas finitas en español, inglés y spanglish.
  Rechaza negaciones, condicionales, bulk, controles, UTF-16 malformado,
  selectores múltiples, filesystem y composiciones con recordatorios.
- La métrica 40/40 se limita expresamente al oráculo curado de creación de nota
  standalone: 40 IDs únicos de producto, 13 literales y 49 ocurrencias de
  procedencia. Cada fila se lee del corpus congelado y enruta a `note.create`;
  siete negativos auditados permanecen fuera. No es 40/40 de toda
  `note.manage`: esa familia contiene 65 filas de producto con ruido, archivos
  y composiciones.
- Las notas rápidas usan un título determinista derivado del contenido,
  normalizado Form C y limitado a 120 bytes UTF-8 sin cortar runas. Los títulos
  de selección admiten comillas exteriores y máximo 512 bytes.
- Lectura resuelve una única nota activa por título exacto ignorando mayúsculas.
  Papelera/restauración exigen unicidad en `all`, hacen búsqueda+mutación bajo
  el mismo lock y devuelven sin otra revisión un estado ya alcanzado. Una
  ambigüedad responde `note_ambiguous` y deja todas las notas intactas.
- El fault injection interrumpe el completion del journal después del efecto de
  trash y restore: repetir la misma identidad reconcilia revisión 2/3 sin otra
  mutación y el siguiente intento se sirve como replay.
- La GUI muestra título y contenido de `note.read` sin JSON, acota a 16.384
  caracteres y declara truncamiento sin dividir UTF-16. Las mutaciones afirman
  estado verificado —en papelera/activa— y no un efecto nuevo durante retries.
- El handshake exige exactamente una instancia de cada capacidad usada por la
  GUI y su riesgo (`read_only`, `low_reversible`, `recoverable_delete`).
  `app.status` rechaza argumentos extra y el arranque falla si catálogo y
  registro divergen.
- El E2E real de la capa de presentación recorrió
  ViewModel→core→store→respuesta natural: create/read/trash/list/restore/list,
  cero JSON visible y outbox vacío. Tras cerrar el core, otro `LocalNoteStore`
  verificó una única nota activa, contenido exacto y revisión 3.
- Release aprobó 337/337 pruebas .NET: Contracts 23, Kernel 26, Provider 60 e
  integración 228. Python mantuvo 59/59 —36/36 del corpus, con 54 subtests—;
  total conjunto 396. `dotnet format --verify-no-changes` y `git diff --check`
  aprobaron.
- La auditoría adversarial de ese checkpoint no encontró P0/P1. El P2 de
  surrogate aislado quedó corregido y probado. En ese momento permanecía un P2:
  títulos duplicados fallaban seguro, pero la GUI aún no ofrecía selección;
  el cuarto corte lo cerró después.

## Cuarto corte productivo — desambiguación durable de notas

- `note_ambiguous` entrega una snapshot ordenada e inmutable de candidatos; la
  GUI presenta cinco por página, con índices absolutos hasta 512, estado, fecha
  y preview de máximo 128 bytes UTF-8, sin UUID ni JSON visibles.
- El parser contextual acepta selección, paginación y cancelación en español,
  inglés y spanglish. Rechaza índices inválidos, controles, composiciones y
  UTF-16 malformado; un número desnudo fuera de la aclaración no ejecuta nada.
- Elegir sustituye atómicamente la operación por título en el outbox por una
  ruta exacta: conserva la misión, renueva la invocación y persiste antes de
  enviar. Reinicios antes de elegir regeneran la misma shortlist; reinicios
  después de elegir recuperan el UUID ya fijado y no reinterpretan el ordinal.
- El provider verifica bajo el mismo lock UUID, título esperado normalizado,
  revisión y estado. Lectura no filtra contenido de una nota enviada a papelera;
  trash/restore no actúan si el candidato quedó obsoleto. El retry posterior al
  efecto se limita al caso exacto N+1/estado objetivo; no hay receipt schema v2.
- El caso adversarial máximo de 512 candidatos serializa por debajo de 700.000
  bytes y del límite JSONL de 1 MiB. También se prueban orden estable, selección
  512,
  casing/Form C, stale, replay, restart, cancelación, reemplazo atómico y texto
  accesible.
- Release aprobó 375/375 pruebas .NET: Contracts 23, Kernel 27, Provider 64 e
  integración 261. Python mantuvo 59/59 —36/36 del corpus, con 54 subtests—;
  total conjunto principal 434. Formato y diff quedaron limpios.
- La auditoría adversarial final no encontró P0/P1. El P2 de desambiguación de
  títulos duplicados queda cerrado; el marcador global permanece en 5/15 Must.

## Quinto corte productivo — `system.status` local read-only

- El catálogo productivo contiene ocho operaciones; la GUI exige siete
  capacidades interactivas porque `app.status` permanece como salud interna.
  `system.status` usa riesgo `read_only`.
- Los scopes públicos son `summary`, `cpu_memory`, `os_memory`, `cpu`, `memory`,
  `disk`, `battery` y `os`. Uptime solo forma parte de `summary`. Los pares
  CPU+RAM y Windows+RAM son una sola operación finita, no composición general.
- El provider Win32 consulta únicamente CPU —dos muestras separadas por 150
  ms—, RAM, disco del sistema, batería, Windows y uptime. No expone GPU/VRAM,
  procesos, IP, hostname ni usuario. Un summary puede publicar mediciones
  corroboradas y fallos parciales saneados sin inventar las secciones ausentes.
- El corpus contiene 306 filas globales `system.status`: 294 product y 12 trace;
  279 son product `user_mission`. El oráculo curado fija un subconjunto de 113
  IDs —50 literales, una misión, nueve rutas `source`— con digest
  `9d55e3fafc60a588da7714ee1dd795378952cc3f986ed166a3dd545b3027f21e`.
  Los scopes son CPU+RAM 9, Windows+RAM 1, batería 56, memoria 25, CPU 12 y disco
  10. Los 113/113 enrutan; resumen, `os` standalone y spanglish históricos no
  quedan acreditados.
- El E2E automatizado atravesó ViewModel→core→provider Win32→respuesta natural
  para CPU+RAM, disco, batería y Windows, sin JSON/nombre interno y con outbox
  vacío. En ese checkpoint Release aprobó 460/460 .NET y Python 59/59 más 148
  subtests.
- Un `baxy-core.exe` NativeAOT temporal de 4.857.856 bytes, SHA-256
  `83e972f4273380b587192684a14cb01f42837f08e389082a87cd8d443cb4c488`,
  aprobó 2/2 requests reales: CPU+RAM minimizado y summary de seis secciones. El
  artefacto fue eliminado; no es el distribuible ni un instalador.
- El red-team final terminó con cero P0/P1 después de cerrar batería all-unknown
  y Windows 11/Server. El marcador global continúa en 5/15 Must y
  B-004/B-005/B-006 permanecen abiertos.

## Sexto corte productivo — control global de audio

- El commit `33b62bc` añadió `audio.volume` y `audio.mute`, ambas
  `low_reversible`, sobre el endpoint de salida predeterminado
  `eRender`/`eMultimedia`. Volumen solo admite un porcentaje absoluto de 0 a
  100; mute exige silenciar o reactivar de forma explícita. No controla
  micrófono, sesiones por aplicación, dispositivos no predeterminados, cambios
  relativos ni composiciones.
- El parser conservador queda respaldado por 143/143 mensajes históricos, 109
  literales, 14 fuentes y dos misiones. El universo de audio suma 529 filas y
  397 filas de producto clase `user_mission`. Las dos misiones standalone
  contienen 335 mensajes
  —248 de volumen y 87 de mute—; esta slice deja 192 mensajes de esas dos
  misiones standalone sin acreditar. Además quedan composiciones.
- El provider usa Core Audio mediante COM generado compatible con NativeAOT,
  serializa efectos con un mutex y persiste una intención antes de invocar el
  setter. Lee de nuevo el endpoint y sus dos dimensiones antes de responder. Un
  receipt reconciliado describe únicamente estado observado: no demuestra que
  BAXY causara el cambio ni promete exactly-once.
- Si queda una intención sin receipt terminal, el core devuelve `pending` sin
  completar el journal. La GUI bloquea otras rutas y conserva exactamente el
  mismo `missionId`/`invocationId` para continuar, incluso después de reiniciar.
  No hay rollback ni reaplicación automática cuando el efecto es incierto. El
  store de audio falla cerrado antes de otro efecto al alcanzar 16.384 entradas
  o 64 MiB; es un límite operativo P2, no una política de descarte.
- Release aprobó 665/665 pruebas .NET y Python 59/59 más 148 subtests. La
  auditoría final de la slice no dejó P0/P1; el marcador global continúa en
  5/15 Must.
- El build local post-`33b62bc` contiene 14 archivos de carga y 54.831.324 bytes
  más el manifiesto. SHA-256: manifiesto
  `4c0378c01ffd67d6949f90f1c0f2f611300cea2450e32ef1ac5756d36fb3553a`,
  `Baxy.exe` `f017ba4babdf307f6dc5a3403089e9d14e59ed76c6c62526693bea907b80be80`
  y `baxy-core.exe`
  `0f794ae353a22e2b6bdbc21da51513e4116c776d12e170c02616ce440d38cc94`.
  El manifest revalidó 14/14 archivos. El smoke del core anunció
  `baxy.local.v1` y diez capacidades —incluidas las dos de audio—, terminó con
  exit 0, stderr vacío y cero procesos Baxy/core residuales; preservó el Notepad
  PID 5472.
  La app es framework-dependent y el core self-contained; es un directorio de
  desarrollo, no instalador, prueba en Windows limpio ni release firmada.
- La captura GUI `artifacts/product/product_notes_slice.png` mide 980×680 y
  71.521 bytes, SHA-256
  `4eb2dd03bc0d1ba32c452d2b92c0d13124acb12e7651b4e59133abdb702ca6b6`.
  Verifica core listo, misión de nota terminada, una nota, outbox vacío y cero
  procesos residuales. No recorre audio de extremo a extremo.
- `artifacts/product/audio_control_gate.json` registra un gate físico pasado por
  el core NativeAOT sobre JSONL. El binario temporal medía 5.199.360 bytes y
  tenía SHA-256
  `7a45f1e8e49d169db401eca87bf95896e6a883db26f7cf2f8e977d570dd5a225`.
  Partió de 0,98/98 %/no silenciado, verificó volumen 88 %, mute activo, replay
  de ambas invocaciones sin segundo efecto y restauración exacta a 0,98/98 %/no
  silenciado; no dejó procesos ni estado temporal.
- Una primera ejecución marcó la terminación como no corroborada cuando
  `WaitForExit(0)` compitió con el cierre asíncrono. La restauración automática
  falló cerrada; se conservó la evidencia, se restauró y verificó el baseline
  antes de corregir el harness y repetir. El mismo artefacto documenta el
  incidente y su limpieza.
- El gate observa estado de control del endpoint, no sonido audible. Cubre un
  equipo y un endpoint predeterminado; tampoco atraviesa el parser natural WPF
  ni acredita otros dispositivos, sesiones o modo exclusivo. B-004 queda
  reducido pero abierto, y B-005/B-006 permanecen abiertos.

## Séptimo corte productivo — memoria privada explícita

- El commit `478a19a` añadió 11 operaciones `memory.*`; el catálogo total pasó a
  21 y el handshake interactivo a 20. La memoria está apagada por defecto y no
  guarda por inferencia: solo procesa órdenes explícitas ES/EN/spanglish.
- Los riesgos son proporcionales: enable/export/sensitive.save
  `privacy_sensitive`, forget `work_loss`, recall/list/status `read_only` y las
  cuatro operaciones restantes `low_reversible`. La GUI liga confirmaciones y
  recuperación a la misma misión/invocación y oculta el contenido sensible en
  su proyección pública.
- El oráculo exacto registra save 59 IDs/32 literales, recall 19/15, forget
  22/13, unión positiva 100/60, correct 5/2 y 34 negativos duros. Sus 44 casos
  canónicos y contratos de TTL/consentimiento/inspección pasaron dentro de la
  colección Python de 65/65 + 157 subtests.
- Argumentos privados y resultados privados exitosos se sellan ligados a
  operación, mission, invocation y sesión. Challenge/control viajan fuera del
  envelope; el bearer token queda en RAM, redactado y sin persistir. Fallos
  genéricos y metadatos quedan en claro. Snapshot, recovery, watermark, intención y payloads
  privados de memory en outbox/journal también quedan cifrados y autenticados.
  La clave usa DPAPI Current User: key ausente con sentinel original falla antes
  de crear otra, pero el sentinel no detecta un reemplazo coordinado de ambos
  archivos bajo el mismo usuario.
- El store admite 512 registros/4.096 receipts, recall máximo 5, listado
  paginado y retención persistente, de sesión o temporal. El watermark detecta
  rollback parcial/incoherente y la intención durable evita convertir una
  interrupción en éxito falso; un rollback coordinado de
  current/recovery/watermark autenticados puede conservar coherencia. La raíz se
  restringe a `%LocalAppData%\BAXY\<hijo-directo>` con DACL usuario+SYSTEM. Raíz,
  key, store y export usan handles resistentes a reparse y swaps de directorio;
  los archivos validan además un solo hardlink.
  Outbox/journal aún abren archivos por path.
- Export requiere confirmación y escribe un JSON local en `Documentos/BAXY`;
  redacta el contenido de registros sensibles/secretos y nunca exporta sus
  valores originales. Replay vuelve a verificar por handle ruta, schema,
  invocation, conteo y SHA-256; archivo borrado o alterado falla sin afirmar
  integridad. La GUI advierte que Documentos puede estar redirigido o
  sincronizado.
- Release aprobó 37 Contracts, 44 Kernel, 189 Providers y 765 integración:
  1.035/1.035 .NET. Con Python son 1.100 pruebas principales. La auditoría del
  diff/frontera de memoria quedó en 0 P0/P1; permanece un P2 teórico sobre
  semántica NTFS sensible a mayúsculas bajo una precondición especial o elevada.
- La última validación NativeAOT temporal registrada midió 6.252.544 bytes,
  SHA-256
  `D32423255E93C51FDDDAA79E3A92C39C7F0D59D21D81A5F3C760CCA93F3A7EF7`;
  el digest canónico de 101 archivos fuente/props/global conservó
  `b6c1eccf6aca5cc58c29daa6e8dd01d21b301d996cee034a08a83c1d16c0a0e7`.
  El smoke verificó hello 21/11, DPAPI real, status, enable con challenge y
  confirmación, list vacío, rechazo de raíz compartida, exit 0/stderr 0, cero
  huérfanos y cleanup de helper/raíz temporal; Notepad 5472 fue preservado. El
  output ignorado permanece en `src/Baxy.Core/bin/.../native/baxy-core.exe`; no
  se versionó un artefacto independiente bajo `artifacts/product`.
- No se cerró ningún Must: el marcador sigue 5/15. La memoria todavía no
  personaliza otras operaciones; notas y contenedores/metadatos generales
  siguen en texto plano, el journal global no tiene HMAC y, en ese corte, no
  existían instalador ni prueba en Windows limpio.

### Cierre vigente de Gate 10 — techo determinista v3

- El corte histórico anterior fue endurecido después con cadena
  HMAC-SHA-256 y clave dedicada protegida por DPAPI. Las regresiones rechazan
  key loss, anchor ausente, truncado, rollback, tamper y journals legados sin
  firma.
- La auditoría final pasó 405/405 pruebas focalizadas: 6 del oráculo, 272 de
  integración, 73 de provider/DPAPI/store/export, 24 de journal/frontera privada
  y 30 de catálogo/schema/confirmación/riesgo. No quedan P0/P1.
- Gate 10 queda aprobado. La personalización de otras operaciones pertenece a
  Fable; no es deuda del cuerpo determinista. Evidencia:
  `artifacts/product/memory_privacy_gate.json`.

## Octavo corte productivo — estado local de GPU

- Los commits `3037445`, `e33267d`, `cf44b89` y `18061e0` añadieron los scopes
  `gpu_identity` y `gpu_usage` a `system.status`. El catálogo no creció: conserva
  21 operaciones totales y 20 interactivas. El summary sigue usando el provider
  y JSON legados y no abre la sonda GPU.
- El oráculo `baxy.system-status.gpu-local.v1` selecciona 74 de 148 candidatos
  léxicos de producto y añade tres colisiones de temperatura: en total son 7 de
  identidad, 19 de uso, 17 composiciones y 34 negativos duros. Los 26 positivos
  enrutan al scope exacto; los otros 51
  impiden degradar composiciones, temperatura, conocimiento, web/precios,
  condicionales, historial, investigación o mutación a un snapshot standalone.
  El quinto corte conserva por separado sus 113/113 casos.
- `nvidia-smi` es únicamente un alias natural acotado de `gpu_usage`. BAXY no
  ejecuta el binario, no crea subprocess y no afirma haberlo usado. Temperatura,
  procesos, energía, ventilador, clocks y monitoreo continuo quedan fuera.
- El provider enumera identidad/capacidades con DXGI y toma uso puntual con PDH
  mediante interop manual compatible con NativeAOT. Conserva orden y
  multiplicidad, correlaciona sin publicar LUID/PID y representa falta de
  medición con `unsupported` global o indexado. No deduplica nombres ni inventa
  0 % cuando faltan contadores.
- El core exige identidad válida, capacidades sin overflow, nombres/Unicode
  saneados, rangos válidos y presencia conjunta de porcentaje/memoria dedicada
  usada/memoria compartida usada. También valida la matriz entre adapters y
  failures; cualquier contradicción falla cerrada.
- Release aprobó 37 Contracts, 44 Kernel, 232 Providers y 896 integración:
  1.209/1.209 .NET. Python aprobó 74/74; son 1.283 pruebas principales. La
  auditoría cruzada no dejó P0/P1/P2 dentro de la slice.
- Una ejecución física managed anunció 21 operaciones y observó tres
  adaptadores, dos medidos y uno no disponible con fallo indexado, exit 0. El
  publish NativeAOT mide 7.376.384 bytes y tiene SHA-256
  `17b88aed29af5d4cc9dffb3931b73ce13791b304e4f1a7692d2f9eb588550fe9`.
  La compuerta `scripts/test_gpu_status.ps1` corroboró hello 21, identity/usage
  completados y verificados, tres adaptadores, dos medidos, uno no disponible,
  un `unsupported` indexado, cero fallos globales, correlaciones exactas, warmup
  `malformed_json`, stderr vacío y exit 0. Publicó atómicamente el resumen
  sanitizado schema `baxy-gpu-status-gate-v1` en
  `artifacts/product/gpu_status_gate.json`.
- No se cerró ningún Must. La evidencia cubre un host y snapshots puntuales, no
  temperatura/procesos, hardware exhaustivo, el perfil de 4 GB, GUI, instalador,
  firma o Windows limpio; B-004/B-005/B-006 permanecen abiertos.

## Noveno corte productivo — distribución reproducible

- `scripts/build_product.ps1` rechazó Release dirty y construyó dos réplicas
  desde worktrees detached de `aac3e05`. Los árboles de siete archivos fueron
  idénticos: 82.842.635 bytes en total. El manifiesto canónico mide 1.478 bytes
  y tiene SHA-256
  `3e6486ee67ec9f0c263a6f83ccbe34eacd0c6ca4dc7a21d34d59ac35e852e259`.
- La primera pareja A/B aisló tres bytes variables en copias del timestamp PE
  generado por `link.exe`; no había diferencia de código ni datos AOT. Tras
  pasar `/Brepro`, la repetición limpia completa coincidió byte a byte.
- `Baxy.exe` mide 67.079.643 bytes y tiene SHA-256
  `57031a0fc5f79229bf8499da2cfb075e8872d7b9877a771bf7202a05e3ea9309`;
  `core/baxy-core.exe` mide 7.376.384 bytes y tiene SHA-256
  `d2b03ef8fb4dc8c2379bbf3acde962b6b8fd15f04e59dd59729a22b52c204de5`.
- Dos ejecuciones de `scripts/package_product.ps1` produjeron el mismo ZIP de
  nueve entradas Stored: 82.845.957 bytes y SHA-256
  `11971bc0501598009145506f815407ec42a7c8fde2e88996815c1d2eaf3e7ba9`.
  Sidecars, orden, timestamps, nombres, headers locales/centrales, descriptores,
  CRC, tamaños y regiones contiguas fueron revalidados en destino.
- El core distribuido aprobó `scripts/test_gpu_status.ps1`: hello 21, identidad
  y uso verificados, tres adaptadores, dos medidos, uno no disponible, un fallo
  indexado, cero fallos globales, stderr vacío y exit 0.
- La GUI distribuida arrancó con `DOTNET_ROOT` inválido y resolución externa
  deshabilitada; el smoke 980×680 completó una nota y terminó sin procesos ni
  datos de prueba. Notepad 5472 fue preservado. La captura mide 71.335 bytes y
  SHA-256 `b9826c98cef137a21e2de42a1d010ef576c5dd30a668624916945101e13ad94d`.
- En ese corte, la suite aprobó 95/95 Python y 1.209/1.209 .NET: 1.304 pruebas
  principales. El red-team final no dejó P0/P1 abiertos. La evidencia
  sanitizada es `artifacts/product/product_package_gate.json`.
- El alcance es same-host y sin firma first-party. No hubo VM limpia,
  integración Windows, update, rollback o uninstall; el marcador continúa
  5/15 y B-004/B-005/B-006 permanecen abiertos.

## Décimo corte productivo — Setup reproducible

- `Baxy.Setup.exe` quedó ligado a un ZIP y atestación embebidos; Release sin el
  par falla. El parser independiente exige las nueve entradas Stored exactas,
  CRC sobre bytes reales, hashes, manifest v3, checksum, commit/epoch y límites.
- El motor de instalación aprobó 61/61 tests sobre versiones inmutables,
  punteros, journal, recovery por fase, corrupción, downgrade, hardlinks,
  reparse/ADS y fault matrix. El programa no expone rollback.
- Dos cadenas limpias desde `5dad02a` produjeron producto y paquete idénticos.
  El ZIP embebido mide 82.845.968 bytes y tiene SHA-256
  `9a7acc74ef4530c6411c553e7884209d6cf1559827edc966e09663b2e8322532`.
- Los dos Setup son byte a byte idénticos: 85.858.304 bytes, SHA-256
  `50b8b8d415a822efabfa8986f3ec10d8d20d940dd2feca84b97f547b65452c7a`.
  PE acredita AMD64/PE32+/GUI/REPRO/recurso y ausencia de CLR, certificado,
  COFF y CodeView; Authenticode informa `NotSigned`.
- Los dos publishes y ambos outputs promovidos ejecutaron verificación embebida
  con exit 0. La evidencia final A/B fue idéntica y declaró `status=passed`.
- Dos fallos físicos previos —separador `PathMap` y atestación dentro del input
  exacto— fallaron antes de promoción, fueron corregidos en `864170f` y
  `5dad02a`, y quedaron cubiertos por regresión.
- La validación final aprobó 110/110 Python y 1.270/1.270 .NET. Dos tests
  físicos `[Explicit]` no pertenecen a la corrida estándar. Las auditorías del
  motor y builder no dejaron P0/P1. Evidencia sanitizada:
  `artifacts/setup/setup_package_gate.json`.
- No se ejecutó la instalación canónica ni una VM limpia. No hay Inicio, Apps
  instaladas, UI, uninstall, update/rollback de datos o firma; 5/15 y
  B-004/B-005/B-006 permanecen sin cambio.

## Cierre de la frontera determinista Codex → Fable

- El catálogo queda congelado en 22 operaciones de producto, 21 tools públicas
  y una salud interna (`app.status`). El handshake exige identidad, schema,
  riesgo, verificador, descripción y orden exactos.
- `MissionInput` acredita paridad de texto/transcripción; la salida separa
  `OperationOutcome` tipado de `ProductOperationNarrator`; el core comparte un
  host JSONL configurable y Job Object con la frontera del futuro sidecar.
- Pruebas focalizadas: Contracts 46/46, catálogo 15/15 e integración de costuras
  184/184. Suite global: 1.787/1.787 .NET estándar, cero P0/P1; tres pruebas
  físicas `[Explicit]` quedaron fuera de esa corrida por diseño.
- Evidencia: `artifacts/product/architecture_seams_gate.json`, ligada al corte
  funcional `78169adb48a8a3ab5fbbc64f337bd3bf9190fe7b`.
- No se implementaron embeddings, conversación general, planner, runtime de
  modelos, micrófono, STT ni TTS. Esas capacidades son frontera Fable.

## Release reproducible final

- Fuente limpia: `455243c7c14fc915c9c70f7d356012dc5303e457`, epoch
  1784170130, .NET SDK 10.0.100 y PowerShell 5.1.26100.8737.
- Candidato 1.0.1 A/B idéntico: ocho archivos de producto, dos de paquete y tres
  de Setup. `Baxy.Setup.exe` mide 87.040.000 bytes/SHA-256
  `68cfc30172b5b15e72e4085fcfb243107b54931d050f111d87cfb1991930cd83`;
  el ZIP mide 83.121.455 bytes/SHA-256
  `fdded6df99c9353a1c752855d5279e0f88642fa940f911b1982951e15a866978`.
- Predecesor 1.0.0: Setup de 87.040.000 bytes/SHA-256
  `22face7dc817f51fba6beebd3922d0b87e2cdd8b3a695cdf5ecfd8a8363553da`.
- Los tres Setup verificaron su paquete embebido con exit 0 y continúan
  `NotSigned`. El core NativeAOT final pasó el smoke de saludo/21 tools y
  limpieza aislada. Python pasó 118 pruebas + 176 subtests; Ruff pasó en
  `scripts`/`tests`.
- Evidencia: `artifacts/setup/final_release_gate.json`. Es build/verificación
  same-host, no instalación limpia ni claim cross-host.

## Voz local completa — wake, STT, TTS y frontend acústico

- Se reemplazó el alcance anterior de micrófono directo por dos modos visibles:
  `direct` y escucha continua activada por «Baxy». El arranque de desarrollo la
  deja activa por petición explícita del propietario; el default de producto
  sigue siendo opt-in.
- La ruta de producto es Silero VAD 6.2.1 ONNX → Parakeet TDT 0.6B v3 int8 →
  matcher wake cerrado/corrector → `MissionInput`. La salida usa SAPI local;
  no importa ni distribuye Piper/openWakeWord.
- `mind_voice_gate.json` pasó 6/6 segmentaciones, 3/3 wakes y 6/6 rutas en
  español, inglés y spanglish con voces Windows instaladas.
- `voice_system_gate.json` pasó versiones/licencias, micrófono USB físico,
  loopback WASAPI, TTS físico y purge, wake negatives, AEC determinista
  (61,01 dB ERLE en camino directo) y un clip hablado histórico con entidad
  recuperada; no conserva audio ni transcripts.
- La UI física pasó core actualizado, carga diferida, wake automático,
  micrófono directo, retorno a wake y toggle off/on. Una locución ambiente en
  modo directo recorrió STT → LLM → respuesta visible/TTS; seis segundos tras
  hablar no hubo turno fantasma por self-hearing.
- Regresión final: Ruff verde; Python 171 tests +179 subtests; .NET 1.882/1.882
  —46 Contracts, 81 Kernel, 297 Providers, 986 Integration y 472 Setup—.
- Límite: la voz personal ausente no puede medirse automáticamente. FAR/FRR y
  barge-in humano sobre parlantes fuertes quedan como calibración guiada, no
  como wiring faltante ni como resultado inventado.

## Límites vigentes

- La red se comprobó por snapshots discretos, no ETW continuo.
- La contención cubre T09–T12, snapshots del workspace y probes junction/
  reparse/sentinela, no observación system-wide ProcMon/USN.
- No se ejecutaron Narrator/NVDA, DPI físico al 200 % ni reduced motion.
- El ZIP reproducible es un mecanismo offline autocontenido, no MSI/MSIX ni
  instalación en VM limpia; `clean_machine_claimed=false`.
- Ejecutables y manifests no tienen Authenticode. El journal global sí encadena
  HMAC-SHA-256 con una clave dedicada protegida por DPAPI Current User.
- El contenedor del outbox general no está cifrado ni autenticado con HMAC;
  únicamente los argumentos `memory.*` dentro de él usan envelope privado.
- Trash/restore reconcilian la interrupción posterior al efecto solo mediante
  revisión N+1/estado objetivo y el binding del candidato; no existe receipt
  causal schema v2 ni se afirma exactly-once.
- La reproducción fue same-host con caches compartidas; MSVC/Windows SDK no
  están fijados y no hubo clean-room ni cross-host.
- Falta licencia global first-party y procedencia/licencia del icono.
- Ni el perfil GPU del torneo ni el snapshot local cargan modelos o demuestran
  hardware físico objetivo de 4 GB; tampoco cubren temperatura o procesos.
- Estos resultados cierran el torneo y aportan slices físicas acotadas de audio
  y GPU, no las pruebas físicas del producto completo.
- El parser natural cubre el ciclo de notas, su desambiguación, apertura acotada
  de Notepad, estado local del PC —incluidos identidad/uso puntual de GPU—,
  audio global y memoria explícita bajo
  gramáticas finitas; no
  cubre conversación general ni composición multioperación.
- El store de intenciones de audio tiene topes fail-safe de 16.384 entradas y
  64 MiB. No descarta recibos antiguos ni ejecuta rollback/reapply automático
  frente a una intención incierta.
- El build local post-`33b62bc` queda preservado como evidencia histórica y fue
  supersedido para distribución por el paquete reproducible de `aac3e05`. El
  ZIP nuevo tampoco es un instalador, una prueba en Windows limpio ni una
  release firmada y no cierra Must 14.
