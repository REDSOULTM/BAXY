# HANDOFF CRÍTICO — BAXY, continuación autónoma con GPU (R257)

Usa este texto para retomar BAXY con GPT-5.6 Terra y razonamiento Alto. Continúa
el checkout existente: no reinicies, no sustituyas el producto ni repitas una
línea que ya produjo un veredicto.

## Arranque y autoridad

El checkout canónico se localiza con `git rev-parse --show-toplevel`; debe
contener `Baxy.slnx`, `main.py` y `AGENTS.md`. Comprueba primero:

```powershell
git rev-parse --show-toplevel
git status --short --branch
git log --oneline -12
```

Lee `AGENTS.md`, `README.md`, `goal.md`,
`documentacion/00_META_VIGENTE.md`, el registro de mantenibilidad y
`artifacts/fixes/integral_review_ledger_20260811.json` antes de elegir frente.
El estado Git y esos artefactos tienen prioridad sobre este resumen si difieren.

Puedes modificar, probar, commitear y hacer push de la rama actual, usar red,
GPU y `D:\BAXYRuntime` para investigación aislada. Nunca ejecutes por BAXY un
efecto externo real, no cambies el runtime registrado, no reescribas historia,
no abras V9, ni abras o ajustes contra
`artifacts/holdout/situated_cut_b_r228.jsonl`. CLINC `test` y `oos_test` siguen
opacos; `oos_train` y `oos_val` son las únicas particiones CLINC permitidas.
Congela el árbol antes de toda corrida; si se modifica durante ella, la corrida
no es válida.

La arquitectura no cambia: catálogo tipado único; la mente propone, el kernel
autoriza y los providers verifican. No se autorizan operaciones desde prompts,
corpus, UI o modelos. No hay respuestas visibles fijas ni éxitos no verificados.
Voz, wake word y STT están fuera de alcance: §7 no está cumplido.

## Estado que no se debe volver a pagar

El producto determinista y el camino por modelo no son el mismo corte. El
reconocedor resolvió 324/336 en Corte B R28, pero 0/21 de V8; V8 llegó a una
operación final correcta sólo 1/21. Sus pérdidas son recuperación 13, decisión
1 y vetos 6; OOS llega con candidatas 9/9. La latencia p95 de primera señal es
2,668 s; R134 demostró que pasar de 28 a 2 herramientas ahorra cerca de un
segundo, pero R103 ya demostró que recortar sin recall pierde la operación.

No construyas otro gate léxico: R116/R117, R124 y R139–R144 fueron rechazados.
No revivas E5 aislado (R126: top-1 5/17, top-5 10/17), streaming/acuse temprano
(R132) ni los reemplazos Qwen3.5-4B, Phi-4-mini o Qwen3-4B-Instruct-2507.
Tampoco ajustes ni relances las familias BGE descartadas:

- R236 BGE-M3 de máximo coseno: sólo 15/256 OOS sin candidata.
- R241 reranker BGE zero-shot: 2/256 OOS sin candidata.
- R243/R244 reranker supervisado: pérdidas no finitas.
- R246 cabeza congelada: 0/256 OOS sin candidata.
- R247/R248 clasificador directo: no había OOS fresco para su balance sellado.
- R250 abstención explícita: 256/256 familias erróneas y 4/256 OOS sin
  candidata.
- R253: la fuente que quedaba cubría sólo 9/31 familias; no se ejecuta.
- R255: BGE-M3 con centroides de familia y frontera CLINC falló 27/256 familias
  y dejó 84/100 OOS sin candidata. No cambies su umbral ni lo repitas.

R228 permanece cerrado: su alcance determinista R229 fue 0/93, por lo que es un
oráculo futuro válido, no corpus de ajuste. R225 ya consumió otro corte situado
y fue rechazado por recuperación, decisión, vetos, latencia, efectos no
solicitados y textos deshonestos. No confundas medición de desarrollo con una
promoción de runtime o con Corte B.

