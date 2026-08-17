# La comprensión — qué se midió, qué se cambió y dónde está la frontera

Goal 03, cerrado el **2026-08-17**. Todo lo de aquí se corrió en esta máquina
sobre una población de paráfrasis que el sistema no había visto, con el crudo
instrumentado: qué se le ofreció al modelo y qué propuso **antes** de que ningún
veto lo tocara.

> **El resultado en una línea:** BAXY entiende **46,0 %** de las paráfrasis
> frescas, no ≥ 90 %. Y la frontera está medida y tiene nombre: **sin la puerta
> de dominio léxica entiende 66,9 %, pero ejecuta 20 efectos no pedidos en 36
> peticiones fuera de catálogo.** BAXY no tiene un mecanismo de abstención;
> tiene una lista de vocabulario haciendo de abstención, y esa lista es el techo.

---

## 1. El instrumento

**El corpus.** 160 filas escritas para este goal: 124 dentro de catálogo y 36
fuera, en español, inglés y spanglish, con la formulación de alguien que no
conoce el catálogo. Vive en
[`artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl`](../../artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl),
SHA-256 `761c1bc3…`. Las siete corridas de abajo puntuaron **esos mismos bytes**.

**Su independencia, medida.** El reconocedor determinista resuelve **30 de las
124** filas dentro de catálogo — el **24 %**. Las otras 94 salen de su gramática,
así que el corpus **puede contener el fallo**. El corpus vigente hasta hoy no
podía: lo generó una gramática que no sale de la del reconocedor, y su 700/700 no
dice nada sobre formulación libre.

**El reparto por causa.** Cada fila se clasifica con el crudo, no con el
resultado:

| Causa | Qué significa |
|---|---|
| **recuperación** | la operación esperada nunca se le ofreció al decisor |
| **decisión** | se le ofreció y propuso otra cosa |
| **veto** | la propuso bien y una etapa posterior se la quitó |

Sin esa partición, los tres arreglos —que son opuestos— reciben el mismo número
y el siguiente cambio va al blanco equivocado.

**La latencia.** `turn.decide` va del texto a la decisión y trae ya el texto
visible de una conversación, así que su tiempo de pared **es** la latencia hasta
la primera señal. El listón del dueño son 3 segundos de silencio.

Programa: [`run_goal03_comprehension.py`](../../experiments/mind_router_spike/run_goal03_comprehension.py).
Ningún provider habilitado, cero efectos ejecutados, V9 sin abrir.

---

## 2. Las siete corridas

Todas sobre el mismo corpus, todas esperando a que la recuperación semántica esté
en pie antes de la primera fila (el audit lo acredita fila a fila).

| # | Corrida | Sirve | Tasa | Recup. | Decisión cruda | Pierde R/D/V | Fuera de catálogo honesto | p50 | p90 | máx | > 3 s |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | **Punto de partida** — Gemma-4-E2B, el árbol tal cual | 43/124 | **34,7 %** | 73 | 52 | 49/21/11 | 33/36 | 2,75 | 3,71 | 7,54 | 39 |
| 2 | Gemma-4-E2B, recuperación arreglada | 49/124 | 39,5 % | 102 | 63 | 20/39/16 | 34/36 | 2,63 | 3,59 | 7,41 | 34 |
| 3 | Qwen3-4B, contrato de esquema, con banderas explícitas | 56/124 | 45,2 % | 103 | 82 | 19/21/28 | 33/36 | 2,18 | 3,02 | 5,55 | 13 |
| 4 | Qwen3-4B + `tool_choice: required` | 56/124 | 45,2 % | 103 | 85 | 19/18/31 | **25/36** | 1,52 | 3,06 | 5,24 | 13 |
| 5 | Qwen3-4B, shortlist de 8 en vez de 28 | 54/124 | 43,5 % | 91 | 75 | 31/16/23 | 31/36 | 2,08 | 2,90 | 8,34 | 11 |
| 6 | Qwen3-4B **sin la puerta de dominio** | 83/124 | **66,9 %** | 103 | 84 | 19/19/3 | **16/36** | 1,82 | 2,56 | 4,94 | 6 |
| 7 | **Tal como queda instalado** — sin banderas, leyendo el manifiesto registrado | 57/124 | **46,0 %** | 103 | 86 | 19/17/31 | 33/36 | 2,08 | 3,15 | 6,05 | 13 |

Las latencias son del camino por modelo. El camino determinista responde en
**p50 0,007 s** y no aparece en esas columnas.

