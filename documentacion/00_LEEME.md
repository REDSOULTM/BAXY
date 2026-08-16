# Documentación de BAXY

Esta carpeta es el puente entre todo lo aprendido desde Carter y la
reconstrucción definitiva de BAXY.

No sustituye las fuentes originales ni pretende comprimir cientos de
documentos en unas pocas conclusiones sin procedencia. Organiza el conocimiento
en siete niveles:

1. Arquitectura y mantenibilidad vigentes: decisión, mapa, fronteras, puntos
   de extensión y estado de la cimentación.
2. Evidencia primaria preservada: repositorios, conversaciones, logs, corpus,
   pruebas, commits y grabaciones.
3. Índice de fuentes: dónde está cada familia de evidencia y qué contiene.
4. Archivo recuperado de subagentes: índice versionado y segmentos privados.
5. Síntesis de procedencia: contrato, hallazgos y candidatos tecnológicos.
6. Evidencia ejecutable: ledger histórico, misiones, regresiones y gates
   físicos del producto nuevo.
7. Genealogía causal y ledger de auditorías con estado de evidencia.

## Orden de lectura

1. [00_MVP_2026-08-11.md](00_MVP_2026-08-11.md), para ejecutar o retomar el adelanto actual
2. [01_ARQUITECTURA/GUIA_AGENTES_IA/README.md](01_ARQUITECTURA/GUIA_AGENTES_IA/README.md)
3. [01_ARQUITECTURA/DECISION_VIGENTE.md](01_ARQUITECTURA/DECISION_VIGENTE.md)
4. [01_ARQUITECTURA/MAPA_DEL_SISTEMA.md](01_ARQUITECTURA/MAPA_DEL_SISTEMA.md)
5. [01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md](01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md)
6. 01_CONTRATO_PRODUCTO.md
7. 02_INDICE_FUENTES.md
8. agentes\README.md
9. agentes\INDICE.md y manifest.json, solo para arqueología
10. 03_HALLAZGOS_AGENTES.md
11. 04_ARQUITECTURA_TECNOLOGICA.md
12. 05_FALLOS_Y_REGRESIONES.md
13. 06_MAPA_FUENTES_HISTORICAS.md
14. 07_LEDGER_REQUISITOS_HISTORICOS.md
15. 08_EVOLUCION_CARTER_A_BAXY.md
16. 09_LEDGER_EVIDENCIA_AGENTES.md
17. 10_TORNEO_TECNOLOGICO.md
18. 11_PRIMER_CORTE_PRODUCTIVO.md
19. 12_SEGUNDO_CORTE_APP_OPEN.md
20. 13_TERCER_CORTE_NOTAS_NATURALES.md
21. 14_CUARTO_CORTE_DESAMBIGUACION_NOTAS.md
22. 15_QUINTO_CORTE_ESTADO_LOCAL_PC.md
23. 16_SEXTO_CORTE_AUDIO_GLOBAL.md
24. 17_SEPTIMO_CORTE_MEMORIA_PRIVADA.md
25. 18_OCTAVO_CORTE_GPU_LOCAL.md
26. 19_NOVENO_CORTE_DISTRIBUCION_REPRODUCIBLE.md
27. 20_DECIMO_CORTE_SETUP_REPRODUCIBLE.md
28. 21_UNDECIMO_CORTE_DATA_SCHEMA_CONGELADO.md
29. BAXY_GPT56_ULTRA_PROMPT.md, en la raíz y solo como contrato histórico

Los archivos de arquitectura bajo `01_ARQUITECTURA/` describen el producto
activo. Los cortes numerados, torneos y síntesis anteriores conservan sus
conteos y conclusiones como historia de su fecha; no deben usarse para
sobrescribir el mapa vigente.

## Regla de procedencia

Cada afirmación futura debe distinguir:

- decisión directa del usuario;
- evidencia física reproducible;
- prueba automatizada;
- conclusión de una auditoría o agente;
- hipótesis pendiente;
- dato histórico obsoleto.

No se considera incorporado un descubrimiento por aparecer en un resumen. Debe
terminar en una decisión, una prueba, una misión histórica o una limitación
documentada.

## Por qué no se copian todas las fuentes aquí

