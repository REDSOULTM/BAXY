# La semántica de BAXY — cómo se entiende un mensaje

Borrador vivo de la Fase 3.5 (2026-09-23). Se lee en diez minutos. Si una sección dice «hoy» es el mapa verificado del
código; si dice «destino» es a dónde se está migrando (`src/baxy_mind/semantic/`). Meta vigente:
`artifacts/comprobaciones/C03/META_SEMANTICA_TOTAL_2026-09-22.md`.

## La regla que manda

> «BAXY debe funcionar de forma generalizada, no sólo para los 742 casos: esos son ejemplos de los cuales se debe
> generalizar para que BAXY siempre entienda cuando cualquier persona le hable de lo que sea.» — dueño, 2026-09-21,
> turno 164.

Un arreglo nunca es «una frase más». Se arregla la forma (una familia de verbos, una manera de apuntar al turno
anterior, una guarda que se come la charla) y se prueba con frases que el arreglo no nombra. La prueba de que
generalizó es un guion que el autor no vio mientras arreglaba (held-out). Otras dos reglas del dueño que atraviesan
todo: **lo mal dicho lo arregla BAXY** (2026-09-19: el error suele ser del oído de BAXY; se corrige con el catálogo y el
corrector antes de preguntar) y **D24** (se actúa con contexto determinista o candidato único; se pregunta sólo con
ambigüedad real).

«Entendió» (meta 2026-09-22): intención, operación y argumentos correctos, o conversación, o una sola aclaración con
ambigüedad real; y cuando BAXY no puede, **lo dice sin inventar el efecto**. Hacerlo de verdad dentro de otra app es
del motor (Fase 4/5).

## Los tres caminos, en orden (hoy)

Todo pasa por `turn.decide` → `src/baxy_mind/__main__.py::_prepare_turn_result`.

0. **Atajos del shell** (`MainWindowViewModel.TryExecuteWithMindAsync`): hora → `system.time`, conexión →
   `network.status`, saludo / «quién eres» / «sigue así» → conversación. Una confirmación pendiente la decide el
   shell (`ConfirmationReplyParser`: una respuesta hecha sólo de palabras afirmativas confirma esa invocación exacta).
1. **Hueco de diálogo** (`dialogue_slot.py` + `_rearm_in_context`). Antes de clasificar, si el mensaje depende del turno
   anterior se re-arma como pedido autónomo; ver la sección siguiente.
2. **Lectura** (`semantic.reading.read()` → `Reading`): el patrón (`semantic/patterns.py`, verbo + objeto contra el
   catálogo y las apps/juegos instalados) y las formas de enunciado que el patrón solo no lee (orden después de
   charla, destino delante, deseo de escuchar) devuelven `effects` y de qué forma salieron (`source`); un efecto
   reconocido sin su valor es `clarification`; la charla que no pide nada es `talk`. Un efecto → action, varios →
   plan, falta un dato → clarify, límite conocido / fuera del mundo / charla → conversation. Antes de la lectura
   quedan en `__main__` los lectores que necesitan el historial (una oferta pendiente, «repetilo», el pronombre de
   una búsqueda del navegador).
3. **Recuperación + modelo**: `PlannerCatalog.shortlist` (E5 consulta contra el pasaje de cada operación; ordenar
   por familia se midió y se rechazó, 73/124 contra 102/124), `llm.decide_turn` (Qwen3-4B, temperatura 0, esquema
   cerrado: conversation | clarify | action | plan sobre la lista corta). La segunda lectura sin catálogo
   (`_verify_semantic_effect_shape`) y la sonda de conversación (`turn_evidence`) **sólo pueden bajar** la clase.

Prioridad cuando varios dicen algo: efecto explícito > aclaración tipada > conocimiento / redacción > límite conocido >
modelo. Guardas que **retiran autoridad y nunca la inventan**: pregunta de información, dominio en el texto
(`operation_domain_is_grounded`), conservación de la misión compuesta, relevancia, argumentos literales,
presentación, límite fuera del mundo.

