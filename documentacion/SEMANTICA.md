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
2. **Patrón** (`effect_intent.py`): verbo + objeto contra el catálogo y las apps/juegos instalados. Un efecto → action,
   varios → plan, falta un dato → clarify (`resolve_explicit_clarification_intent`), límite conocido / fuera del
   mundo / charla estable → conversation. Si no cuadra, calla (`None`).
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
pedía cantidad; tiene que caer en la misma familia que la pregunta), o el clítico sustituido por el objeto del pedido
anterior; (2) modelo — `llm.rewrite_in_context` con la instrucción del tipo de dependencia, aceptado sólo si cada
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
  (`%LOCALAPPDATA%\BAXY\semantic-corpus-v1`).

## `src/baxy_mind/semantic/` — lo que ya está

| Módulo | Qué es | Regla |
|---|---|---|
| `normalize.py` | el único fold (minúsculas, sin tildes, espacios) | antes había cuatro copias idénticas en effect_intent, request_reading, llm y el hueco |
| `lexicon.py` | las palabras de cada familia, dichas una vez: micrófono (sustantivos, verbos de silenciar / activar), volumen, brillo, ajustes del PC, restaurar el sonido | el lector del patrón, la guarda de dominio, las pistas de estado del planner y el veto importan lo mismo; un sinónimo se añade una vez («micro», «prender», «devolver el sonido») |
| `grammar.py` | la gramática compartida del pedido: sobre (saludos, cortesía, «¿podés…?», «volvé a…», «ahora/luego…» + verbo), cabeza, cláusulas, negación | `_head_is` reconoce **formas**, no entradas: la cabeza tal cual, sin clíticos («cerralo» → «cerra»), y el voseo como infinitivo («cerra» → «cerrar»). Una lista de verbos ya no necesita «cerralo», «abrilo», «devolvele» |
| `dialogue.py` | el hueco de diálogo (arriba) | |

Guardas de entrada sin pedido (`__main__._unresolved_input_kind`, pasan a `dialogue` al migrar): «mensaje cortado»
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
| `normalize.py` | fold único (tildes, mayúsculas), clíticos, voseo, número en palabras, typos ≤2 contra el catálogo | `effect_intent._fold`, `request_reading.fold`, `corrector`, `dialogue_slot._fold` |
| `dialogue.py` | hueco, re-armado, guardas de entrada sin pedido (corte, habla ajena) | `dialogue_slot.py`, `__main__._unresolved_input_kind` |
| `identity.py` | qué es BAXY, qué no hace y por qué (límites de primera clase) | `request_reading` (identidad/capacidad), `known_unsupported_effect_request`, `_closed_unsupported_request` |
| dominios | `audio`, `display`, `apps`, `windows`, `media`, `web`, `files`, `messaging`, `system`, `games`, `notes_tasks`, `memory`, `network` | `effect_intent.resolve_explicit_effects` / `_strict_catalog_request` / `resolve_explicit_clarification_intent` y sus `_review_*` |

Cada dominio: tabla de formas aceptadas (rioplatense y neutro, voseo/tú, inglés, sin tildes, errores típicos del oído),
guardas (qué NO es), ejemplos como tests, y de qué BAXY anterior se heredó (ley 1).
