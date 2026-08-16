# Bloqueantes

| ID | Bloqueante | Cierre requerido |
|---|---|---|
| B-004 | Producto nuevo incompleto | Expandir los cortes por ledger y cerrar su aceptación |
| B-005 | Lifecycle e instalación limpia incompletos | Instalación canónica, integración Windows, update/rollback/uninstall, checksum/firma y prueba limpia |
| B-006 | Acceptance física incompleta | Gates autorizados restantes con evidencia real |

Estos bloqueantes son estado de trabajo, no permiso para reducir el alcance.

Actualización 2026-07-16 (adaptadores externos): calendario Outlook/MAPI,
Office OOXML, navegador CDP, búsqueda web, captura, OCR y selección exacta de
Spotify y streaming pasaron **14/14** por el core real. El gate de hardware pasó impresión
y escaneo físicos y quedó **7 verificados/0 fallos/5 sin objetivo exacto**. El
planner histórico bajó de 53 errores seguros a cero: los casos incompletos se
convierten en aclaraciones concretas y los operables en planes acotados, sin
exponer memoria ni ejecutar tools durante la medición.

B-004 conserva únicamente fronteras honestas: `night_light` sin API pública,
compras Steam sin precio/propiedad/confirmación confiables y efectos que este
host no pudo probar porque no ofreció dispositivo Bluetooth emparejable,
brillo WMI, perfil Wi-Fi activo resoluble, juego poseído/no instalado o descarga
parcial. El lanzamiento Steam sí pasó físicamente con proceso postleído y
cleanup dirigido. B-005/B-006 conservan VM/perfil limpio, firma y diversidad física; no
se presentan las omisiones por falta de objetivo como éxitos.

Los diez cortes productivos reducen B-004, pero no lo cierran: hoy cubren
`app.status`, notas locales, `app.open` limitado a `windows.notepad`,
`system.status` read-only y volumen absoluto/mute explícito del endpoint de
salida predeterminado. La GUI natural crea/lista/lee/envía a papelera/restaura
notas, acepta órdenes permitidas de Bloc de notas, consulta CPU, RAM, disco del
sistema, batería, Windows e identidad/uso puntual de GPU, controla esa slice de
audio y ofrece memoria privada explícita bajo gramáticas finitas. Release aprobó
1.270/1.270 pruebas .NET y 110/110 pruebas Python —1.380 pruebas principales—,
pero aún
faltan los gates de aceptación restantes. El noveno corte produjo dos builds
limpios idénticos de siete archivos/82.842.635 bytes y dos ZIP Stored idénticos
de 82.845.957 bytes, SHA-256
`11971bc0501598009145506f815407ec42a7c8fde2e88996815c1d2eaf3e7ba9`.
El gate GPU del core distribuido y un smoke GUI autocontenido pasaron con cero
procesos/datos temporales; la evidencia está en
`artifacts/product/product_package_gate.json`. Esto cierra la incertidumbre
same-host del build y ZIP reproducibles para ese SDK y caches, pero el ZIP no
crea integración Windows ni acredita
instalación limpia, update, rollback o uninstall. Los first-party siguen sin
firma y `authenticity=not_provided`; por eso B-005 permanece abierto.

El décimo corte añadió `Baxy.Setup.exe`: dos NativeAOT de 85.858.304 bytes y
SHA-256 `50b8b8d4…2c7a` fueron idénticos y verificaron físicamente el mismo ZIP
embebido. El motor tiene versiones inmutables, punteros, journal y recovery,
pero el gate no ejecutó la instalación sobre `%LOCALAPPDATA%\Programs\BAXY`.
Tampoco existen todavía Inicio/registro de desinstalación, interfaz de usuario,
uninstall keep/purge, update y rollback compatible con datos ni prueba en VM
limpia. Por eso el nombre de B-005 cambia, pero el bloqueante sigue abierto.

El hardening de retry durable —persistido antes de enviar, recuperable tras
reiniciar el shell y eliminado tras el terminal— ahora incluye checksum SHA-256
canónico contra corrupción accidental. El contenedor del outbox general sigue
en texto plano y sin HMAC, limitado a 1 MiB y 128 entradas; los argumentos
`memory.*` dentro de él sí están cifrados y autenticados.

