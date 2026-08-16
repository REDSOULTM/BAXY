# Estado actual

- Actualizado: 2026-07-25, zona `America/Santiago`.
- Fase: 6 — mente entregada por Fable sobre las cuatro costuras; BAXY 1.0
  completo salvo pendiente-por-entorno.
- Rama: `codex/baxy-rebuild-v3`.
- Release instalado comprobado: **1.0.8**, con **1.0.7** como rollback.
  Producto/paquete/Setup A/B son byte-idénticos; el ciclo enlazado validó la
  activación recuperada, rollback real a 1.0.7 y reactivación de 1.0.8 sin
  alterar los 11 árboles versionados ni 1.780.271.404 bytes privados.
- Definition of Done formal: **13/15 gates Must aprobados (86,7 %)**. Los
  gates 13 y 14 esperan el equipo/perfil limpio del usuario; Gate 7 ya abrió
  micrófono, loopback y TTS físicos en este host. La calibración de la voz
  personal y el tramo de GPU física de 3 GiB siguen anotados como entorno.
- Mente (ADR-0005): sidecar Python `baxy-mind` (router de embeddings
  e5-small 675/675 contra oráculos; LLM Gemma-4 E2B QAT por llama-server;
  voz completa Silero 6.2.1 + Parakeet int8 + wake verificado + SAPI +
  loopback/AEC/ducking/barge-in) sobre la frontera
  JSONL + Job Object. Opcional y degradable: sin `BAXY_MIND_PYTHON`, el
  producto es exactamente el cuerpo determinista congelado (1.787/1.787
  pruebas verdes en la corrida final). Ver
  `contexto/06_pruebas_y_mediciones/GATES_MENTE.md` y `src/baxy_mind/README.md`.

## Estado del cuerpo al handoff (histórico, 2026-07-15)

- Último commit funcional del cuerpo: `78169ad` (`refactor(architecture): freeze tools and sidecar seams`).
- Definition of Done del cuerpo: 8/15 gates Must aprobados (53,3 %).
- El coordinador/worker/journal/Run heredado fue retirado y sustituido por una
  fachada convencional pequeña en `901b6c4`. No restaurar ese subsistema sin una
  prueba roja del gate físico.
- Procesos relevantes: no hay servidor persistente. Debe preservarse el Notepad
  preexistente PID 5472 en cualquier gate físico.

## Alcance 1.0 congelado

- Corpus schema v3: 14.836 mensajes únicos y 122.744 ocurrencias, todos con
  procedencia; 12.036 mensajes de producto y 2.800 `trace_only`.
- Ledger vigente: 2.084 misiones y 43 familias después del corte audio 28.
- Arquitectura base: host WPF + core .NET 10 NativeAOT, JSONL local
  `baxy.local.v1`. ADR-0008 sustituye solo la presentación: WebView2 sirve el
  BAXY Field literal de `4a83f2d` por virtual host local y bridge nativo, con
  navegación y requests externos bloqueados. Rust queda como fallback del core.
- El cuerpo determinista conserva su techo histórico de 22 operaciones. La
  capa Fable vigente lo amplía mediante el catálogo autenticado de 168
  capacidades, router, LLM, planner durable y pila de voz; el core continúa
  siendo la única autoridad de schemas, riesgo, ejecución y verificación.

## Evidencia semántica y decisión de turnos

- El corpus runtime exacto contiene **25.156 filas** y SHA-256
  `8abff5805a93615c6f5a655b9af5559063e34226cfc0db58c5547d97a70ee680`:
  17.784 filas públicas de train y 7.372 históricas filtradas. El holdout
  público de 9.172 filas permanece fuera de runtime y tiene cero
  solapamientos de texto normalizado.
- El encoder real es `intfloat/multilingual-e5-small`, 384 dimensiones. El
  caché local v4 verificado tiene forma 25.156 × 384, se recarga sin volver a
  codificar y declara `contains_text:false`.
- La política runtime `baxy.turn-evidence-one-sided-policy.v1`, evaluada contra
  el sello final v2, sólo puede sugerir conversación o abstenerse. Obtuvo
  precisión 0,994083 (Wilson inferior 0,973916), recall 0,42 (inferior
  0,380079) y 0/400 falsos accionables (Wilson superior 0,006718). El
  diagnóstico de familia no tiene autoridad de ejecución.
- El candidato jerárquico E5 de desarrollo v2 quedó
  `failed_no_runtime_promotion`: aunque tuvo cero errores direccionales,
  seleccionó 12/2.300 turnos `supported_effect` (0,005217 < 0,02). Además, dos
  rutas de guards del prerregistro no resolvían contra el artefacto; no se
  corrigieron a posteriori. No se publicó peso, fast path ni señal de acción.
  El test oficial de MTOP (7.384 filas selladas a nivel de bytes) y el holdout
  final reservado continúan sin abrir.