El repositorio Probando Gemma 4 contiene al menos 852 archivos Markdown y más
de 2.000 artefactos JSON/JSONL/TSV. FunctionGemma contiene 227 módulos Python y
550 artefactos estructurados. El BAXY archivado conserva 916 archivos
versionados y 97 archivos con marcadores relacionados con auditorías, Spotify,
Gemma o soak.

Duplicarlos dentro del nuevo árbol haría más difícil saber qué es fuente y qué
es interpretación. Por eso las fuentes permanecen intactas y esta carpeta
mantiene rutas, prioridades, hallazgos y reglas de extracción.

La excepción controlada es el historial de agentes: sus 322 segmentos propios
se comprimieron en documentacion\agentes\privado para no depender de la UI ni
duplicar los contextos heredados. Esa carpeta es local, sensible e ignorada por
Git; solo el índice sanitizado y el exportador reproducible se versionan.

## Estado vigente

El estado operativo se mantiene en un solo lugar:
[01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md](01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md).
Allí están el último extremo validado, conteos, omisiones, publicaciones,
instalación comprobada, deuda y condiciones de cierre. Esta página no duplica
esos valores para evitar que un agente mezcle campañas.

Las fronteras estables son:

- 169 operaciones públicas y una operación interna de salud;
- catálogo validado contra el proceso Core hijo y los descriptores compilados,
  sin afirmar firma criptográfica del hello;
- Core/Kernel como autoridad de schema, riesgo, confirmación, ejecución,
  verificación, journal y replay;
- Mind como conversación/propuesta degradable, sin autoridad de efecto;
- evidencia semántica unilateral: conversación o abstención;
- FieldUi histórica sellada y servida localmente por WebView2;
- Setup independiente y transaccional.

Para una medición histórica concreta, usa su artefacto y commit. Para corpus de
turnos, consulta ADR-0009; para gates de mente,
`contexto/06_pruebas_y_mediciones/GATES_MENTE.md`; para instalación,
`artifacts/setup/baxy_1_0_8_release_attestation.json`.

## Estado histórico de los cortes iniciales

Todo lo que sigue es una transcripción de estado de sus respectivos cortes.
Palabras como «vigente», «pendiente», «sigue» o «todavía» dentro de esta
sección se leen en la fecha de aquel corte, nunca como estado del producto
actual.

- El BAXY anterior está en legacy y en el commit ee06786.
- El archivo limpio comenzó en d3b92a3.
- El prompt de genealogía fue consolidado en 886a435.
- legacy se considera referencia de solo lectura.
- Se reconstruyeron 322 sesiones de subagentes: 302 directas y 20 anidadas.
- El archivo privado contiene 322 segmentos y sus informes; no debe publicarse.
- El torneo aprobó como base shell .NET 10 WPF + core .NET NativeAOT; WPF +
  core Rust estático queda como fallback Pareto. Modelos, voz, visión, providers
  restantes y el lifecycle productivo del Setup todavía deben competir o
  validarse; la memoria local explícita ya tiene una slice, pero no su uso
  integral en el resto del producto.
- Los diez cortes productivos ya materializan esa base: protocolo JSONL local
  `baxy.local.v1`, `app.status`, `app.open` acotado a Bloc de notas, notas
  `create/read/list/trash/restore`, `system.status` local de solo lectura
  —incluidos identidad y uso puntual de GPU— y
  control absoluto de volumen/mute de la salida predeterminada, más once
  operaciones explícitas de memoria privada. El catálogo del core contiene 22
  operaciones y la GUI exige 21 capacidades interactivas; `app.status`
  permanece como salud interna. La entrada natural enruta frases acotadas
  ES/EN/spanglish para esas slices; no es conversación general ni composición
  libre.
- Las notas usan JSON con SHA-256, reemplazo atómico y backup, sin cifrado ni
  MAC. El journal global encadena HMAC-SHA-256 con una clave dedicada envuelta
  por DPAPI y falla cerrado ante ausencia, truncado, rollback o tamper; los
  payloads privados `memory.*` además son envelopes cifrados y autenticados.