## Evidencia nueva: R256–R257

R256 selló un probe distinto de R255: BGE-M3 congelado en CUDA BF16, ranking
por operación con máximo coseno contra ejemplares positivos R207 y división
estricta por consulta normalizada. Sin OOS, umbral, clasificador, decisión,
vetos ni runtime. R257 se ejecutó una única vez en la RTX 4060 Ti:

- 4.426 ejemplares de entrenamiento y 256 consultas disjuntas.
- Recall top-1: 253/256 (98,828125 %); top-2/top-5/top-8: 256/256.
- Las 168 operaciones y 31 familias que tienen ejemplar conservaron todas sus
  consultas en top-2 y top-8.
- Carga 3,078 s; embeddings de evaluación 0,359 s; ranking 0,031 s; VRAM pico
  2.221,4 MiB.
- R207 no contiene ejemplares para las seis operaciones `office.word.*`; por
  ello cubre 168/174 operaciones y el veredicto es
  `development_retrieval_signal_only_catalogue_coverage_incomplete`.

Recibos: `artifacts/development/bge_m3_r207_operation_retrieval_r256.preregistration.json`
(`951fbc5b…1e776`) y
`artifacts/development/bge_m3_r207_operation_retrieval_r257.json`
(`55dd65e7…48ab3`). Esta señal respalda sólo una condición necesaria en la
población cubierta: un shortlist top-2 u top-8 no perdió la esperada ahí. No
permite acortar el shortlist del producto, abrir R228 ni afirmar seguridad.

R258 examinó la candidata externa Windows Agent Arena de Microsoft, commit
`6d39ed88…7332`, MIT, con 19 tareas de `libreoffice_writer`. Fue rechazado
antes de modelo: no es Microsoft Word, no trae etiquetas BAXY y no permite
deducir sin inventar `append`, `close`, `discard`, `save`, `start` o `status`
con sus verificaciones COM. No reutilices esa fuente para rellenar R207. El
recibo es `artifacts/audit/windows_agent_arena_office_source_r258.json`.

R259 examinó OfficeBench, commit `b978b808…02b7`, Apache-2.0. Aunque 84 de sus
300 instrucciones públicas mencionan documento/Word/docx, la fuente ejecuta
`word_app` como archivos `python-docx` en Linux (LibreOffice sólo para
conversión) y evalúa existencia/contenido de archivos. No prueba una instancia
activa de Microsoft Word, COM, Saved/Dirty ni descarte confirmado, y tampoco
etiqueta operaciones BAXY. Sus conteos léxicos (append 8, close 0, discard 0,
save 29, start 10, status 4) son descubrimiento, no mapeo. Fue rechazado sin
modelo como `rejected_preexecution_file_backend_and_state_verification_mismatch`;
no reutilices OfficeBench para rellenar R207. El recibo es
`artifacts/audit/officebench_word_source_r259.json`.

R260 examinó UFO Dataflow de Microsoft, commit `96983c73…b684`, MIT. Es distinto
de OfficeBench: su ejecución puede usar WinCOM, pero no publica el corpus que
aceptaría. `dataflow/tasks` y `dataflow/results` están ignorados y el árbol
versionado tiene 0 filas de tarea y 0 resultados; las nueve plantillas Word no
son solicitudes. Para usarlo habría que aportar o generar `original_task` y
`original_steps`, lo que inventaría corpus. Además, su final WinCOM llama siempre
save y Quit, sin estado Saved/Dirty ni descarte confirmado. Fue rechazado como
`rejected_preexecution_unversioned_input_and_forced_save_quit_semantics`; no
uses UFO Dataflow para generar o etiquetar R207. Recibo:
`artifacts/audit/ufo_dataflow_word_source_r260.json`.

