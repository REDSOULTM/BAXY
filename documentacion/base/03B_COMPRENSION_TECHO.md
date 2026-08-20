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

También se midió heredar como datos, no sólo como diseño
(`goal03_historical_family_classifier_v1.json`). Un TF-IDF de palabras y
caracteres con SVM lineal se entrenó sólo con **9.666** mensajes no duplicados
del corte histórico y su mapping versionado, nunca con el corpus fresco. Logra
**93,28 %** en las 1.934 filas de validación histórica y clasifica las 160 filas
frescas en **7,398 ms** totales, pero acierta apenas **41/124** familias; abstiene
honestamente en **31/36**. El salto entre ambas poblaciones prueba cambio de
distribución: el corpus histórico de ejemplos documentales no sirve como
entrenamiento directo para las paráfrasis coloquiales actuales. Queda rechazado
antes de darle autoridad o añadirlo al runtime.

El primer cambio de pesos que sí mueve la decisión es Qwen3.5-4B Q4_K_M
(`goal03_qwen35_minimal_policy_v4.json`, **2.740.937.888 bytes**, SHA-256
`00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4`). Con el
mismo shortlist congelado y el mismo contrato mínimo con `no_operation`, elige
una operación esperada en **91/124**, nueve más que Qwen3-4B; mide p50
**0,787 s** / p90 **0,926 s**. Aislado no es promovible: sólo produce **9/36**
abstenciones honestas. A diferencia de las variantes anteriores, no se descarta
el modelo todavía: la siguiente medida debe ser punta a punta con las puertas
vigentes, porque ellas —no esta política aislada— son dueñas de contener los
efectos no pedidos.

La medida punta a punta cierra esa promoción
(`goal03_qwen35_e2e1.json`): Qwen3.5-4B sirve **58/124** y abstiene honestamente
en **35/36**, con p50 **4,445 s** / p90 **5,702 s**. Pierde 6 filas en
reconocedor, 8 en recuperación, **45 en decisión** y 7 en veto; la decisión
cruda sólo conserva la operación esperada en **59/124**. Las puertas sí corrigen
la sobrellamada aislada, pero el contrato completo del producto es incompatible
con la mejora del selector mínimo y duplica aproximadamente la latencia. El
candidato queda rechazado y el modelo registrado no cambia.

El ranker congelado heredado (`operation_shortlist_v3`) tampoco reemplaza a E5
por sí solo (`goal03_frozen_operation_ranker_v1.json`): ofrece una operación
esperada en **50/124** a top-1, **101/124** a top-8 y **109/124** a top-28; pone
`no_action` primero en **20/36** peticiones fuera de catálogo. La señal útil es
que sus errores no son los mismos. La unión simétrica ranker+E5 recupera
**110/124** con 10 candidatos, **116/124** con 16 y **119/124** con 28. Por
primera vez el techo de recuperación supera las 112 filas sin tocar el corpus,
el catálogo ni una regla por caso. No se promueve todavía: falta demostrar que
un selector puede convertir esa cobertura en acierto sin perder abstención.

Entrenar sólo un cabezal lineal sobre el E5 vigente tampoco cobra esa cobertura
(`goal03_semantic_operation_classifier_v1.json`). Usa **4.740** paráfrasis
heredadas de FunctionGemma, 170 clases y **cero solapamientos exactos
normalizados** con el corpus fresco. Aunque valida a **98,50 %** sobre 948 filas
del mismo origen, en el corte fresco acierta **57/124** a top-1 y **117/124** a
top-28; abstiene **25/36**. Restringirlo a la unión de 16 o 28 candidatos no
cambia el top-1: 57/124. El cabezal tarda **0,904 ms** para las 160 filas una vez
obtenidos los embeddings, pero el cambio de distribución vuelve a impedir darle
autoridad.

Qwen3-8B UD-IQ2_M sí mejora simultáneamente ambas caras del selector mínimo
(`goal03_qwen3_8b_iq2_minimal_v5.json`, **3.110.897.472 bytes**, SHA-256
`1dfd67f311a5a82f57ecc1763b54884066ccf1727c45cbe1a619f85ac96368b2`).
Sobre el shortlist E5 congelado selecciona una operación esperada en **90/124**
y abstiene honestamente en **29/36**, con p50 **0,817 s** / p90 **0,866 s**.
Contra Qwen3-4B con el mismo centinela son +8 aciertos y +12 abstenciones; contra
Qwen3.5-4B conserva casi todo el acierto y gana 20 abstenciones. No se promueve
aún porque el shortlist sólo ofrece 109 hojas esperadas: la siguiente medida es
el mismo selector sobre la unión ranker+E5 de 16 y 28 candidatos.