- Por tanto sigue vigente el fallback contextual del LLM, complementado sólo
  por la evidencia one-sided ya promovida y siempre detrás del catálogo,
  schema, riesgo y verificador del core.
- El gate físico v4 aprobó 45/45 solicitudes y cero errores por perfil. GPU
  usó 1.509,6 MiB de VRAM atribuida al árbol; CPU puro usó 109,5 MiB y
  `turn.decide` tuvo p50 19,509 s bajo el SLA de 22 s. Saludo y catálogo
  compartieron el handshake acumulado de 120 s.

## Producto implementado

- BAXY Field histórico exportado desde Git sin redibujarlo: host WPF, React
  congelado, campo neuronal, actividad y compositor bloqueado hasta `core_ready`.
  El bridge conserva `MissionInput`, planner, voz/wake y controles de ventana;
  memoria/rutinas directas y adjuntos no obtienen autoridad por la GUI antigua.
- Catálogo público autenticado con **168 operaciones**; el handshake transporta
  y exige nombre, schema cerrado, riesgo, verificador y descripción exactos.
  Las cifras de 22/21 que aparecen en cortes anteriores describen el cuerpo
  determinista histórico, no el catálogo público actual.
- `MissionInput` unifica texto/transcripción. Los handlers devuelven resultados
  tipados y un narrador separado produce el lenguaje natural. El core usa un
  host JSONL reutilizable con Job Object por sidecar, listo para un segundo
  proceso local sin incorporar todavía IA.
- `audio.status` y doce aliases nominales de volumen están integrados; las
  consultas de estado ES/EN/spanglish son exclusivamente `read_only` y no
  colisionan con `audio.volume`.
- Memoria local apagada por defecto con 11 operaciones explícitas, DPAPI Current
  User, cifrado autenticado, TTL/sesión, inspección, borrado y export redactado.
- Journal durable global autenticado por HMAC; las reservas y replays privados
  ya no dependen de un checksum sin clave.
- Notas con creación, lectura, paginación, trash/restore, selección durable y
  fail-closed ante ambigüedad o cambio de revisión.
- Audio global con pre/postlectura, mutex y journal de intención. No controla
  micrófono, sesiones por app ni otros endpoints y no afirma causalidad cuando
  sólo observa reconciliación.
- GPU mediante DXGI/PDH in-process, sin `nvidia-smi`, red ni subprocess.
- Voz local en dos modos: botón directo y escucha continua por «Baxy»; ambos
  confluyen en `MissionInput`. Silero/Parakeet hacen VAD/STT, WASAPI+NLMS aporta
  AEC, SAPI habla/cancela y la UI mantiene un indicador visible de escucha.

## Lifecycle Windows implementado

- Coordinador transaccional de instalación/actualización/rollback/reconcile con
  gates nominales ordenados, host estable verificado, integración Windows y
  recuperación por fases. `Program` ya enruta install/update y rollback a este
  lifecycle.
- Registro de desinstalación y shortcut Start Menu exactos; el shortcut puede
  borrarse por COM/hash/handle incluso después de mover la instalación.
- Uninstall es una fachada de 418 líneas físicas (371 no vacías): adquiere los
  dos mutex por usuario y entre sesiones, verifica
  puntero/estado/host/shortcut/registro, renombra la raíz a un sibling único con
  `Directory.Move`, elimina integración exacta y deja a `System32\cmd.exe` tres
  intentos acotados para borrar el ejecutable una vez que sale el Setup padre.
- `--uninstall` y `--uninstall --keep-data --quiet` no inspeccionan la hoja
  `%LOCALAPPDATA%\BAXY`; purge sólo existe con el token exacto
  `--purge-data --confirm-purge-data --quiet`.
- No existe ya protocolo interno `--uninstall-worker`, maintenance root,
  handoff, Run/RunOnce, Restart Manager, journal o state machine de uninstall.
  La poda elimina más de 16.600 líneas tracked de producción/pruebas en este diff; no
  se reconstruye ninguna pieza sin un fallo físico reproducible que la exija.

Commit funcional reciente:

- `901b6c4` reemplazó el subsistema uninstall por primitivas Windows y eliminó
  16.602 líneas netas en el commit.
- `40126f3` unificó la entrada de misión tipada y la futura entrada de voz.
- `17d85bd` cerró Audio Global 28, `audio.status`, niveles nominales y el gate
  físico aislado sobre `BAXY_DATA_DIR`.

