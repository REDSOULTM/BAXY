# El techo de la comprensión — qué se movió, cuánto, y qué queda

Goal 03B, cerrado el **2026-08-19**. Todo lo de aquí se corrió en esta máquina
sobre el corpus de paráfrasis frescas del goal 03, **los mismos bytes**
(`artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl`, SHA-256
`761c1bc3…`, 124 dentro de catálogo y 36 fuera), sin ningún provider habilitado y
con cero efectos ejecutados.

> **El resultado en una línea:** la comprensión pasa de **45,2 %** a **66,1 %**
> —82 de 124, con 81, 82 y 84 en tres corridas de la misma configuración— y el
> techo que el goal 03 midió en **84,7 %** pasa a **89,5 %**. Lo que se movió no
> es un modelo, ni un umbral, ni el catálogo: **la puerta dejó de borrar la
> capacidad y pasó a pedir permiso.**
>
> **El 90 % sigue sin alcanzarse, y ahora la causa es otra.** Ya no es el veto:
> pierde 6 filas donde perdía 27. Lo que manda es la decisión —21 a 24 filas, y
> **8 a 11 de ellas eligen una hermana** de la operación correcta— sobre un suelo
> de 13 filas entre reconocedor y recuperación.
>
> **Y la puerta curada ya no es el techo.** Quitarla ahora compra 3 a 6 filas
> —justo en el borde del ruido de ±3 que el goal 03 midió— y cuesta **22 efectos
> no pedidos más**. En el goal 03 el mismo trato era 21 puntos contra 20 efectos.

---

## 1. Qué estaba roto, y por qué costaba tanto

El goal 03 dejó el diagnóstico hecho: cuando una etapa retira el efecto que el
modelo propuso, el turno se publica como `conversation` de tipo `unsupported`
—que significa «no está en el catálogo»— cuando lo que de verdad pasó fue «no
pude confirmar el dominio».

Medido sobre el árbol limpio antes de tocar nada
(`artifacts/development/goal03_goal03b_before.json`): **56/124 = 45,2 %**, y de
las 27 filas que el veto retira, **24 contestan «No puedo X» sobre una capacidad
que está en el catálogo** — «No puedo apagar el bluetooth», «No puedo sacar una
foto de la pantalla», «I cannot minimize everything you have open right now».

**Y un daño que nadie había atribuido.** El contrato de presentación de
`unsupported` exige una frase declarativa que nombre el pedido y afirme la
incapacidad. El modelo no la escribe de buena gana sobre algo que sí puede hacer:
**8 turnos de 160 murieron ahí** y cayeron a recuperación total, con
`unsupported_missing_anchor` y `unsupported_malformed_modal` como razones. En un
intento anterior del mismo arreglo fueron 22 de 160. El síntoma estaba diciendo
la causa: **al modelo le costaba escribir la mentira.**

---

## 2. El cambio: el veredicto deja de ser binario

Un solo principio, aplicado en los cuatro sitios que lo violaban: **BAXY no puede
afirmar una incapacidad mientras el catálogo autenticado responda al pedido.**

### a. Un efecto retirado se retiene, no se borra

`information_question` y `domain_grounding` ya no eliminan la operación. Piden una
segunda opinión independiente sobre el contrato —*¿esta operación **es** el efecto
que la persona nombró?*— y cuando lo es, la autoridad **se retiene hasta que la
persona confirme la invocación exacta**. El turno sale como `clarify`, con la
operación en `intentOperations` y una pregunta escrita por el modelo.

No se despacha ningún efecto en ninguno de los dos casos, así que el invariante
por el que existe la puerta queda intacto. Lo que cambia es que BAXY pregunta en
vez de mentir. Y es literalmente el invariante 4 del producto: **la confirmación
se liga a la invocación exacta.**

**Lo que este goal no hace, y hay que decirlo:** el shell no ejecuta todavía la
operación cuando la persona contesta que sí. `MindSidecarClient` ya acepta la
forma —`clarify` con `intentOperations` y cero efectos— y la lleva sin tocarla,
pero atar el «sí» a esa invocación exacta es trabajo del goal 05, que es el que
enciende los providers. Hasta entonces la confirmación es honesta y estéril: dice
la verdad y no hace nada.

**Esto refuta por construcción el contraejemplo que mató la exención de
`read_only`.** El goal 03 midió que exentar las lecturas daba +8 filas y lo
revirtió porque «¿Cómo está la red neuronal?» propone `network.status` y BAXY
contestaría con la conectividad del equipo. Una confirmación **no contesta**:
pregunta «¿Quieres que revise el estado de la red del equipo?», y la persona dice
que no. La puerta sigue protegiendo contra contestar del dominio equivocado; lo
que ya no hace es negar la capacidad. El contraejemplo vive en
`tests/test_turn_policy.py` como prueba de que sigue sin reabrirse.

### b. El reconocedor determinista gana una declinación