R261 examinó OmegaUse-OfficeVal, commit `cd6ba6d8…54a5`, Apache-2.0. Esta vez
la fuente sí publica 100 solicitudes reales y rúbricas; 39 mencionan Word/docx/
documento. Aun así, mide sólo el entregable final y permite GUI, scripts o APIs,
no la trayectoria. Sus categorías de intentos no son etiquetas BAXY y el conteo
léxico sólo encuentra append 11 y start 6; close/discard/save/status son 0. No
prueba documento activo, Microsoft Word/COM, Saved/Dirty ni descarte confirmado.
Fue rechazada como `rejected_preexecution_final_artifact_only_lifecycle_mismatch`;
no uses OmegaUse para rellenar R207. Recibo:
`artifacts/audit/omegause_officeval_word_source_r261.json`.

R262 examinó white-collar, commit `6c1c9056…927a4`, MIT. Es una herramienta
WinCOM real con 72 casos Word de prueba (63 operaciones distintas); su adaptador
puede insertar, guardar y leer `Document.Saved`. Pero esos casos son pruebas
técnicas y sus cinco JSON publicados son planes de máquina con sólo `app`,
`operations`, `policy`, `schema`, `target` y `write`: no contienen petición,
prompt, consulta o utterance, ni etiquetas BAXY. Sus 64 operaciones públicas
tampoco incluyen close o discard. Las llamadas `Close(SaveChanges=False)` son
gestión interna, no un descarte solicitado y confirmado. No se admite ninguna
operación para R207; no conviertas sus planes o tests en ejemplos de lenguaje.
Recibo: `artifacts/audit/white_collar_word_trace_source_r262.json`.

R263 siguió la procedencia de R207 sin repetir R257. R196/R207 se originan en
un snapshot anterior de 169 operaciones más `__no_action__`; el catálogo actual
es de 174 y las seis operaciones Word son exactamente las ausentes. La única
operación de aquel snapshot que ya no está es `notification.cancel.at`. Las
4.740 filas R196 y los 23.700 pares R207 declaran `human_semantic_audit: false`;
4.179 filas R196 señalan `qwen-generator+gemma-reviewer`. Los números R257 no
cambian sobre su población, pero no acreditan el catálogo actual ni solicitudes
Word/COM. No rellenes el hueco con descripciones, texto generado ni planes.
Recibo: `artifacts/audit/r207_catalog_provenance_drift_r263.json`.

R264 abandona esa línea de fuente para atender el frente A: preinscribió sin
medir un corte B manual, independiente de reconocedor, aliases, builders
anteriores, lenguaje R196 y descripciones del catálogo. Contiene 114 filas
(38 es/en/spanglish), 31 familias y 38 casos semánticos: sus ocho casos Office
incluyen las seis operaciones Word antes ausentes y los tres descartes exigen
confirmación. El corpus no tiene autoridad de ejecución y no arrancó
reconocedor/modelo/providers ni abrió R228/CLINC/V9. El SHA del corpus es
`d36489e7…758b2`; no edites el builder ni el corpus. Recibos:
`artifacts/development/fresh_independent_cut_b_r264.jsonl` y
`artifacts/development/fresh_independent_cut_b_r264.preregistration.json`.

R265 ya selló, sin cargar el reconocedor, el runner que abrirá R264 una sola
vez. Compara exactamente la tupla de `resolve_explicit_effects` contra la
esperada y reporta resolved_expected/resolved_other/unresolved globalmente, por
familia, idioma y operación, más la cobertura real del alias. Runner SHA:
`1b7d03d3…7bad4`; prerregistro:
`artifacts/development/fresh_independent_cut_b_r265.recogniser.preregistration.json`
(`f1a4db35…b7194`). No edites ambos ficheros antes de ejecutarlo.