- En aquel corte, la validación aprobó 1.270/1.270 pruebas .NET —Contracts 37, Kernel
  44, Setup 61, Providers 232 e integración 896— y 110/110 pruebas Python:
  1.380 pruebas
  principales. Un E2E automatizado real
  completó ViewModel→core→store para create/read/trash/list/restore/list; otro consultó
  CPU+RAM, disco, batería y Windows por ViewModel→core→Win32. Ambos terminaron
  sin JSON visible y con outbox vacío. La captura histórica de la app publicada
  después del sexto corte,
  980×680, registra `core_ready`, `mission_completed`, una nota, cero procesos
  residuales y el outbox vacío tras el terminal. En ese mismo checkpoint se
  reconstruyó el directorio local: 14 archivos/54.831.324 bytes y manifiesto
  SHA-256 `4c0378c01ffd67d6949f90f1c0f2f611300cea2450e32ef1ac5756d36fb3553a`.
  Sus 14/14 entradas y el hello de diez capacidades fueron verificados. Ese
  paquete histórico no contiene los cortes séptimo ni octavo. Sigue siendo un
  directorio de desarrollo, no un instalador firmado ni una prueba de Windows limpio, y
  ningún Must adicional se considera cerrado por estos cortes. El progreso
  permanece en 5/15 Must (33,3 %).
- El oráculo curado de creación de nota standalone contiene 40 mensajes únicos,
  13 literales y 49 ocurrencias: 40/40 enrutan. No representa toda la familia
  `note.manage`. La selección por título normaliza Form C; ante duplicados, una
  shortlist durable permite elegir por número/ordinal ES/EN/spanglish sin
  mostrar UUID ni JSON. La ruta queda enlazada a UUID, título, revisión y estado
  antes del envío, y un candidato obsoleto falla sin contenido ni efecto. Las
  auditorías de los cortes tercero a octavo no dejaron P0/P1; la slice GPU no
  dejó tampoco P2 abiertos.
- El oráculo curado del quinto corte de estado local contiene 113 IDs de producto
  —50 literales,
  una misión y nueve rutas `source`— y enruta 113/113. Es un subconjunto: el
  corpus registra 306 filas globales `system.status` —294 product/12 trace; 279
  product `user_mission`—. Resumen genérico, `os` standalone y spanglish solo
  tienen contratos sintéticos, no cobertura histórica. Ese provider legado
  mide CPU, RAM, disco del sistema, batería, Windows y uptime; el octavo corte
  añade GPU mediante un provider separado sin alterar el summary. No se exponen
  procesos, IP, hostname ni usuario. El red-team del quinto corte terminó con
  cero P0/P1 tras cerrar batería all-unknown y Windows 11/Server. Un NativeAOT
  temporal de 4.857.856 bytes aprobó 2/2 requests reales y fue eliminado; no es
  el distribuible ni un instalador.
- El oráculo curado de audio contiene 171 IDs de producto —139 de volumen, 16
  de mute/unmute y 16 de consulta—, 120 literales, tres misiones y 14 rutas
  `source`; enruta 171/171. Solo admite volumen absoluto, nueve alias nominales
  congelados, mute explícito y consulta read-only del endpoint
  `eRender/eMultimedia` predeterminado. El corpus conserva 529 filas únicas
  relacionadas con audio y las tres misiones standalone reúnen 335 mensajes,
  por lo que este subconjunto no cierra la familia completa.
- El provider de audio persiste intención y receipt, liga el hash del endpoint,
  preserva la dimensión no solicitada y nunca repite el setter al reconciliar.
  `audio.status` reutiliza la postlectura y el lock global, pero no ejecuta un
  setter ni crea estado durable.
  `reconciled` es observación, no causalidad ni exactly-once. El estado pendiente
  conserva mission/invocation en core, journal, outbox y GUI. El store falla
  cerrado a 16.384 registros o 64 MiB; no poda evidencia incierta.
- Un gate físico NativeAOT pasó volumen, mute, replay sin segundo efecto y
  restauración exacta en un endpoint real: baseline scalar 0,98/98 %/mute false,
  request 88, mute true y restore al baseline. El primer intento quedó
  fail-closed por una carrera del arnés, fue recuperado y el rerun aprobó; el
  historial completo está en `artifacts/product/audio_control_gate.json`. El
  gate acredita estado de control, no sonido audible ni diversidad de hardware.
- El oráculo de memoria explícita congela 100 IDs positivos —60 literales—,
  cinco casos de corrección y 34 negativos duros. La memoria nace deshabilitada
  y sus once operaciones cubren habilitar, guardar, corregir, consultar, listar,
  olvidar, limpiar sesión y exportar; las fronteras sensibles o destructivas
  exigen confirmación. Gate 10 quedó aprobado en el techo determinista v3 tras
  405/405 pruebas focalizadas y cero P0/P1. Personalizar notas, apertura de apps,
  audio o estado corresponde a la futura capa de IA de Fable.
