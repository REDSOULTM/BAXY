# Matriz de criterios originales

Los 97 criterios se transcriben completos desde el cierre de los once prompts
01-09, incluidos 03B y 03C. Las casillas antiguas no se heredan como aprobadas.
Cada fila empieza PENDIENTE, tiene un owner de reparación y exige evidencia
actual antes de CUMPLIDO. C09 vuelve a verificar todas sobre el candidato final.

El número de línea y SHA-256 identifican la fuente inspeccionada en b2505da.
La copia conserva el texto; se unen saltos de línea de maquetación. Los criterios
con varias condiciones exigen todas, no sólo la primera.

Los hechos históricos (por ejemplo, el commit heredado del 01) se verifican por
procedencia; las capacidades y mediciones requieren ejecución actual. Los conteos
antiguos de tests no son una instrucción para borrar tests hasta igualarlos.
Publicación, cambios ajenos y las salidas por imposibilidad se interpretan según
el [contrato de campaña](01_CONTRATO_DE_CAMPANA.md).

No basta completar esta tabla de memoria: enlaza corrida, commit, runtime,
comando y oráculo en Evidencia. Los mínimos de casos frescos añadidos en los
Cxx son requisitos de esta campaña; no se atribuyen a los prompts antiguos.

## Condiciones transversales de esta campaña

Los Cxx conservan las instrucciones completas. Esta matriz no permite saltar
condiciones del cuerpo de un goal. Si se identifica otra condición explícita,
se añade con fuente y owner sin sustituir ni eliminar las existentes.

Estas diez filas añaden controles de la petición actual y explicitan compromisos
de Identidad o del cuerpo de los goals; no se presentan como casillas históricas.

| ID | Condición / fuente | Owner | Estado | Evidencia |
|---|---|---|---|---|
| X01 | Misma admisión, estado, ejecución y publicación para usuario y agente; sin ventana obligatoria. Petición actual y contrato de campaña. | C01 | PENDIENTE | — |
| X02 | Conductor con runtime real, entrada natural, oráculo externo y captura de final/silencio; ninguna decisión ni respuesta esperada inyectada. Petición actual. | C01 | PENDIENTE | — |
| X03 | Cuatro herencias del 01 y decisiones 09.5 conciliadas con código integrado; inventario no equivale a ejecución. [01, cuerpo](../01_HERENCIA.md). | C02 | CUMPLIDO | `f9391c1` + [INVENTARIO-2026-09-04.md](../../../artifacts/comprobaciones/C02/INVENTARIO-2026-09-04.md) |
| X04 | Memoria visible, editable y borrable, modelo local y sin salida de contenido privado, con datos de prueba. [Identidad](../../00_IDENTIDAD.md). | C06 | PENDIENTE | — |
| X05 | Cambiar de tema, cancelar, Nueva sesión y reiniciar conservan evidencia sin capturar objetivos nuevos; secuencias R04–R06/R12/R16. Auditoría y petición actual. | C05 | PENDIENTE | — |
| X06 | Primera señal p50 ≤1 s / p95 ≤2 s; acción simple completa p50 ≤2,5 s; máximo silencio ≤3 s. [08, objetivo](../08_PRIMERA_SENAL.md). | C07 | PENDIENTE | — |
| X07 | Calibración válida, FAR/FRR y sus límites, voces reales diversas, salida audible y controles accesibles; sin ALLOW_UNCALIBRATED como aprobación. Identidad y contrato de calibración. | C08 | PENDIENTE | — |
| X08 | Mismo candidato, runtime y estado controlado para la aceptación final; evidencia independiente, corpus reservado y cero filas omitidas como pass. Petición actual. | C09 | PENDIENTE | — |
| X09 | Casos R01–R16 y A01–A06 correctos, sin borrar fallos ni reset privado; campañas originales y regresiones afectadas revalidadas. Petición actual. | C09 | PENDIENTE | — |
| X10 | Todos los prompts/cierres preparados y ejecutados con Grok 4.6 High, ventana 500K, estado persistido; contexto agotado no equivale a cumplimiento. Petición actual. | C09 | PENDIENTE | — |

## G01

Fuente: [01_HERENCIA.md](../01_HERENCIA.md), cierre desde línea 332.
SHA-256: `50db76ca77e8106f129e736bc37ee8a0d686da9f2f1e11ff201c611482d820e4`.