La unión de 16 candidatos confirma que la recuperación adicional se convierte
en acierto, pero no toda (`goal03_qwen3_8b_iq2_union16_v6.json`): ofrece la hoja
esperada en **116/124**, Qwen3-8B selecciona una esperada en **97/124** y
conserva **28/36** abstenciones. El prompt más corto también baja a p50
**0,628 s** / p90 **0,677 s**. Son +7 filas contra E5-28 y menor latencia, pero
siguen faltando 15 para el listón. Añadir hasta 28 sólo puede ofrecer tres hojas
más y aumenta la ambigüedad; el siguiente experimento debe mejorar la
deliberación del selector, no seguir ensanchando la lista.

Una deliberación acotada dentro del mismo schema sí distingue cinco hojas más,
pero vuelve a abrir alcance (`goal03_qwen3_8b_iq2_reasoned_union16_v7.json`). El
modelo resume primero verbo, objeto y postcondición y después elige: sube a
**102/124**, pero baja a **23/36** abstenciones; p50 **0,753 s** / p90
**0,921 s**. De las 22 pérdidas, 8 no están en la unión y 14 son selección aun
con la hoja disponible. No se promueve ese campo: el siguiente cambio debe caer
en el reconocedor dueño de verbos inequívocos, no añadir más prosa al prompt.

El modo nativo de pensamiento con presupuesto **64** confirma que la capacidad
de deliberación importa (`goal03_qwen3_8b_iq2_think64_union16_v8.json`): sobre la
misma unión-16 sube a **105/124**, pero baja a **21/36** abstenciones y tarda p50
**1,469 s** / p90 **1,516 s**. Son ocho hojas más que la política mínima sin
pensamiento y tres más que verbalizar el efecto dentro del JSON. Aún faltan
siete; queda justificado un único escalón a 128 tokens sobre la misma población,
no una búsqueda abierta de presupuestos.

Duplicar el presupuesto a **128** tokens muestra rendimientos decrecientes
(`goal03_qwen3_8b_iq2_think128_union16_v9.json`): **108/124**, **18/36**
abstenciones, p50 **2,297 s** / p90 **2,365 s**. Compra tres filas por 0,83 s
de p50 y pierde otras tres abstenciones. La unión-oráculo de los aciertos de 64
y 128 sólo llega a **109/124** (una fila exclusiva de 64 y cuatro de 128), por
lo que votar ambas corridas tampoco alcanza. Queda una comprobación: el mismo
128 sobre unión-28, cuyo techo añade tres hojas; no se probarán más presupuestos.

La unión-28 cierra la búsqueda de la política mínima
(`goal03_qwen3_8b_iq2_think128_union28_v10.json`): ofrece **119/124**, selecciona
**109/124**, abstiene **15/36** y tarda p50 **2,428 s** / p90 **2,523 s**. Las
tres hojas adicionales del shortlist producen sólo un acierto adicional y tres
abstenciones menos. La arquitectura queda agotada en 109: más presupuesto o más
candidatos ya mostró rendimiento decreciente. Hay, sin embargo, una señal para
el producto: la corrida registrada conserva tres aciertos que este selector
pierde (`note.search`, `input.pointer.control`, `backup.known.create`), y la
unión-oráculo de ambas llega exactamente a **112/124**. Por eso la próxima
medición es Qwen3-8B dentro del pipeline completo con sus verificadores, no otro
prompt aislado.

