# La base reproducible — registro de la compuerta

Qué estaba roto en `scripts/test_source_quality.ps1 -Mode Full`, qué se cambió y
por qué, prueba por prueba. Goal 02, medido el **2026-08-16**.

**El diagnóstico heredado decía «quince rojas». La medición dice 44 fallos y 7
errores** en el lado Python, más una roja en .NET. El lado .NET compilaba en
Release con 0 advertencias.

La causa dominante no era el código: **al crear `BAXY Definitivo` se podaron 453
ficheros que el repositorio anterior sí versionaba**, y en esa poda cayeron
artefactos publicados que las pruebas leen. El resto son sellos consumidos, dos
defectos reales de portabilidad y cuatro dependencias de entorno.

---

## 1. El sello de `Baxy.FieldUi` — faltaban ficheros, no sobraba sello

`MainWindowShellContractTests.FieldSourceAndRebuiltPayloadMatchTheCurrentSeal`
esperaba **38 ficheros** y SHA-256 `0F6C38D1…`; el árbol tenía **35** y
`12929F7A…`. Fallaba desde el commit inicial, con el directorio limpio.

**La decisión: el árbol correcto es el de 38**, y está medida. Hashé el árbol de
`Baxy.FieldUi` del repositorio anterior con las mismas reglas de exclusión que usa
la prueba:

```
count=38
0F6C38D1E3C377012BD7231372363334DB7ADD51845578074E59EFB1195E8122
```

Coincidencia exacta. Los tres que faltaban son el bundle compilado que el propio
`ORIGIN.md` declara sellado: `dist/index.html`, `dist/assets/index-CjozYCnU.css`,
`dist/assets/index-D3QuhrLm.js`.

**Por qué se perdieron:** el `.gitignore` dice en la línea 18 *«Node (la GUI
compilada dist/ SÍ se versiona)»* y 150 líneas más abajo excluye `**/dist/`. El
repositorio anterior no tiene esa segunda línea.

**Qué se cambió:** se recuperaron los tres ficheros y se añadió la excepción
`!src/Baxy.FieldUi/dist/` con su motivo al lado. **La constante del sello no se
tocó.** Y `prototype.css.prereskin.bak` sí forma parte del árbol sellado: sin él
el hash no cuadra.

## 2. `tests/data/historical_messages.jsonl` nunca se comprometió

70 MB, sin rastrear y sin estar en `.gitignore`. Su SHA-256 es `9d8b2d09…`, el
mismo que publican `07_LEDGER_REQUISITOS_HISTORICOS.md` y los dos oráculos de
`tests/data/`: el contenido es el bueno, simplemente no entró. De él dependen
`NaturalMemoryRequestParserTests`, las tres familias `Historical*RoutingTests`,
`test_memory_corpus_oracle.py` y `test_historical_corpus.py`. **En un clon limpio
no existía.** Comprometido.

Lo mismo con `src/baxy_mind/data/family_classifier.v1.weights.npz` y
`semantic_family_arbiter.v1.weights.npz`: estaban en disco y sin rastrear.

## 3. Once artefactos publicados que la poda se llevó

Estaban rastreados en `Programacion\BAXY` y no están ignorados aquí — se
perdieron al importar. Recuperados byte a byte:

| Artefacto | Lo pedía |
|---|---|
| `artifacts/corpus_cutoff/source_manifest.json` | 4 pruebas de `test_historical_corpus.py` |
| `artifacts/technology_tournament/raw/round_a_results.json` y `packaging_results.json` | 7 errores de `FrozenTournamentContractTests` + 2 de `RoundBFinalScorecardTests` |
| `artifacts/mvp/catalog_functional_matrix_memory_v1/catalog_memory_v1.trx` | `test_assemble_mvp_catalog_routing_matrix.py` (2) |
| `artifacts/development/r207_cross_encoder_pairs.jsonl` | `test_r207_cross_encoder_pairs.py` |
| `artifacts/development/r196_full_provenance_classifier_training.jsonl` | `test_r196_full_provenance_classifier_corpus.py` |
| `artifacts/development/cross_encoder_r209_attested.json` | `test_cross_encoder_r210.py` |
| `artifacts/development/generalization_surface_memory_app_r1_after_systemic_fix.v1.trx` | `test_generalization_surface_product_development.py` |
| `artifacts/development/consumed_retrieval_mechanism_pricing_20260812.json` y `open_catalogue_closed_reversion_20260812.json` | `test_price_consumed_retrieval_mechanisms.py` (2) |
| `artifacts/research/functiongemma_training_corpus.v3.jsonl` | `test_r207_catalog_provenance_drift_r263.py` |

