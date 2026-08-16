# Cambios y migraciones

## 2026-07-15

- El HEAD limpio `455243c` cerró el release determinista final. Predecesor 1.0.0
  y candidato 1.0.1 A/B comparten commit/epoch y las candidatas coinciden byte
  a byte en producto, paquete y Setup. El Setup candidato mide 87.040.000 bytes
  y tiene SHA-256 `68cfc301…30cd83`; el ZIP mide 83.121.455 bytes y tiene
  SHA-256 `fdded6df…866978`.
- Los tres Setup aprobaron `--verify-embedded` y permanecen `NotSigned`. Un smoke
  del core NativeAOT final anunció 21 tools públicas con schemas cerrados,
  excluyó `app.status`, terminó con stderr vacío/exit 0 y eliminó únicamente su
  hoja aislada. No se ejecutó instalación, purge ni `app.open`.
- La validación final añadió 118/118 pruebas Python con 176 subtests y Ruff
  limpio sobre `scripts`/`tests`. Evidencia completa:
  `artifacts/setup/final_release_gate.json`.
- `d950570` separó el resultado tipado de su verbalización: los handlers ya no
  fijan la respuesta pública y `ProductOperationNarrator` consume
  `OperationOutcome` mediante `IOperationResponseNarrator`.
- `78169ad` cerró las cuatro costuras Codex→Fable sin agregar operaciones. El
  catálogo queda congelado en 22 definiciones internas/21 tools públicas; el
  descriptor wire incorpora schema cerrado y contrato verificador, y excluye
  `app.status`.
- `MissionInput` conserva una ruta única para texto/transcripción; un test de
  arquitectura confina las regex a la capa interina declarada. El core pasó a
  `LocalJsonlSidecarProcess`, host JSONL reutilizable con Job Object propio,
  verificado con dos procesos independientes.
- La solución Release aprobó 1.787 pruebas .NET estándar: 46 Contracts, 75
  Kernel, 241 Providers Windows, 953 Integration y 472 Setup. Tres pruebas
  físicas `[Explicit]` no forman parte de esa corrida. Cero P0/P1.
- La enmienda de audio global v3 añade una sola operación pública:
  `audio.status`, read-only y sin argumentos. Lee volumen y mute del endpoint
  predeterminado bajo el lock global, verifica hash/estado y no ejecuta setter
  ni crea intención durable. El catálogo runtime queda en 22 operaciones
  totales/21 interactivas.
- El parser promueve únicamente el oráculo finito de 28 IDs: 12 alias nominales
  de `audio.volume` y 16 consultas de `audio.status`; agrega casos deterministas
  ES/EN/spanglish sin planner, embeddings ni composición general. El oráculo de
  audio queda en 171/171 IDs, 120 literales, tres misiones y 14 fuentes.
- El builder aplica la enmienda semántica reproducible
  `2026-07-15-audio-status-v3`: mantiene 122.744 ocurrencias/14.836 mensajes,
  crea la misión 2.084 y la familia derivada 43. Preview y salida canónica
  coincidieron 4/4 byte a byte; no se editó ningún JSONL congelado a mano.
- El décimo corte (`ee699c6`, `701adc1`, `864170f`, `5dad02a`) incorporó
  `Baxy.Setup.exe`, su motor transaccional y el builder reproducible. Release
  exige ZIP + atestación embebidos, HEAD limpio, worktree detached y outputs
  aislados; el Setup solo reconoce `%LOCALAPPDATA%\Programs\BAXY`.
- El motor valida el paquete y el árbol publicado, crea versiones inmutables,
  mantiene `current/current.previous`, journaliza cada transición y recupera la
  fault matrix. Rollback queda interno: el programa no lo expone hasta resolver
  compatibilidad de datos.
- Dos cadenas A/B de `5dad02a` produjeron producto, paquete y Setup idénticos.
  El ZIP mide 82.845.968 bytes/SHA-256 `9a7acc74…2532`; `Baxy.Setup.exe`,
  85.858.304 bytes/SHA-256 `50b8b8d4…2c7a`. Los dos publishes y los dos outputs
  promovidos ejecutaron verificación embebida con exit 0.