También reducen riesgo el journal limitado a 64 MiB con compactación exacta y
reservas de 2 MiB reconstruidas tras reiniciar; el rechazo por capacidad antes
del efecto sin perder la identidad; los límites JSONL bidireccionales y stderr
acotado; el store de máximo 512 notas con listado paginado sin contenido; y los
fallos mutantes inesperados que quedan incompletos y reintentables con el mismo
ID. Las correcciones de timeout, falsa disponibilidad y ciclo de vida del hijo,
junto con las defensas de ancestros, ADS/reparse y cleanup por handles propios,
no cierran B-004 ni acreditan la aceptación física completa. La prueba junction únicamente
demostró que se preservó el centinela fuera del destino autorizado.

`app.open` añade inventario/identidad/verificación independientes y replay
at-most-once por invocación; su auditoría final no dejó P0/P1. Sin embargo, el
gate físico directo core/provider quedó `skipped` por Notepad preexistente y
preservó esa instancia. No aprueba lanzamiento fresco, replay, supervivencia
al Job ni E2E GUI; B-006 permanece abierto.

El sexto corte congela 143/143 mensajes de audio —109 literales, 14 fuentes y
dos misiones— para volumen absoluto y mute explícito del endpoint
`eRender`/`eMultimedia`. El universo contiene 529 filas de audio y 397 filas de
producto clase `user_mission`; las dos misiones standalone reúnen 335 mensajes
—248 volumen y 87
mute—, así que quedan 192 mensajes de esas dos misiones standalone fuera de la
slice; además quedan composiciones.
No se implementaron control relativo, sesiones por aplicación, micrófono,
otros devices ni composición general; B-004 continúa abierto.

`artifacts/product/audio_control_gate.json` acredita en un equipo real el core
NativeAOT por JSONL: baseline 0,98/98 %/no silenciado, volumen 88 %, mute activo,
replay sin segundo efecto y restauración exacta. El primer intento conservó un
incidente fail-closed del harness y el baseline fue restaurado/verificado antes
de repetir. La evidencia mide estado del control, no sonido audible, y solo un
endpoint predeterminado; no atraviesa el parser WPF ni cubre otros
devices/sesiones/modo exclusivo. Reduce B-006, pero no lo cierra.

La recuperación de audio conserva el mismo `missionId`/`invocationId` cuando
queda una intención abierta y la reconciliación es deliberadamente
observacional, sin afirmar causalidad ni exactly-once. No hay rollback/reapply
automático ante incertidumbre. El store falla cerrado antes de otro efecto al
alcanzar 16.384 entradas o 64 MiB; ese cap sigue como P2 operativo y no cierra
B-004.

El séptimo corte congela 100/100 IDs positivos de memoria explícita —60
literales— y 34/34 negativos duros; además separa cinco casos de corrección. La
memoria nace deshabilitada, exige confirmación en las fronteras sensibles y
ofrece once operaciones de habilitación, guardado, corrección, consulta,
listado, olvido, limpieza de sesión y exportación. Sus argumentos privados y
resultados privados exitosos viajan cifrados y autenticados; challenge/control
quedan fuera del envelope y el bearer token permanece RAM-only, redactado y sin
persistir. Fallos genéricos y metadatos quedan en claro. El store queda bajo DPAPI `CurrentUser`
en un hijo directo protegido de `%LOCALAPPDATA%\BAXY`; la exportación redacta el
contenido sensible/secreto, nunca expone sus valores originales y se revalida
desde el artefacto antes de aceptar un replay. La auditoría del diff/frontera de
memoria no dejó P0/P1; permanece un P2 teórico sobre semántica NTFS sensible a
mayúsculas bajo una precondición especial o elevada. Según la ejecución
registrada, un NativeAOT temporal de 6.252.544 bytes, SHA-256
`D32423255E93C51FDDDAA79E3A92C39C7F0D59D21D81A5F3C760CCA93F3A7EF7`,
corroboró 21 capacidades, las once de memoria y la frontera de confirmación. Se
eliminaron helper/raíz temporal; el output ignorado permanece en
`src/Baxy.Core/bin/.../native/baxy-core.exe`, sin evidencia versionada bajo
`artifacts/product`. No es el paquete distribuible ni acredita Windows
limpio. Una revisión posterior añadió HMAC-SHA-256 al journal y Gate 10 aprobó
405/405 pruebas focalizadas con cero P0/P1. La personalización transversal y la
composición libre permanecían del lado Fable en ese corte. ADR-0006 implementa
ahora el planner general sin reabrir la memoria determinista: `memory.*` conserva
su parser/envelope privado y la composición privada-mixta sigue siendo una
frontera separada. El gate físico ampliado del planner continúa abierto.