## El hueco de diálogo (clase 1, commit b280a84c)

Un turno deja como mucho un hueco. `dialogue_slot.dependency` dice por qué el mensaje lo necesita:

| Dependencia | Forma | Ejemplo de forma (no una frase a memorizar) |
|---|---|---|
| `answer` | respuesta corta o «sí» a la pregunta que BAXY acaba de hacer | «¿cuánto?» → número; «¿en Spotify?» → «no, en X» |
| `destination` | sólo cambia el lugar o la app del pedido anterior | «mejor en X» |
| `reference` | pronombre objeto pegado al verbo | «apagalo», «cerrala», «subilo a N» |
| `topic` | verbo de búsqueda sin su tema | «averiguá qué dijeron», «fijate cuándo sale» |

Re-armado, en este orden: (1) patrón — pedido pendiente + respuesta (un número se une como porcentaje si la pregunta
pedía cantidad; tiene que caer en la misma familia que la pregunta), el clítico sustituido por el objeto del pedido
anterior (o por la obra de una pregunta pública, «investigala»), o el pedido anterior con su destino cambiado («en
YouTube mejor», aceptado si `read()` lo lee como efecto); (2) modelo — `llm.rewrite_in_context` con la instrucción del tipo de dependencia, aceptado sólo si cada
palabra de contenido ya la dijo la persona o BAXY. El pedido re-armado se clasifica por el camino de siempre y vuelve
al shell como `objective`; el shell lo ejecuta y lo guarda si hace falta otra pregunta. **Un solo lector**: el shell
ya no concatena nada. Charla, «gracias» y quejas nunca se re-arman.

Lección (2026-09-22, no repetir): «cerralo» leído sin antecedente como «la ventana activa» cerró VS Code. Un pronombre
con antecedente es el objeto de ese antecedente, nunca «lo que esté delante».

## Cómo se mide

- `scripts/semantic_replay.py conv` — guiones de conversación por el conductor, con efectos reales reversibles, ventana
  guardia y comprobación de VS Code. Guiones: `contexto/dueno-2026-09-21`, `contexto/heldout-2026-09-22` (congelado),
  35 bancos por categoría.
- `scripts/semantic_replay.py literals` — sólo `turn.decide`, sin ejecutar nada (742, capas A/B/C).
- `scripts/semantic_corpus.py` — corpus por capas del histórico de todos los BAXY (filtros de idioma y destinatario,
  oráculo proyectado a familias) y puntuación por tipo de fallo. Todo lo que contiene texto del dueño es privado
  (`%LOCALAPPDATA%\BAXY\semantic-corpus-v1`). Capa A = lo dicho de verdad a BAXY (encuesta de 742 y registro real);
  B = ejemplos de los documentos de los BAXY anteriores, sólo los que tienen forma de turno (`speech_act_of`, decisión
  §12: los criterios de aceptación y notas técnicas no son turnos); C = corpus de frases dichas a asistentes (muestra de
  1 000). El oráculo de B y C es heredado y ruidoso (espera «conversación» para «silenciá el sonido»): sus
  re-etiquetas son públicas y contadas (RL1, RL2), y la capa A nunca se re-etiqueta.

## `src/baxy_mind/semantic/` — lo que ya está