- El gate físico descubrió y cerró dos regresiones antes de promoción:
  `PathMap` requería `%2C` para no dividir propiedades MSBuild, y la atestación
  debía vivir fuera de la raíz exacta ZIP+sidecar. La evidencia sanitizada está
  en `artifacts/setup/setup_package_gate.json`.
- La suite vigente aprobó 1.270/1.270 .NET y 110/110 Python; Setup aporta 61
  tests de motor y 15 de builder. El formato quedó limpio y las auditorías
  adversariales cerraron con cero P0/P1.
- No cambia el marcador 5/15. No se ejecutó la instalación canónica y faltan
  integración Windows, UX, update/rollback de datos, uninstall, firma y VM
  limpia; B-004/B-005/B-006 siguen abiertos.
- El noveno corte (`d58aa48`, `aac3e05`, `7f65bc0`) incorporó build y paquete
  reproducibles mediante `scripts/build_product.ps1` y
  `scripts/package_product.ps1`. Release rechaza un árbol sucio antes de mutar
  outputs, compila desde un worktree detached de `HEAD` y publica únicamente
  siete rutas autocontenidas bajo el manifiesto canónico
  `baxy-product-build-v3`.
- La primera réplica limpia encontró que el core NativeAOT variaba solo en tres
  timestamps PE de `link.exe`. Se añadió `/Brepro` bajo `PublishAot=true`; dos
  builds limpios posteriores desde snapshots aislados quedaron idénticos sin
  normalizar ni parchar binarios post-build.
- El payload repetido mide 82.842.635 bytes. `Baxy.exe` mide 67.079.643 bytes y
  SHA-256 `57031a0fc5f79229bf8499da2cfb075e8872d7b9877a771bf7202a05e3ea9309`;
  `baxy-core.exe`, 7.376.384 bytes y SHA-256
  `d2b03ef8fb4dc8c2379bbf3acde962b6b8fd15f04e59dd59729a22b52c204de5`.
- El writer produce nueve entradas Stored en orden ordinal —payload,
  `build-manifest.json` y `SHA256SUMS`— y valida layout local/central/EOCD,
  CRC, hashes, nombres, timestamps, flags y ausencia de bytes opacos. Los dos
  ZIP miden 82.845.957 bytes y tienen SHA-256
  `11971bc0501598009145506f815407ec42a7c8fde2e88996815c1d2eaf3e7ba9`.
- El core del build limpio aprobó el gate GPU y el shell aprobó un smoke de nota
  con runtime .NET externo deliberadamente ausente; no dejó procesos ni datos
  temporales y preservó Notepad 5472. La evidencia sanitizada queda en
  `artifacts/product/product_package_gate.json`.
- En ese corte, la suite aprobó 1.209/1.209 pruebas .NET y 95/95 Python: 1.304
  pruebas principales. El red-team de packaging terminó sin P0/P1 abiertos.
- Este corte no agrega operaciones ni cierra Must: el marcador sigue 5/15. La
  reproducibilidad acreditada es same-host y los ejecutables first-party no
  tienen firma. Instalación por usuario, integración Windows, prueba limpia,
  update, rollback y uninstall mantienen B-005 abierto; B-004/B-006 también
  continúan abiertos.
- El octavo corte (`3037445`, `e33267d`, `cf44b89`, `18061e0`) amplió
  `system.status` con los scopes `gpu_identity` y `gpu_usage`; no agregó una
  operación. El catálogo conserva 21 operaciones totales y el handshake 20
  capacidades interactivas. El summary conserva el provider y JSON legados y no
  sondea GPU.
- El oráculo `baxy.system-status.gpu-local.v1` congela 77 casos: 7 de identidad,
  19 de uso, 17 composiciones y 34 negativos duros. Los 26 positivos enrutan al
  scope exacto y las otras 51 fronteras fallan cerradas. Parte de 148 candidatos
  léxicos de producto, selecciona 74 y añade tres colisiones de temperatura; no
  es cobertura exhaustiva del ledger.