- Los argumentos privados y resultados privados exitosos de `memory.*` viajan
  cifrados y autenticados. Challenge/control quedan fuera del envelope y el
  bearer token permanece RAM-only, redactado y sin persistir; fallos genéricos y
  metadatos permanecen en claro. El store usa AES-256-GCM con clave envuelta por DPAPI `CurrentUser`
  bajo un hijo directo protegido de `%LOCALAPPDATA%\BAXY`; la exportación redacta
  el contenido sensible/secreto, nunca expone sus valores originales y revalida
  el artefacto antes de aceptar replay. `Documentos\BAXY` puede estar
  redirigido o sincronizado y la exportación es menos privada que el store. La
  auditoría del diff/frontera de memoria cerró sin P0/P1; queda un P2 teórico
  sobre semántica NTFS sensible a mayúsculas que requiere una precondición
  especial o elevada.
- Según la ejecución registrada, un publish NativeAOT temporal del séptimo corte
  produjo un core de 6.252.544 bytes, SHA-256
  `D32423255E93C51FDDDAA79E3A92C39C7F0D59D21D81A5F3C760CCA93F3A7EF7`,
  y corroboró 21 capacidades, las once de memoria, DPAPI real y la frontera de
  confirmación. Se eliminaron helper/raíz temporal; el output ignorado permanece
  en `src/Baxy.Core/bin/.../native/baxy-core.exe`, sin artefacto versionado bajo
  `artifacts/product`. No reemplaza el paquete histórico, un instalador ni la
  validación en Windows limpio.
- El oráculo GPU del octavo corte congela 77 casos: 7 de identidad, 19 de uso,
  17 composiciones y 34 negativos duros. Los 26 positivos enrutan a
  `system.status` con scope `gpu_identity` o `gpu_usage`; composiciones y
  negativos fallan cerrados. Tras incorporar `audio.status`, el catálogo tiene
  22 operaciones totales y 21 interactivas; el summary legado no sondea ni
  incluye GPU.
- El provider GPU usa DXGI para identidad/capacidades y PDH para uso puntual,
  sin red, subprocess ni dependencia de fabricante. `nvidia-smi` es únicamente
  un alias natural: BAXY no ejecuta ni afirma haber usado esa herramienta. La
  salida conserva adaptadores repetidos y representa de forma explícita fallos
  globales o parciales por índice; no publica LUID, PID ni metadata interna.
- Una ejecución física **managed** anunció 21 operaciones y observó tres
  adaptadores, dos medidos y uno no disponible con fallo indexado; terminó con
  exit 0. También se publicó un core NativeAOT de 7.376.384 bytes, SHA-256
  `17b88aed29af5d4cc9dffb3931b73ce13791b304e4f1a7692d2f9eb588550fe9`.
  La compuerta reproducible `scripts/test_gpu_status.ps1` corroboró hello 21,
  identidad/uso verificados, tres adaptadores, dos medidos, uno no disponible,
  un `unsupported` indexado, cero fallos globales, warmup `malformed_json`,
  stderr vacío y exit 0. Su evidencia sanitizada usa schema
  `baxy-gpu-status-gate-v1` en `artifacts/product/gpu_status_gate.json`.
- El noveno corte convierte esa base en un paquete offline reproducible. Dos
  builds Release limpios desde snapshots Git aislados de `aac3e05` produjeron
  el mismo árbol de siete archivos/82.842.635 bytes; dos empaquetados produjeron
  el mismo ZIP Stored de nueve entradas/82.845.957 bytes, SHA-256
  `11971bc0501598009145506f815407ec42a7c8fde2e88996815c1d2eaf3e7ba9`.
  La primera réplica detectó timestamps PE variables del linker NativeAOT;
  `/Brepro` corrigió la causa y la repetición limpia completa pasó. El core del
  paquete aprobó el gate GPU y la GUI autocontenida completó una nota con el
  runtime externo deliberadamente ausente, cero procesos/datos temporales y
  Notepad 5472 preservado. La evidencia sanitizada está en
  `artifacts/product/product_package_gate.json`. Es reproducibilidad same-host,
  no instalador, firma, VM limpia ni autenticidad del editor; el estado sigue
  5/15 Must y B-005 permanece abierto.