| Módulo | Qué es | Regla |
|---|---|---|
| `normalize.py` | el único fold (minúsculas, sin tildes, espacios), el de palabras (`_policy_guard_text`: la puntuación es espacio) y el que conserva la puntuación (`_accent_folded_with_punctuation`) | antes había cuatro copias idénticas en effect_intent, request_reading, llm y el hueco; los dos últimos salieron de `llm` con sus lectores (2026-09-25) |
| `request.py` | la lectura única del pedido: idioma (también el de un turno de conversación y la respuesta neutra «sí/confirmar»), saludo, intenciones (identidad, capacidad, restricciones) | era `baxy_mind/request_reading.py`; pasó entera (2026-09-25). `first_signal` ya no tiene su propio lector de idioma |
| `conversation.py` | lo que se contesta hablando: acto social, «no entendí», conocimiento y factoides, aritmética, descripción, charla personal, límites cerrados, conversación estable sin efecto, app o juego no instalado; la forma de respuesta pedida (`_conversation_presentation_shape`: contenido libre, risa, directiva de conducta, deletreo, versus, sarcasmo…), el sorteo, lo que se pide repetir, y las lecturas del pedido que usan los vetos del compositor (pregunta sí/no sobre lo propio, «¿qué es esto?», cargo público actual) | salió de `__main__` y `llm` (2026-09-25). Devuelve lecturas (tipo de conversación e idioma, o si la forma está); `__main__._conversation_turn_decision` arma la decisión |
| `arguments.py` | el ligador de argumentos: los valores literales de cada operación leídos de las palabras de la persona (`_explicit_arguments_from_evidence` y sus lectores por familia, hora canónica, correferencia ordinal de un paso del plan) | salió de `__main__` (2026-09-25); `__main__._ground_explicit_arguments` lo contrasta con el esquema del catálogo |
| `lexicon.py` | las palabras de cada familia, dichas una vez: micrófono (sustantivos, verbos de silenciar / activar), volumen, brillo, ajustes del PC, restaurar el sonido | el lector del patrón, la guarda de dominio, las pistas de estado del planner y el veto importan lo mismo; un sinónimo se añade una vez («micro», «prender», «devolver el sonido») |
| `grammar.py` | la gramática compartida del pedido: sobre (saludos, cortesía, «¿podés…?», «volvé a…», «ahora/luego…» + verbo), cabeza, cláusulas, negación | `_head_is` reconoce **formas**, no entradas: la cabeza tal cual, sin clíticos («cerralo» → «cerra»), y el voseo como infinitivo («cerra» → «cerrar»). Una lista de verbos ya no necesita «cerralo», «abrilo», «devolvele» |
| `dialogue.py` | el hueco de diálogo (arriba), el antecedente del pedido y la aclaración pendiente del historial | un rechazo («no, dejalo», «mejor no», «never mind») nunca completa el pedido pendiente; «no, en YouTube» lleva destino y sí |
| `intent.py`, `catalog.py`, `temporal.py` | el tipo de lectura (`EffectIntent`), los índices de apps y juegos instalados, las palabras de tiempo | compartidos por varios dominios: ningún dominio importa de otro para esto |
| dominios | `audio`, `display`, `windows`, `media`, `web`, `files`, `games`, `network`, `system`, `notes`, `messaging`, `ui`, `apps` | los lectores acíclicos que estaban en `effect_intent` (19 140 → 13 133 líneas). Traslado puro: las 4 946 lecturas del patrón del corpus son idénticas antes y después (`pattern_dump`) |
| `levels.py` | los niveles de salida (volumen del sistema, brillo) dichos sin objeto, mezclando idiomas, secos («Brillo 20%») o como respuesta a «¿cuánto?» | no decide efectos: reescribe el pedido en la frase canónica que ya leen los lectores de volumen y brillo (`patterns.output_level_request`); una cantidad suelta sólo completa el pedido relativo inmediatamente anterior, «a 40» es el nivel final y «20» lo que se mueve; sin cantidad pregunta cuánto (H0027) |
| `surface.py` | la superficie canónica: las palabras con que la persona nombra algo servido y que ningún lector conoce («speaker/bocina/parlante» → «el audio», «hacer sonar» → «poner», «quiero/me apetece que + subjuntivo» → imperativo, «inactivar» → «desactivar», «gallery/galería» → «carpeta de imágenes», «añadir una lista» → «crea una lista», «pon en pausa» → «pausa»), con su tabla en `lexicon` | como `levels`, no decide efectos: antes de publicar un límite, `__main__._served_surface_reread` relee la reescritura con los lectores y las guardas de siempre (tanda 3, 2026-09-24) |
| `reading.py` | la puerta `read(text, …) -> Reading` y las formas de enunciado (orden con charla alrededor, destino delante, deseo de escuchar, cláusulas de una compuesta y su oferta parcial, charla que no pide nada) | `__main__._decide_turn_result` consume la lectura; el conteo «una sola resolución por turno» sigue probado (`test_turn_resolves_explicit_effects_only_once`) |
| `patterns.py` | el orquestador del patrón: `resolve_explicit_effects`, `resolve_explicit_clarification_intent`, las revisiones por dominio que se llaman entre sí, los contratos compuestos | salió entero de `effect_intent` (traslado puro, 0 diferencias en 4 946 lecturas); `effect_intent` queda como capa de re-exportación de 687 líneas mientras los llamadores migran |