- `nvidia-smi` permanece como alias natural acotado de `gpu_usage`: el runtime no
  lanza ese ejecutable, no crea subprocess y nunca afirma haber usado la
  herramienta. Temperatura, procesos, energía, ventilador, clocks, monitoreo
  continuo y composiciones que creen carga quedan fuera.
- El provider nuevo enumera identidad/capacidades con DXGI y toma uso puntual
  con PDH mediante interop manual compatible con NativeAOT. Conserva adaptadores
  repetidos y su orden, correlaciona internamente sin publicar LUID/PID y
  representa falta de uso con `unsupported` global o indexado; no inventa 0 %.
- Core valida nombres/Unicode, cantidad, capacidades/overflow, rangos, presencia
  conjunta de los tres campos de uso y coherencia adapter/failure antes de
  publicar. La respuesta distingue VRAM, RAM reservada y límite compartido, y
  usa ordinales visibles para desambiguar nombres repetidos.
- Release aprobó 1.209/1.209 pruebas .NET —37 Contracts, 44 Kernel, 232
  Providers y 896 integración— y 74/74 Python: 1.283 pruebas principales. La
  auditoría cruzada cerró sin P0/P1/P2 dentro de la slice.
- Una ejecución física managed anunció 21 operaciones y observó tres
  adaptadores, dos medidos y uno no disponible mediante fallo indexado, con exit
  0. El publish NativeAOT mide 7.376.384 bytes y tiene SHA-256
  `17b88aed29af5d4cc9dffb3931b73ce13791b304e4f1a7692d2f9eb588550fe9`.
  La compuerta `scripts/test_gpu_status.ps1` corroboró hello 21, identidad/uso
  verificados, tres adaptadores, dos medidos, uno no disponible, un
  `unsupported` indexado, cero fallos globales, correlaciones exactas, warmup
  `malformed_json`, stderr vacío y exit 0. Publicó atómicamente el resumen
  sanitizado `baxy-gpu-status-gate-v1` en
  `artifacts/product/gpu_status_gate.json`.
- No se cerró ningún Must. El perfil físico de 4 GB, temperatura/procesos,
  diversidad exhaustiva de hardware, GUI GPU, instalador, firma y Windows limpio
  siguen pendientes; B-004/B-005/B-006 permanecen abiertos.
- El séptimo corte (`478a19a`) completó once operaciones `memory.*`. El catálogo
  contiene 21 operaciones y el handshake exige 20 capacidades interactivas;
  `app.status` continúa reservado a salud interna.
- La memoria queda apagada por defecto. Habilitar, exportar y guardar datos
  sensibles usan riesgo `privacy_sensitive`; olvidar usa `work_loss`;
  recall/list/status son `read_only`; las demás rutas son `low_reversible`.
  Confirmaciones y recuperación conservan la misma identidad durable.
- El parser explícito ES/EN/spanglish cubre guardar, recordar, olvidar, corregir,
  configurar, listar, limpiar sesión, estado y exportar, y no promueve contexto
  conversacional a memoria. El oráculo congela 100 positivos —60 literales—,
  cinco correcciones y 34 negativos duros bajo contratos de TTL, consentimiento
  e inspección.
- Los argumentos privados, resultados privados exitosos y payloads privados de
  outbox/journal usan sobres AEAD ligados a operación/misión/invocación/sesión;
  challenge/control viajan fuera del envelope y el bearer token queda RAM-only,
  redactado y sin persistir; fallos genéricos y metadatos quedan en claro. Snapshot, intención y
  watermark usan propósitos de dominio fijos separados. La clave local se
  protege con DPAPI Current User. Protocolo, store y payloads privados de
  outbox/journal no exponen contenido privado en claro; la exportación confirmada
  es la excepción y publica valores normal/personal, no sensitive/secret.