La invocación R265 falló antes de importar el reconocedor: `KeyError:
runner_sha256`, pues el runner buscó erróneamente `identities.runner_sha256` en
vez de `scoring.runner_sha256`. No hay artefacto R265 ni se consumió R264. No lo
reintentes. R266 ya sella un runner corregido (`3eee32f9…59b06`) y preregistro
`artifacts/development/fresh_independent_cut_b_r266.recogniser.preregistration.json`
(`ee33b30a…75665`), que valida tanto el hash en la ruta correcta como la ausencia
de resultado R265 antes de importar la mente.

R266 ejecutó una sola vez con el runner sellado y rechazó R264: 66/114 exactas
(57,8947 %), 2 otras y 46 sin resolver; es 21/38, en 23/38 y spanglish 22/38.
No satisface el límite de menos de 0,5 y no puede medir el camino por modelo.
El alias vigente ofrece 158/174 operaciones; faltan `memory.status` y las seis
Word, que cubren 21 filas sin alias. No retoques R264 ni agregues reglas: el
corpus se cierra como población de desarrollo rechazada. Recibo único:
`artifacts/audit/fresh_independent_cut_b_recogniser_r266.json`
(`c9781184…bd3a63`).

R267 reparó después la deriva estática del manifiesto de aliases, sin volver a
abrir R264: retiró el alias ya inalcanzable `notification.cancel.at` y actualizó
sus metadatos al catálogo R219 de 174 operaciones. El manifiesto ahora tiene
157 aliases, todos de operaciones vigentes. Los 17 huecos se separan en las 11
operaciones privadas `memory.*` excluidas explícitamente y los seis ciclos Word
sin alias; no se añadió ninguna regla Word. Recibo:
`artifacts/audit/recogniser_alias_catalogue_drift_r267.json`
(`06d20c1e…fe7cd`).

R268 descartó WindowsWorld, commit `fbccd464…2f580`, Apache-2.0. Publica 181
instrucciones con checkpoints y 40 tareas que nombran Word, pero sólo inglés y
chino (cero es/spanglish), sin etiquetas BAXY. Dentro de esas 40, `append`/`save`/
`start` aparecen 1/20/30 veces, y `close`/`discard`/Saved-Dirty 0/0/0. Sus
checkpoints pueden nombrar `WINWORD.EXE`, pero no hay `Word.Application` ni
COM; el entorno documenta LibreOffice Writer y la evaluación es juicio LLM de
capturas con métrico no-op. No se reutiliza para R207 ni para el nuevo Corte B.
Recibo: `artifacts/audit/windowsworld_word_source_r268.json`
(`5696425f…c848b`).

R269 descartó PC-Eval, commit `39317b7…31b21`, Apache-2.0. Su fichero de
instrucciones es un stream de 27 cadenas (26 distintas), no un arreglo JSON;
solamente siete mencionan Word y todas son inglés. Tiene documentos de entrada
pero ningún código de ejecución o verificador. Sus conteos Word son
append/close/discard/save/start/Saved-Dirty = 0/0/0/2/4/0. No hay etiquetas BAXY,
trazas COM o confirmación de descarte, por lo que no se divide ni se reutiliza
para R207 o el nuevo Corte B. Recibo:
`artifacts/audit/pc_eval_word_source_r269.json` (`f92b2baa…64ad`).

R270 cambia de enfoque tras los descartes Word: selló un corte B de 93
solicitudes incompletas (31 es/en/spanglish), una por familia e idioma. Todas
esperan una pregunta que obtenga el dato ausente y cero efectos. Sus textos no
coinciden normalizados con R196 ni R264 y el constructor no lee reconocedor,
aliases, builders previos ni descripciones del catálogo. Es una población
semánticamente distinta de las solicitudes ejecutables R264 y puede refutar si
la gramática todavía resuelve efectos cuando faltan datos. No se ejecutó el
reconocedor todavía. Corpus/prerregistro:
`artifacts/development/independent_clarification_cut_b_r270.jsonl`
(`a38ab784…7d99`) y
`artifacts/development/independent_clarification_cut_b_r270.preregistration.json`
(`c26fddc3…87c1`).