**Unificación (dueño, 2026-09-24): toda lectura del pedido va a `semantic/`.** `__main__`, `llm` y los módulos de
prosa consumen lecturas; no aplican patrones propios al texto de la persona salvo para redactar (eco, cita), para
contrastar un valor con sus palabras literales o sobre el habla antes de ser pedido. Lo cuenta
`scripts/inventory_reading_outside_semantic.py` y lo exige `tests/test_reading_lives_in_semantic.py`: una lectura
nueva fuera de `semantic/` falla hasta moverla a su familia o revisar por qué no es lectura. Inventario y cifras:
`artifacts/comprobaciones/C03/UNIFICACION_LECTURA_2026-09-25.md`.

Formas nuevas (Fase 3.5, cada una con pruebas de frases que no son las que la originaron):

- **Misión compuesta con una parte imposible** (`__main__._leading_proved_clauses`, `_compound_partial_offer`): antes
  «abre Steam, ve a biblioteca y busca Batman» terminaba en «no puedo abrir Steam ni…» (el cierre de catálogo leía la
  frase entera como nombre de juego). Ahora BAXY cita las dos partes con las palabras de la persona y pregunta si hace
  la posible; un «sí» retoma sólo esa parte. No afirma que el resto sea imposible, sólo que no lo hace en ese pedido.
  Cláusulas por coordinación: heredado de Carter v4 (`mission_goal._MULTISTEP_SEPARATORS`); una cláusula cuenta si
  empieza por una orden, por lista o por la forma del imperativo (idea de Carter v3, `request_patterns.looks_imperative`),
  así «abre Ratchet y Clank» sigue siendo un nombre.
- **Orden con charla alrededor** (`_order_with_talk`): «Me encanta cómo lo definís, oye, hablando de amor, pon una canción
  de amor en YouTube» → la cola con la orden; no si lo anterior es una condición («si llueve, …») o habla citada. Y
  la orden dicha antes de la charla («para la música, me va a explotar la cabeza», tanda 3) → la orden; no si lo que
  sigue es otra orden, una condición, una corrección («digo…», «no, mejor no») o más de la misma orden («algo
  tranquilo», «al 50»).
- **Límite sólo de lo que no se sabe hacer** (`__main__._served_surface_reread`, tanda 3): antes de publicar
  «no hago eso» el turno relee la superficie canónica (`surface.py`). Lo que los lectores prueban se hace, lo que
  falta se pregunta, y una operación servida que sólo la reescritura fundamenta (la guarda de dominio curada, y
  para apps y juegos su identidad instalada) se vuelve a decidir sobre la reescritura; si el modelo vuelve a
  negarse, se pregunta la invocación exacta. Un límite de lo que BAXY no tiene («prende la smart camera», «pide un
  taxi») conserva sus palabras y sigue siendo límite. El código se escribe en la conversación
  (`conversation_only_content_request`), y restaurar o tirar una nota exige nombrar una nota. «Muéstrame la
  carpeta de imágenes» o «mis fotos» son las imágenes del PC, nunca una imagen bajada de la web
  (`web.web_image_request`).