- El store privado admite hasta 512 registros y 4.096 receipts, recall de cinco,
  paginación de hasta 100, memorias persistentes/de sesión/temporales y TTL
  temporal máximo de 30 días. Mantiene snapshot/recovery/watermark cifrados,
  intención durable y fail-closed del ciphertext previo ante rollback
  parcial/incoherente, corrupción o pérdida de clave. Un rollback coordinado de
  current/recovery/watermark autenticados puede seguir siendo coherente.
- La raíz de datos privada solo admite `%LocalAppData%\BAXY\<hijo-directo>`.
  El padre y la hoja se crean con DACL protegida usuario+SYSTEM; raíz, clave,
  store y export validan handles, owner, identidad final y reparse; para
  archivos validan además un solo hardlink. Key y store publican ciphertext por
  rename relativo; la exportación confirmada escribe primero un temporal JSON
  legible en su directorio de destino y luego lo renombra. Outbox y journal aún
  operan por path/FileStream dentro de esa raíz.
- `memory.export` confirma antes de escribir y crea JSON local inspeccionable en
  `Documentos/BAXY`; redacta el contenido de registros sensibles/secretos y nunca
  exporta sus valores originales. El replay revalida ruta determinista,
  schema, identidad, conteo y SHA-256 por handle; un archivo ausente o alterado
  falla sin una afirmación falsa. La GUI advierte que Documentos puede estar
  redirigido o sincronizado.
- Release aprobó 1.035/1.035 pruebas .NET —37 Contracts, 44 Kernel, 189 Providers
  y 765 integración— y Python 65/65 más 157 subtests: 1.100 pruebas principales.
  La auditoría adversarial del diff/frontera de memoria no dejó P0/P1; queda un
  P2 teórico sobre semántica NTFS sensible a mayúsculas que exige una
  precondición especial o elevada.
- La última validación NativeAOT temporal registrada midió 6.252.544 bytes,
  SHA-256
  `D32423255E93C51FDDDAA79E3A92C39C7F0D59D21D81A5F3C760CCA93F3A7EF7`.
  Con un digest canónico de 101 archivos fuente/props/global
  `b6c1eccf…c0a0e7`, verificó hello 21/11, DPAPI real,
  status, challenge/confirm de enable, list vacío y rechazo de raíz compartida;
  terminó exit 0/stderr 0, eliminó helper/raíz temporal y preservó Notepad 5472.
  El output ignorado permanece en `src/Baxy.Core/bin/.../native/baxy-core.exe`;
  no se versionó un artefacto independiente bajo `artifacts/product`.
- En ese checkpoint el progreso permanecía en 5/15 Must. La memoria aún no personaliza otras
  operaciones; notas y contenedores/metadatos generales siguen en texto plano,
  el journal no tiene HMAC y el último directorio empaquetado era todavía el
  sexto corte.
  B-004/B-005/B-006 continúan abiertos.
- El sexto corte (`33b62bc`) añadió `audio.volume` y `audio.mute` con riesgo
  `low_reversible`. El catálogo contiene diez operaciones y el handshake exige
  nueve capacidades interactivas; `app.status` sigue reservado a salud interna.
- El parser conservador solo enruta volumen absoluto y silenciar/reactivar
  explícito sobre el audio global. Su oráculo congela 143/143 mensajes, 109
  literales, 14 fuentes y dos misiones. El corpus suma 529 filas de audio y 397
  filas de producto clase `user_mission`; las dos misiones standalone contienen
  335 mensajes
  —248 volumen y 87 mute—, por lo que quedan 192 mensajes de esas dos misiones
  standalone fuera de esta slice; además quedan composiciones.
- El provider controla únicamente el endpoint predeterminado
  `eRender`/`eMultimedia` mediante COM generado compatible con NativeAOT.
  Serializa los efectos, realiza prelecturas frescas, persiste una intención
  antes del setter y verifica por postlectura volumen, mute y la dimensión que
  debía conservar. No cubre micrófono, sesiones por aplicación, otros devices,
  cambios relativos ni composiciones.