Publica las operaciones que resolvió y no rankea nada, así que cuando una regla
acierta la familia y falla la hoja, el shortlist que entrega **es** esa hoja
equivocada y todo lo de abajo la hereda. El goal 03 midió el coste —12 de 124— y
midió que mandarle sus 38 filas al camino por modelo es peor: 24 servidas contra
26. Lo que nunca tuvo fue la tercera opción: **conservar las que acierta y
declinar las que no.**

Medido antes de escribirlo, sobre sus 38 filas y con el mismo verificador:

| | El verificador acepta | El verificador rechaza |
|---|---:|---:|
| El reconocedor acertó | 22 | 2 |
| El reconocedor falló | 3 | **11** |

Once de sus catorce errores se pueden declinar a cambio de dos aciertos. Y una
fila declinada no se refuta: **cae al camino por modelo**, que es exactamente la
alternativa que el goal 03 ya midió para esas filas. Su reparto por causa baja de
12 a 5–6.

### c. Una regla cerrada ya no refuta antes de que corra la recuperación

`open the last file I downloaded` moría en la cláusula de
`filesystem.file.open.named` de `known_unsupported_effect_request`, porque su
exención lista `ultimo`, `latest`, `reciente` y `newest` **pero no `last`**,
mientras `filesystem.file.open.latest` está en el catálogo haciendo exactamente
eso. Y `what is on my to do list` se cerraba como pregunta sin efecto y se
contestaba «I don't have access to your personal to-do list» con `task.list` en el
catálogo. Cinco filas de 124 cerradas por listas de vocabulario **antes de que
nadie mirara el catálogo**: `candidate_operations` valía 0 en las cinco.

Ahora, antes de publicar una negativa cerrada —de tipo `unsupported` o
`knowledge`—, se rankea el pedido contra el catálogo autenticado y se le pregunta
al verificador si alguna operación **es** el efecto pedido. Si la hay, la negativa
se retira y decide el camino de siempre. El guarda no selecciona nada: nombrar una
operación es sólo la evidencia que retira la refutación. Los turnos sociales y de
seguimiento se dejan en paz — quien saluda a BAXY no debe pagar una consulta al
catálogo.

### d. Una respuesta de memoria no puede sustituir a una observación

`knowledge` y `social` significan «contesto con lo que sé», y contestar así una
pregunta sobre el estado actual de **esta** máquina es una observación inventada
presentada como observada. El goal 03 encontró tres y las cerró con el guarda de
efecto retirado; quedaban dos formas que ese guarda no puede ver, porque nunca se
propuso un efecto:

- *«what does this page actually say»* volvía con el contenido de la página
  inventado —«The page says that I am BAXY, a local assistant living on the
  Windows PC of the user»— mientras `browser.page.read` estaba en el shortlist;
- *«con que usuario estoy entrado»* volvía como respuesta social afirmando el
  nombre de la cuenta —«Estás en el usuario "usuario" con la PC Windows»— con
  `system.identity` en el shortlist.

Es el mismo guarda que en (c), acotado a esas dos clases. El acotamiento no es
prudencia: **ninguna petición fuera de catálogo llega a esa rama** —se refuta como
`unsupported`, no se contesta como conocimiento—, así que la abstención que podría
costar no está en este camino. Medido en las tres corridas publicadas: de las 36 filas fuera
de catálogo, 23 a 26 terminan en `unsupported` y **ninguna** en `knowledge` ni en
`social`.

---

## 3. El verificador: heredado, no nuevo

El goal prohíbe escribir un sexto mecanismo que mire la forma del texto. Éste no
la mira —lee el contrato autenticado, descripción y schema— y además ya estaba en
el árbol.

`experiments/mind_router_spike/probe_current_catalog_leaf_compatibility.py`
escribió y midió el **2026-08-02** dos preguntas distintas sobre las propuestas
crudas de R2:

| Verificador | Propuestas correctas conservadas | Propuestas equivocadas rechazadas | p50 |
|---|---:|---:|---:|
| El de producto (`OPERATION_COMPATIBILITY_PROMPT`) | 10/48 | 82/84 | 0,35 s |
| **Identidad de hoja** (`SEMANTIC_LEAF_IDENTITY_PROMPT`) | **46/48** | 21/84 | 0,24 s |

El de producto pregunta si la operación **satisface todo el pedido**, argumentos
incluidos, porque guarda una ejecución; rechaza `bluetooth.radio.set` para
«apágame el bluetooth». Ésa es la estrictez correcta para actuar y la equivocada
para decidir si BAXY puede decir que no sabe hacer algo.

El de identidad pregunta si la operación **es** el efecto que la persona nombró.
Su 21 de 84 lo descalificó como puerta de ejecución en agosto, y es exactamente lo
que lo hace utilizable aquí, donde el resultado es una pregunta y ningún efecto
puede despacharse.

Se le añadió **una** cláusula, y está medida: qué hacer cuando la persona pide
algo que la máquina sencillamente no hace —un recado físico, una compra, una
llamada, otro aparato—. El prompt original sólo sabía distinguir hojas vecinas del
catálogo, que es la mitad del problema.