R271 ya selló, sin importar reconocedor, el runner de lectura única R272 para
esa población. Validará hashes de R270, R219 y del propio runner antes de
importar `resolve_explicit_effects`; usará los 174 nombres de operación R219 y
contará toda resolución como posible fuga, con cortes por idioma, familia y
operación intencionada. Prerregistro:
`artifacts/development/independent_clarification_cut_b_r271.recogniser.preregistration.json`
(`211aa41f…7b3eb`); programa/runner:
`experiments/mind_router_spike/preregister_independent_clarification_cut_b_recogniser_r271.py`
(`f2dd8a72…2ed8d`) y
`experiments/mind_router_spike/run_independent_clarification_cut_b_recogniser_r272.py`
(`cb15c663…ab8d6`). Ese sellado todavía no había ejecutado R272, modelo ni
efectos.

R272 ya consumió esa lectura única. Resultado sellado:
`artifacts/audit/independent_clarification_cut_b_recogniser_r272.json`
(`a42e6099…9ddc6`). De 93 filas, hubo 14 resoluciones deterministas (15,05 %),
10 intencionadas, cuatro de otra operación y 79 sin resolver; como las 93
requerían aclaración, las 14 son falsos positivos y no se ajustó la gramática.
Los cortes por idioma son es/en/spanglish = 4/5/5 de 31. R272 no retiene textos
ni identificadores de solicitudes, no inició modelo y no ejecutó providers ni
efectos. El corte queda bajo 0,5 y sólo habilita diseñar, por separado, un
candidato de camino de modelo que demuestre aclaración natural, dato faltante y
cero efectos.

Antes de abrir modelo, R273 detectó y selló una partición que R272 no medía:
el flujo de turno consulta `resolve_explicit_clarification_intent` antes de
`resolve_explicit_effects`; una aclaración de esa primera rama no ejercita
recuperación, propuesta cruda ni vetos. R274 clasificará las 93 filas sólo en
`explicit_clarification`, `explicit_effect` o
`model_decision_candidate_after_two_effect_gates`, sin retener textos o IDs.
Prerregistro:
`artifacts/development/independent_clarification_cut_b_r273.entry-path.preregistration.json`
(`e1cad3a4…d5961`); programa/runner:
`experiments/mind_router_spike/preregister_independent_clarification_cut_b_entry_path_r273.py`
(`234cfd60…361a4`) y
`experiments/mind_router_spike/measure_independent_clarification_cut_b_entry_path_r274.py`
(`2cfc1078…ffe87`). No se importó reconocedor ni modelo y no hubo efectos.

R274 ya consumió la partición una sola vez. Recibo:
`artifacts/audit/independent_clarification_cut_b_entry_path_r274.json`
(`3c4f08a0…83db0`). Clasificó 0/93 como aclaración explícita, 14/93 como efecto
explícito y 79/93 (84,95 %) como candidatas después de ambas compuertas
deterministas; es/en/spanglish dejan 27/26/26 candidatas de 31. No inició
modelo, no modificó runtime y no produjo providers ni efectos. Las 14 rutas de
efecto siguen siendo falsos positivos del corte. El resultado permite diseñar
un probe de modelo separado, pero no acredita modelo, recuperación, veto,
texto visible ni latencia.

## Siguiente frente permitido

