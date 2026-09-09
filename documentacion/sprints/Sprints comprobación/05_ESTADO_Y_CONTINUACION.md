# Estado de Sprints comprobación

C01 CERRADO `d6500f8`. C02 CERRADO `88b5370`. **C03 EN_CURSO**. C04 no abierto.
Rama de trabajo `Goal-c03`, base `2bf3d4c`, candidato Astra en curso. Falta 100/100.
Encargo vigente: `C03_ASTRA_AUTORIDAD.md`; estado operativo único en
`artifacts/comprobaciones/C03/CHECKPOINT.md`. El handoff de Opus y los apartados
de abajo conservan evidencia histórica, no certifican el candidato nuevo.

La baseline Astra de 16 turnos da **10/16 útiles y fieles, 15/16 publicados**;
adjudicación en `artifacts/comprobaciones/C03/astra-baseline/ADJUDICACION.md`.
El candidato con coordinación reparada da 11/16 útiles/fieles y 15 publicados
en `astra-serial`; `astra-facts` conserva 11/16, `astra-prose` cae a 9/16 por
una pregunta elíptica que inicia una misión wifi y arrastra los turnos siguientes.
El veto de efectos reparado elimina esa contaminación en cuatro controles:
3/4 plenamente correctos, uno con fallo de gramática. No son aceptación fresca.
El primer Full Astra terminó rojo por una huella histórica desactualizada;
el segundo se interrumpió durante Python por instrucción de reservar Full para
el cierre; .NET terminó sin fallos. No equivale a Full verde. Tras conservar la
pregunta bajo INTENT_KNOWLEDGE, `astra-knowledge-question` da 4/4 correctos por
la entrada real y 366 pruebas dueñas pasan. Ver checkpoint para fuente y proceso.
El panel ampliado `astra-routes-development` da 11/18 correctos: pérdida del pedido
al ocultar un nombre de archivo, spanglish y disposición de error bloquean C03.
Los apartados históricos no aplazan estos fallos a C05/C06. Ningún modelo
diagnóstico se ha promovido. Fixture propio retirado tras comprobar su hash.

Tramo 4: un acuse tardío de cancelación de voz ya no invalida la mente;
la decisión ausente conserva mind_unavailable. Cancelar una aclaración limpia
el objetivo sin reinterpretarlo, también con cancel that/cancela eso. Dueños
C#: 101 pass/0 skips; Python: 369 pass/101 subtests. La proyección conserva el
estado resultante; el panel de cancelación pasó de 3/6 a 5/6 correctos antes
del último ajuste causal, cuya medición consta en CHECKPOINT.md. Estos controles
no acreditan las ocho rutas ni reemplazan los cien turnos frescos.

Tramo 5 conserva unsupported en el protocolo, mixed entre lectores y la lectura
del reloj cuando se pide un idioma. Dueños: Python 1219 pass/101 subtests; C# 73
pass de subtipo y 190 de hora/hechos/idioma, sin omisiones (suites con solapamiento).
astra-language-boundary 4/8 correctos y astra-language-preserved 3/8 plenamente
correctos muestran defectos de calidad abiertos; ocho publicados no son ocho
correctos. La salida anticipada del resolver contextual se corrige después de
esa medición. ASTRA-TRAMO-5.md y CHECKPOINT.md conservan la reanudación.

Tramo 6: Qwen3-8B heredado, con override diagnóstico, obtiene 3/6 útiles;
con kind/estado conservados sube a 4/6. Retirar el veto general de una frase
recupera las bienvenidas ES, pero quedan dos explicaciones mixed sin respuesta.
Picos atribuidos 3336–3338 MiB; ninguna promoción. Se conserva ahora el pedido
en todos los intentos de progreso y se retira el recorte del primer verbo.
Dueños: 222 pass/101 subtests. El contraste final figura en CHECKPOINT.md;
no hay aceptación 100 ni Full final. Los apartados siguientes son históricos.

## Criterios de C03 ya cumplidos