- El replay consume el receipt terminal sin repetir el setter. Una intención
  abierta queda `pending`: no se completa el journal y la GUI conserva el mismo
  `missionId`/`invocationId`, bloquea otras rutas y permite continuar tras un
  reinicio. La reconciliación solo acredita estado observado; no afirma
  causalidad ni exactly-once, y no hay rollback/reapply automático ante
  incertidumbre.
- El store de audio falla cerrado antes de otro efecto si alcanza 16.384
  entradas o 64 MiB. El cap queda como P2 operativo: no se descartan recibos
  antiguos de forma insegura para fabricar capacidad.
- Release aprobó 665/665 pruebas .NET y 59/59 Python, 724 pruebas principales
  más 148 subtests. La auditoría final de la slice no dejó P0/P1.
- `artifacts/product/audio_control_gate.json` registra el gate físico AOT
  aprobado. El binario temporal de 5.199.360 bytes y SHA-256
  `7a45f1e8e49d169db401eca87bf95896e6a883db26f7cf2f8e977d570dd5a225`
  verificó desde 0,98/98 %/no silenciado un cambio a 88 %, mute activo, replay
  sin segundo efecto y restauración exacta del baseline.
- La primera ejecución del gate marcó la terminación como no corroborada cuando
  un chequeo con timeout cero compitió con el cierre asíncrono. Se conservó la
  evidencia, se restauró y verificó el baseline antes de corregir el harness y
  repetir; el artefacto documenta también la limpieza. El gate observa estado,
  no sonido audible, y cubre un equipo y un endpoint.
- El progreso permanece en 5/15 Must. El sexto corte reduce B-004 y aporta una
  evidencia acotada a B-006, pero no cierra ninguno; B-005 también sigue abierto.
- El build local se reconstruyó después de `33b62bc`: 14 archivos de carga y
  54.831.324 bytes más el manifiesto. SHA-256: manifiesto
  `4c0378c01ffd67d6949f90f1c0f2f611300cea2450e32ef1ac5756d36fb3553a`,
  app `f017ba4babdf307f6dc5a3403089e9d14e59ed76c6c62526693bea907b80be80`
  y core `0f794ae353a22e2b6bdbc21da51513e4116c776d12e170c02616ce440d38cc94`.
  El manifest revalidó 14/14 archivos. El smoke anunció `baxy.local.v1` y diez
  capacidades —incluidas `audio.volume`/`audio.mute`—, con exit 0, stderr vacío
  y cero procesos Baxy/core residuales; preservó el Notepad PID 5472.
  Sigue siendo un directorio de desarrollo —app framework-dependent y core
  self-contained—, no instalador, prueba en Windows limpio ni release firmada.
- La captura GUI vigente en ese checkpoint `product_notes_slice.png` mide
  980×680 y 71.521 bytes,
  SHA-256
  `4eb2dd03bc0d1ba32c452d2b92c0d13124acb12e7651b4e59133abdb702ca6b6`.
  Registra core listo, misión de nota completada, una nota, outbox vacío y cero
  procesos residuales. No acredita un E2E de audio.
- El quinto corte (`88cb456`) añadió `system.status` como operación local
  `read_only`. El catálogo productivo contiene ocho operaciones y el handshake
  exige siete capacidades interactivas; `app.status` permanece como salud
  interna.
- El provider Win32 mide únicamente CPU, RAM, disco del sistema, batería,
  versión/build/arquitectura de Windows y uptime. CPU usa dos muestras separadas
  por 150 ms. No existen campos ni probes para GPU/VRAM, procesos, IP, hostname
  o usuario; los fallos parciales se sanean y una batería all-unknown no se presenta
  como presente o ausente.
- El parser acepta scopes finitos en frases completas y rechaza negaciones,
  condicionales, conocimiento/precios, procesos, red y mezcla con otra operación.
  CPU+RAM y Windows+RAM siguen siendo un único `system.status`, no composición
  multioperación.
- El oráculo curado congela 113/113 IDs —50 literales, una misión, nueve rutas
  `source`, digest `9d55e3fa…f21e`—. Es un subconjunto de 306 filas globales
  `system.status` —294 product/12 trace; 279 product `user_mission`—. Resumen,
  `os` standalone y spanglish históricos no quedan acreditados.