## Evidencia vigente y límites

- Setup simplificado aprobó 472/472 pruebas Release. El gate `[Explicit]` que
  ejecuta una copia de `cmd.exe` desde la raíz demostró que Windows puede
  renombrar el directorio mientras ese ejecutable sigue activo.
- El cleaner real de `cmd.exe` aprobó tanto borrado inmediato como retry ante un
  archivo sin delete sharing, preservando un sibling. Un primer rojo reveló que
  `ArgumentList` no entregaba el comando compuesto con la forma esperada; la
  regresión fija ahora el argumento `/s /c` completo.
- Publish NativeAOT payloadless aprobó con un único `Baxy.Setup.exe` de 3.917.824
  bytes, SHA-256 `37703252c4266f3e1a5bdfb96ad2a49407edf3a1d13583c177c931fa2a390644`.
- Evidencia histórica del release 1.0.1: `d69a960` fue construido desde HEAD
  limpio como predecesor
  1.0.0 y candidato 1.0.1 A/B. Las dos candidatas son byte-idénticas en producto
  (8 archivos), paquete (2) y Setup (3). El Setup candidato mide 87.016.960
  bytes y tiene SHA-256
  `fe2b16c14a7369713cb76333ce8a248b27ede216c357a45c55d253e5ee9b5be5`.
- El recorrido físico same-host aprobó instalación 1.0.0, update 1.0.1,
  rollback 1.0.0 y uninstall keep-data. Quedaron ausentes InstallationRoot,
  shortcut, registro y tombstones, con cero procesos; un canary propio sobrevivió
  byte-idéntico y se retiró sin tocar las tres entradas preexistentes. Evidencia:
  `artifacts/setup/gate14_lifecycle_gate.json`.
- Gate 14 sigue pendiente: esta ejecución no fue en perfil limpio, no ejerció
  purge-data ni primer inicio instalado. Esos claims esperan un Windows o perfil
  desechable; no se usarán los datos reales del perfil actual.
- Audio Global 28 aprobó 183/183 integración, 44/44 provider, 14/14 catálogo,
  37 tests + 58 subtests de corpus, A/B byte-idéntico, Ruff, NativeAOT y gate
  GPU físico con 22 operaciones. Un aparente P0 de HMAC era un falso diagnóstico:
  el script exportaba `BAXY_DATA_ROOT`, mientras Core consume `BAXY_DATA_DIR`.
  Corregido el aislamiento, un perfil realmente nuevo crea journal, anchor y
  clave HMAC, reinicia/reproduce y mantiene tamper fail-closed.
- Gate 11 está aprobado. El release 1.0.1 completó una misión de nota en WPF con
  raíz aislada, respuesta visible y UIA, captura nativa 980×680 e inspección
  visual; 14/14 contratos de geometría/paleta/layout/automatización/contraste y
  22/22 regresiones de packaging pasan. El rojo anterior se aisló al observador:
  mezclaba éxito durable con UIA y usaba literales Unicode incompatibles con la
  lectura ANSI de Windows PowerShell 5.1. Evidencia:
  `artifacts/product/gui_capture_gate.json`.
- Gate 10 está aprobado en su techo determinista v3. El oráculo congelado y las
  fronteras de DPAPI/store/export/journal pasaron 405/405 pruebas focalizadas,
  con cero P0/P1. Evidencia: `artifacts/product/memory_privacy_gate.json`. La
  personalización de otras operaciones queda del lado Fable y no reabre este
  gate.
- Las cuatro costuras Codex→Fable pasan. La corrida completa vigente aprobó
  **2.063/2.080 pruebas .NET** —46 Contracts, 88 Kernel, 373 Providers, 1.092
  Integration y 464 Setup— con 17 omisiones explícitas y cero fallos. Python
  aprobó **611 pruebas y 350 subtests**, sin fallos ni omisiones. El E2E
  post-hardcode aprobó 4/4 recorridos read-only shell→mente→core en 142,772 s,
  sin efectos externos y con journal HMAC validado. Cero P0/P1 conocidos.
  Evidencia:
  `artifacts/product/architecture_seams_gate.json`.
- Release 1.0.8 reproducible: el candidato limpio `b41dda11567a` produjo dos
  árboles de producto exactos, dos ZIP SHA-256
  `9e4abb30c8f4312e094b5fad9dd1d40c631f2c0399769447da9acc22767f8cbb`
  y dos Setup SHA-256
  `c71fad8fce77d82a07ba97729d67546632b0772273a7cdf8f902204386696fe5`.
  Setup mide 175.300.096 bytes, conserva `NotSigned` y verificó el paquete
  embebido.