**Frontera idioma/intención/hechos.** `src/baxy_mind/request_reading.py` es el
único owner: idioma, saludo (`none|only|leading`), petición real e intenciones,
con precedencia traducción → idioma pedido → evidencia → idioma de conversación
→ español. `IsEnglishGreetingRequest` se retiró de C#: la mente reporta
`responseLanguage` en `turn.result` y la política lo consume. Corpus compartido
`tests/data/request_reading_cases.json` (89 casos), comprobado en pytest y en
`RequestReadingConformanceTests`.

**Hechos.** El payload no deduce `effect`/`seen.window` del verbo, no convierte
una red sin lectura en `online=false`, no publica un `reason` en JSON crudo y
acepta el reloj en su forma de doce horas. `close_clip` retirado. Fuera de
catálogo es un límite, no un intento fallido.

**Cero prosa fija.** Los prompts ya no dictan la frase. Se vetan la copia de lo
enviado (sin acentos), las aperturas sobre el encargo, el metadiscurso de tarea,
los nombres de campo y la segunda persona en una respuesta de capacidades.

**R07 cumplido** (`r07-opus-1/`): un proceso (PID 37680), un perfil, una sesión;
`reject`, `timeout` y `exhaust` con terminal honesto, causa pública y controles
utilizables, y la respuesta normal vuelve tras restaurar, en ES y EN.

**UI real cumplida** (`ui-opus-2/`): `py main.py --ui-probe` teclea en el
`input` de la ventana y lee `.activity-scroll .act`. Siete de siete útiles y
fieles, con estado y turno siguiente. Encontró y se reparó la bienvenida de
arranque que publicaba `situación.greeting`.

**Instrumentación.** `compose-audit.jsonl` v2 (turno, etapa, idioma, saludo,
payload, borrador sin recortar, motivo, `finish_reason`, publicación) y
`paired.json` con `mindReplyRejection` nombrado. `IsSafeConversationReply` pasó
de una disyunción de 45 términos a comprobaciones con nombre.

**Full verde** sobre el candidato de aquel momento: `source_quality_gate_passed: mode=Full`.
Para el candidato actual el Full está **NO VERIFICADO**: ver «Pruebas» más abajo.

## Seguimientos elípticos: reparado, con el defecto de fondo a la vista

Ver `artifacts/comprobaciones/C03/SEGUIMIENTOS.md`.

La anotación anterior («la ruta contextual sólo corre para `followup`/`None`»)
era falsa. La traza de composición con el campo `situation` enseña que **todo
turno conversacional que degrada llega al compositor con
`{"kind":"conversation","polarity":"success"}` y nada más**: sin la respuesta
que escribió la mente, sin historial y sin tema. El compositor vuelve a
contestar desde cero con el texto del turno. Con una pregunta que se basta sale
bien; con «¿por qué importa?» no puede salir bien.

La elipsis se lee ahora donde se lee el pedido —`is_elliptical_followup`,
`request_topic`, `followup_topic` en `request_reading.py`— y el shell manda
`priorRequests` (lo que la persona pidió antes, no lo que se le contestó) en los
hechos de conversación. De 0 de 9 seguimientos en tema a 7–9 de 9.

Queda abierto que el seguimiento, ya en tema, a menudo repita la definición en
vez de contestar la pregunta. Eso es generación conversacional (C05/C06);
forzarlo desde el prompt fue lo que empeoró en `seguimiento-12`.

## Lo que falta: 100/100

`panel-opus-13/` (78 turnos, ver `ADJUDICACION.md`): 75 publicados, 2
agotamientos, 1 silencio, ~75 % de respuestas útiles y fieles —estimación, no
cifra exacta—. No procede congelar cien turnos frescos hasta que el panel sea
fiel. Clases pendientes:

1. El seguimiento en tema que repite la definición (arriba). C05/C06.
2. Saludo mal formado («Hello hi!») y persona impersonal («se puede abrir…»).
   La persona de la negativa («No abres la Calculadora») sí quedó reparada.
3. Capacidades o límites inventados y rechazos de preguntas contestables:
   reparados y medidos en `limites-22/` (8 de 9), **sin panel completo todavía**.
4. Fuga del contrato interno.
5. Dos agotamientos y un silencio por corrida, más el turno que muere agotado
   porque el veto del shell tira la respuesta correcta del compositor.

## Hipótesis medidas y descartadas