| Segunda opinión | Ofrece la esperada | Ofrece otra | Sigue `unsupported` | **Fuera de catálogo ofrecidas** |
|---|---:|---:|---:|---:|
| Identidad tal cual | 24 | 12 | 7 | **3** |
| **Identidad + la cláusula** | 21 | 9 | 13 | **0** |
| El de producto | 5 | 1 | 37 | 0 |
| Identidad **y** el de producto | 5 | 1 | 37 | 0 |

Sobre las 64 filas que la puerta refuta (43 dentro de catálogo, 21 fuera).
Programa: `probe_goal03b_second_opinion_variants.py`, artefacto
`goal03b_second_opinion_variants_v2.json`.

### El séptimo mecanismo, medido y rechazado

La línea de **predicción selectiva** que el goal nombra —decidir *cuándo* no
decidir— se probó en su forma más barata y honesta: preguntarle al mismo decisor
la **contrapositiva** («¿produciría esta operación un resultado distinto del
pedido?») y exigir que la propuesta sobreviva a las dos lecturas. El modelo dice
que sí a las dos: con el prompt de desajuste, **0 de 43** filas dentro de catálogo
sobrevivían, y aun así 2 de fuera pasaban. Una segunda opinión del mismo peso con
el mismo estilo de pregunta mide la sugestión del prompt, no el alcance. Va con
los otros seis.

### Los dos sellos que este cambio movió, y cómo se cerraron

Ninguno se cerró relajando nada. Los dos son sellos que congelan un árbol y se
repinan nombrando lo que se movió, con el precedente de R277: *un commit que
cambia el árbol congelado sin repinar lo deja roto.*

| Sello | Qué pasó | Cómo se cerró |
|---|---|---|
| `test_price_v8_veto_damage_by_cause` | V8 tasó el daño del veto sobre un camino en el que el veto **borraba** la capacidad, y ese camino ya no existe | Repinados `__main__.py` y `llm.py` en `V8_PROGRAMS_REPLACED_BY_GOAL_03`, con la razón dicha en el propio fichero. Cualquier deriva no listada lo sigue poniendo rojo |
| `wake-validation-program-tree` (5 programas de `experiments/stt_quality`) | congela `experiments/voice_latency`, `scripts` y **todo `src/baxy_mind`** antes de abrir un holdout ciego de STT | Repinado de `2124b0a3…` a `b7f218e6…`, 347 ficheros Python. El evaluador de STT no ejecuta nada de lo que cambió; está anotado en `APLAZADOS.md` desde el goal 03 y volverá a dispararse |

---

## 4. Lo que se midió, corrida a corrida

| # | Corrida | Sirve | Tasa | Pierde rec/rec/dec/veto | Fuera de catálogo honesto | Ejecutarían sin pedirlo | p50 | p90 | > 3 s |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | **Antes** — el árbol tal como cerró el goal 03 | 56/124 | 45,2 % | 12/7/22/27 | 32/36 | 3/36 | 1,72 | 2,64 | 11 |
| 2 | Sólo la retención de efectos | 82/124 | 66,1 % | 12/7/20/3 | 27/36 | 4/36 | 1,96 | 2,70 | 13 |
| 3 | \+ la declinación del reconocedor | 84/124 | 67,7 % | 10/7/17/6 | 27/36 | 4/36 | 2,00 | 2,82 | 12 |
| 4 | \+ la refutación cerrada retirada | 85/124 | 68,5 % | 7/7/18/7 | 28/36 | 4/36 | 1,93 | 2,62 | 10 |
| 5 | **Tal como queda** — \+ la observación que no se recita | 81/124 | 65,3 % | 5/8/24/6 | 26/36 | 2/36 | 2,33 | 3,20 | 19 |
| 6 | La misma, repetida | 82/124 | 66,1 % | 5/8/23/6 | 26/36 | 4/36 | 2,26 | 2,97 | 14 |
| 7 | La misma, repetida | 84/124 | 67,7 % | 6/7/21/6 | 28/36 | 2/36 | 2,30 | 2,92 | 14 |
| 8 | Una variante intermedia, **con el escritorio de la persona trabajando** | 80/124 | 64,5 % | 7/7/24/6 | 26/36 | 3/36 | **4,14** | **7,14** | **119** |
| 9 | **Sin la puerta curada** | 87/124 | 70,2 % | 6/8/20/3 | **6/36** | **26/36** | 1,82 | 2,74 | 9 |

Las corridas 1–4 se midieron con el equipo tranquilo; 5–7 y 9 con Steam, Discord,
WhatsApp, tres WebViews de Edge y Chrome residentes pero ociosos; la 8 con esos
mismos programas **en uso**.

**La dispersión.** Tres corridas de la configuración publicada dan **81, 82 y 84
de 124** — el mismo ±3 que el goal 03 documentó sobre esta población. Ninguna
comparación de este documento que dependa de menos de tres filas es concluyente;
las que sí lo son —27 filas de veto a 6, 26 a 6 abstenciones honestas al quitar la
puerta, 4 a 26 efectos— están muy por encima de ese ruido.