- El décimo corte añade `Baxy.Setup.exe`: NativeAOT autocontenido con ZIP y
  atestación embebidos, raíz canónica por usuario, versiones inmutables,
  `current/current.previous`, journal y recovery. Dos cadenas de `5dad02a`
  produjeron ejecutables idénticos de 85.858.304 bytes, SHA-256
  `50b8b8d415a822efabfa8986f3ec10d8d20d940dd2feca84b97f547b65452c7a`,
  y cuatro ejecuciones físicas de verificación aprobaron. Evidencia:
  `artifacts/setup/setup_package_gate.json` y
  `20_DECIMO_CORTE_SETUP_REPRODUCIBLE.md`. El gate no instaló, no probó VM
  limpia ni integración/lifecycle Windows; 5/15 y B-005 siguen abiertos.
- La reconciliación de trash/restore tras una interrupción posterior al efecto
  se limita a revisión N+1/estado objetivo con binding de candidato. Falta un
  receipt causal schema v2 y no se afirma exactly-once.
- El gate físico directo de core/provider quedó `skipped` porque ya existía
  Bloc de notas; preservó esa instancia y no aprueba lanzamiento, replay,
  supervivencia al Job ni E2E GUI. La auditoría final de código no dejó P0/P1.
- La revisión semántica v3 preserva las 122.744 ocurrencias y las consolida en
  14.836 mensajes —12.036 de producto ES/EN/spanglish y 2.800 de traza—,
  reagrupados en 2.084 misiones. La v2 separó tres contratos por alcance y la
  v3 escinde 16 consultas read-only sin agregar historia. El catálogo derivado
  contiene 43 operaciones, `app.open` queda en 329 filas y 98 mensajes registran
  efectos denegados de forma explícita. Las reconstrucciones A/B coincidieron
  4/4 byte a byte y 37/37 pruebas de contrato del corpus aprobaron.
- El compromiso funcional de BAXY 1.0 es español, inglés y spanglish, incluidos
  code-switch y errores STT de esos idiomas. Las expresiones inequívocamente
  ajenas se conservan con procedencia solo como trazabilidad histórica; el campo
  `language` es heurístico y `other` no decide por sí solo ese estado.
- El corte acota a 1 MiB el JSONL en ambas direcciones, limita stderr y pagina
  `note.list` en el provider con 50 por defecto, máximo 100 y `offset`, sin
  devolver contenido. El store admite como máximo 512 notas. La GUI mantiene los
  identificadores de misión e invocación durante el retry. El outbox se
  persiste antes del envío, sobrevive al reinicio completo del shell y se vacía
  tras una respuesta terminal; cada entrada lleva un checksum SHA-256 canónico
  contra corrupción accidental. El contenedor general sigue en texto plano y
  sin HMAC; los argumentos `memory.*` que contiene sí viajan cifrados y
  autenticados. Se limita a 1 MiB y 128 entradas y falla cerrado ante corrupción
  o reparse.
- El journal tiene un tope duro de 64 MiB, compactación exacta y reservas de
  2 MiB reconstruidas tras reiniciar. La saturación se rechaza antes del efecto
  sin perder la identidad durable. Un fallo mutante inesperado queda incompleto
  y reintentable con el mismo ID. Un conflicto sobre `started` incompleto no
  mata el core; los timeout cortan disponibilidad falsa y el ciclo de vida del
  hijo se limpia aunque falle su asociación al Job de Windows.
- Los scripts validan cada ancestro, ADS y puntos reparse, y limitan la limpieza
  a handles de procesos propios. Una prueba hostil de junction preservó el
  centinela externo.
- El cutoff corregido liga 17 fuentes por commit, prefijo o hash; 14.836
  mensajes se enlazan a 2.084 misiones canónicas bajo el schema 2 y revisión
  semántica v3.
- La genealogía Carter→BAXY, 22 auditorías decisivas y 36 modos de fallo
  estructurales están trazados. Sus regresiones aún deben implementarse.
- El soak de 24 horas no está completado y queda para la última etapa.
- No existe validación física del perfil objetivo en una GPU real de 3 GiB, ni
  cobertura de temperatura, procesos o hardware GPU exhaustivo.
- No existe todavía un corpus guiado completo de voz real.