Esa comprobación también queda cerrada
(`goal03_qwen3_8b_iq2_e2e1.json`): Qwen3-8B dentro del pipeline vigente sirve
**89/124**, abstiene honestamente en **23/36** y tarda p50 **1,774 s** / p90
**2,659 s** (camino de modelo: p50 **1,947 s** / p90 **2,694 s**). Recuperación
ofrece la hoja esperada en 110 filas, pero se pierden 4 en reconocedor, 8 en
recuperación, **18 en decisión** y 5 en `domain_grounding`; la decisión cruda
sólo conserva 89. Es +7 sobre el baseline registrado, pero -20 contra el mismo
8B como selector mínimo, así que las capas del contrato completo no realizan la
unión-oráculo de 112: vuelven a abrir la pérdida de decisión. Los tres ceros se
mantienen, pero 13/36 peticiones fuera de catálogo aún producirían una operación.
La telemetría simultánea tomó **1.638 muestras válidas cada 200 ms** bajo WDDM:
el total del sistema osciló entre 1.755 y 5.172 MiB, un incremento conservador
de **3.417 MiB**, por debajo de 4.096 MiB; WDDM no expuso memoria por proceso.
El modelo sí cabe, pero queda rechazado punta a punta por acierto y abstención.

La última fusión legítima se probó sin añadir recuperación ni reglas por fila
(`goal03_qwen3_8b_iq2_proposal_arbiter_v11.json`). Los seis selectores 8B ya
medidos tienen una unión-oráculo de **118/124** —y la misma cifra sin el baseline
registrado—, pero su pluralidad sólo da 105–107. Un segundo pase escalar con
pensamiento 128 recibe únicamente las operaciones que esos selectores propusieron:
recupera las **118**, elige correctamente **111/124**, abstiene **24/36** y añade
p50 **2,075 s** / p90 **2,212 s**. Queda una fila bajo 112 y sobrellama doce de
las 36 negativas. Esta costura queda agotada: otra variante de prompt o desempate
elegida mirando el mismo corpus dejaría de ser una comprobación fresca. El bloqueo
nuevo ya no es VRAM ni recuperación, sino un árbitro que distinga siete propuestas
sin perder al menos siete de esas doce abstenciones; no existe evidencia heredada
ni un corte fresco independiente que autorice entrenarlo o seleccionarlo aquí.

La autorización para heredar código de las escrituras anteriores permitió
recuperar una línea distinta del prompting: el selector FunctionGemma R2. El
checkpoint LoRA ya no estaba en su ruta histórica, pero el corpus ganador se
reconstruyó **byte a byte** desde el BAXY anterior: retirar sólo las 112 filas
`core-contract-authored-contrastive-v3` del corpus posterior deja **1.821 filas**
y SHA-256 `325a287fcb8797893f78aa6bf2209fcf238cdb8c56c2f1dd7001a09d8f095530`,
idéntico al recibo R2. El entrenamiento heredado cerró con las mismas 169
actualizaciones y 3.704 MiB asignados; pérdida media **0,065464** frente a
0,065826 histórica. En el control antiguo de familia-oráculo reproduce
**64/74 = 86,49 %**, una fila menos que el R2 original (65/74), con p50
**0,736 s**, p95 **0,884 s** y pico asignado **602,4 MiB**
(`goal03_functiongemma_r2_rebuild_control.json`). La señal basta para medirlo
una vez sobre la unión ranker+E5 vigente; todavía no acredita el corpus fresco,
abstención ni una integración.

La apertura única sobre el corpus fresco rechaza esa combinación
(`goal03_functiongemma_r2_union28_v12.json`). La unión ranker+E5 ofrece la hoja
esperada en **119/124**, pero FunctionGemma R2 sólo selecciona una esperada en
**63/124** y abstiene honestamente en **1/36**; p50 **0,717 s**, p90 **0,815 s**
y pico CUDA asignado/reservado **665,4/768,0 MiB**. El selector heredado aprendió
contrastes dentro de una familia, mientras que la unión-28 mezcla familias: fuera
de la distribución de entrenamiento casi siempre emite alguna tool call. El
resultado reproduce el mecanismo del rechazo histórico con shortlist realista
(52,7 % en el corte antiguo) y no se corrige apilándole el árbitro por familia,
que allí ya bajó a 48,6 %. La reconstrucción queda como evidencia, no como guard.