Las corridas 3 y 7 son **la misma configuración** —Qwen3-4B con el contrato de
esquema— pedida de dos maneras: la 3 con banderas explícitas y la 7 leyendo el
manifiesto registrado. Difieren en una fila de 124. Ésa es la varianza entre
corridas de este instrumento, y **la cifra que se publica es la 7**, porque es la
que responde a quien instale esto.

Por idioma, en la corrida 7: **es 30/73 (41,1 %)**, **en 15/35 (42,9 %)**,
**spanglish 12/16 (75,0 %)**. El spanglish va mejor porque sus filas caen más a
menudo dentro de la gramática del reconocedor.

---

## 3. Tres defectos de producto que la medición destapó

Ninguno era una fragilidad teórica. Los tres estaban en producción y los tres
bloqueaban este goal, así que se arreglaron aquí.

### A. El runtime registrado ejecutaba el `baxy_mind` del repositorio anterior

`%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json` declaraba
`python_path = …\Programacion\BAXY\src`. Como `python -m baxy_mind` resuelve el
paquete por `PYTHONPATH`, **toda medición hecha en `BAXY Definitivo` corría el
código del cuarto intento**. Los dos árboles eran idénticos salvo por lo que este
goal cambió, así que ninguna cifra anterior queda invalidada — pero ningún cambio
de este repositorio se habría medido nunca. El manifiesto apunta ahora aquí.

### B. El primer turno retiraba el router E5 para siempre

El worker del encoder arranca 3 s después del proceso y tarda **~11 s** en cargar
E5. `ProcessIntentRouter.encode` trataba el `TimeoutError` de **esperar a que
estuviera listo** igual que un timeout a mitad de petición: como un desajuste de
protocolo, con `_fail_closed_locked`, que retira el canal de forma permanente.
Cualquier turno dentro de esos ~14 s mataba el router, y `PlannerCatalog` se
quedaba con su instantánea **léxica** —solapamiento de tokens— durante toda la
vida del proceso.

Eso es lo que producía shortlists como ésta para «como anda la maquina en
general»: `notification.*`, `media.*`, `window.*`, `input.*`, y `system.status`
ni aparece.

Esperar a que un worker cargue no es un desajuste: no se ha enviado nada y el
canal sigue sincronizado. La espera se separó del tramo que sí lo es.

### C. La recuperación rankeaba familias y repartía plazas dentro de la ganadora

`PlannerCatalog.shortlist` ordenaba **familias**, se quedaba con diez, y dentro de
cada una entregaba una ventana de tres operaciones dentro de una banda de
relevancia. Es una pregunta más gruesa que la que se está haciendo: la hoja que la
persona quería perdía su plaza a manos de hermanas de una familia que puntuaba
bien. Y cuando el clasificador de familias hablaba, el shortlist era **la familia
entera**, en orden de catálogo, sin ranking ninguno.

Rankear las operaciones autenticadas directamente: **73 → 106 de 124** ofrecidas
en el banco offline, **73 → 102** vivo.

Con ello se retiró, no se apiló encima:

| Retirado | Por qué |
|---|---|
| `FamilyClassifier` y `SemanticFamilyArbiter` del camino del turno | sólo se instanciaban si el nombre del fichero del modelo contenía `qwen3`: dos recuperaciones vivas para el mismo trabajo según qué modelo estuviera cargado |
| `_prioritized_family_tools` | volcaba la familia entera |
| `MAX_SHORTLIST_FAMILIES`, `MAX_CATALOG_GUARANTEED_FAMILIES`, `MAX_FAMILY_OPERATIONS`, `FAMILY_RELEVANCE_BAND`, `LEADING_FAMILIES`, `FAMILY_RELEVANCE_BAND_LEADING` | seis constantes que sólo servían al reparto por familia |
| `_family_document`, `_family_vectors`, `_semantic_family_scores`, `_catalog_related_families`, `_family_lexical_score`, `_family_specific_lexical_score` | el documento y los vectores por familia |
| `preferred_families` / `restrict_to_preferred` | ya no hay familia preferida que imponer |

### Lo que estos tres cambios pusieron rojo, y cómo se cerró

Ningún rojo se cerró relajando un umbral. Se cerraron **nombrando lo que se
movió**, que es para lo que están los sellos:

| Sello | Qué pasó | Cómo se cerró |
|---|---|---|
| `wake-validation-program-tree` (5 programas de `experiments/stt_quality`) | congela `experiments/voice_latency`, `scripts` y **todo `src/baxy_mind`** antes de abrir un holdout ciego de STT | Repinado de `22f3bd4e…` a `b62972b6…`, siguiendo el precedente de R277: *un commit que cambia el árbol congelado sin repinar lo deja roto*. Anotado en `APLAZADOS.md`, porque el evaluador de STT no ejecuta nada de lo que se cambió |
| `test_price_v8_veto_damage_by_cause` | exigía que **todo programa que V8 ejecutó** siguiera byte a byte | Se separó el libro en dos: `V8_DATA_DRIFTED_SINCE_THE_CAMPAIGN` y `V8_PROGRAMS_REPLACED_BY_GOAL_03`, con las dos hojas nombradas y su consecuencia dicha — **las cifras de V8 describen un camino de decisión que este árbol ya no tiene**. Cualquier deriva no listada sigue poniéndolo rojo |
| R277, R280 | auditorías consumidas cuyo sujeto —el literal `qwen3` en `llm.py`— ya no existe | Selladas por el hash de su artefacto (§7 de `00_COMPUERTA.md`), conservando todo lo que concluyeron. R280 gana además una prueba nueva: que **ningún nombre de fichero decide ya el contrato de decisión** |
| R231, R232, R233 | R231 ata `registered_runtime_manifest_sha256`, un fichero fuera del repositorio que este goal cambió al promover el decisor | Selladas. Es el caso de R225 que el goal 02 ya documentó: esa prueba no podía pasar en ningún clon |

Y una trampa de este repositorio que hay que decir, porque cuesta una corrida
entera: **`.gitattributes` declara `* text=auto eol=lf`, y Python en Windows
escribe CRLF por defecto.** Cualquier fichero regenerado con `write_text` sale
con CRLF, se hashea con CRLF y ese hash muere en el primer checkout limpio. Los
sellos de este goal se recalcularon sobre los bytes LF. Y al revés: buena parte
de `artifacts/` está comprometida **con CRLF en el índice** y no lleva
declaración `-text`, así que renormalizarla mueve hashes publicados — ahí no se
toca nada.

---

## 4. Dos correcciones de recuperación que sí se pagaron, y una que no

Medidas offline sobre el mismo corpus, con el mismo snapshot de e5-small ya en
producción ([`compare_goal03_retrieval.py`](../../experiments/mind_router_spike/compare_goal03_retrieval.py)).

| Cambio | Ofrecida en top-28 |
|---|---:|
| Como estaba: documento y consulta con el prefijo `query:` | 0,855 |
| **`passage:` en el documento** — e5 se entrenó asimétrico | **0,911** |
| Documento reescrito «como lo diría un usuario», quitando la cola de verificación | 0,823 ✗ |

La tercera parecía la buena y salió peor: **rechazada**. Toda descripción del
catálogo termina contando cómo se verifica el efecto, y quitarlo no discrimina
más — quita señal.

Y una corrección de escala que hacía falta: los cosenos de e5 sobre entradas
cortas viven en una banda de **~0,05**, así que mezclarlos con un bonus léxico en
escala 0–1 dejaba que un solo token compartido mandara sobre el significado.
Reescalar los scores de cada consulta a 0–1 antes de mezclar: **+8 filas de 124**.

---

## 5. El decisor: heredado contra elegido

El decisor puesto era Gemma-4-E2B-it QAT Q4_K_XL porque estaba, y el propio
`assets.manifest.json` listaba Qwen3-4B por delante. Se midieron los dos sobre la
misma población, con la misma recuperación:

| | Gemma-4-E2B | **Qwen3-4B-Q4_K_M** |
|---|---:|---:|
| Decisión cruda correcta | 63/124 | **82/124** |
| Condicionada a que se le ofreciera | 63/102 = 62 % | **82/103 = 80 %** |
| Sirve de punta a punta | 49/124 | **56/124** |
| p50 / p90 / máx del camino por modelo | 2,63 / 3,59 / 7,41 s | **2,18 / 3,02 / 5,55 s** |
| Turnos por encima de 3 s | 34 de 121 | **13 de 122** |
| Fuera de catálogo, abstención honesta | 34/36 | 33/36 |

**Entra Qwen3-4B.** Gana en acierto y en reloj a la vez, y su p90 de 3,02 s se
pone por primera vez sobre el listón de 3 segundos en vez de muy por encima. Son
2,5 GB, dentro del presupuesto.