| ID / línea | Criterio original completo | Owner | Estado | Evidencia |
|---|---|---|---|---|
| G01.01 / 336 | Un mapa que dice **qué intentos hubo**, qué se propuso cada uno, y por qué se abandonó. | C02 | CUMPLIDO | [INVENTARIO.md](../../../artifacts/comprobaciones/C02/INVENTARIO.md); `00_MAPA.md` §1 |
| G01.02 / 338 | Para cada intento, **qué funciona hoy**, comprobado ejecutándolo — no leído. | C02 | CUMPLIDO | Runtime 2026-09-04; [RUNTIME-2026-09-04.md](../../../artifacts/comprobaciones/C02/RUNTIME-2026-09-04.md); [LAUNCH-2026-09-04.md](../../../artifacts/comprobaciones/C02/LAUNCH-2026-09-04.md) |
| G01.03 / 339 | **Qué se hereda**, de dónde, y qué hace falta para traerlo. | C02 | CUMPLIDO | INVENTARIO G01.03; 09.5.9 `conservar_actual` |
| G01.04 / 340 | **Qué no se hereda y por qué.** Un rechazo con el mecanismo entendido vale tanto como una herencia. | C02 | CUMPLIDO | INVENTARIO G01.04; rechazos 09.5.9 |
| G01.05 / 342 | Las **cuatro herencias obligatorias** resueltas: existe / no existe / existía a medias, con evidencia en cada caso. | C02 | CUMPLIDO | [INVENTARIO-2026-09-04.md](../../../artifacts/comprobaciones/C02/INVENTARIO-2026-09-04.md) G01.05 |
| G01.06 / 344 | El inventario de **preguntas ya respondidas y dónde**, separando lo vigente de lo caducado. | C02 | CUMPLIDO | INVENTARIO G01.06; `00_MAPA.md` §7 |
| G01.07 / 346 | Las **soluciones al problema de comprensión** que hay en los cuatro repositorios, listadas y comparables — el goal 03 arranca de ahí y no de cero. | C02 | CUMPLIDO | INVENTARIO G01.07; `00_MAPA.md` §6 |
| G01.08 / 348 | La lista, fichero por fichero, de los **adaptadores por aplicación** que hay que sustituir por capacidad genérica. | C02 | CUMPLIDO | `D_ADAPTADORES_POR_APP.md`; Goal 07 sustituye |
| G01.09 / 350 | `MainWindowViewModel` descompuesto y `MissionEngine` con un solo constructor, con la compuerta .NET verde después: 3.865 pruebas, 0 advertencias. | C02 | CUMPLIDO | `MindPlanSession`+`MemoryTurnSession`; 1 constructor; Full 2026-09-04 4025 .NET / 0 warn. 3865 y 3996 son históricos. |
| G01.10 / 352 | **Publicado.** `git status --short` vacío y `git rev-list --count origin/main..main` en **0**: todo lo del goal está en `origin/main`. Un goal con el trabajo sólo en este PC no está cerrado, por verdes que estén los demás criterios. | C02 | CUMPLIDO | Revalidación 2026-09-04 en `origin/main`. WIP C03 ajeno no cuenta. [PANEL-2026-09-04.md](../../../artifacts/comprobaciones/C02/PANEL-2026-09-04.md) |

## G02

Fuente: [02_BASE.md](../02_BASE.md), cierre desde línea 302.
SHA-256: `031e311f6c96590948398045ee845f84e344662feccda613806332c57ef9c0d4`.

