# Auditoría de preparación para Goal 10 — 2026-09-03

Árbol auditado: `b2505da`, rama `main`. Encargo: contrastar el progreso de
los goals 01–09 con la conducta real y determinar si procede Goal 10.
Auditoría, sin cambios de implementación. Al empezar ya existía sin rastrear
`tests/test_wakeword_runtime_resources.py`; no es trabajo de esta auditoría.

## Veredicto de producto

**No está acreditado que los goals 01–09 estén cumplidos de extremo a extremo
en el producto actual. No está listo para presentarse como asistente de uso
diario.** Hay avances verificables en componentes y corpus, pero se reprodujeron
fallos básicos desde la casilla pública de texto. Goal 10 puede continuar como
trabajo de corrección y certificación; no debe partir de «01–09 funcionan» ni
pasar por alto las regresiones de sus owners.

`git fetch origin` y `git merge --ff-only origin/main` confirmaron
`HEAD == origin/main == b2505da` durante esta auditoría. Ese era el último
commit disponible; no se hizo push de cambios de producto.

Los prompts están en [`sprints/00_INDICE.md`](sprints/00_INDICE.md), con el
pendiente actual en [`sprints/00_LANZAR_DESDE_10_7.md`](sprints/00_LANZAR_DESDE_10_7.md).
Los cierres históricos se encuentran en `documentacion/base/`,
`documentacion/herencia/` y el `HANDOFF.md` de cada goal en `artifacts/`.

**Compuerta Full actual: ROJA.** Estática y build Release aprobados;
.NET 3.978 pass / 0 fail / 1 skip; Python 8.788 pass / 4 fail / 3 skips.
Los cuatro fallos están clasificados al final. Dos fallos de sello se
reproducen en archivos versionados idénticos a HEAD; no dependen de los
documentos de esta auditoría ni de la prueba local sin rastrear.

## Cierres que declara el repositorio

- El índice y `artifacts/goal10/HANDOFF.md` declaran cerrados 10.0, 10.1,
  10.2 y 10.2.5. El siguiente es 10.7. Las familias funcionales y los 200
  turnos públicos de 10.18 todavía no están certificados.
- 03C: cierre histórico 114/124 mediana; revalidación 09.5.11A 113/124
  en las tres corridas, sobre el mismo corpus. Es medición del corpus,
  no una garantía de acierto general. Fuente: `base/03C_ALCANCE.md`.
- 05: 170 operaciones, 82 observadas, 88 no verificables con razón;
  se repite en 09.5.11B. El informe dice que no se arrancó `py main.py`.
  Fuente: `base/05_EJECUCION_VERIFICADA.md`.
- 09.5.11C: reutiliza el sello R6 para misiones y cifras históricas para
  latencia; no reabre Steam físico ni FAR; voz mediante WAV inyectado,
  no micrófono. Fuente: `herencia/09_5_11C_REVALIDAR.md`.
- 09: wake positivo 12 clips de voces sintéticas Sabina/Zira; STT tres
  clips sintéticos. FAR real 5 activaciones/2 h, umbral no aprobado y
  escucha habilitada con `BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED`.
  Fuentes: `artifacts/goal09/{HANDOFF.md,wake_holdout.json,stt_holdout.json}`.
- 10.2.5 reconoce que 10.2 medía sólo Baxy.exe, omitiendo el árbol de
  procesos; corrigió ONNX, refresco UI y bloqueo de turnos.
  Fuente: `artifacts/goal1025/HANDOFF.md`.

## Reproducción desde la interfaz pública

Arranque: `py main.py`, modelo registrado Qwen3-4B-Q4_K_M, Windows de esta
máquina. Entrada mediante teclado en `message input` y Enter; ninguna petición
de esta tabla se envió directamente a mente/Core/provider. El manifiesto
registrado confirma `python_path` en `BAXY Definitivo/src`, aunque el binario
auxiliar `llama_server` conserva una ruta dentro de la herencia BAXY.
Tras el primer arranque se habilitaron trazas locales para correlacionar los fallos.