El siguiente patch heredado sí conserva techo antes de llamar al modelo
(`goal03_inherited_adaptive_shortlist_v13.json`). Fusionar ranker+E5 por RRF
`k=60` y aplicar la puerta original —cap 4 sólo cuando ambos ponen la misma hoja
primera y el score fusionado es al menos 0,030; cap 16 en otro caso— recupera
**114/124**, con 30 filas `high`, 94 `low` y **13,10 candidatos medios**. La
extensión histórica `TIGHT_CLUSTER` no se traslada: su cap 8 sobre desacuerdos
corroborados baja el techo a **109/124**. El 114 justifica una única inferencia
con Qwen3-8B; los umbrales vienen del patch anterior y no se calibraron contra
este corpus.

La inferencia única rechaza la puerta adaptativa como política de selección
(`goal03_qwen3_8b_iq2_inherited_adaptive_v14.json`). Aunque conserva la hoja
esperada en **114/124**, Qwen3-8B sólo elige una esperada en **99/124**, abstiene
**21/36** y tarda p50 **2,348 s** / p90 **2,436 s**. La banda `high` resuelve
28/30 con 29 hojas recuperadas, pero la banda `low` sólo 71/94 con 85
recuperadas: el recorte a 16 cambia decisiones más de lo que elimina ruido.
Frente a unión-28 gana cuatro casos y pierde catorce; su unión-oráculo llega a
**113/124**, señal complementaria pero no una regla de arbitraje autorizada. No
se promoverán estos umbrales ni se calibrarán contra el mismo examen fresco.

También se heredó literalmente el desacople propuesto por el BAXY anterior:
selección nativa con `tool_choice=required` y una tool sintética explícita de
«ningún efecto coincide», sin pensamiento ni JSON de política
(`goal03_qwen3_8b_iq2_native_no_match_union28_v15.json`). Sobre la unión-28
selecciona **100/124**, abstiene **24/36** —doce acciones indebidas— y tarda p50
**0,922 s** / p90 **1,022 s**. Gana tres filas distintas y pierde doce frente a
pensamiento-128; el oráculo de ambas llega a 112, pero no hay una señal previa
que separe esos brazos. La receta resuelve formato y latencia, no la ambigüedad
semántica entre 28 hojas, y queda rechazada para producto.