| ID / línea | Criterio original completo | Owner | Estado | Evidencia |
|---|---|---|---|---|
| G02.01 / 304 | El trabajo del goal 01 comprometido en su propio commit, antes del tuyo. | C02 | CUMPLIDO | `7092c1a` (goal 01) ≺ `605e486` (C02) |
| G02.02 / 305 | El sello de `Baxy.FieldUi` cuadra, **con la decisión escrita** de qué árbol es el correcto y por qué — no con la constante subida a lo que había. | C02 | CUMPLIDO | `ORIGIN.md` 10.2.5; constante `0F6DCDA5…`; test FieldSource |
| G02.03 / 307 | La compuerta pasa **entera** dos veces seguidas sobre un árbol congelado. | C02 | CUMPLIDO | [FULL-2026-09-04.md](../../../artifacts/comprobaciones/C02/FULL-2026-09-04.md) ×2 sobre `f9391c1` |
| G02.04 / 308 | Pasa una tercera vez sobre un **clon limpio** del repositorio. | C02 | CUMPLIDO | worktree `f9391c1`; pnpm --frozen-lockfile; `dotnet restore`; [FULL-2026-09-04.md](../../../artifacts/comprobaciones/C02/FULL-2026-09-04.md) |
| G02.05 / 309 | Los fallos por entorno se distinguen de las regresiones: una máquina sin el `.venv` del spike no cuenta nueve regresiones falsas. | C02 | CUMPLIDO | 2026-09-04 clon 11 skip env vs 3 en desarrollo; 0 fail |
| G02.06 / 311 | Ningún rojo se cerró con `skip`, `xfail`, umbral relajado ni fallback. | C02 | CUMPLIDO | G02_09.md; STT intermitente pasó sin bajar umbral |
| G02.07 / 312 | El artefacto .NET dependiente del estado local ya no lo es, o está declarado con su causa. | C02 | CUMPLIDO | skip Integration opt-in declarado; no hay artefacto nuevo atado a esta máquina |
| G02.08 / 314 | El manifiesto de runtime está **versionado**, y un binario distinto del declarado pone la compuerta en rojo. | C02 | CUMPLIDO | schema v1; tests hash GGUF/llama; `IsForeignBaxyWorktree` |
| G02.09 / 316 | Registro de qué cambiaste y por qué, prueba por prueba. | C02 | CUMPLIDO | [G02_09.md](../../../artifacts/comprobaciones/C02/G02_09.md) |
| G02.10 / 317 | **Publicado.** `git status --short` vacío y `git rev-list --count origin/main..main` en **0**: todo lo del goal está en `origin/main`. Un goal con el trabajo sólo en este PC no está cerrado, por verdes que estén los demás criterios. | C02 | CUMPLIDO | Revalidación 2026-09-04 en `origin/main`. WIP C03 ajeno no cuenta. [PANEL-2026-09-04.md](../../../artifacts/comprobaciones/C02/PANEL-2026-09-04.md) |

## G03

Fuente: [03_COMPRENSION.md](../03_COMPRENSION.md), cierre desde línea 430.
SHA-256: `8743a3fa67f57fb38c245dbf285db2b6223bebdc866949076d09ffea7a5ff5fe`.

| ID / línea | Criterio original completo | Owner | Estado | Evidencia |
|---|---|---|---|---|
| G03.01 / 432 | ≥ 90 % sobre paráfrasis frescas, con la tasa **partida por causa**. | C06 | PENDIENTE | — |
| G03.02 / 433 | **La latencia hasta la primera señal, medida junto al acierto.** Un decisor que acierta y tarda nueve segundos no cierra este goal. | C07 | PENDIENTE | — |
| G03.03 / 435 | El pass-rate end-to-end publicado **antes y después** de tocar el catálogo — ahí es donde consolidar hizo daño la última vez (75,93 % → 62,96 %), y no en la recuperación. | C06 | PENDIENTE | — |
| G03.04 / 438 | Las peticiones fuera de catálogo llegan a la decisión con **cero candidatos**. | C06 | PENDIENTE | — |
| G03.05 / 439 | **Cobertura y cuenta publicadas juntas**, con la cobertura medida antes y después: no bajó. | C06 | PENDIENTE | — |
| G03.06 / 441 | El número y la forma del catálogo **justificados midiendo**, no eligiendo. | C06 | PENDIENTE | — |
| G03.07 / 442 | El acierto de argumentos medido aparte, para que la ganancia no se haya mudado de sitio. | C06 | PENDIENTE | — |
| G03.08 / 444 | Los tres ceros intactos. | C03 | CUMPLIDO | [CIEN.md](../../../artifacts/comprobaciones/C03/CIEN.md) cien-11: sin efectos no pedidos, sin taxi afirmado, sin 14:30; C06 pregunta, no ejecuta |
| G03.09 / 445 | Publicado **qué heredaste y de dónde** — y sólo si no heredaste nada, por qué ninguna de las soluciones anteriores servía. | C06 | PENDIENTE | — |
| G03.10 / 447 | El LLM decisor sigue **detrás de la frontera de proceso** y declarado en el manifiesto con su hash: cambiarlo mañana no debe recompilar nada. | C06 | PENDIENTE | — |
| G03.11 / 449 | Rellenas las filas de `03_COSTURAS.md` que te tocan —LLM decisor, runtime, recuperador, reconocedor, forma del catálogo— con la medición que decide un sustituto. | C06 | PENDIENTE | — |
| G03.12 / 452 | **Publicado.** `git status --short` vacío y `git rev-list --count origin/main..main` en **0**: todo lo del goal está en `origin/main`. Un goal con el trabajo sólo en este PC no está cerrado, por verdes que estén los demás criterios. | C06 | PENDIENTE | — |