| Petición | Resultado visible observado | Contraste independiente |
|---|---|---|
| `Hola, ¿qué puedes hacer?` | Aviso «Sigo con…»; volvió a habilitarse la entrada sin respuesta en activity. | Árbol de accesibilidad antes/después; este primer turno no tenía trazas internas. |
| `¿Qué hora es?` | `No pude: no pude encontrarlo.` | Decisor: `system.time`. Journal: `completed`, `verified=true`, hora real `2026-09-03T01:37:09.5472814+00:00`, offset −240. La respuesta visible contradice un resultado real correcto. |
| `Abre la calculadora` | `No pude: la composición se perdió y se verificaron hechos.` | Apareció la ventana Calculadora. Journal: `app.open`, `failed`, `verification_failed`, `effectMayHaveOccurred=true`. El efecto sí se observó, pero el ciclo verificación/narración falló. |
| `Cuéntame un chiste corto.` | `La aplicación está abierta y muestra el título "Nota: Informe de actividad".` | No hubo `decision.start` ni llamada a Core para este turno. Sólo recuperación pendiente y composición; el título no procede de una nueva observación. |
| `¿Tengo conexión a internet?` | `¿Tienes conexión a internet?` | No hubo decisión nueva ni lectura `network.status`; el plan anterior siguió interceptando el turno. |
| Tras **Nueva sesión**, `Dime la hora y el estado del audio.` | `Listo, audio está abierto.` | Historial visible vacío antes de enviar; ninguna decisión ni llamada a Core en ese turno. Nueva sesión no retiró la interacción pendiente. |

Son **seis peticiones con resultado insatisfactorio**, no una estimación
estadística de todos los usos: los tres últimos fallos están encadenados al
estado que dejó Calculadora. Precisamente ese encadenamiento es parte del
defecto que experimenta una persona.

También apareció una entrada `No me ve.` que esta auditoría no escribió.
La traza carece del Enter/bridge de texto correspondiente. Se apagó la escucha
para aislar los turnos posteriores; no se atribuye esa entrada a una causa
acústica concreta sin grabación independiente.

Un reinicio intermedio falló por crash del proceso WebView2, mostrado por la
propia ventana. El siguiente arrancó. Se registra como incidente observado,
sin presentarlo como fallo permanente ni causa demostrada de todos los demás.

Evidencia conservada:

- [`ui-turns.json`](../artifacts/audit/goals_01_10_20260903/ui-turns.json): peticiones, respuestas y árboles de accesibilidad.
- [`core-observations.json`](../artifacts/audit/goals_01_10_20260903/core-observations.json): registros de hora y Calculadora del journal, sin copiar otros datos del usuario.
- [`shell-trace.jsonl`](../artifacts/audit/goals_01_10_20260903/shell-trace.jsonl): etapas de la interfaz, composición y Core.
- [`turn-audit.jsonl`](../artifacts/audit/goals_01_10_20260903/turn-audit.jsonl): decisiones del sidecar; no hay decisiones nuevas para chiste/red/misión posterior.
- [`public-ui-final.png`](../artifacts/audit/goals_01_10_20260903/public-ui-final.png): respuesta falsa de la misión después de Nueva sesión.

## Causas y fronteras identificadas

### 1. Un resultado verificado se pierde al redactarlo — Goals 04/06

El caso de la hora demuestra la frontera: Core cumple y la publicación falla.
`ModelMessageComposer.cs:87,129–159` permite sustituir el resultado por un
nuevo borrador `composition_lost_verified_facts` cuando la prosa se rechaza.
La recuperación ya no conserva la hora original. La causa precisa del primer
rechazo no quedó en esta traza; no se inventa. Sí está probado que el usuario
recibe un fallo pese al `completed/verified` del journal.

La prueba de prosa no reprodujo el contrato real de la hora:
`scripts/goal06_voice_sample.py:166–167,207–209` fabrica
`observed.localTime = "09:05" / "22:10"`, mientras
`src/Baxy.Core/Operations/TimeStatusHandler.cs:21–25` entrega `utc` y
`localUtcOffsetMinutes`. Que esa muestra pase no acredita que la salida real
del provider llegue correctamente a pantalla.

Además, `PendingModelMessageQueue.cs:143–153` retira la respuesta después
de tres composiciones fallidas y liquida la presentación; su callback en
`MainWindowViewModel.cs:82` sólo actualiza un diagnóstico interno. Es un camino
de pérdida de respuesta. El primer saludo es compatible con ello, pero no se
atribuye a ese camino exacto sin su traza.

### 2. Un efecto incierto captura las siguientes peticiones — Goal 07

`MainWindowViewModel.cs:465–468` envía **todo** texto nuevo al plan pendiente
antes de volver a decidir su intención. `2421–2435` conserva el plan tras un
efecto ambiguo; `2516–2681` trata el texto como respuesta a recuperación.
Preservar la identidad del efecto es necesario, pero no exige apropiarse de
peticiones ajenas como un chiste o una consulta de red.