La ficha oficial de Qwen3 permitió corregir una variable que estas corridas
tenían mal fijada: desaconseja greedy en modo pensamiento y prescribe
temperatura 0,6, top-p 0,95, top-k 20 y penalización de presencia 1,5. Aplicar
ese perfil sin cambiar modelo, prompt, shortlist ni presupuesto produce
**110/124**, **18/36** abstenciones y p50 **2,478 s** / p90 **2,589 s**
(`goal03_qwen3_8b_iq2_think128_official_sampling_s0_v16.json`). Gana `aud-02`,
`win-03` y `bak-01`, pero pierde `sys-04` y `med-02`; cambia 24 decisiones y
abre 18 acciones en negativas. El +1 queda dentro de la dispersión, empeora tres
abstenciones y no autoriza un barrido ni selección por semilla. Referencia
primaria: [Qwen/Qwen3-8B-GGUF, Best Practices](https://huggingface.co/Qwen/Qwen3-8B-GGUF#best-practices).

La cuantización oficial tampoco es la hoja que faltaba
(`goal03_qwen3_8b_q4_think128_official_sampling_ngl20_s0_v17.json`). El
Qwen3-8B Q4_K_M oficial, SHA-256
`d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`, se
midió con sólo 20/36 capas en GPU para respetar recursos. Da **109/124**,
**20/36** abstenciones y p50 **8,904 s** / p90 **10,142 s**. WDDM pasó de
1.037 a un máximo observado de 4.921 MiB —incremento conservador **3.884 MiB**—
y volvió a 1.107 MiB al cerrar. Cabe, pero el offload de dieciséis capas hace
inservible la latencia y no compra calidad: gana cinco filas distintas y pierde
seis frente a IQ2; su oráculo conjunto es 115. No se probarán 64 tokens ni más
capas. El mecanismo de offload está documentado por
[llama.cpp `--n-gpu-layers`](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md#common-params),
y el modelo/quant por [Qwen](https://huggingface.co/Qwen/Qwen3-8B-GGUF).

La primera pieza de la pila heredada tampoco completa la guarda
(`goal03_inherited_router_stack_v18.json`). Se midió el despliegue coordinado de
`Probando Gemma 4`, no el bundle anterior de FunctionGemma: su
`model_int8.onnx` es byte a byte el backup señalado por el goal (SHA-256
`987091a86e004caafcbcc9d61148dc5d5851b9cac3d2a5700db810e578e4f026`) y las
cabezas/centroides/exemplars son los recalibrados del 26 de junio. En el
call-site real del planner, que pasa `intent=None` y `keyword_fired=False`, la
cabeza conserva las 124 positivas pero abstiene **0/36** negativas: sus
probabilidades quedan entre 0,019 y 0,430, siempre bajo el umbral heredado 0,68.
El planner completo también ofrece alguna tool de dominio en **160/160** filas,
por lo que superponerlo al mejor selector medido no mueve nada: sigue en
**110/124** y **18/36** abstenciones honestas.

Restituir sólo para diagnóstico las features de intención usadas por el arnés
heredado prueba que el problema no es un import roto: la cabeza entonces
abstiene 10/36 negativas, pero también 38/124 órdenes del catálogo. Como guarda
del selector oficial evita cuatro acciones indebidas y destruye 34 aciertos:
**76/124** y **22/36**. `inp-03` («type hello world for me») es uno de esos
falsos vetos, con `P(no_tool)=0,840`. El componente es muy ligero —p50 del
encoder ONNX **2,302 ms**, dot de abstención **0,015 ms**, intención+cabeza
**2,228 ms**, tool-head **0,038 ms** y planner completo **5,089 ms**—, pero no
compra la frontera pedida y queda rechazado antes de producto.

El detector deíctico del mismo stack sí marca `clp-02` («pegalo aca»), pero no
`clp-03` («what did I copy last») ni `inp-03`; estas dos últimas son peticiones
completas, no referencias sin antecedente. Además marca 13 órdenes completas
adicionales y tres fuera de catálogo. Su diseño sólo inyecta una ruta, URL o ID
extraído del resultado anterior; el corpus sellado no contiene ese resultado y
BAXY ya pide referente cuando falta, así que no puede acreditar un acierto nuevo
en este instrumento. Su coste p50 es **0,004 ms** porque las frases largas salen
antes del encoder, p90 **1,925 ms**. Se conserva como evidencia heredada, no se
copia al runtime.

El cross-encoder heredado también queda agotado con su política literal
(`goal03_inherited_mmarco_reranker_v19.json`). El historial prueba que sí tuvo
call-site en `Probando Gemma 4` (`3f2664c`): sólo se ejecutaba cuando el router
no había encontrado ninguna tool de dominio y la cabeza daba
`P(no_tool)<0,85`. El cambio posterior a router cien por cien semántico
(`406905a`) retiró ese bloque y dejó import, constante y documentación muertos;
nunca existió en producto el disparo por top-1 fusionado `[0,40, 0,65]` que
describían los informes.

Se ejecutó offline el mismo snapshot local
`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1@1427fd652930e4ba29e8149678df786c240d8825`,
CPU, longitud 128, suelo logit `-3` y top-3, leyendo la petición junto a cada
descripción tipada de la unión-28. Sin cambiar el umbral, sólo pone una hoja
esperada primera en **23/124** y dentro de top-3 en **28/124**; de las 14 filas
que falla el selector oficial rescata **0**. Como sustituto completo daría
23/124 y 20/36 abstenciones. Como el rescue literal de la versión anterior
conserva **110/124**, porque no toca decisiones existentes, pero rellena diez
vacíos fuera de catálogo y baja la abstención de 18 a **8/36**. Tampoco recupera
`clp-02`, `clp-03` ni `inp-03`: sus mejores logits son -3,816, -3,329 y -4,678,
todos bajo el suelo heredado.

El forward conjunto sobre los candidatos de una petición cuesta p50
**106,205 ms**, p90 **142,847 ms**, máximo 165,152 ms y 17,249 s acumulados en
160 turnos. El coste cabría como banda condicional, pero no compra ni una sola
de las decisiones residuales y abre alcance. Coincide con dos rechazos previos
del mismo mecanismo, no los sustituye: BGE-reranker-v2-m3 R241 conservó 256/256
positivas pero sólo abstuvo 2/256 OOS, y el verificador cruzado FunctionGemma
perdía 98 pares ya servidos y aceptaba 86–148/169 operaciones para cada encargo
sin match. No se integra ni se inventa otra banda sobre el examen fresco.

El splitter heredado sí conserva una señal útil, todavía sólo estructural
(`goal03_inherited_command_splitter_v20.json`). Con el mismo encoder ONNX y sus
parámetros literales —máximo tres cláusulas, margen acción-sustantivo 0,05 y
capa multilingüe activa— produce el número exacto de cláusulas en **7/15**
misiones del banco. Separa más de una en 8/15: cuatro ya las resolvía enteras el
producto (`cmp-b01`, `b07`, `b12`, `b14`) y cuatro son fallos actuales
(`cmp-b04`, `b05`, `b10`, `b15`). Las ocho restantes quedan subpartidas y no hay
ninguna sobrepartida; en `cmp-b12` da dos cláusulas donde el sello pide tres.

El coste es pequeño: p50 **3,015 ms**, p90 **4,534 ms**, máximo 4,857 ms y
44,586 ms para las quince. Esto no autoriza copiar sus 1.300 líneas ni afirmar
una mejora: igualdad de cantidad no prueba que cada cláusula nombre su operación
ni que sobreviva la dependencia entre turnos. Sí justifica el escalón siguiente
y único: enviar esas cuatro misiones actualmente fallidas, cláusula por cláusula,
al mind vigente con providers desactivados y medir si recupera pasos sin
inventar ejecución. Hasta ese resultado, el producto permanece en su suelo ya
cumplido de **5/15 misiones y 13/32 pasos**.

El escalón por cláusula confirma el límite antes de copiar el orquestador
(`goal03_split_clauses_v21.json`). Se enviaron sólo las ocho cláusulas de las
cuatro misiones fallidas que V20 separó exactamente, cada una como un
`turn.decide` independiente, con historial vacío, providers apagados y cero
efectos. El subgrupo pasa de **0/4 misiones y 0/8 pasos** a **1/4 y 5/8**:
`cmp-b05` nombra `app.installed` y después `app.open`; `cmp-b04`, `b10` y `b15`
reconocen la primera cláusula, pero pierden respectivamente `task.create`,
`audio.status` y `window.active` en la segunda. `b10` incluso propone la hermana
ajena `window.resize` para «después decime cómo quedó».

Ese 1/4 no se suma como un falso 6/15 punta a punta. La cláusula «if it is, open
it» nombra `app.open` sin haber observado si Discord está instalado; el probe no
fabricó el resultado anterior y por eso acredita reconocimiento, no condición,
argumentos ni ejecución. Para hacerlo real habría que trasladar también el loop
secuencial, el carry de resultados, las condicionales y sus verificaciones, no
sólo `split_command`. Cada cláusula cuesta p50 **2,555 s**, p90/máximo **4,907
s** y las ocho acumulan 20,241 s, aparte de los 3 ms del split. Como el criterio
vigente ya está exactamente verde en **5/15 y 13/32**, las leyes de arreglar sólo
lo que bloquea y retirar la capa sustituida impiden añadir ese segundo
orquestador por una ganancia no verificada. La línea compuesta queda agotada
para este goal y se conserva íntegra para el goal 07, su dueño.

El gate KVA coordinado tampoco completa la frontera
(`goal03_inherited_kva_gate_v22.json`). Se cargaron sin reentrenar el ONNX
reexportado SHA `987091a8…` y `fg/kva_gate.json` SHA `592733de…`, cuya
recalibración conjunta fijó `P(conocimiento) >= 0,89` antes de este corpus. El
guard preserva las **124/124** órdenes del catálogo, pero no corta ninguna de
las **36** negativas: superpuesto al selector oficial deja exactamente
**110/124** aciertos y **18/36** abstenciones. La negativa más próxima es
`ooc-32` («llámame un plomero para mañana») con 0,88; bajar ahora el umbral
sería ajustarlo contra el examen sellado, además de contradecir su calibración
cost-sensitive para no perder acciones. El coste sí es despreciable —encoder
p50 **2,087 ms**, cabeza p50 **0,029 ms**—, pero una capa ligera que no compra
conducta sigue siendo una capa inútil y no se integra.

También se midió el campeón heredado posterior al R2, sin escoger checkpoints
contra el corte (`goal03_functiongemma_tools_reduce_iter3_v23.json`). La
evidencia de `TOOLS_REDUCE_STATE.md` preselecciona iter3 y rechaza iter4 por
regresar conocimiento 100→50 %, acción de producción 97,5→87,5 % y contraste
90→80 %. El fichero promovido e `iter3` son idénticos, SHA-256
`c6fe7e947b24035f1286bb355d7defc010670c2dc8740c2bb42751dba46dca24`;
no se barrió ningún otro peso.

Con su contrato nativo —developer prompt publicado, greedy, `no_tool` siempre,
stop `<end_function_call>`— y la misma unión simétrica de 28 hojas actuales,
sólo selecciona una hoja esperada en **19/124** pese a recuperar 119. La causa
queda observable: el modelo fue afinado para las 110 funciones del catálogo
Tools-Reduce anterior y, ante nombres actuales, emite 88 nombres no autorizados
dentro del catálogo y sólo 36 nombres válidos; de éstos apenas 19 son correctos.
Fuera de catálogo nunca emite el sentinel literal: propone seis operaciones
actuales que sí pasarían autorización y 30 nombres inventados que el kernel
rechazaría. Esos 30 rechazos son seguros, pero no se cuentan como abstención
honesta ni como comprensión.

En CPU real (`CUDA_VISIBLE_DEVICES=-1`, `-ngl 0`) cuesta p50 **0,370 s**, p90
**0,432 s**, máximo 1,419 s y 59,519 s para 160 peticiones; el proceso se cerró
sin servidor huérfano. Adaptarlo en serio exigiría reentrenarlo o construir un
bridge semántico nuevo entre dos catálogos, después de haber quedado 19/124;
ninguna de las dos cosas es copiar una solución ya validada. Se descarta antes
de producto y se conserva el campeón intacto como evidencia.

Los bancos históricos exigidos por el goal quedan inventariados en
`goal03_inherited_eval_banks_v24.json`, sin confundir su unidad con la actual.
`_router_eval_NEWBASE_noes.txt` mide si una **familia** aparece en un subset:
1258/1280 (0,9828) en dev y 327/334 (0,9790) en holdout, con no-tool keep
395/396 y 92/92. Nuestro corte ya recupera la hoja exacta en 119/124 y falla
después al elegirla; esas cifras de familia no ofrecen un selector de hoja. Los
22 dev-fails publicados tampoco tienen solapamiento textual exacto con las 160
frases selladas ni resultados sobre sus 14 fallos de decisión actuales.

La otra mejora del banco, `_gates_ft_r2_guard5.json`, sí llevó las afirmaciones
de valor sin evidencia de 7 a 0 y se sostuvo en `deploy_smoke`, pero corre
**después** de ejecutar y validar la respuesta visible; no decide operación ni
abstención. Su solución ya está heredada con ownership más estricto:
`visible_reply_asserts_an_unread_machine_state` veta conversación que describe
una máquina no leída, `OperationOutcome.Verified` hace imposible convertir un
provider no verificado en éxito, y el narrador sólo declara éxito cuando
`Succeeded && Verified`. Copiar además el reply-validator antiguo duplicaría
la misma responsabilidad y violaría la ley 2. Los bancos quedan agotados para
03B: confirman recuperación y grounding ya cubiertos, no resuelven selección.

La memoria de exemplars nombrada por el goal queda además separada del planner
en `goal03_inherited_exemplar_router_v25.json`. Con su artefacto coordinado,
top-5, suelo 0,92, margen de abstención 0,05 y banda 0,15, sólo produce match en
**1/160**: `inp-05` («cambia el keyboard a español») a familia `input`, score
0,9463. No abstiene ninguna de las 36 negativas ni ninguna positiva y, como
guard del selector oficial, deja sin cambio **110/124** y **18/36**. Cuesta p50
**2,527 ms**, p90 2,921 ms. Bajar el suelo ahora sería calibrar contra el examen;
copiar un store que no reconoce 159 frases tampoco compra conducta. La pieza
queda agotada junto al planner que ya la servía indirectamente.

Agotadas las piezas heredadas concretas, la investigación externa acota el
siguiente cambio en vez de abrir otro guard. When2Call formula por separado
llamar, pedir información y admitir que ninguna tool sirve; su SFT usa como
mejor mezcla global **2:1** llamadas frente a no-llamada/follow-up, y la
optimización de preferencia reduce más la alucinación de tools. AgentFlux
separa selección de argumentos, calcula pérdida sólo sobre el nombre y muestra
que el mismo dataset pasa de 16 % a 61,5 % al sustituir fine-tuning general por
un selector dedicado dentro de un shortlist. SimpleToolHalluBench, por el otro
lado, encuentra que activar razonamiento incrementa la llamada de distractores.
En BAXY esto converge con la evidencia de Tools-Reduce iter3: FunctionGemma
directo, especializado en selección, con `no_action` explícito y los
distractores reales de producción; no otro prompt deliberativo ni otra puerta.

El dataset para ese único challenger ya está sellado antes de entrenar
(`goal03_functiongemma_current_union_corpus_v26.json`). Hereda el ranker del
repositorio anterior con sus pesos exactos SHA `63de7aae…`, lo une al E5 fijado
y construye cada subset con la misma política simétrica 14+14. Los positivos
provienen de `functiongemma_training_corpus.v3.jsonl` SHA `93702074…`; las
negativas son las 3.015 filas MASSIVE/PRESTO sin familia ya incluidas en
`turn_evidence_runtime.v1.jsonl`. El corpus sellado sólo se usa como conjunto
de exclusión normalizada y el solapamiento final es **0**.

Train queda en **6.922** filas —4.222 acciones y 2.700 `no_action`, 169
operaciones— y validación independiente en **784** —477 y 307—, con split SHA
determinista por operación. Las 4.699 positivas completas tenían su operación
en la unión antes de cualquier corrección (**4.699/4.699**), por lo que no se
forzó una sola hoja. Los subsets contienen 16–28 tools, media 24,051. Los JSONL
viven fuera del árbol en `D:\BAXYRuntime\experiments\functiongemma-current-union-v1`
y el repositorio conserva rutas, hashes, receta y conteos. El siguiente escalón
es una sola LoRA desde el base FunctionGemma fijado, pérdida sólo en el nombre,
muestreo 2:1 y evaluación primero en esa validación; el corte fresco no decide
hiperparámetros.

El primer arranque de esa LoRA no llegó al modelo porque el límite heredado de
1.024 tokens era menor que el máximo medido del corpus, **1.392**. El segundo,
con 1.536 y la atención por defecto del checkpoint, avanzó más de **61,4 min**
pero terminó en OOM durante `backward`; no creó directorio de salida, informe ni
pesos parciales (`goal03_functiongemma_current_union_train_v27.json`). No se
cuenta como modelo ni se cambia una sola muestra por ese fallo.

La causa se aisló sobre el ejemplo máximo, no mediante otra época: la ruta SDPA
nativa completa forward y backward de sus **1.392 tokens** con **4.748,8 MiB**
asignados y **5.586,0 MiB** reservados, pérdida 0,014474 y cero efectos. Es una
implementación equivalente de atención, no un hiperparámetro de aprendizaje.
El único reintento permitido conserva corpus, orden determinista, LoRA r16,
alpha 32, lr 2e-4, semilla 5601, una época y mezcla 2:1; sólo fija SDPA y el
límite mecánico mínimo de 1.408. La cota de 4 GB del goal sigue pendiente de la
inferencia real: esta preprueba de entrenamiento no pretende satisfacerla.

El reintento único SDPA sí completa la época y queda sellado en
`goal03_functiongemma_current_union_train_v28.json`. Entrena las **2.028** filas
balanceadas previstas —1.352 acciones, ocho por cada una de 169 hojas, y 676
`no_action`— durante **254** actualizaciones. La pérdida baja de 0,004685 a
0,000030 (media 0,025847) en **4.779,975 s**; el pico asignado interno es
**4.786,6 MiB**. La reserva WDDM/CUDA no se interpreta como requisito de
producto: el adapter pesa 15.220.968 bytes, SHA-256 `61906906…`, y su inferencia
se medirá aparte.

Los pesos viven sólo en
`D:\BAXYRuntime\experiments\functiongemma-selector-current-union-v1`; el
informe externo y la copia versionada son idénticos, SHA `b208b03e…`. No hubo
efectos ni cambio del manifiesto. La pérdida casi nula sólo prueba ajuste al
train y hace especialmente importante no mirar aún el corte fresco: el próximo
y único escalón es la validación independiente de 784 filas ya sellada.