## G03B

Fuente: [03B_COMPRENSION_TECHO.md](../03B_COMPRENSION_TECHO.md), cierre desde línea 273.
SHA-256: `2306665f3a7087569c07a189cb8f400fcc54ae4d8ceccea6ebc537181c44ac39`.

| ID / línea | Criterio original completo | Owner | Estado | Evidencia |
|---|---|---|---|---|
| G03B.01 / 275 | **≥ 90 %** sobre el corpus del goal 03, mismos bytes, partido por causa. | C06 | PENDIENTE | — |
| G03B.02 / 276 | **El techo re-medido y movido**, con la aritmética publicada igual que la del goal 03: cuánto pierde cada tramo y cuál es su límite ahora. | C06 | PENDIENTE | — |
| G03B.03 / 278 | Las **17 filas del contrato** resueltas: BAXY deja de decir «no puedo» sobre lo que sabe hacer, con el estado de conversación nuevo y su prueba. | C06 | PENDIENTE | — |
| G03B.04 / 280 | **Cobertura y cuenta antes y después**, con el sello del libro: no bajó. | C06 | PENDIENTE | — |
| G03B.05 / 281 | **El banco de misiones compuestas medido antes y después: no bajó.** Si bajó, el cambio de catálogo se acotó hasta que dejó de bajar, y está dicho cuánto se cedió. | C05 | PENDIENTE | — |
| G03B.06 / 284 | La **puerta curada más pequeña que antes**, o retirada, con el sobreveto medido en los dos casos. | C06 | PENDIENTE | — |
| G03B.07 / 286 | **Latencia junto al acierto**, p50 y p90, con el equipo cargado y tranquilo. | C07 | PENDIENTE | — |
| G03B.08 / 287 | Los **tres ceros intactos**, y las decisiones que habrían ejecutado un efecto no pedido en 3–5 de 36 o menos. | C06 | PENDIENTE | — |
| G03B.09 / 289 | Publicado **qué heredaste de la biblioteca y qué del estado del arte**, con la fuente. Y lo que probaste y no funcionó, con su mecanismo. | C06 | PENDIENTE | — |
| G03B.10 / 291 | Las filas de `03_COSTURAS.md` que toques, rellenas. | C06 | PENDIENTE | — |
| G03B.11 / 292 | **Publicado.** `git status --short` vacío y `git rev-list --count origin/main..main` en **0**: todo lo del goal está en `origin/main`. Un goal con el trabajo sólo en este PC no está cerrado, por verdes que estén los demás criterios. | C06 | PENDIENTE | — |

## G03C

Fuente: [03C_ALCANCE.md](../03C_ALCANCE.md), cierre desde línea 280.
SHA-256: `4b842d107451164d257bdc8a9c9e54982bfd0ef95aa603e5995f86faf8c57989`.