`StartNewUiSession`, en `1655–1668`, limpia mensajes y saluda; no separa ni
retira `_pendingMindPlan`. La reproducción después de Nueva sesión coincide
con ese código. El fallo de apertura, la captura de nuevos turnos y la mala
redacción se amplifican entre sí.

### 3. El verificador de apertura no certificó un efecto que sí ocurrió — Goal 05

Calculadora apareció en la lista de ventanas y en pantalla, antes de que la
auditoría devolviera el foco a BAXY. El journal registra fallo de verificación
y efecto incierto. No se confundió ese estado con éxito del provider.
Owner: `AppOpenHandler` y `Baxy.Providers.Windows/Applications/`. La rama exacta
del verificador que falló requiere una reproducción enfocada; no está demostrada
sólo por el mensaje `verification_failed`.

### 4. El cero de prosa fija tiene un punto ciego — Goals 06/08

`src/baxy_mind/first_signal.py:132–160` construye
`Sigo con {snippet}.` / `Still working on {snippet}.` mediante plantillas,
sin llamada a un modelo. `__main__.py:5570–5589` las envía como `turn.signal`
y `MainWindowViewModel.cs:1671–1685` las publica. Se vio el aviso en la prueba.
El censo `scripts/censo_voz_visible.py` devuelve 0 en este mismo árbol:
sus filtros léxicos y de archivos no equivalen a seguir todas las rutas de
texto publicable. El criterio del 06 incluye expresamente el progreso y
prohíbe las plantillas (`sprints/06_VOZ_DEL_PRODUCTO.md:275–284`). El propio
08 declara rechazado el acuse temprano de plantilla
(`sprints/08_PRIMERA_SENAL.md:263–264`).

### 5. Dos contradicciones vigentes de Identidad

- `ProductCatalog.cs:1719` convierte `RecoverableDelete` en reversible y
  `RiskPolicy.cs:32` lo autoriza sin confirmar. La discrepancia con confirmar
  borrados está reconocida en `APLAZADOS.md` desde Goal 04. No se borraron
  datos para comprobarla.
- `SubstratePanel.tsx:51–52` bloquea los modos `no_vidente` y `movilidad`.
  Ambos se vieron deshabilitados. La existencia de voz no certifica todos
  los modos ni el uso completo sin pantalla.

## Progreso por goal y alcance real de su cierre

| Goal | Avance acreditado por el repositorio | Evaluación actual |
|---|---|---|
| **01 — Herencia** | Mapa de cinco intentos, motores ejecutados y rechazos documentados; infraestructura heredada. | Aporta una base real. Es inventario y selección, no garantía del producto. Se aplazó parte de la descomposición del ViewModel; hoy tiene 3.407 líneas. `llama_server` aún depende del árbol BAXY anterior en esta máquina. |
| **02 — Base reproducible** | Dos Full históricos del árbol y otro del clon limpio: Python 8.511/8.511/8.503 pass; omisiones diferenciadas. | **El cierre no se mantiene hoy: Full rojo.** Dos tests versionados fallan de forma reproducible por un sello desactualizado tras modificar un script. Además, Full deja fuera el gate real mente-shell-Core y otros Explicit. |
| **03/03B/03C — Comprensión y alcance** | De ~46 % inicial a mediana 114/124 = 91,9 %; revalidación 113/124 = 91,1 %, 1/36 `acted`, mismo corpus. Catálogo 169/158/31 preservado. | Acredita esa población y esa frontera, con providers desactivados. No es 91 % de tareas terminadas ni cobertura universal. Aquí hora y apertura se reconocieron bien y fallaron después. |
| **04 — Honestidad** | Scorer congelado y dos corridas con 0/0/0; rechazo de efectos fuera de alcance y estado terminal tipado. | Cierre insuficiente para todo el producto actual: la hora se narró como fallo y la misión tras Nueva sesión como éxito ajeno sin ejecución. Revalidación del sidecar con providers off no detecta esta composición del shell. |
| **05 — Ejecución verificada** | Postlecturas y pruebas de ejecutores mentirosos; matriz 170 filas, 82 `observed`, 88 `unverifiable`. | Funciona la lectura real de hora. Apertura falló su verificación. **82 no equivale a 82 operaciones físicas exitosas:** el contador nace de `ClassifyCatalog`; `liveRuns` de 09.5.11B tiene 42 invocaciones, 23 operaciones únicas, 41 completed/verified y 1 app.open fallida. |
| **06 — Voz del producto / prosa** | Retirada de muchos literales, personalidad por prompt y muestra de 100 respuestas. | **Reabrir funcionalmente:** hechos reales se pierden, aparecen mensajes incoherentes y falsas afirmaciones. La muestra de hora usa datos distintos al contrato real. Persiste progreso por plantilla. |
| **07 — Misiones** | R6 histórico 6/6 misiones, 22 pasos; Core y planificador reales sobre lecturas/notas. Steam físico documentado aparte. | **Reabrir continuidad y recuperación:** un app.open incierto captura nuevos objetivos y Nueva sesión no los libera. 09.5.11C volvió a comprobar sello/fixture, no reejecutó R6 ni Steam físico. |
| **08 — Primera señal** | GPU p95 0,146–0,161 s y CPU máximo 2,973 s en el instrumento de 17 turnos. | Instrumento de sidecar: no ejecuta operaciones ni observa el ciclo público completo. Un aviso rápido no acredita respuesta final útil ni disponibilidad posterior. Además el aviso medido es plantilla. |
| **09 — Voz y oído** | Wake/STT/TTS locales, interrupción y escucha; wake 12/12, STT 3/3 en muestras sintéticas. FAR de 2 h documentado. | **No certifica voz real diversa en habitación:** 12 wake clips de Sabina/Zira y tres STT; revalidación WAV sin micrófono. FAR 5/2 h = 2,5/h (superior 5,26/h), calibración no aprobada; bootstrap activa `ALLOW_UNCALIBRATED=1`. En el Full fresco, STT falló con «open up pad please»; la repetición aislada pasó. |
| **09.5 — Reconciliación histórica** | Manifiesto conciliado, colas auditadas, cero lotes trasplantados y revalidaciones parciales. | Aporta trazabilidad, no una certificación pública integral de 01–09. La propia 11C enumera campañas físicas no reejecutadas. |
| **10 — Uso diario** | Publicados 10.0, 10.1, 10.2 y 10.2.5; este último corrigió ONNX/CPU, refresco y bloqueo de entrada. Siguiente 10.7. | **Abierto.** 10.7–10.17 y los 200 turnos públicos de 10.18 no están cerrados. Debe corregir y acreditar estas fronteras antes de declararse apto para uso diario. |