- **Destino delante** (`_fronted_place_request`): «en YouTube pon una canción» se lee como «pon una canción en YouTube».
- **Opinión de una obra pública y hecho fechado** (`semantic/web.public_opinion_query`, `record_fact_query`):
  «¿la nueva peli de X es buena?», «¿X vale la pena?», «qué piensa la gente de X», «cuál fue el primer libro de…»,
  «cuándo sale…» → `web.search` antes de afirmar. Exige pregunta (la opinión de la persona no es un pedido), una obra con
  nombre y nada personal, deíctico ni de este PC.
- **Vocativo con otro nombre** (`grammar._ASSISTANT_NAME`): «Gemma, …», «Carter, …», «Alexa, …» son sólo la dirección.
  Gemma y Carter fueron nombres de los BAXY anteriores (`Probando Gemma 4/_tesis_curso/_rebrand_carter_to_baxy.py`).
- **El PC como objeto de silenciar** («silenciá la notebook», «unmute the pc») es el audio global; «apagá el PC» sigue
  siendo apagar. **«Sacá una captura»** a secas es una captura de pantalla. **Comilla sin cerrar** al dictar un texto
  para el portapapeles abre el literal.
- **Código interno**: la causa `request_analysis_failed` llegaba al redactor como «request analysis failed» y se leía
  en voz alta («el análisis de la solicitud falló»). Ahora tiene su hecho en `llm._CAUSE_FACT` (BAXY no entendió, no
  hizo nada, pide decirlo de otra forma) y el veto la rechaza también en castellano.
- **El pronombre tras una pregunta pública** (`dialogue.asked_about`): «¿la nueva peli de X es buena?» → «investigala»
  busca X. Sólo palabras que dijo la persona; el pedido re-armado se clasifica como siempre.
- **Lecturas que no se confirman**: la hora con calificativo o cortesía («la hora exacta, porfa»), «quiero saber /
  ¿sabés quién es X?», «qué app / proceso está activo o en primer plano». Antes llegaban al modelo, la guarda de
  dominio retiraba la operación y BAXY preguntaba «¿Quieres que te diga la hora?»; leer no cambia nada del PC (D24).
- **Charla que no pide nada** (`dialogue.talk_act`, `__main__._talk_act_turn_decision`): una afirmación en primera
  persona («me gusta crear cosas como tú», «anoche vi Oppenheimer»), una queja o comentario sobre BAXY («odio estos
  fallos», «no lo hiciste», «tus detectores no funcionan») o una reacción («jajaja qué respuesta más rara») se
  contesta como charla y conserva el historial. Nunca si hay una orden, un pedido que el patrón lee, un deseo o
  reproche que repite un pedido («yo quiero ver Netflix», «te dije que abras Spotify»), un verbo de búsqueda o, en una
  afirmación, una palabra del PC («estoy con el volumen muy alto» puede ser un pedido). Guarda del dueño 4/8 → 13/14.
- **Deseo de escuchar = orden de reproducir** (`_desired_media_request`): «quiero una canción de amor», «tengo ganas
  de escuchar a Soda Stereo», «I want to listen to…» se leen como «pon …» con las palabras de la persona.
- **Dativo con objeto dicho no es referencia** (`dialogue._object_pronoun`): «devolvele el sonido» se entiende solo;
  «devolvele» a secas sí apunta al turno anterior.
- **Verbo de búsqueda delante de la pregunta**: «fijate cuándo sale…», «averiguá qué dijo la crítica de X» piden la
  misma búsqueda que la pregunta sola.
- **Volumen**: «al mínimo» (0, como ya hacía el volumen por aplicación) y el voseo «subí/bajá … N puntos».
- **Medios y pantalla**: pausar o reanudar «el video / la peli / la serie» controla la misma sesión que la música;
  «qué dice el mensaje en la pantalla» se lee de la pantalla como «leé el mensaje de la pantalla»; oscurecer o
  aclarar la pantalla es su brillo (`display.screen_light_as_brightness`, un solo punto de normalización; sin cantidad
  pregunta cuánto); «escuchar X» con un nombre o género a secas es «pon música de X».