- En el checkpoint del quinto corte, Release aprobó 460/460 pruebas .NET
  —Contracts 23, Kernel 27, Provider 81 e
  integración 329— y 59/59 Python: 519 pruebas principales más 148 subtests. El
  red-team final terminó con cero P0/P1 tras cerrar batería all-unknown y
  Windows 11/Server.
- Un NativeAOT temporal de 4.857.856 bytes, SHA-256
  `83e972f4273380b587192684a14cb01f42837f08e389082a87cd8d443cb4c488`,
  aprobó 2/2 requests reales: CPU+RAM minimizado y summary de seis secciones. Se
  eliminó tras el smoke; no es distribuible, instalador ni gate de Windows
  limpio.
- El progreso permanece en 5/15 Must y B-004/B-005/B-006 siguen abiertos. El
  quinto corte reduce B-004 sin afirmar cobertura completa de `system.status`,
  conversación general o composición.
- El cuarto corte (`fa08653`) cerró la ambigüedad de títulos mediante un flujo
  conversacional durable en dos fases. La primera petición conserva una
  shortlist inmutable; elegir reemplaza atómicamente esa entrada del outbox por
  una ruta exacta con el mismo `missionId` y otro `invocationId` antes de enviar.
- La shortlist muestra cinco candidatos por página y números absolutos hasta
  512, junto con estado, fecha y un preview de máximo 128 bytes UTF-8. No expone
  UUID ni JSON. El resultado completo de 512 candidatos adversariales queda por
  debajo de 700.000 bytes y del límite JSONL de 1 MiB.
- La selección se valida bajo el lock del store contra UUID, título Form C sin
  distinguir mayúsculas, revisión y estado. Un cambio posterior devuelve
  `note_selection_stale` sin contenido ni efecto; un retry mutante solo
  reconcilia el caso exacto revisión N+1/estado objetivo.
- El parser de selección es contextual: acepta números y ordinales acotados en
  español, inglés y spanglish, además de paginación/cancelación; fuera de una
  aclaración, un número desnudo no es una orden global. Rechaza controles,
  composiciones, índices fuera de rango y UTF-16 malformado.
- En el checkpoint del cuarto corte, Release aprobó 375/375 pruebas .NET
  —Contracts 23, Kernel 27, Provider 64 e integración 261— y 59/59 Python: 434
  en total. La auditoría final no dejó
  P0/P1 y cerró el P2 de duplicados. No se cierra ningún Must adicional;
  B-004/B-005/B-006 siguen abiertos.
- La durabilidad actual no añade un schema v2 de recibos de mutación: la
  reconciliación posterior al efecto usa la aproximación acotada N+1/estado
  objetivo, además del enlace de candidato y journal/outbox. Este límite queda
  documentado y no se presenta como autenticidad adversarial.
- El distribuible de 50.546.916 bytes del segundo corte quedó supersedido por el
  build local post-`33b62bc` descrito arriba; ninguno constituye un instalador.
- El tercer corte (`c1c07ff`) expuso conversacionalmente el ciclo local de
  notas `create/list/read/trash/restore` con gramáticas finitas en español,
  inglés y spanglish. No añade conversación general ni composición libre.
- El oráculo curado de creación standalone queda en 40 mensajes únicos,
  13 literales y 49 ocurrencias de procedencia; 40/40 enrutan a `note.create`.
  No equivale a toda la familia histórica `note.manage`, que contiene archivos,
  recordatorios compuestos, documentación y ruido.
- Las notas rápidas reciben un título determinista derivado del contenido,
  Unicode Form C y máximo 120 bytes UTF-8 sin cortar runas. Negaciones,
  condicionales, órdenes masivas, controles, UTF-16 malformado, filesystem y
  recordatorios compuestos fallan cerrado.