Fuentes principales: `herencia/00_MAPA.md`, `base/00_COMPUERTA.md`,
`base/03C_ALCANCE.md`, `base/04_HONESTIDAD.md`,
`base/05_EJECUCION_VERIFICADA.md`, `base/06_VOZ_DEL_PRODUCTO.md`,
`base/08_PRIMERA_SENAL.md`, `herencia/09_5_11A_REVALIDAR.md`,
`herencia/09_5_11B_REVALIDAR.md`, `herencia/09_5_11C_REVALIDAR.md`,
`artifacts/goal09/HANDOFF.md`, `artifacts/goal1025/HANDOFF.md` y
`artifacts/goal10/HANDOFF.md`.

## Por qué las pruebas no bastaron

No hay base para decir que todo el trabajo anterior fuera ficticio. El journal
de esta auditoría confirma una operación real correcta. El problema demostrado
es **dar por garantizada la experiencia completa a partir de componentes,
muestras construidas y resultados históricos**.

Tres ejemplos concretos: la muestra de prosa sustituye el contrato de hora;
la revalidación de misiones vuelve a leer el JSON R6 en
`scripts/goal095_09511c_revalidate.py:673–713`; y Full excluye por `[Explicit]`
`OptInRealRuntimeTraversesShellMindAndCoreUsingReadOnlyOperations`, explicado en
`artifacts/goal10/skip-classification.md`. Los tests pueden conservar su verde
mientras falla lo que una persona introduce en la casilla.

## Orden de corrección propuesto

1. **06 + 04:** conservar resultado/postcondición al redactar, preservar hora y
   causa reales, terminar explícitamente los fallos de composición y rechazar
   afirmaciones ajenas al resultado. Reproducir con el JSON real del Core.
2. **07 + shell:** separar la recuperación de un efecto incierto de un nuevo
   objetivo; mantener la evidencia durable sin secuestrar nuevos turnos.
   Probar cancelar, cambiar de tema y Nueva sesión desde la UI.
3. **05:** explicar y reparar la verificación de apertura con Calculadora real,
   sin rebajar el requisito de postcondición ni asumir éxito por launch.
4. **08/09:** medir salida percibida y voz real con los motores y micrófono
   actuales; corregir plantillas y cerrar calibración/robustez con sus criterios.
5. Resolver el rojo reproducible de los evaluadores STT y volver a pasar Full,
   conservando la distinción entre sellos históricos y el árbol actual. No
   cambiar hashes a ciegas ni excluir pruebas para obtener verde.