- La primera atestación se detuvo honestamente en el smoke. El diagnóstico
  local, cubierto después por las regresiones del gate, identificó un perfil
  fuera del almacén privado permitido y stdin abierto por PowerShell con BOM.
  Su recuperación dejó 1.0.8/1.0.7 exacto y datos preservados; la evidencia
  fallida se conserva con SHA-256 `ae0885b6…281c7`. El gate limpio
  `cc2bf9de73b1` corrigió ambas precondiciones y reanudó desde ese SHA fijado,
  sin borrar ni reconstruir la versión instalada.
- La continuación aprobó los tres estados 1.0.8/1.0.7 → 1.0.7/1.0.8 →
  1.0.8/1.0.7, con smoke `baxy.local.v1` de 168 capacidades, exit 0 y salida
  limpia en cada estado. Los 11 árboles inmutables, `install_id`, acceso directo
  y 1.780.271.404 bytes privados quedaron idénticos; no hubo procesos,
  transacciones ni perfiles residuales. Evidencia SHA-256 `83295630…81c31` y
  resumen versionado `artifacts/setup/baxy_1_0_8_release_attestation.json`.
  El commit documental posterior no se presenta como el commit embebido del
  candidato, evitando una autorreferencia imposible.
- Evidencia histórica de reproducibilidad: el HEAD limpio `455243c` produjo
  predecesor 1.0.0 y candidato 1.0.1
  A/B byte-idéntico en producto (8 archivos), paquete (2) y Setup (3). El Setup
  candidato mide 87.040.000 bytes, SHA-256
  `68cfc30172b5b15e72e4085fcfb243107b54931d050f111d87cfb1991930cd83`;
  su ZIP mide 83.121.455 bytes, SHA-256
  `fdded6df99c9353a1c752855d5279e0f88642fa940f911b1982951e15a866978`.
  Los tres Setup verificaron su paquete embebido y siguen `NotSigned`. El core
  NativeAOT saludó con 21 tools públicas, sin `app.status`, y retiró su hoja
  aislada. Evidencia: `artifacts/setup/final_release_gate.json`.
- Packaging previo es reproducible same-host, no cross-host ni firmado. No hay
  Windows Sandbox, VirtualBox ni ISO disponibles en este host; no afirmar VM
  limpia hasta obtener evidencia real. Para Gate 14 el contrato vigente exige
  artefacto y checksum, no certificado de editor.

## Definition of Done pendiente

- Gate 4 completo: la comprensión usa embeddings E5 y el catálogo autenticado,
  sin ampliar capacidades mediante regex o respuestas por frase. La política
  one-sided puede sugerir conversación o abstenerse; el candidato jerárquico
  v2 fue rechazado sin promoción y el LLM conserva la decisión contextual.
- Gates 7 y 9 están implementados por Fable. Gate 7 pasó micrófono, loopback,
  TTS/cancelación física, 6/6 ES/EN/spanglish y UI real; queda la calibración
  personal FAR/FRR/barge-in. Gate 12 mantiene pendiente una pasada en una GPU
  física de exactamente 3 GiB.
- Gate 8: planner/composición general y política transversal son frontera
  Fable; el catálogo/riesgo de las 168 operaciones vigentes queda bajo
  autoridad determinista del core.
- Gate 13: suites globales y cero P0/P1 están cerrados; solo `app.open` físico
  espera una sesión limpia.
- Gate 14: falta únicamente instalación/primer inicio/purge en perfil limpio;
  install/update/rollback/keep-data same-host ya están demostrados.
- Gate 15 está aprobado: operación, rollback, comparación, checksums, evidencia
  y cierre documental quedan versionados.

## Pendiente por entorno — no bloquea v3

1. Instalación desde cero, primer inicio y uninstall purge de Gate 14 esperan un
   perfil/Windows desechable. El perfil actual contiene tres entradas BAXY que
   no se inspeccionarán ni borrarán.
2. El gate físico `app.open` espera un entorno sin procesos preexistentes; el
   Notepad PID 5472 se preserva. No se reintentará en este equipo.

Ambos recorridos deben quedar listos para una sola ejecución cuando el usuario
disponga del equipo limpio. No cuentan como P0/P1 ni detienen Gates 4/8/10/11.

## Próximos tres pasos

1. En un perfil desechable limpio, ejecutar el recorrido único de Gate 14.
2. En una sesión sin procesos preexistentes, ejecutar el recorrido `app.open`.
3. Con el usuario presente, ejecutar el corpus corto de wake/barge-in personal;
   la pila y el gate ya están preparados y el cuerpo determinista no cambia.