Está declarado en el manifiesto con su SHA-256
`7485fe6f…`, que es **byte a byte el modelo con el que se corrió V8** (R280 lo
registró con ese mismo hash). Cambiarlo mañana no recompila nada: se apunta a
otro binario, se corre esta medición y entra.

### El contrato de tool-call forzado, rechazado sobre población fresca

`tool_choice: "required"` se encendía si el **nombre del fichero** del modelo
contenía `qwen3`. Medido:

- gana **3** decisiones crudas (85 contra 82 de 124);
- pierde **8** abstenciones honestas (25/36 contra 33/36).

Obligar a elegir una herramienta cuando ninguna sirve es exactamente el efecto no
pedido que BAXY no admite. **Apagado, y ya no depende de ninguna cadena en una
ruta.** Esto confirma sobre población fresca lo que R277 dedujo estáticamente.

---

## 6. La puerta de dominio: la frontera, con las dos cifras

Con la recuperación arreglada y Qwen3 decidiendo, el que manda es el veto:
**pierde 27 de las 86 decisiones crudas correctas** en la corrida instalada —26
de 82 en la corrida 3—, casi todas en la etapa `domain_grounding`. El modelo
propuso exactamente lo correcto y la puerta lo convirtió en conversación:

| Petición | Propuso | Quedó en |
|---|---|---|
| «apagame el bluetooth» | `bluetooth.radio.set` | conversación |
| «sacame una foto de la pantalla» | `capture.screenshot` | conversación |
| «drop the wireless connection» | `wifi.disconnect` | conversación |
| «cual es mi direccion ip» | `network.ip.list` | conversación |
| «minimize everything I have open right now» | `window.minimize` | conversación |

Es una lista de vocabulario mantenida a mano, familia por familia, y falla justo
donde este goal mide: paráfrasis que no usa sus palabras, y inglés.

**Y no se puede quitar.** La corrida 6 la desactiva:

| | Con la puerta | Sin la puerta |
|---|---:|---:|
| Comprensión | 46,0 % | **66,9 %** |
| Abstención honesta fuera de catálogo | **33/36** | 16/36 |
| Efectos no pedidos en 36 peticiones fuera de catálogo | 3 | **20** |

Veintiún puntos de comprensión contra veinte efectos no pedidos. Los tres ceros
no se negocian, así que la puerta se queda y **el número que se publica es
46,0 %**.

### Cuatro sustitutos medidos, cuatro rechazados

El goal prohíbe escribir un sexto gate léxico. Se midió lo que no es una lista:

**1. Umbral sobre el score de recuperación.** No separa. La mediana del mejor
score es 0,849 dentro de catálogo y 0,823 fuera: **0,026 de separación** sobre
una escala que vive entre 0,81 y 0,87. Ningún umbral relativo ni absoluto deja
cero candidatos fuera de catálogo sin llevarse medio catálogo por delante.

**2. El mismo umbral con el catálogo paramétrico.** Peor: 0,012.

**3. El score de la operación *propuesta*.** Es una pregunta mejor planteada y
tampoco separa: propuestas fuera de catálogo llegan a puntuar **1,0** —el primer
puesto— mientras propuestas correctas bajan a 0,615.

| Umbral | Conserva correctas | Deja pasar fuera de catálogo |
|---|---:|---:|
| 0,60 | 62/62 | 7/7 |
| 0,80 | 54/62 | 5/7 |
| 0,90 | 49/62 | 3/7 |

**4. El verificador de compatibilidad del propio modelo**
(`_operation_is_fully_compatible`, que ya existía). Rápido —0,1–0,3 s— y peor que
la puerta: conserva **48 de 82** legítimas contra las 54 de la puerta. Rechaza
`bluetooth.radio.set` para «apagame el bluetooth», `web.search` para «busca en
internet cuánto mide el everest» y `calendar.event.list` para «qué tengo en la
agenda».

| Guarda | Conserva legítimas | Deja pasar fuera de catálogo |
|---|---:|---:|
| ninguna | 82/82 | 24/24 |
| **puerta léxica (hoy)** | **54/82** | **6/24** |
| verificador del modelo | 48/82 | 4/24 |
| las dos (Y) | 31/82 | 2/24 |
| cualquiera (O) | 71/82 | 8/24 |

Ninguna combinación compra las 26 sin pagar el invariante.

**Con esto van cuatro campañas independientes diciendo lo mismo** —R236 con BGE-M3
por familia, R250 con un clasificador directo de 32 vías, y las dos de aquí—: en
este catálogo, **el score semántico no separa dentro de fuera**. Ya no es una
hipótesis abierta.