| ID / línea | Criterio original completo | Owner | Estado | Evidencia |
|---|---|---|---|---|
| G03C.01 / 285 | **≤ 5 de 36 `acted`** fuera de catálogo, misma función que `run_goal03_comprehension.py`, en **tres** corridas. Las 9 estables de arriba no pueden seguir `acted`. | C06 | PENDIENTE | — |
| G03C.02 / 288 | **Mediana ≥ 112/124** en esas mismas tres corridas, mismos bytes, partido por causa. Si sube, mejor; si baja de 112, no has cerrado. | C06 | PENDIENTE | — |
| G03C.03 / 290 | Las 6 filas in-catalog estables de arriba, servidas o con diagnóstico medido de por qué no, **sin** haberlas empujado al 04. Las intermitentes no pueden ser las que tumben la mediana. | C06 | PENDIENTE | — |
| G03C.04 / 293 | Cobertura 169/158/31 sello `dc0a7893…` antes y después. | C06 | PENDIENTE | — |
| G03C.05 / 294 | Banco compuesto ≥ 6/15 misiones y ≥ 15/32 pasos. | C05 | PENDIENTE | — |
| G03C.06 / 295 | Pico VRAM ≤ 4 GB durante un turno con el modelo cargado, medido. | C07 | PENDIENTE | — |
| G03C.07 / 296 | Sobrecarga frente a inferencia pura (mismo prompt/modelo/tokens), desglosada: el Δ de 17 ms de la capa LLM sigue siendo la referencia; si añades una etapa, dice qué compra. | C07 | PENDIENTE | — |
| G03C.08 / 299 | Listón de silencio 3 s (p50 del turno). Hoy 1,50–1,60 s. | C07 | PENDIENTE | — |
| G03C.09 / 300 | Tres ceros intactos. | C03 | CUMPLIDO | Misma muestra [CIEN.md](../../../artifacts/comprobaciones/C03/CIEN.md) cien-11 |
| G03C.10 / 301 | `03_COSTURAS.md` con las filas que toques. | C06 | PENDIENTE | — |
| G03C.11 / 302 | `documentacion/base/03C_ALCANCE.md` con las cifras, y `documentacion/base/03B_COMPRENSION_TECHO.md` §12 actualizado para que no mienta. | C06 | PENDIENTE | — |
| G03C.12 / 305 | **Publicado.** `git status --short` vacío y `git rev-list --count origin/main..main` en **0**: todo lo del goal está en `origin/main`. Un goal con el trabajo sólo en este PC no está cerrado, por verdes que estén los demás criterios. | C06 | PENDIENTE | — |

## G04

Fuente: [04_HONESTIDAD.md](../04_HONESTIDAD.md), cierre desde línea 299.
SHA-256: `c20d609655c58c1a031395b8faf44012b89015e50b9459c5a57a344192eeceff`.

| ID / línea | Criterio original completo | Owner | Estado | Evidencia |
|---|---|---|---|---|
| G04.01 / 301 | Los tres ceros, sobre población abierta, con el texto visible **auditado a mano**. | C03 | CUMPLIDO | [CIEN.md](../../../artifacts/comprobaciones/C03/CIEN.md); `cien-11/finals.txt` leído turno a turno |
| G04.02 / 303 | La autocorrección funciona: una afirmación desmentida por la verificación se corrige sola, y hay una traza que lo demuestra. | C03 | CUMPLIDO | `Goal06VisibleVoiceTests` polaridad invertida; compose reintenta los mismos hechos utc+offset (`PlannerAppBoundaryTests`) |
| G04.03 / 305 | Los dos modos funcionan, y el *bypass* no relaja ni el cero de efectos no pedidos ni el de éxitos no verificados. | C04 | PENDIENTE | — |
| G04.04 / 307 | La puerta de dominio ya no rechaza operaciones correctas por ausencia de lista — o está retirada y sustituida por algo que no herede el defecto. | C06 | PENDIENTE | — |
| G04.05 / 309 | Ninguna capa nueva sin retirar la que sustituye. | C03 | CUMPLIDO | Retirado `CreateRecoveryDraft` / `composition_lost_verified_facts`; reintento de los mismos hechos. [HERENCIA.md](../../../artifacts/comprobaciones/C03/HERENCIA.md) |
| G04.06 / 310 | **Publicado.** `git status --short` vacío y `git rev-list --count origin/main..main` en **0**: todo lo del goal está en `origin/main`. Un goal con el trabajo sólo en este PC no está cerrado, por verdes que estén los demás criterios. | C03 | CUMPLIDO | `c1ebb79` en `origin/main` |


## G05

Fuente: [05_EJECUCION.md](../05_EJECUCION.md), cierre desde línea 265.
SHA-256: `3b5d659ba7382208c8d40b9f56e190663b380a55a83772ccc53c727a64d5c969`.