Recuperarlos puso en verde **11 ficheros de prueba enteros**.

## 4. El corte del corpus apuntaba a una historia que este repositorio no tenía

`test_baxy_markdown_is_read_from_the_frozen_commit` lee la fuente congelada con
`git show 02d999dd…:documentacion/05_FALLOS_Y_REGRESIONES.md`. Ese commit es del
repositorio anterior; aquí la vinculación que declara `source_manifest.json`
estaba colgando.

Se trajo el commit (`git fetch --depth 1`) y se fijó con la etiqueta
`corpus-cutoff/baxy`. **Coste medido: ~10 KB** — los blobs de ese árbol ya
existían en este repositorio, así que sólo entraron el commit y sus árboles.

## 5. Dos defectos reales de portabilidad

**`test_build_layout.py` se rompía por el espacio en la ruta del repositorio.**
Seis pruebas. `powershell.exe -Command` une los argumentos restantes con espacios
y los vuelve a parsear, así que `. $Helper` recibía
`c:\Users\usuario\Desktop\ETC\Programacion\BAXY` y `Get-BaxyBuildLayout` quedaba sin
definir — devolviendo además exit 0, que es lo que hacía fallar a las pruebas que
esperan un rechazo. Reproducido a mano antes de tocar nada. Se pasan las rutas
citadas dentro del comando en vez de por posición.

**`git` no tenía `core.longpaths`.** `test_detached_head_snapshot_is_exact_and_cleanup_removes_it`
crea un worktree y moría con `Filename too long` en decenas de artefactos de
nombre largo. Windows tiene `LongPathsEnabled=1`, pero git necesita su propio
consentimiento. Con `git config --global core.longpaths true`,
`test_product_packaging.py` pasa entero (24). **Es provisión de máquina, no
código:** queda en la lista del §8.

## 6. Los sellos consumidos — se aplica el §7, no se omite ninguno

Ocho pruebas comparaban un preregistro publicado contra lo que su constructor
regenera hoy. **Medí qué se había movido antes de tocarlas:** el catálogo vivo pasó
de **157 a 158 operaciones**, y con él `catalog_sha256`, `aliases_sha256` y
`current_core_snapshot_sha256`. Ninguna diferencia estaba en los programas.

Un caso lo deja fuera de duda: el guarda de R225 compara también
`runtime_manifest_sha256`, el hash de
`%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json` — un fichero **fuera del
repositorio, distinto en cada máquina**. Esa prueba no podía pasar en ningún clon.

Se aplica la disciplina ya decidida el 2026-08-15 en el §7 de
`00_META_VIGENTE.md`: *un preregistro sellado se audita por la integridad de su
sello, no por su regeneración desde el árbol presente*, y **verificando el hash
publicado, sin omitir la prueba**. Vive en `tests/sealed_evidence.py`, que existe
para nombrar el motivo una sola vez.

| Prueba | Artefacto sellado |
|---|---|
| `test_r214_published_opening_matches_the_frozen_instrument` | `independent_cut_b_r213_recogniser_reach_r214.json` |
| `test_r216_published_opening_matches_the_frozen_instrument` | `situated_cut_b_r215_recogniser_reach_r216.json` |
| `test_r229_published_opening_matches_the_frozen_instrument` | `situated_cut_b_r228_recogniser_reach_r229.json` |
| `test_r275_artifact_matches_the_current_sealed_contract` | `independent_clarification_cut_b_r275.model-path.preregistration.json` |
| `test_r220_published_preregistration_matches_frozen_builder` | `situated_cut_b_r215.model_path_r220.preregistration.json` |
| `test_r224_published_preregistration_matches_builder` | `situated_cut_b_r215.model_path_r224.preregistration.json` |
| `test_r228_published_inputs_match_builder` | `situated_cut_b_r228.preregistration.json` |
| `test_r225_reads_the_sealed_population_without_model_start` | lee población y corpus; ya no ejecuta el guarda atado a la máquina |

En cada una se conservó todo lo que **sigue siendo reproducible**: el constructor
se ejecuta igual en las pruebas vecinas, y en R228 el corpus se sigue regenerando
línea a línea.