- **Un sinónimo, un lugar**: devolver/restaurar/recuperar el sonido se genera con sus clíticos una vez en
  `lexicon.AUDIO_RESTORE_WORDS` y lo usan el lector, el argumento (`state: false`) y las pistas del planner.
- **Niveles como se dicen** (uso real 2026-09-23, `semantic/levels.py`): «súbele un poco», «más bajito», «Volume
  más alto please», «I don't wanna hear it tan alto» preguntan sólo la cantidad; «baja un veinte por ciento»,
  «Brillo 20%», «súbelo a 80» actúan; «un 10», «20», «a 40» completan el pedido relativo anterior con su objeto y
  dirección («a 40» tras «bajá el brillo» es brillo 40: antes el modelo lo leyó como 40 menos y dejó el brillo en
  60). El pronombre sin objeto toma el del pedido anterior saltando las respuestas (`levels.followup_antecedent`
  en `_previous_user_request`); el hueco de diálogo completa estos niveles antes de pedir la reescritura al modelo.
  El silencio como interruptor («Turn off silenciar», «activá el silencio»), el sonido que vuelve («vuelve el
  sonido») y parar un ruido («¡detén este ruido!») son `audio.mute`, con sus palabras en `lexicon`.
- **Una cláusula es una orden**: en una misión compuesta el vocativo («baxy, …», «Carter, …») no es una cláusula, y
  toda cláusula —la probada y la pendiente— tiene que empezar por una orden.

Guardas de entrada sin pedido (`semantic/guards.py`, `_unresolved_input_kind`; salieron de `__main__`): «mensaje cortado»
sólo para un **pedido** (con cabeza de orden: «como tú» al final de una charla no está cortado); «habla ajena» sólo
sin conversación en curso (los literales que la justificaron llegan sin diálogo); tras ellas no queda objetivo
pendiente. Veto de efecto inventado: un turno sin operaciones no afirma un efecto (primera persona del pretérito por
forma, impersonal y pasiva sobre un objeto del PC; no la pseudo-hendida descriptiva «lo que hice fue decir…»), también
en el camino de seguimiento con historial.

## Destino: el resto de `semantic/`

Una puerta `read(text, history, catalog) -> Reading`; `__main__` y `llm` consumen la lectura, no leen texto. El
orquestador del patrón (`_strict_catalog_request`, los `_review_*`, la resolución de apps: 29 nombres que se llaman
entre sí) va a `patterns.py` al final; antes salen los lectores acíclicos de cada dominio.

| Módulo | Qué lee | De dónde sale hoy |
|---|---|---|
| `normalize.py` | fold único (tildes, mayúsculas), clíticos, voseo, número en palabras, typos ≤2 contra el catálogo | `effect_intent._fold`, `request.fold`, `corrector`, `dialogue_slot._fold` |
| `guards.py` | guardas de entrada sin pedido (corte, habla ajena, ruido, eco, ruta suelta) | ya trasladadas desde `__main__` |
| `identity.py` | qué es BAXY, qué no hace y por qué (límites de primera clase) | `request` (identidad/capacidad), `known_unsupported_effect_request`, `conversation._closed_unsupported_request` |
| lectores con historial | oferta de Wi-Fi pendiente, respuesta de lugar, pronombre de búsqueda del navegador, «repetilo», estado de una ventana nombrada antes | siguen en `__main__` antes de `read()`; pasan a `reading` cuando `read()` reciba el historial |
| `memory.py` | guardar, recordar y olvidar datos de la persona | hoy la ruta es del shell (`NaturalMemoryRequestParser`); la puntuación de capas la deja fuera |

Cada dominio: tabla de formas aceptadas (rioplatense y neutro, voseo/tú, inglés, sin tildes, errores típicos del oído),
guardas (qué NO es), ejemplos como tests, y de qué BAXY anterior se heredó (ley 1).