| ID / línea | Criterio original completo | Owner | Estado | Evidencia |
|---|---|---|---|---|
| G05.01 / 267 | La matriz de operaciones con su verificación, **ejecutada de verdad** en esta máquina. | C04 | PENDIENTE | — |
| G05.02 / 269 | Ningún resultado se declara con el código de retorno del ejecutor. | C04 | PENDIENTE | — |
| G05.03 / 270 | Los estados terminales honestos funcionan: `pending` sólo reintentable, y el efecto ambiguo no reintentable acaba en `failed` con `effectMayHaveOccurred`. | C04 | PENDIENTE | — |
| G05.04 / 272 | Un provider que miente no consigue que BAXY mienta. Pruébalo provocándolo. | C04 | PENDIENTE | — |
| G05.05 / 273 | Las operaciones que **no se pueden verificar** están listadas con su razón. | C04 | PENDIENTE | — |
| G05.06 / 274 | Cero marcos de verificación genéricos: comprobaciones directas. | C04 | PENDIENTE | — |
| G05.07 / 275 | **Publicado.** `git status --short` vacío y `git rev-list --count origin/main..main` en **0**: todo lo del goal está en `origin/main`. Un goal con el trabajo sólo en este PC no está cerrado, por verdes que estén los demás criterios. | C04 | PENDIENTE | — |

## G06

Fuente: [06_VOZ_DEL_PRODUCTO.md](../06_VOZ_DEL_PRODUCTO.md), cierre desde línea 294.
SHA-256: `3fc2e9c96110e204f6a5fae55f9f2b75ee095dfa6f510b1eb3bb60cfd2aae1b0`.

| ID / línea | Criterio original completo | Owner | Estado | Evidencia |
|---|---|---|---|---|
| G06.01 / 296 | Cien respuestas seguidas leídas a mano y ninguna suena a máquina rellenando un hueco. | C03 | PENDIENTE | [CIEN.md](../../../artifacts/comprobaciones/C03/CIEN.md) cien-11: rúbrica de hechos/palabras/plantillas en cero; aclaraciones C06 («¿Quieres que…?») siguen sonando a producto desviado — owner C06 |
| G06.02 / 298 | Cero palabras inventadas en la muestra, con la causa resuelta —modelo, cuantización o comprobación— y la decisión justificada midiendo. | C03 | CUMPLIDO | cien-11: 0 talcr/vme/llamarar/comprobo/nochesos/readver. Causa: contrato utc+offset + comprobación, no cambio de Q. [HERENCIA.md](../../../artifacts/comprobaciones/C03/HERENCIA.md) |
| G06.03 / 300 | Cero constantes en pantalla, incluidos los caminos feos y el degradado. | C03 | CUMPLIDO | `Sigo con {snippet}` fuera de producción; welcome/progreso por compose; `composition_failed` SYSTEM sin dump (R07) |
| G06.04 / 301 | La narración de accesibilidad sale por la misma ruta de prosa, sin subsistema propio. | C08 | PENDIENTE | — |
| G06.05 / 303 | La personalidad está en el prompt y se puede cambiar editando un texto. | C03 | CUMPLIDO | `USER_MESSAGE_PROMPT` en `src/baxy_mind/llm.py`; seguridad en otro bloque |
| G06.06 / 304 | **Publicado.** `git status --short` vacío y `git rev-list --count origin/main..main` en **0**: todo lo del goal está en `origin/main`. Un goal con el trabajo sólo en este PC no está cerrado, por verdes que estén los demás criterios. | C03 | CUMPLIDO | `c1ebb79` en `origin/main` |

## G07

Fuente: [07_MISIONES.md](../07_MISIONES.md), cierre desde línea 274.
SHA-256: `43207bd56968a97192b6dc71bc598af80c0c0ff3337509e70168e03a4f90c415`.

| ID / línea | Criterio original completo | Owner | Estado | Evidencia |
|---|---|---|---|---|
| G07.01 / 276 | ≥ 90 % de misiones completas y verificadas sobre misiones frescas, con **cada paso** verificado — no sólo el resultado final. | C05 | PENDIENTE | — |
| G07.02 / 278 | Cero pasos huérfanos: sin ejecutar, sin verificar, o ejecutados fuera del plan. | C05 | PENDIENTE | — |
| G07.03 / 279 | «Abre Steam y ve a la biblioteca» funciona sobre Steam de verdad, en esta máquina. | C05 | PENDIENTE | — |
| G07.04 / 281 | La cascada UIA → OCR → visión funciona sin una sola app codificada a mano. | C05 | PENDIENTE | — |
| G07.05 / 282 | Ninguna misión pasa más de 3 s sin salida visible. | C07 | PENDIENTE | — |
| G07.06 / 283 | Los tres ceros intactos durante toda la misión. | C05 | PENDIENTE | — |
| G07.07 / 284 | **Publicado.** `git status --short` vacío y `git rev-list --count origin/main..main` en **0**: todo lo del goal está en `origin/main`. Un goal con el trabajo sólo en este PC no está cerrado, por verdes que estén los demás criterios. | C05 | PENDIENTE | — |