Por idioma en la corrida 7: **es 50/73 (68,5 %)**, **en 22/35 (62,9 %)**,
**spanglish 12/16 (75,0 %)**. Antes eran 42,5 %, 37,1 % y 75,0 %. **El spanglish no
se movió**, y tiene explicación: sus filas caen dentro de la gramática del
reconocedor determinista, que no pasaba por la puerta.

### De qué está hecho el 66,1 %

De las 82 filas servidas, **50 lo son sin preguntar nada** y **32 llegan como una
confirmación**: BAXY nombra la operación exacta y pide permiso. Contar una
confirmación como comprensión es legítimo —lo que este instrumento mide es si una
paráfrasis libre llega a la operación correcta, y llega— pero el número que se
compara con el 45,2 % del goal 03 son los dos juntos, y por eso van los dos.

---

## 5. La puerta curada, con el sobreveto en los dos casos

| | Con la puerta | Sin la puerta |
|---|---:|---:|
| Comprensión | 81–84/124 | 87/124 |
| Abstención honesta fuera de catálogo | **26–28/36** | 6/36 |
| Decisiones que ejecutarían un efecto no pedido | **2–4/36** | **26/36** |
| Propuestas dentro de catálogo que retira | 48–50, **todas ofrecidas como pregunta**; 32–36 son la operación esperada | 15, retiradas por otras etapas |

En el goal 03 el trato era *veintiún puntos de comprensión contra veinte efectos
no pedidos*. Ahora es **tres a seis filas —el borde del ruido— contra veintidós
efectos**: quitarla ya casi no compra comprensión, porque la confirmación recupera
esas filas sin ella.

**Su tamaño en reglas no baja. Lo que baja es su autoridad**, de eliminar la
capacidad a retenerla, y eso es lo que la sacó del camino crítico. Retirarle
reglas sí reabriría ejecuciones —la corrida 9 dice cuántas—, así que no se le
retira ninguna, y ahora hay una medición que lo justifica en vez de una
suposición.

---

## 6. El techo, re-medido

Con la misma aritmética que publicó el goal 03: regalando decisión y vetos
perfectos, el suelo es lo que pierden el reconocedor y la recuperación.

| Tramo | Pierde de 124 (goal 03) | Pierde de 124 (hoy) | Su límite ahora |
|---|---:|---:|---|
| Reconocedor determinista | 12 | **5–6** | ya tiene cómo declinar: declina 11 de sus 14 errores y pierde 2 aciertos |
| Recuperación | 7 | 7–8 | sin tocar y sin volver a medir: el goal 03 la dejó en su techo (91,9 %) |
| Decisión | 17 | 21–24 | Qwen3-4B sigue siendo el mejor decisor local medido |
| Vetos | 31 | **6** | ya no borran: retienen |

**Techo del goal 03: 105/124 = 84,7 %. Techo de hoy: 111/124 = 89,5 %.**

El techo se movió porque uno de los dos tramos que lo fijaban dejó de ser un
suelo: el reconocedor ya puede declinar. Para 90 % siguen haciendo falta 112, así
que **incluso con decisión y vetos perfectos falta una fila**, y tendría que salir
del reconocedor o de la recuperación. La recuperación está medida en su límite; el
reconocedor pierde 5.

Y hay que decir lo que la aritmética no dice: **el tramo que hoy manda es la
decisión**, que pasó de 17 a 21–24 filas porque ahora atiende las que el
reconocedor le devuelve. No es un empeoramiento del decisor: es el mismo decisor
con más trabajo.

### El suelo, nombrado fila por fila

El techo de §6 no es una estimación: es un conjunto concreto de filas, y son **las
mismas trece en las seis corridas**, sin una sola variación. Ninguna llega al
decisor con la operación correcta disponible, así que ninguna puede servirse por
buena que sea la decisión o por mucho que se retire el veto.

| Fila | Tramo | Pedido | Esperaba |
|---|---|---|---|
| `app-01` | reconocedor | «necesito el bloc de notas» | `app.open` |
| `med-05` | reconocedor | «play the tiny desk concert on youtube» | `media.play.youtube` |
| `fs-03` | reconocedor | «hay archivos repetidos en descargas» | `filesystem.known.duplicates` |
| `per-01` | reconocedor | «qué cosas tengo conectadas al equipo» | `peripheral.list` |
| `cmp-04` | reconocedor | «anota que hay reunión el jueves y avísame ese día» | `note.create` + `reminder.create` |
| `sys-04` | recuperación | «tráncame el equipo que me voy» | `system.power` |
| `net-02` | recuperación | «see if 8.8.8.8 answers» | `network.ping` |
| `med-01` | recuperación | «para lo que está sonando» | `media.control` |
| `tsk-01` | recuperación | «agrégame al pendiente revisar el contrato» | `task.create` |
| `clp-02` | recuperación | «pégalo acá» | `clipboard.paste` |
| `clp-03` | recuperación | «what did I copy last» | `clipboard.read.text` |
| `inp-03` | recuperación | «type hello world for me» | `input.text.type` |
| `cal-02` | recuperación | «agéndame una reunión mañana de diez a once» | `calendar.event.create` |