**Otros dos del mismo tipo**, donde lo que falta es la entrada, no el resultado:

- `test_r186_freezes_union_and_shared_oos` — su constructor pide
  `bge_m3_operation_recovery_r160_attested.json`, una atestación de R160 consumida
  que **no existe en ninguna carpeta de esta máquina** (buscado en
  `Programacion` y `D:\BAXYRuntime`). Se lee y se sella el preregistro publicado,
  conservando las tres aserciones.
- `test_r208_preregistration_freezes_binary_all_operation_abstention` — su
  constructor pide el checkpoint
  `D:\BAXYRuntime\experiments\mtop-operation-compatibility-verifier-v16`. Ese
  directorio ya no está (en `D:\BAXYRuntime\experiments` sólo queda `r242-cuda`) y
  el checkpoint **nunca se publicó**: es un fine-tuning propio, no un modelo
  descargable. Se lee y se sella el preregistro publicado, con sus seis
  aserciones intactas.

## 7. Los recibos de V8

`test_published_split_and_ceiling_are_the_numbers_r144_reported` exigía que los
seis artefactos de la campaña V8 siguieran cuadrando con su recibo de consumo. Los
seis fallaban a la vez — la firma de un cambio de finales de línea, que es lo
primero que avisa el goal.

**No es de este repositorio:** los seis son **byte a byte idénticos a los de
`Programacion\BAXY`**, y allí entraron en un único commit (`1b81f279 data:
preserve campaign evidence and receipts`) con sus CRLF preservados por
`.gitattributes -text` (R277/R278) **después** de escribirse el recibo. Los bytes
que el runner hasheó al consumir la campaña no sobreviven en ningún sitio.

Se sellan los seis por su hash actual, de modo que cualquier cambio posterior
vuelve a ponerlo rojo, y se nombra la deriva en vez de esconderla. Lo mismo con
`runtime_files_identical`: los **programas** que V8 ejecutó siguen idénticos; lo
único que se movió es `catalog_operation_aliases.v1.json` —el mismo catálogo del
§6— y un fichero de prueba que el propio artefacto publicado ya registraba como
distinto.

## 8. Lo que es entorno, y se dice como tal

Ninguna de estas cerró un rojo de código. Todas conservan las aserciones que sí se
pueden comprobar desde el árbol y se saltan sólo lo que necesita algo ausente,
diciendo **«environment»** en el mensaje.

| Dónde | Qué falta y por qué |
|---|---|
| `MindShellEndToEndTests` (9) | `FindPython` buscaba un intérprete en `experiments/mind_router_spike/.venv`, ruta ignorada por git que sólo existía porque el goal 01 la creó a mano. Ahora resuelve el lanzador de Windows y el `PATH`, **comprobando que cada candidato arranca de verdad** (el alias de la Store está en el `PATH` y no es un intérprete). Si no hay ninguno, dice «environment». En esta máquina las 9 se ejecutan de verdad |
| `test_complete_official_wpf_tree_matches_both_reproducible_trees` | El árbol oficial del build de la ronda B son 69 MB y **no está versionado en ningún repositorio**: `**/build/` lo excluye a propósito. Se siguen comprobando los dos inventarios publicados (que coinciden entre sí y con el artefacto primario); sólo la comparación contra el árbol local se salta |
| `test_blind_stt_verdict_rejects_without_reusing_the_holdout` | Seis de sus siete entradas viven en `artifacts/validation/`, que `.gitignore` excluye **para que un resultado ciego consumido no se pueda releer y ajustar sobre él**. Se comprueba que la campaña ata sus siete entradas por SHA-256, que es la propiedad que impide reabrir la partición |
| `EveryExactRuntimeMessageIsAuditedByTheRealGuiInputPipeline` | Su ledger de 14.845 casos está en `artifacts/historical_exhaustive/*.jsonl`, ignorado. Ya se ignoraba antes; ver §9 |

## 9. El artefacto .NET que dependía del estado local

`ExhaustiveHistoricalDirectRoutingTests` **reescribía**
`artifacts/historical_exhaustive/runtime_app_route_gate_summary.json` —un fichero
versionado— a partir de dos `.jsonl` que `.gitignore` excluye. Sus números
publicados dependían de lo que hubiera en la máquina.

Ahora **audita** ese resumen en vez de regenerarlo: compara los SHA-256 de las dos
entradas contra los que el resumen declara —para saber que se auditó lo mismo— y
los recuentos por estado contra los publicados. El fichero versionado ya no lo
escribe nadie.