- `note.read` selecciona el único título activo exacto con comparación
  `OrdinalIgnoreCase`. `note.trash`/`note.restore` exigen unicidad global entre
  activas y papelera, seleccionan y mutan bajo el mismo lock y reutilizan sin
  otra revisión un estado ya alcanzado tras una interrupción.
- La GUI proyecta título/contenido de lectura sin JSON, con límite de 16.384
  caracteres, truncamiento explícito y frontera UTF-16 válida. Las mutaciones
  responden con el estado verificado, no vuelven a afirmar un efecto en retries.
- El handshake ahora exige las seis capacidades interactivas con riesgos
  exactos. `app.status` tiene argumentos vacíos estrictos y el arranque compara
  el catálogo declarado con el registro real.
- Un recorrido automatizado ViewModel→core→store completó crear, leer,
  papelera, listar, restaurar y listar de nuevo; una instancia independiente
  reabrió el store, verificó contenido/revisión 3 y el outbox quedó vacío.
- Release aprobó 337/337 pruebas .NET —Contracts 23, Kernel 26, Provider 60 e
  integración 228— y 59/59 Python: 396 en total. El fault injection de
  trash/restore corta el completion después del efecto y demuestra recuperación
  con la misma revisión antes del replay terminal.
- La auditoría de ese checkpoint no encontró P0/P1. Se corrigió el P2 de
  surrogates UTF-16 aislados; en ese momento permanecía el P2 de títulos
  duplicados, cerrado después por el cuarto corte. No se cerró ningún Must
  adicional; B-004/B-005/B-006 siguieron abiertos.

## 2026-07-14

- Se creó la memoria operativa `contexto/` sin modificar `legacy/`.
- Se congeló el corpus histórico y se ejecutó el torneo de base cero sin
  migrar `legacy/` por inercia.
- La repetición final corrigió T16, red fail-closed y procedencia de raws. Se
  aprobó WPF + .NET NativeAOT como base y WPF + Rust estático como fallback
  Pareto. Evidencia:
  `../04_arquitectura/ADR/ADR-0001-arquitectura-base-baxy-1.md`.
- Los prototipos y scripts del torneo no se promocionan por copia directa. El
  producto nuevo se inició por un corte vertical sobre contratos rediseñados.
- Se creó `Baxy.slnx` con shell WPF, core .NET NativeAOT, contratos, kernel,
  provider Windows y cuatro proyectos de pruebas. Shell y core se comunican por
  JSONL local `baxy.local.v1`.
- El primer catálogo productivo contiene `app.status` y el ciclo local de notas
  `create/read/list/trash/restore`. La GUI natural solo expone creación y
  listado; las otras operaciones quedan disponibles únicamente por contrato.
- El store usa JSON con SHA-256, escritura atómica y backup recuperable. No hay
  cifrado ni MAC. El journal enlaza por hash las fases de misión y permite
  replay, pero no usa HMAC.
- Se acotó a 1 MiB el JSONL en ambas direcciones y se limitó también stderr. Se
  paginó `note.list` en el provider con límite 50 por defecto, máximo 100 y
  `offset`, se excluyó el contenido de sus resultados y se fijó un máximo de
  512 notas en el store.
  La GUI conserva identificadores al reintentar hasta una respuesta terminal;
  el outbox se persiste antes del envío, sobrevive al reinicio completo del
  shell y elimina la entrada tras el terminal. Un `started` incompleto en
  conflicto devuelve `idempotency_conflict` sin matar el core y los fallos
  normales de arranque muestran `No disponible`.
- Se acotó el outbox JSON en texto plano a 1 MiB y 128 entradas. Cada entrada
  incorpora un checksum SHA-256 canónico contra corrupción accidental; no tiene
  cifrado ni HMAC y falla cerrado ante corrupción o rutas reparse. Los scripts
  validan cada ancestro, ADS y puntos reparse; la limpieza se liga a handles de
  procesos propios. Una prueba hostil de junction preservó el centinela.