## G08

Fuente: [08_PRIMERA_SENAL.md](../08_PRIMERA_SENAL.md), cierre desde línea 297.
SHA-256: `7d508070c1e09d2905815cc89098d5aca063fdb67875adb381c98f36ab2e86e0`.

| ID / línea | Criterio original completo | Owner | Estado | Evidencia |
|---|---|---|---|---|
| G08.01 / 299 | Los números, sobre población que incluya lo difícil, con el perfil CPU aparte. | C07 | PENDIENTE | — |
| G08.02 / 300 | **Ninguna tarea, de ninguna duración, pasa 3 s en silencio.** | C07 | PENDIENTE | — |
| G08.03 / 301 | La señal temprana es condicional —sólo cuando se prevé tardar— y es prosa formulada, no una constante. | C07 | PENDIENTE | — |
| G08.04 / 303 | Ninguna señal temprana afirma un resultado, y la autocorrección funciona cuando la verificación desmiente. | C07 | PENDIENTE | — |
| G08.05 / 305 | Publicado cuántas llamadas por modelo quedan por turno y por qué cada una sigue ahí. | C07 | PENDIENTE | — |
| G08.06 / 307 | Sin regresión en exactitud ni en los tres ceros. | C07 | PENDIENTE | — |
| G08.07 / 308 | **Publicado.** `git status --short` vacío y `git rev-list --count origin/main..main` en **0**: todo lo del goal está en `origin/main`. Un goal con el trabajo sólo en este PC no está cerrado, por verdes que estén los demás criterios. | C07 | PENDIENTE | — |

## G09

Fuente: [09_VOZ_Y_OIDO.md](../09_VOZ_Y_OIDO.md), cierre desde línea 332.
SHA-256: `859fd11704166476bf24060b91c1452f027ed748118cecb68b366f9ac65ae7d1`.

| ID / línea | Criterio original completo | Owner | Estado | Evidencia |
|---|---|---|---|---|
| G09.01 / 334 | Wake, transcripción y habla funcionando en esta máquina, medidos sobre voces diversas y audio real. | C08 | PENDIENTE | — |
| G09.02 / 336 | Las tres detrás de la frontera de proceso, declaradas en el manifiesto con su hash, y sus tres filas de `03_COSTURAS.md` rellenas. | C08 | PENDIENTE | — |
| G09.03 / 338 | Falsas activaciones medidas sobre horas de audio que no le hablan a BAXY. **Audio grabado sirve** —una película, un pódcast, una reunión—: es una medición por volumen de audio, no por horas de calendario delante del micrófono. | C08 | PENDIENTE | — |
| G09.04 / 341 | De fin de habla a primera señal, p50 ≤ 1,5 s, y nunca 3 s en silencio. | C08 | PENDIENTE | — |
| G09.05 / 342 | Se le puede interrumpir a media frase. | C08 | PENDIENTE | — |
| G09.06 / 343 | **Ninguna capacidad de BAXY exige ver la pantalla o usar el ratón.** | C08 | PENDIENTE | — |
| G09.07 / 344 | Publicado qué heredaste, de dónde, qué cambiaste — y qué descartaste porque el estado del arte lo dejó atrás. | C08 | PENDIENTE | — |
| G09.08 / 346 | Consumo en reposo medido, con la escucha permanente encendida. | C08 | PENDIENTE | — |
| G09.09 / 347 | **Publicado.** `git status --short` vacío y `git rev-list --count origin/main..main` en **0**: todo lo del goal está en `origin/main`. Un goal con el trabajo sólo en este PC no está cerrado, por verdes que estén los demás criterios. | C08 | PENDIENTE | — |