1. **Turno anterior como contexto de conversación** (`panel-opus-4/-5`): el
   modelo continuaba el turno anterior en vez de responder el nuevo.
2. **Muestreo de composición 0.2/0.9** (`panel-opus-6` contra `-5`, misma
   población): agotamientos 1 → 7 y peor tasa.
3. **Forzar la ruta contextual en preguntas elípticas** (`seguimiento-3` contra
   `-2`): sin mejora y con una regresión —el tema anterior arrastrado a una
   pregunta nueva—. La causa real estaba en los hechos del compositor.
4. **Prohibir la definición en un seguimiento** (`seguimiento-12` contra `-11`,
   misma población): el modelo rodeó la prohibición con frases contorsionadas y
   de nueve seguimientos en tema bajó a seis.

Las tres están revertidas y documentadas en el código donde vivían.

## Candidato (sin publicar)

`llm.py` `f0569f87d070a043…`, `request_reading.py` `60b9e8b595976ea1…`,
`__main__.py` `5092f2e5c3a89ae9…`, `UserMessagePolicy.cs` `b0c8baf4b706509d…`,
`MainWindowViewModel.cs` `3889ccd755146dcb…`, `ModelMessageComposer.cs`
`45cf5cfa6a73b0db…`, `FieldUiProbe.cs` `06b0733966ccc24d…`, `UserMessagePhrases.cs`
`29ee866bbed09384…`, `censo_voz_visible.py` `a503171e01922ab9…`,
`request_reading_cases.json` `66dcd7a6cd663a8a…` (92 casos).
Granite 4.2 3B Q4_K_M, gguf `e0406663`, sin `BAXY_MIND_LLM_GGUF`.
`registered_runtime_expectation_r281` declara Granite; STT/TTS/wake conservan
sus hashes: la voz no se volvió a medir y esto no lo afirma.

## Pruebas

Intérprete: el del manifiesto
(`%LOCALAPPDATA%\BAXYRuntime\python\mind-runtime-v1\Scripts\python.exe`); con el
Python del sistema fallan 20 pruebas por dependencias ausentes.

**Full: NO VERIFICADO para el candidato actual.** El último `-Mode Full`
(`full_gate8.txt`) dejó verdes todas las etapas —Contracts 60, Integration 2920
(1 skip), Kernel 138, Providers 451, Setup 477, ruff, compileall, eslint, tsc,
dotnet-format, censo de prosa visible 0— salvo `test_stt_quality_evaluators`,
por deriva del pin `EXPECTED_PROGRAM_TREE_SHA256` al editar durante la corrida.
El pin no se refrescó al cerrar la sesión: hay que refrescarlo con su nota y
relanzar Full.

Recogido después de ese Full, sobre el candidato actual: `test_request_reading.py`
177 pass; `-k "turn or planner or compose or reading or policy or goal06"` 1853
pass con 101 subtests; Integration completo 2922 pass, 1 skip —anterior a la
prueba roja de caracterización que documenta el fallo abierto—.

## Corridas conservadas (publicado ≠ fiel)

`panel-opus-1..13`, `seguimiento-1..14`, `limites-13..22`, `r07-opus-1`,
`ui-opus-1/2`, y las de Grok (`cien-35` 93 publicados/7 agotamientos —no
aciertos—, `disc-68` 15/1). Todas son regresión: ninguna vale como aceptación
fresca. La última completa es `panel-opus-13` (78 turnos, 75 publicados, 2
agotamientos, 1 silencio, ~75 % fieles), anterior a las reparaciones de límites.

## Siguiente acción

1. Poner en verde la prueba roja de caracterización
   `AcceptingTheConstraintInThePersonsOwnWordsIsNotVetoed`: el compositor ya
   escribe la respuesta correcta y el veto del shell la tira, así que el turno
   acaba `composition_failed`.
2. `panel-opus-14` sobre `panel-opus-13.turns.jsonl`, para medir las
   reparaciones de límites en población completa.
3. Con el panel fiel: congelar 100 turnos nuevos, adjudicarlos por lotes de 20
   sin partir secuencias, refrescar el pin del árbol y repetir Full antes de
   publicar.

Procesos propios activos: ninguno.