**124 − 13 = 111, y 111 de 124 es 89,5 %.** El 90 % pide 112. Así que **≥ 90 % no
es alcanzable en este instrumento ni con un decisor perfecto y sin un solo veto**,
y no por poco: falta exactamente una fila, y esa fila tendría que salir de esta
lista.

### Los dos mecanismos que podrían moverlo, medidos y rechazados

Las trece son de dos clases y las dos tienen un candidato obvio. Los dos se
midieron.

**1. Elegir la familia antes que la hoja — la forma paramétrica.** Cinco de las
ocho filas de recuperación tienen su familia correcta entre las ofrecidas y sólo
les falta la hoja; una selección en dos etapas —familia cerrada, luego hoja dentro
de ella— las alcanzaría. Medida sobre el corpus entero: **acierta 13 de las 40
filas perdidas y rompe 10 de 30 que ya se servían**, con 1,24 s de coste por
turno. Cambia una hoja por otra sin ganar nada neto, y confirma de punta a punta
lo que el goal 03 dedujo del ranking: consolidar sale caro aguas abajo.

**2. Elegir la hoja dentro de la familia que el decisor ya nombró.** Es la mitad
barata de lo mismo, y sobre las filas perdidas parecía clara: en el sondeo previo
acertaba 9. Implementada y medida en cuatro corridas contra tres sin ella:

| | Corridas | Mediana | p50 | Abstención honesta |
|---|---|---:|---:|---|
| Sin selección por familia | 81, 82, 84 | **82** | **2,30 s** | 26, 26, 28 |
| Con selección por familia | 84, 80, 81, 85 | **82,5** | 2,62 s | 26, 26, 26, 27 |

**La mediana no se mueve y el reloj sí.** Lo que hace es trasladar filas del tramo
de decisión al de veto: elige mejor la hoja y luego la pierde confirmándola. Se
retira, por la ley 2 — una capa que no paga no se queda.

---

## 7. Los tres ceros

| | Antes | Después |
|---|---:|---:|
| Efectos ejecutados | 0 | 0 |
| Providers habilitados | no | no |
| Decisiones que **habrían** ejecutado un efecto no pedido | 3/36 | **2–4/36** |
| Estados de máquina inventados y presentados como observados | **1** | **0** |
| Respuestas visibles fijas | 0 | 0 |

Los dos estados inventados de §2.d no los introdujo este goal, y hay que decir
cómo se vio cada uno. **El contenido de la página está en la corrida de antes con
el mismo texto**, y el goal 03 no lo vio porque su guarda depende de que un veto
haya retirado un efecto y aquí nunca se propuso ninguno. **El nombre de la cuenta
apareció durante el goal**, en 2 de 6 corridas intermedias, y no por un cambio de
este goal: es el decisor, que a veces propone `system.identity` y a veces contesta
como charla — o sea que estaba latente antes y salió al repetir la medición. Las
tres corridas publicadas tienen cero de los dos.

Y ninguna de las confirmaciones lleva una palabra fija: las escribe el modelo con
un contrato acotado, y **cuando no devuelve una pregunta bien formada el turno
conserva la negativa honesta** en vez de publicar una plantilla. Una constante en
pantalla es el mismo defecto de producto diga «no puedo» o diga «¿lo hago?».

---

## 8. La latencia, y lo que cuesta el cambio

**Lo que cuesta el cambio, con el equipo en el mismo estado** (corridas 1 y 4,
ambas tranquilas): p50 **1,72 → 1,93 s**, p90 **2,64 → 2,62 s**, turnos por encima
de 3 s **11 → 10**. El decodificado extra del verificador —p50 0,15 s— se paga
sobre todo en el camino determinista, que pasa de **p50 0,007 s a 0,16 s**, y se
compensa porque las filas que antes componían una prosa `unsupported` —y a veces
la reintentaban dos veces antes de morir— ahora escriben una pregunta corta.

La configuración publicada añade dos consultas más (§2.c y §2.d) y mide p50 2,26–
2,33 s y p90 2,92–3,20 s **con el escritorio de la persona ya residente**. Contra
el número que el goal 03 publicó para su corrida instalada —p50 2,08 s, p90
3,15 s— está en la misma banda.

**Lo que cuesta el estado de la máquina** (corrida 8): p50 **4,14 s** y p90
**7,14 s**, con **119 de 160 turnos por encima de 3 s**. Es el mismo orden que
midió el goal 03 (3,7–4,0 s) y **el listón de 3 segundos sigue sin cumplirse
cuando la persona está usando el PC**, que es cuando lo va a usar.