- El journal quedó limitado a 64 MiB, con compactación exacta, reservas de
  2 MiB reconstruidas tras reiniciar y rechazo por capacidad antes del efecto
  sin perder la identidad durable. Los fallos mutantes inesperados conservan la
  invocación incompleta y reintentable con el mismo ID. Se corrigieron además la
  falsa disponibilidad tras timeout y la limpieza del hijo aun cuando falle la
  asociación al Job de Windows.
- En el primer checkpoint, Release aprobó 101/101 pruebas .NET —Contracts 23,
  Kernel 26, Provider 16 e integración 36— y la suite histórica Python aprobó
  41/41: 142 pruebas en la corrida conjunta. Se produjo una captura de 980×680
  con `core_ready`, `mission_completed`, una nota, cero procesos
  residuales y un outbox vacío tras el terminal, y un build local de 14 archivos
  de carga y 48.396.888 bytes, más el manifiesto. El build todavía no es un
  instalador ni una migración de datos de `legacy/`.
- El segundo corte incorporó `app.open` exclusivamente para
  `windows.notepad`. El parser natural solo emite ese identificador constante y
  rechaza rutas, argumentos, URLs, negaciones, preguntas informativas y
  comandos compuestos.
- El provider Windows inventaría antes de actuar, valida identidad exacta
  System32/paquete Microsoft sin reparse, lanza sin argumentos ni handles
  heredados y verifica de forma independiente PID, creación, ruta, ventana
  visible y foco. El breakaway queda reservado a ese bootstrap; el core y los
  demás hijos continúan bajo el Job.
- El estado durable por invocación usa checksum y escritura atómica, con topes
  de 16.384 entradas/64 MiB. El replay es at-most-once: un intent ambiguo o un
  receipt cuyo PID desapareció no vuelve a lanzar y divulga el posible efecto.
  La frontera del core rechaza recibos contradictorios o ajenos.
- En el segundo checkpoint, Release aprobó 230/230 pruebas .NET —Contracts 23,
  Kernel 26, Provider 56 e integración 125— y Python 41/41: 271 en total. La
  auditoría final cerró sin P0/P1. El build contiene 14 archivos de carga y
  50.546.916 bytes, más el manifiesto.
- El gate físico directo de core/provider se abstuvo con
  `preexisting_notepad`; preservó el PID 5472. No aprueba todavía lanzamiento
  fresco, replay, supervivencia al Job ni recorrido WPF completo. Su cleanup no
  cierra Notepad por defecto y nunca fuerza terminación.
- Los artefactos derivados del corpus migraron al schema 2, revisión
  `2026-07-14-polarity-and-game-routing-v2`. La revisión modela operaciones
  denegadas y corrige polaridad y routing de juegos sin cambiar el manifiesto,
  el cutoff ni las 122.744 ocurrencias. La nueva consolidación semántica produce
  14.836 mensajes —12.036 de producto y 2.800 de traza— y 2.083 misiones
  canónicas. Los tres mensajes adicionales son separaciones por alcance, no
  ocurrencias nuevas.
- El metadata derivado fija el alcance funcional de producto en español,
  inglés y spanglish, incluidos code-switch y errores de STT de esos idiomas.
  Las variantes inequívocamente ajenas quedan como trazabilidad `trace-only` y
  no se usan para inflar cobertura ni justificar nuevas reglas de 1.0.
- `language` continúa siendo una señal heurística, no un filtro de aceptación:
  textos breves objetivo pueden quedar etiquetados como `other`. La pertenencia
  al alcance se liga a oráculos semánticos auditados.
- Esta migración sanea especificación y artefactos derivados; no añade providers
  al runtime, no acredita gates físicos o instalación y no altera el estado de
  los Must ni de los bloqueantes vigentes.
- La validación conjunta posterior aprobó 59/59 pruebas Python y mantuvo
  230/230 pruebas .NET: 289 en total. Este incremento corresponde a contratos
  del corpus y no acredita nuevas capacidades físicas.
- Dos reconstrucciones finales A/B con el builder `857e1774…11efeec` coincidieron
  byte a byte en los cuatro artefactos derivados. Esta reproducibilidad tampoco
  acredita providers, instalación ni gates físicos.