**Por qué.** Con 158 hojas casi sinónimas siempre hay alguna que encaja
plausiblemente con cualquier petición que suene a ordenador. «Prende las luces del
living» recupera `window.active`; «formatea el pendrive» recupera
`filesystem.write.text`. No es un fallo del encoder: es la forma del catálogo.

---

## 7. El catálogo: cobertura y cuenta, y por qué no se consolidó

**La medida de cobertura se definió antes de tocar nada**, que es lo único que
permite distinguir consolidar de amputar. Cobertura es el conjunto enumerado de
cosas que la persona puede pedir: una entrada por operación autenticada que el
planner alcanza, identificada por su nombre y por el SHA-256 de su contrato
—descripción más schema—. Dos catálogos cubren lo mismo cuando toda entrada del
primero sigue alcanzable en el segundo: directamente, como acción nombrada de una
herramienta paramétrica, o como paso de una cadena.

Programa: [`measure_goal03_catalog_coverage.py`](../../experiments/mind_router_spike/measure_goal03_catalog_coverage.py).

| | Antes | Después |
|---|---:|---:|
| Operaciones | 169 | **169** |
| Alcanzables por el planner | 158 | **158** |
| Familias | 31 | **31** |
| Sello del libro de cobertura | `dc0a7893…` | **`dc0a7893…`** |

**Cuenta y cobertura, las dos, sin cambio.** Y el pass-rate de punta a punta antes
y después de tocar el catálogo es el mismo por la misma razón: **46,0 % → 46,0 %**,
porque no se tocó.

### La forma, decidida midiendo

Se comparó específica (158 hojas) contra paramétrica (una herramienta por familia,
30, con cada hoja viva como valor de `action`), con la cobertura constante por
construcción ([`compare_goal03_catalog_form.py`](../../experiments/mind_router_spike/compare_goal03_catalog_form.py)):

| Forma | Entradas | r@1 | r@3 | r@5 | r@8 | Rango medio |
|---|---:|---:|---:|---:|---:|---:|
| Específica | 158 | 0,387 | 0,637 | 0,710 | 0,742 | 10,07 |
| **Paramétrica** | 30 | **0,605** | **0,823** | **0,871** | **0,895** | **2,95** |

La paramétrica gana la recuperación con holgura. **Y aun así el catálogo no se
consolidó**, por una medición que se hizo justo para no decidir con la mitad de
los datos: la corrida 5 le da al decisor **8 candidatos en vez de 28**.

| | 28 candidatos | 8 candidatos |
|---|---:|---:|
| Recuperación ofrecida | 103/124 | 91/124 |
| Decisión cruda | 82 | 75 |
| **Condicionada a que se le ofreciera** | **79,6 %** | **82,4 %** |
| Sirve | 56 | 54 |

**El decisor no está limitado por cuántos candidatos ve.** Pasar de 28 a 8 le sube
el acierto condicionado tres puntos y le cuesta doce filas de recuperación: neto,
peor. Y ésa era la premisa entera de consolidar — que menos herramientas hacen
elegir mejor.

Así que el reparto real es éste: la forma paramétrica compraría como mucho el
hueco de recuperación que queda (103 → ~113 de 124), a cambio de mover la
desambiguación de hermanas al relleno de argumentos, que **ya está en 30,8 %**
(§8), y de arriesgar exactamente donde consolidar hizo daño la última vez —
follow-ups, multilingüe y encadenado, 75,93 % → 62,96 % en los JSON de Carter.

**Decisión: se conserva la forma específica y la cuenta actual.** La ganancia de
ranking que sí era real se obtuvo sin tocar el catálogo, rankeando operaciones en
vez de familias. La lectura de Carter se repite ahora sobre población fresca y de
punta a punta: consolidar es gratis en la recuperación y caro aguas abajo.

---

## 8. Los argumentos, medidos aparte

Elegir la operación y rellenar sus argumentos son dos peticiones distintas del
protocolo. 26 filas cuyo texto fija el valor sin ambigüedad
([`goal03_argument_expectations.v1.jsonl`](../../artifacts/development/goal03_argument_expectations.v1.jsonl),
[`measure_goal03_arguments.py`](../../experiments/mind_router_spike/measure_goal03_arguments.py)):