Y un hallazgo que ahorra trabajo al que repita esto: un `llama-server` residente
con el mismo modelo **retiene VRAM pero no mueve el reloj** — medido con
`run_goal03b_loaded_latency.py`, p50 2,26 s, idéntico a las corridas sin él. Lo
que mueve el reloj es el escritorio trabajando, no la memoria ocupada. Una carga
sintética de VRAM no sustituye a la condición real.

---

## 9. Cobertura, y el banco de misiones compuestas

**Cobertura y cuenta, antes y después, sin cambio:**

| | Antes | Después |
|---|---:|---:|
| Operaciones | 169 | **169** |
| Alcanzables por el planner | 158 | **158** |
| Familias | 31 | **31** |
| Sello del libro de cobertura | `dc0a7893…` | **`dc0a7893…`** |

Este goal **no tocó el catálogo**. Todo lo que cambió está en cómo se decide sobre
él, así que la cobertura no puede haber bajado y el sello lo acredita byte a byte.

### El banco de misiones compuestas

El corpus del goal 03 no tiene una sola acción compuesta, así que se escribió el
banco que el goal pide: **15 misiones encadenadas** en los tres idiomas
(`artifacts/development/goal03b_compound_missions.v1.jsonl`), con las dependencias
implícitas que la gente usa al hablar —cabezas de secuencia, verbos elididos,
ordinales desnudos, demostrativos que apuntan a lo que creó la cláusula anterior,
condicionales y segundas cláusulas en otro idioma—, medidas por el mismo
`turn.decide`, sin providers y con cero efectos.

Las formas de cláusula se heredaron de las campañas r3–r5
(`artifacts/holdout/compound_execution_current_tree_r5.json`, 6/6 misiones y 25/25
pasos verificados). El banco es nuevo y no heredado tal cual porque **r5 es un
sello de un solo uso ya consumido** y una guarda de regresión tiene que poder
correrse dos veces.

| | Antes | Después |
|---|---:|---:|
| Misiones enteras | 3/15 | **5/15** |
| Pasos nombrados | 8/32 | **13/32** |

**No bajó: subió.** Y sube por la misma razón que sube el corpus principal — las
cláusulas cuyo efecto se retiraba ahora sobreviven como intención en vez de
desaparecer. Las dos misiones que ganó son `cmp-b03` —«busca en internet cuánto
mide el Everest y guárdalo en una nota»— y `cmp-b14`, la de segunda cláusula en
otro idioma. Ninguna se perdió.

**Y hay un coste que se ve aquí mejor que en el corpus principal:** el p50 del
banco pasa de **0,46 s a 2,83 s**. No es que se haya vuelto lento — es que antes
la mitad de estas misiones se cerraban al instante con una negativa determinista,
y una negativa es siempre más rápida que una respuesta. Construir las misiones
compuestas sigue siendo del goal 07; esto sólo comprueba que no se le dejó roto.

---

## 10. Qué se heredó, y de dónde

| Qué | De dónde | Cómo entró |
|---|---|---|
| **El verificador de identidad de hoja** | `probe_current_catalog_leaf_compatibility.py` y `artifacts/fixes/current_catalog_leaf_compatibility_semantic_r2.json`, escritos y medidos el 2026-08-02 | Promovido a producto con una cláusula añadida y medida. Su tasa de rechazo (21/84) es la razón por la que no era una puerta de ejecución y la razón por la que sirve aquí |
| **El precio de la puerta y sus cinco sustitutos rechazados** | goal 03 §6 | Se respetó: no se escribió un sexto gate léxico ni se entrenó nada |
| **El contraejemplo de la exención `read_only`** | `tests/test_turn_policy.py`, goal 03 §6 | Se comprobó que la confirmación no lo reabre, y quedó como prueba |
| **La aritmética del techo y el reparto por causa** | goal 03 §12 | Re-derivada con la misma fórmula, para que las dos cifras se comparen |
| **El arnés y el corpus** | `run_goal03_comprehension.py` | Sin cambios en el corpus ni en el marcador de filas servidas |
| **Las formas de cláusula del banco compuesto** | `build_compound_execution_current_tree_r5.py` y sus predecesores r3/r4 | El banco nuevo es re-ejecutable; el sello r5 está consumido |
| **La disciplina de repinado de sellos consumidos** | `documentacion/base/00_COMPUERTA.md` §7 y goal 03 §3 | Aplicada al libro V8, que vuelve a moverse por la misma clase de razón |

### Y del estado del arte

Buscado, leído y citado; lo que no entró dice por qué.