La revisión semántica v2 cerró la errata derivada: conserva las 122.744
ocurrencias y las consolida en 14.836 mensajes —12.036 de producto y 2.800 de
traza—, genera 2.083 misiones y deja `app.open` en 329 filas con polaridad
explícita. Esa revisión sanea el ledger; por sí sola no implementa operaciones
ni providers. B-004 continúa
porque el oráculo curado de creación standalone —40 mensajes únicos, 13
literales y 49 ocurrencias— es solo una fracción de `note.manage` y del ledger
target. Las composiciones con recordatorios no dan falso éxito. Los títulos
duplicados ya tienen selección conversacional durable, ligada a
UUID/título/revisión/estado y sin exponer identificadores; esto reduce el riesgo
de actuar sobre la nota incorrecta, pero no agrega conversación general ni
cierra el resto del ledger.
B-005 continúa por el lifecycle e instalación limpia incompletos y B-006 por la
evidencia física restante.

El octavo corte congela 77 casos GPU: 7 de identidad, 19 de uso, 17
composiciones y 34 negativos duros. Los positivos usan los scopes
`gpu_identity`/`gpu_usage` de `system.status`; el summary legado permanece
aislado. DXGI+PDH operan localmente sin subprocess y `nvidia-smi` es solo un
alias natural, nunca una herramienta ejecutada o declarada. Una ejecución
física managed y la compuerta NativeAOT observaron tres adaptadores, dos medidos
y uno no disponible con `unsupported` indexado. `scripts/test_gpu_status.ps1`
verificó cero fallos globales, correlaciones, warmup `malformed_json`, stderr 0
y exit 0; la AOT mide 7.376.384 bytes y tiene
SHA-256 `17b88aed29af5d4cc9dffb3931b73ce13791b304e4f1a7692d2f9eb588550fe9`.
El resumen sanitizado `artifacts/product/gpu_status_gate.json` usa schema
`baxy-gpu-status-gate-v1` y estado `passed`.
Temperatura/procesos, monitoreo continuo, diversidad exhaustiva de hardware y
el perfil físico de 4 GB siguen fuera. Por eso reduce B-004/B-006 sin cerrarlos
y no modifica B-005.

El quinto corte congela 113/113 IDs de estado local —50 literales, una misión y
nueve rutas `source`—, pero son solo un subconjunto de 306 filas globales
`system.status` —294 product/12 trace; 279 product `user_mission`—. Resumen,
`os` standalone y spanglish históricos no están cubiertos. Tampoco se
implementaron en ese corte procesos, IP, hostname, usuario, otros discos o
composición general; GPU/VRAM se añadió después mediante la slice acotada del
octavo corte. B-004 continúa abierto.

El red-team del quinto corte no dejó P0/P1 tras cerrar batería all-unknown y
Windows 11/Server. El smoke NativeAOT temporal —4.857.856 bytes, 2/2 requests—
fue eliminado y no es distribuible, instalador ni aceptación en Windows limpio;
no cierra B-005 ni B-006.

El red-team del cuarto corte no dejó P0/P1 dentro de esa slice; no acredita el
producto completo. Trash/restore siguen reconciliando una interrupción
posterior al efecto mediante el caso estricto revisión N+1/estado objetivo, sin
un receipt causal schema v2 ni garantía exactly-once. Esa deuda tampoco cierra
B-004.

## Cerrados

| ID | Cierre | Evidencia |
|---|---|---|
| B-001 | Cutoff congelado por contenido | 17 fuentes, SHA-256 `85929373…b7eb3fbd`, Git-ignored ligados |
| B-002 | Mensajes y misiones extraídos | Schema v2: 14.836 mensajes, 2.083 misiones, mapeo exacto, A/B idénticos 4/4 y 36/36 pruebas de contrato del corpus |
| B-003 | Arquitectura elegida por torneo | T16 real, red fail-closed, 41/41, score 82,004484 vs 79,992351, ambos Pareto y `ADR-0001` aceptado |