| Decisor | Juegos exactos | Campos correctos | Pregunta en vez de rellenar | p50 |
|---|---:|---:|---:|---:|
| Gemma-4-E2B | 9/26 (34,6 %) | 10/30 | 15/26 | 0,61 s |
| Qwen3-4B | 8/26 (30,8 %) | 9/30 | 14/26 | 0,56 s |

**La ganancia no se mudó de sitio: el relleno de argumentos estaba igual de roto
antes**, y el cambio de decisor no lo movió (la diferencia es una fila sobre 26).

Y el modo del fallo es el que V8 ya nombró: **la pregunta no aporta nada.**
«Abrime la carpeta de descargas» pregunta *«¿abrir la carpeta de descargas?»*;
«apagame el bluetooth» pregunta *«¿cuál es el estado actual?»*. Repetir una
petición ya completa no es desambiguar. Es una frontera propia, abierta, y no la
cierra este goal.

---

## 9. Los tres ceros

Intactos, y acreditados en cada artefacto de las siete corridas:

- **0 efectos no pedidos** — ningún provider habilitado, `effects_executed: 0`;
  ninguna corrida despachó nada. La corrida 6 mide 20 propuestas fuera de catálogo
  que *habrían* ejecutado sin la puerta, y por eso la puerta se queda.
- **0 éxitos no verificados** — no se afirmó ningún resultado; sólo se decidió.
- **0 respuestas visibles fijas** — se leyeron los textos visibles, no sólo las
  decisiones contractuales, y de ahí salen las filas de §8.

**V9 sigue sin abrir.** Ninguna corrida de este goal lo tocó, y con 46,0 % no hay
candidato que acreditar.

---

## 10. Qué se heredó, y de dónde

| Qué | De dónde | Cómo entró |
|---|---|---|
| **Qwen3-4B como candidato de decisor** | `assets.manifest.json` de este repositorio, que ya lo listaba **por delante** de Gemma-4 | Medido contra el heredado y promovido |
| **El SHA-256 con el que se corrió V8** | R280, `artifacts/audit/active_decision_path_r280.json` | El binario descargado coincide byte a byte: la comparación con V8 es contra el mismo modelo |
| **El precio del tool-call forzado** | R277, deducido estáticamente | Confirmado sobre población fresca, con las dos cifras |
| **La lección del benchmark 540 de Carter** | `Carter OS AI/La razon de carter/*.json`, vía el mapa del goal 01 | Es la razón de medir el pass-rate end-to-end antes de consolidar, y de no consolidar |
| **El precedente encoder-67 vs encoder-31** | `FunctionGemma/router/README_ROUTER.md`, recall 0,9521 en ambos | Sostiene que reducir el catálogo no cuesta recuperación — y por eso la recuperación **no** era el argumento para consolidar |
| **La disciplina del §7 para sellos consumidos** | `documentacion/base/00_COMPUERTA.md` del goal 02 | Aplicada a R231–R233, R277 y R280 |
| **El arnés de la campaña V8** | `run_veto_reach_v8.py` | El runner de este goal es su misma forma: sidecar, catálogo autenticado, audit del crudo |
| **Los cinco gates léxicos rechazados** | R116, R117, R124 ×2, R126 | Se respetó: no se escribió un sexto |
| **Las dos abstenciones semánticas rechazadas** | R236 (BGE-M3 por familia), R250 (clasificador de 32 vías) | Se volvió a medir con otro método y sale lo mismo; ahora son cuatro |

**Lo que no se heredó y por qué:** el router Tool2Vec de `FunctionGemma` mide
recall 0,9521 pero a granularidad de **31 herramientas**, que es la misma que la
familia — no resuelve el problema de este goal, que es la hoja dentro de la
familia. Su `abstain_head.json` sí es la pista viva y está anotada en §11.

---

## 11. Lo que este goal deja abierto, con su nombre

**El siguiente paso está identificado y tiene los datos ya mapeados en el árbol.**
Lo que falta es un detector de fuera de dominio que no sea vocabulario ni score:
un clasificador binario dentro/fuera entrenado sobre datos etiquetados. Y este
repositorio ya mapea MTOP, MASSIVE y PRESTO a familias y modos en
`src/baxy_mind/data/*_turn_evidence_map.v1.json` — **`mtop_turn_evidence_map.v1.json`
declara además `ood_intents`**, que es exactamente la etiqueta que hace falta. No
se persiguió aquí porque exige descargar y entrenar, y este goal ya tenía la
frontera medida.

Lo demás está en [`APLAZADOS.md`](../APLAZADOS.md).