- **PRISMS / When2Tool** ([arXiv 2608.00218](https://arxiv.org/html/2608.00218),
  2026) — detecta el mal uso de herramientas leyendo **activaciones de neuronas
  MLP** con una sonda logística L1, ROC-AUC 0,98–1,00 para la sobrellamada y
  0,90–1,00 para la llamada que falta. Es una señal que no es la forma del texto
  ni el score de recuperación, así que **no está en la clase que el goal 03
  refutó**. No se adopta por dos razones: exige leer el interior del decisor, lo
  que rompe la frontera de proceso que hace que cambiar de modelo no recompile
  nada (`03_COSTURAS.md`) y ata la abstención a los pesos de un binario; y sus
  cifras son en su propia distribución, que es exactamente donde el clasificador
  supervisado del goal 03 daba 0,98 antes de dar 0,58 en paráfrasis libre. Es el
  candidato con más fundamento para el goal que retome el alcance.
- **XGrammar-2** ([arXiv 2601.04426](https://arxiv.org/pdf/2601.04426), 2026) — la
  decodificación restringida por gramática sube BFCL sobre todo **eliminando
  llamadas malformadas**. BAXY ya decodifica con `response_format: json_schema` y
  `strict: true` en todas las fronteras que importan, así que esa ganancia está
  cobrada. Su hallazgo útil aquí es el otro: con la restricción puesta, **los
  fallos que quedan son de argumentos, no de selección de función** — que es lo
  que el goal 03 §8 midió por su cuenta (30,8 %).
- **Constraint Tax in Open-Weight LLMs**
  ([arXiv 2606.25605](https://arxiv.org/pdf/2606.25605), 2026) — forzar salida
  estructurada **suprime la invocación de herramientas** en modelos abiertos: el
  modelo se va a una respuesta conversacional. Eso describe con precisión el
  tramo que hoy manda en BAXY: **9 a 13 filas dentro de catálogo terminan en una
  conversación que dice «no puedo» sin que ningún veto haya tocado nada**, porque
  el propio decisor eligió conversar. Su mitigación —desacoplar la decisión de
  llamar de la del formato— no se probó aquí y es la línea concreta que hereda el
  goal siguiente. Aviso al retomarla: el goal 03 ya midió y rechazó la palanca
  opuesta (`tool_choice: required`: +3 decisiones crudas, −8 abstenciones
  honestas).
- **AbstentionBench**
  ([facebookresearch](https://github.com/facebookresearch/AbstentionBench)) —
  banco holístico de abstención, 20 conjuntos y 6 escenarios. No se adoptó como
  instrumento porque su población no es este catálogo, y el goal 03 ya midió lo
  que cuesta calibrar la abstención en una distribución y usarla en otra.

---

## 11. Lo que este goal deja abierto, con su nombre

1. **El decisor se va a conversar, y ahí ya no hay veto que culpar.** 9 a 13 filas
   de 124 terminan en una conversación que niega una capacidad del catálogo sin
   que ninguna etapa haya retirado nada: «dale enter» con `input.key.press` en el
   shortlist, «llevame a wikipedia» con `browser.navigate`, «type hello world for
   me» con `input.text.type`. **Extender ahí la misma regla se midió y se
   rechazó**: los candidatos en ese punto son la recuperación de ese pedido, y
   para uno fuera de catálogo son sus vecinos plausibles — convirtió 8 de 36
   abstenciones honestas en preguntas (28 → 20) y no recuperó ni una fila
   (85 → 84). La línea viva es el desacople de §10.
2. **Las hermanas dentro de la familia son ahora el tramo dominante.** De las 21 a
   24 filas que pierde la decisión, **8 a 11 eligen una hermana**:
   `audio.volume.adjust` por `audio.volume`, `filesystem.known.search` por
   `filesystem.list`, `game.installed.named` por `app.installed`, `note.search`
   por `task.search`, `window.resize` por `window.maximize`. Es la forma del
   catálogo —158 hojas casi sinónimas—, y el goal 03 ya midió que la paramétrica
   gana la recuperación (r@5 0,871 contra 0,710) y que su premisa aguas abajo es
   falsa con el shortlist actual. Reabrirlo pide arreglar antes el relleno de
   argumentos.
3. **El relleno de argumentos sigue en 30,8 %** y no lo movió este goal.
4. **La pregunta de confirmación copia la prosa técnica del contrato** cuando la
   descripción la tiene: «¿Quieres que lea el título, la URL y el texto visible de
   la página CDP activa?». Quitarle la descripción al prompt lo arregla y **cuesta
   precisión**: sin ella el modelo promete lo que la operación no hace
   (`system.status` pasa a ofrecer «qué programas están usando memoria»). Se
   conserva la descripción porque prometer de más es peor que hablar raro.

---

## 12. El estado de los criterios de cierre, uno por uno

| Criterio | Estado |
|---|---|
| ≥ 90 % sobre el corpus del goal 03, mismos bytes, partido por causa | **No cumplido: 66,1 %** (82 de 124; 81, 82, 84 en tres corridas), y **medido imposible**: el suelo son las mismas 13 filas en las seis corridas, así que el máximo con decisión perfecta y sin vetos es 111 de 124 = 89,5 %. Reparto en §4, suelo nombrado fila por fila en §6 |
| El techo re-medido y **movido**, con la aritmética publicada | **Cumplido: 84,7 % → 89,5 %**, §6, con la misma fórmula del goal 03 |
| Las 17 filas del contrato resueltas, con el estado nuevo y su prueba | **Cumplido**: el veto pierde 6 donde perdía 27, y 8 pruebas de regresión en `tests/test_turn_policy.py` |
| Cobertura y cuenta antes y después, con el sello | **Cumplido**: 169/158/31 y `dc0a7893…` idéntico — el catálogo no se tocó |
| El banco de misiones compuestas medido antes y después: no bajó | **Cumplido**: 3/15 → 5/15 misiones, 8/32 → 13/32 pasos. Subió |
| La puerta curada más pequeña, o retirada, con el sobreveto medido en los dos casos | **Medido y publicado, §5.** No se retira ni se le quitan reglas: quitarla compra 3–6 filas y abre 22 efectos no pedidos. Lo que encogió es su autoridad |
| Latencia junto al acierto, p50 y p90, cargado y tranquilo | **Cumplido, §8**, y el listón de 3 s **sigue sin cumplirse con el equipo en uso** |
| Los tres ceros intactos, y ≤ 3–5 de 36 decisiones que ejecutarían | **Cumplido: 2–4 de 36**, y dos estados de máquina inventados que estaban abiertos pasan a 0 |
| Publicado qué se heredó y qué del estado del arte, con la fuente | **Cumplido, §10**, incluido lo que se probó y no funcionó con su mecanismo |
| Filas de `03_COSTURAS.md` rellenas | **Cumplido**: reconocedor y puerta de alcance actualizadas, y una fila nueva para el verificador de identidad |

### Por qué el 90 % no se alcanza, y cómo se sabe

No es que faltara tiempo. **El 90 % pide 112 filas de 124, y trece nunca llegan al
decisor con la operación correcta disponible** — las mismas trece en las seis
corridas, listadas una a una en §6. El máximo aritmético es 111, o sea 89,5 %:
falta una fila, y tendría que salir de esa lista.

Las dos formas de sacarla se midieron y las dos se rechazaron (§6): elegir la
familia antes que la hoja recupera 13 filas perdidas y rompe 10 que ya servían, y
elegir la hoja dentro de la familia que el decisor nombró deja la mediana igual y
sube el reloj. Lo que queda por probar no es una idea suelta: es **un decisor que
distinga hojas casi sinónimas mejor que Qwen3-4B dentro de 4 GB de VRAM**, o un
catálogo cuyas hojas no sean casi sinónimas — y el goal 03 y éste midieron, cada
uno por su lado, que consolidarlo cuesta más de lo que compra.

### Por qué se cierra sin el 90 %

El goal admite una sola salida honesta, y es más estrecha que la del 03: **haber
movido el techo y medido el nuevo**. El techo se movió de 84,7 % a 89,5 %, y el
producto se quedó en 66,1 % — así que **la arquitectura ya no es el límite
principal**, y lo que falta está nombrado y contado: 21 a 24 filas de decisión, de
las que 8 a 11 son hermanas dentro de la familia, sobre un suelo de 13 filas entre
reconocedor y recuperación.

Lo que no se puede decir es que el 90 % esté al alcance con esta forma de
catálogo. Sigue sin estarlo: aun con decisión y vetos perfectos falta una fila, y
tendría que salir de la forma del catálogo — que es donde el goal 03 y éste han
acabado los dos.

**V9 sigue sin abrir.** Ninguna corrida de este goal lo tocó.

### Retoma del 2026-08-20 — selección mínima sin alternativa explícita

Antes de tocar producto se reprodujeron los candidatos exactos de
`goal03_resume_baseline_20260820.telemetry.jsonl` contra el mismo Qwen3-4B, pero
reemplazando sólo el contrato de decisión por un objeto con
`effect_operations`. La selección cruda subió de **83 a 89 de 124** sobre 109
filas recuperadas y una sola inferencia midió **p50 0,578 s / p90 0,994 s**. No
se embarca: aunque el schema permitía el array vacío, el modelo eligió alguna
operación en las **36 de 36** peticiones fuera de catálogo — **0/36 abstenciones
honestas**. La próxima variante debe hacer explícito `no_operation`; no vale
confiar en que el modelo descubra el vacío como alternativa.

Hacer explícita esa alternativa tampoco alcanza
(`goal03_minimal_policy_no_operation_v2.json`): **82/124** selecciones correctas,
**17/36** abstenciones honestas, p50 **0,552 s** y p90 **0,678 s**, sin una sola
mezcla entre el centinela y una operación. El centinela compra abstención
quitando exactamente la ganancia de selección de la variante anterior. Las dos
formas mínimas quedan rechazadas antes de tocar producto.

Forzar una única hoja tampoco resuelve la frontera
(`goal03_scalar_policy_v3.json`). Sobre los mismos candidatos congelados selecciona
la esperada en **76/124**, conserva **19/36** abstenciones honestas y tarda p50
**0,443 s** / p90 **0,775 s**. Es más rápido y evita las listas ansiosas, pero
pierde seis aciertos frente a la política mínima con centinela y siete frente a
la decisión cruda de referencia. Queda rechazado: el error no era sólo permitir
varias operaciones, y esa simplificación tampoco justifica tocar producto.