No ajustes parámetros de R257 ni lo repitas; no retoques ni relances R264/R266.
La siguiente fuente/población debe ser semánticamente distinta y minoritaria al
reconocedor sin derivar lenguaje de él ni de R196. En paralelo, localiza o atesta
una fuente de desarrollo nueva, reproducible y query-disjoint que cubra las 174
operaciones tipadas, con solicitudes humanas **publicadas** ligadas directamente
a trazas y verificadores nativos de Microsoft Word/COM para las seis operaciones
que R207 no cubre, incluido descarte sin guardar confirmado; no inventes corpus,
no rellenes el hueco con texto generado y no reutilices R228/V9. No basta un
benchmark de archivos, Writer, un harness que delegue en el consumidor sus
tareas, una herramienta de planes técnicos, ni una fuente que sólo puntúe el
entregable final. Si existe, preinscribe una nueva medición antes de importar el
modelo y declara qué población la puede refutar. Aun si conserva recall, hacen
falta por separado OOS, decisión cruda, vetos, texto visible y un camino
completo ciego antes de cualquier cambio de runtime.

No reintroduzcas `notification.cancel.at` ni trates la corrección R267 como
cobertura de reconocimiento. Las seis operaciones Word siguen sin alias y no se
rellenan con descripciones del catálogo, texto generado o planes técnicos.
WindowsWorld también está excluido: sus instrucciones compuestas y su
configuración LibreOffice/no-COM no prueban el ciclo de vida Microsoft Word.
PC-Eval está excluido por instrucción sin trazas ni verificador; sus documentos
de entrada no son ejemplos etiquetados de operaciones BAXY.

R270--R274 están cerrados: no modifiques corpus, contratos, runners ni
resultados, y no uses sus textos para ajustar el reconocedor. R274 superó el
umbral, por lo que el único siguiente paso permitido es prerregistrar un
candidato de camino de modelo separado que mida recuperación, propuesta cruda,
vetos, texto visible, latencia y una aclaración natural que obtenga un hecho
faltante con cero efectos. No abras R228, CLINC, holdouts o V9 como atajo.

R275 ya selló ese candidato sin arrancar modelo: usa el sidecar BAXY del manifest
GPU registrado, wake desactivado, sólo `turn.decide` y ningún dispatch. R276
validará hashes de R270/R274/R219, manifest, runner y scorer antes de iniciar,
y medirá las 79 candidatas de decisión con recuperación, propuesta cruda,
vetos, texto visible y latencia. El corte completo conserva separadamente las
14 fugas deterministas y por ello no puede cerrarse con este probe. Barras del
subconjunto: recall 1,0; propuesta sin efecto y aclaración natural >=0,95;
p50/p95 <=1/2 s; cuatro ceros duros. Prerregistro:
`artifacts/development/independent_clarification_cut_b_r275.model-path.preregistration.json`
(`5e819988…a8544`); programa/runner/scorer:
`experiments/mind_router_spike/preregister_independent_clarification_cut_b_model_path_r275.py`
(`2a371cea…c0f5d`),
`experiments/mind_router_spike/run_independent_clarification_cut_b_model_path_r276.py`
(`ea15f1da…fbdb1`) y
`experiments/mind_router_spike/score_independent_clarification_cut_b_model_path_r276.py`
(`93e81a2b…b82e1`). No hubo modelo, provider ni efecto todavía. La siguiente
lectura permitida es una ejecución R276 y auditoría manual posterior del texto
visible, exactamente una vez.

Cada tanda crea instrumento, prueba focal, prerregistro previo a modelo, recibo
con hashes de programa/corpus/resultados, registro, ledger, pruebas focales,
Ruff, `test_source_quality.ps1 -Mode Full -PreflightOnly`, `git diff --check`,
commit intencional y push. No corras Full completo si sólo queda rojo por el
problema histórico CRLF/dotnet-format: publica la evidencia exacta.

Al informar, incluye `Ritmo | Progreso | Errores | Falsos positivos | Tiempo
restante`, qué se midió/no se midió, rutas de evidencia, estado de rama y qué
puede hacer hoy una persona que antes no podía. Si no hubo capacidad nueva, dilo
literalmente: “No hay ganancia de capacidad para la persona usuaria; la ganancia
es evidencia que evita promover una ruta insegura.” Cierra siempre con: “Voz,
wake word y STT siguen fuera de alcance; §7 no está cumplido.”