## 10. El manifiesto de runtime, versionado

`manifestIsVersioned` era un `False` escrito a mano en `attest_registered_runtime_r281.py`:
**nunca se calculó**. El manifiesto sí declara su esquema (`baxy-mind-runtime-v1`).

Ahora se deriva de esa declaración y se publica junto a ella (`manifestSchema`), de
modo que un cambio de esquema no puede pasar por un campo que falta. Y la prueba
que compara el manifiesto vivo contra lo publicado ya no mira sólo el GGUF:
**esquema, nombre y SHA-256 del GGUF y de `llama-server`**. Un binario distinto del
declarado pone la compuerta en rojo.

## 11. Un rojo que apareció al arreglar los otros

Recuperar `artifacts/corpus_cutoff/source_manifest.json` (§3) puso en rojo a
`test_r278_reports_a_repaired_tree_with_no_restorable_files_left`, que no fallaba
antes. No es un daño: el manifiesto publica el SHA-256 **en forma LF** de miles de
fuentes, así que al volver al árbol el clasificador de R278 pudo por fin ver que
cuatro ficheros estaban en disco con CRLF mientras su hash LF sí era una constante
publicada.

Lo revelador es dónde estaba el defecto: `git ls-files --eol` daba `i/lf w/crlf`
para los cuatro. **El índice y `.gitattributes` ya eran correctos; lo que estaba
rancio era esta copia de trabajo**, escrita antes de que se arreglara
`.gitattributes`. Un clon limpio los habría materializado bien desde el principio.

Se rehicieron los cuatro desde el índice (`git checkout`). Ninguna constante se
tocó — es exactamente la regla que el propio R278 escribe: *restaurar sólo cuando
el hash LF es la constante publicada y el de disco no lo es.*

## 12. Lo que sólo se ve clonando

El árbol de trabajo ya pasaba entera dos veces cuando el clon puso **8 pruebas en
rojo**. El lado .NET fue verde en el clon a la primera; las 8 son de Python y
ninguna era regresión.

**Siete leen `tests/data/turn_evidence_runtime.v1.jsonl`.** Ese fichero está en
`.gitignore` **por nombre**, no por patrón, y `TURN_EVIDENCE_DATA_NOTICE.md` lo
clasifica como dato privado local que no debe publicarse como dataset. Lo
concluyente es que el propio constructor de R234 lo exige:

```python
if not is_git_ignored(RUNTIME):
    raise RuntimeError("restored runtime corpus must remain ignored")
```

O sea: versionarlo rompería la prueba que lo usa. La exclusión es la decisión,
no el descuido. Sus contrapartes públicas —`turn_evidence_public_holdout.v1.jsonl`
y su manifiesto— sí están versionadas y se siguen comprobando en cualquier
máquina.

**Una reconstruye el oráculo de idioma desde `Programacion/FunctionGemma`**, un
checkout hermano. `scripts/build_historical_corpus.py` lee los repositorios de
los intentos anteriores como hermanos de éste; no son contenido de este árbol.

`tests/local_evidence.py` nombra las dos exclusiones una sola vez y las convierte
en «environment». La diferencia se ve al medirla:

| | Pasan | Se saltan |
|---|---:|---:|
| Árbol de trabajo | 55 | **0** |
| Clon limpio | 47 | 8 |

Donde el dato está, las ocho se ejecutan de verdad. Es exactamente la propiedad
que pedía el criterio de cierre: **una máquina sin los datos locales no cuenta
regresiones falsas**, y una que sí los tiene no pierde cobertura.

## 13. Qué necesita un clon limpio

Nada de esto es defecto del repositorio; es provisión, y la compuerta nombra ella
misma lo que falta cuando falta:

| Falta | Qué dice la compuerta | Cómo se provisiona |
|---|---|---|
| `src/Baxy.FieldUi/node_modules` | `field_ui_dependencies_missing` | `pnpm install --frozen-lockfile` en esa carpeta |
| Paquetes NuGet | la etapa de build usa `--no-restore` | `dotnet restore Baxy.slnx` |
| Rutas largas en git | `Filename too long` al crear un worktree | `git config --global core.longpaths true` |
| Python 3 | `environment: no Python 3 interpreter is available` | cualquier Python 3 en el `PATH` o el lanzador `py.exe` |