6. Retomar **10.7 en adelante** usando la casilla pública, casos frescos y un
   oráculo que lea efecto y texto. Mantener abiertos los owners que fallen;
   repetir todos los goals desde cero no es necesario.

## Alcance y validación de esta auditoría

No se han reparado fuentes ni redefinido criterios. No se ejecutaron compras,
mensajes a terceros, borrados ni cambios de configuración del sistema.
La aplicación y su Core lanzados por la auditoría se cerraron antes del Full.
Calculadora se abrió durante la prueba. Los turnos y el estado durable que
produjeron se preservan como evidencia; no se purgó manualmente el plan incierto.

No se hizo una campaña acústica nueva, no se repitieron los 124 casos del 03
ni los 200 turnos de 10.18, y no se certificó el ciclo instalado ni un clon
limpio nuevo. Las seis peticiones son diagnóstico de fallos, no un benchmark
de latencia ni una tasa general de acierto.

La primera ejecución Full fue interrumpida al comprobar la sincronización
solicitada. La segunda chocó con el binario del Core abierto durante la prueba
de interfaz (MSB3027/MSB3021). Se repite con BAXY cerrado; ese bloqueo de fichero
no se presenta como regresión funcional del código.

**Resultado final de `scripts/test_source_quality.ps1 -Mode Full`: exit 1.**

| Etapa | Resultado fresco |
|---|---|
| Estática multilenguaje + build Release | PASS |
| .NET Contracts | 60 pass / 0 fail / 0 skips |
| .NET Integration | 2.853 pass / 0 fail / 1 skip |
| .NET Kernel | 137 pass / 0 fail / 0 skips |
| .NET Providers | 451 pass / 0 fail / 0 skips |
| .NET Setup | 477 pass / 0 fail / 0 skips |
| Python | **8.788 pass / 4 fail / 3 skips**, 3 warnings, 446 subtests pass; 555,29 s |

Las omisiones no se cuentan como pass. Los casos NUnit `[Explicit]` descritos
arriba permanecen fuera de los totales de VSTest, además del skip contado.

Se repitieron únicamente los cuatro tests fallidos con el mismo Python
registrado, `PYTHONPATH=src`, `-p no:cacheprovider` y `-q`:
**1 pass / 3 fail, 17,21 s**. Esto no convierte el Full anterior en verde.

| Test fallido en Full | Diagnóstico y repetición |
|---|---|
| `test_goal09_voice_engines.py::test_voice_engine_pcm_source_wakes_on_injected_wav` | El wake ocurrió; falló la aserción de transcripción: se esperaba `notepad` y llegó `open up pad please`. **Pasó aislado.** Inconsistencia entre corrida completa y aislada; causa exacta aún no determinada. |
| `test_stt_quality_evaluators.py::test_stt_evaluator_freezes_final_contract_and_blind_engines` | **Volvió a fallar** con `wake_program_tree_changed`. El sello esperado difiere del árbol versionado actual. |
| `test_stt_quality_evaluators.py::test_fresh_postweight_source_audit_is_preacquisition_and_text_blind` | **Volvió a fallar** por la misma discrepancia de sello. |
| `test_wakeword_runtime_resources.py::test_livekit_sessions_are_single_threaded_and_do_not_spin` | Prueba **sin rastrear preexistente**. Volvió a fallar porque exige un único objeto SessionOptions y recibe tres. El código configura un hilo y spinning desactivado por sesión; esta aserción de identidad, por sí sola, no demuestra consumo alto. |

Se comprobó el sello sobre los 396 archivos Python incluidos por los
evaluadores: disco y blobs de HEAD son idénticos, sin extras, faltantes ni
diferencias de fin de línea. Ambos dan
`1d3a69df31ac1ce1a75517f3f988b25a0d701b29667c89dd015d55956889bdac`;
los evaluadores esperan
`08300d7cec3ef1d770fb1a10c9a6de7e9d8fdf64e69c7a3be9c4bf4221a5fc7b`.
Al sustituir **sólo en memoria para el diagnóstico** el contenido de
`scripts/goal095_09512_integrate.py` por el del commit `192051f`, el cálculo
reproduce exactamente el sello esperado. Es una desincronización concreta
entre el script actualizado y las expectativas congeladas, no una edición de
fuente introducida por esta auditoría. No se modificó ningún sello.

Logs conservados: [Full](../artifacts/audit/goals_01_10_20260903/source-quality-full.txt),
[repetición de fallos](../artifacts/audit/goals_01_10_20260903/failures-recheck.txt),
[diagnóstico del sello](../artifacts/audit/goals_01_10_20260903/program-tree-diagnostic.json).
