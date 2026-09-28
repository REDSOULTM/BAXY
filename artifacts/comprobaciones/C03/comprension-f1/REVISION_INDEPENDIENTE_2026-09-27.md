# REV1 — Revisión de código Fase 3.5b (`src/`, c3df1bea..HEAD)

Alcance: 14 ficheros de `src/` más M27 (`_music_clause_names_content`, ya confirmado en 6ddbaa01 durante la revisión) y el cambio sin confirmar de `data/decider_catalog.es.v1.json`. Las pruebas se hicieron con el Python del runtime, importando `src`. Para comparar, se sacó un snapshot de c3df1bea con `git archive` a la scratchpad. No se modificó el repositorio.

## ALTA

**A1. La reformulación del decisor es la evidencia de los argumentos y sólo se contrasta con lo dicho en los deícticos.** `__main__.py:4038-4051`, `MainWindowViewModel.cs:2440`.
`objective = decided.request` viaja a la App, y `route.Text` se sustituye por ese texto. Los argumentos se extraen y se comprueban (`value not in text`, `llm.py:17548`) contra la reformulación del modelo, no contra las palabras de la persona. `restatement_was_said` sólo se aplica si hay `_deictic_open_request`/`deictic_close_request`. `_rearm_in_context` sí pasaba `rewrite_stays_in_context` (`__main__.py:4004`), pero esa guarda no se heredó.
Entrada: «recuérdame pagar la luz». El decisor puede reformularlo como «Pon un recordatorio para mañana a las 9 para pagar la luz». Con eso, `dueUtc` queda anclado a una hora que nadie dijo. Lo comprobé: `restatement_was_said(esa reformulación, ["recuérdame pagar la luz"])` → `False`, pero no se consulta. Pasa lo mismo con el texto de un `message.send` parafraseado. Además, `request` tiene `maxLength` 300 y `max_tokens` 200, así que un dictado largo llega truncado o hace fallar el JSON.
Arreglo: anclar cada valor extraído en el texto de la persona más el historial, no en `decided.request`. Como mínimo, aplicar `restatement_was_said` a toda acción cuyos argumentos sean literales abiertos.

**A2. «Ya está, activé tu micrófono» se acepta como el fallo dicho.** `llm.py:5112`; su gemelo está en `UserMessagePolicy.cs:3349`.
`_ALREADY_STATEMENT` incluye `ya\s+esta`, que en español coloquial significa «hecho».
Ejecutado con la situación `error: microphone_already_unmuted`:
- `compose_visible_defect("Ya está, activé tu micrófono.", …)` → `''`, sin defecto.
- `_payload_fact_defect` → `''`.

El final publicado afirma una acción que no ocurrió (regla 1 de 00_IDENTIDAD). En la App pasa lo mismo porque la regex es idéntica.
Arreglo: quitar `esta|estan` (dejar «ya estaba/n», «ya era/n», «already») o vetar un verbo de efecto en primera persona («activé», «encendí», «I turned») cuando el fallo es `_already_`.

## MEDIA

**M1. `parse` elimina operaciones repetidas y el respaldo por cláusulas abre sólo la primera app.** `decider.py:161`, `arguments.py:955-964`.
- `parse('{"operations":["app.open","app.open"],…}')` → `('app.open',)`, y el turno queda como `kind=action`.
- `_explicit_arguments_from_evidence("app.open", "Abre Steam y Discord")` → `{'appId':'Steam'}`.

Discord se pierde sin que nadie lo diga. El mismo respaldo también ancla un condicional: «si se cierra steam, abre discord y chrome» → `{'appId':'Discord'}`, que se abre en el acto.
Arreglo: no deduplicar, o convertir una operación repetida en un plan con una evidencia por cláusula. En el respaldo, rechazar el caso si más de una cláusula resuelve una app o si la primera es condicional.

**M2. M27 deja de preguntar «¿qué música?» por muletillas y cortesía.** `patterns.py:5453-5477`.
`_MUSIC_GENERIC_WORDS` no incluye «porfa», «pls», «gracias», «vez», «rato», «po», «weon», «baxy» (tras una coma) ni «something». Comparado con c3df1bea (antes → ahora):
- «pon musica porfa», «pon música, gracias», «ponme musica pls», «pon musica otra vez», «pon musica un rato», «pon musica en el living», «ponle musica weon»: `clar=('media.play.query',)` → `None`.

Nada nombra qué poner, así que es justo lo contrario del título de M27. «pon la lista de exitos de los 80» se lee como «colección propia» porque `lista` está en `_MUSIC_OWN_COLLECTION`, y no nombra contenido. «put some music on» también cae, porque el head sólo reconoce `put\s+on`.
Arreglo: invertir la prueba (que quede un sustantivo o adjetivo musical, o `_desired_music_query` no nulo) o ampliar la lista de palabras vacías con la cortesía y las muletillas del corpus.

**M3. `_with_session_alarm_selector` quedó sin efecto en su propio caso.** `__main__.py:4247`, `_context_decided_result` en 4016.
Su caso (REOPEN1993 H0011, «cancelá la alarma» después de poner una) siempre ocurre dentro de una conversación. Con `in_conversation=True` el turno va al decisor, que recibe `message` (el texto original), no el `objective` reescrito. Pasa lo mismo con `dialogue_state` y `cancel_last_alarm` de `_rearm_in_context`: `_prepare_turn_result` sólo lo llama sin antecedentes, así que queda casi inalcanzable.
Arreglo: pasar `objective`/`history` reescritos a `_context_decided_result`, o retirar ambos lectores y sus pruebas.

**M4. `_not_found_invents_a_cause` rechaza la causa verdadera.** `llm.py:8018`.
- «No encontré nada porque la búsqueda no devolvió resultados.» → `True`.
- «…ya que la búsqueda no trajo resultados» → `True`.
- «…porque los resultados estaban vacíos» → `True`.

Cada caso quema los reintentos del compositor.
Arreglo: añadir `resultad|results?|busqueda|search|nada|nothing` a `_NOT_FOUND_ITSELF`.

**M5. Índice de evidencia E5 construido y nunca leído.** `__main__.py:6496`, espera en 6356.
Tras M11 ningún turno llama a `turn_evidence.retrieve` (0 usos fuera de `turn_evidence.py`). Aun así el servicio se arranca y `promote_planner_resources` espera hasta 185 s a que termine de construirse. Es CPU y RAM de arranque sin uso, lo que choca con la regla de latencia.
Arreglo: dejar de arrancarlo o documentar quién lo consume.

## BAJA

**B1. `_LIMIT_REASON` contradice una pregunta explícita por el motivo.** `llm.py:2706`.
`limit_voice_defect("No hago llamadas porque vivo en tu PC", "¿por qué no puedes hacer llamadas?")` → `limit_gives_a_reason`. Además, «since» y «ya que» coinciden en usos no causales («ya que estás…»).
Arreglo: no aplicarlo cuando el pedido pregunta «por qué/why».

**B2. Divergencia entre gemelos en `IsAlreadyStateFailure` / `_failure_is_an_unchanged_state`.** `UserMessagePolicy.cs:3376` frente a `llm.py:5115`.
- La mente pasa el código a minúsculas; C# usa `Contains` ordinal y distingue mayúsculas.
- C# recorre cualquier objeto anidado (hasta profundidad 4); la mente sólo recorre `error` y `reason`.

Con `MICROPHONE_ALREADY_UNMUTED` o un `error` anidado en `observed`, una capa acepta y la otra no.
Arreglo: aplicar la misma normalización y el mismo recorrido en las dos.

**B3. `_failure_word_is_the_persons` oculta un fallo de BAXY con causa inventada.** `llm.py:4113`.
Con «odio estos fallos», la respuesta «Estos fallos se deben a que Spotify no respondió» da `True`: el resto no contiene ningún marcador de `_asserts_failure`, así que pasa como eco.
Arreglo: exigir que lo que queda tras quitar «los fallos» no atribuya causa (`se deben|porque|because`).

**B4. `decider.parse` y `decider.messages` lanzan `AttributeError`, no `ValueError`.** `decider.py:142, 156`.
- `parse('[]')` → `AttributeError`.
- `messages("s", "x", [None])` → `AttributeError`.

El esquema estricto lo hace improbable, pero el error no es el del contrato.
Arreglo: comprobar `isinstance(raw, dict)` y `isinstance(turn, dict)`.

**B5. `_weather_location` toma por lugar una mayúscula a mitad de frase.** `system.py:50`.
- «como estara el clima para Correr» → `"Correr"`.
- «Qué tiempo hace para Ir al parque» → `"Ir al parque"`.

Antes, el primer caso daba `None`.
Arreglo: exigir que el candidato no sea un infinitivo conocido aunque lleve mayúscula, o aplicar la prueba de la mayúscula sólo a las palabras que no son `-ar/-er/-ir`.

**B6. `(?:a|na|da)\s+tela` marca como portugués el modismo español «en tela de juicio».** `patterns.py` (en `confident_non_target_language`).
«da tela de juicio» → `pt`. Es un caso raro.
Arreglo: excluir `tela\s+de\s+juicio`.

**B7. `levels`: «a level 3» pasó de ser un paso de 3 a ser el destino 3.** `levels.py:84`.
«turn volume up a level 3» daba `amount=3` y ahora da `target=3`. Parece intencional por M17; lo anoto sólo para que conste.

**B8. Contexto en la telemetría.** `FieldProductChannel.cs:1055`: la App informa cualquier `BAXY_MIND_CTX` entre 1024 y 131072, pero la mente lo recorta a 12288 (`llm.py:1748`). Con 16384 la métrica miente.
Arreglo: aplicar el mismo tope en la App.

## Código muerto / comentarios desfasados

- **D1.** `llm.py:790, 996, 1011, 1043`: `TURN_POLICY_PROMPT`, `TURN_EFFECT_REANALYSIS_PROMPT`, `SINGLE_EFFECT_SELECTOR_PROMPT` y `EFFECT_COUNT_VERIFIER_PROMPT` ya no tienen ninguna referencia en `src` (sólo en `tests/test_turn_policy.py`).
- **D2.** `__main__.py:414`: la entrada `"decide_turn": "model_decision"` de `_TURN_FAILURE_STAGE_BY_FRAME` apunta a un método retirado, y `decide_in_context` no está mapeado, así que un fallo del decisor queda sin etapa en la auditoría.
- **D3.** `__main__.py:4592-4596`: `recogniser_declined` siempre es `[]`. La etapa `recogniser_declined` (4825-4831) y el comentario rec5e2e6 están muertos.
- **D4.** `__main__.py:2369, 2395-2403`: el parámetro `already_declined` de `_catalog_answers_the_request` y su docstring sobre el «native selector» ya no reciben valor.
- **D5.** `__main__.py:63`: el import de `compound_retrieval_operation_hints` quedó sin uso. `_withheld_operation_verdict(rewrite_grounded=True)` ya no tiene ningún llamador con `True`.
- **D6.** `_served_surface_reread` (`__main__.py:2495-2512`) llama a `_decide_turn_result` sin `in_conversation`, así que en un seguimiento vuelven a correr los lectores de aclaración que F4 retiró. Además, `result.setdefault("objective", canonical)` le vuelve a poner `objective` a un resultado de conversación del que `_context_decided_result` lo había quitado a propósito (4104).
- **D7.** `decider.py` duplica literalmente el cuerpo de `rewrite_stays_in_context` en `restatement_was_said`; conviene factorizarlo.

## Cambio sin confirmar en `decider_catalog.es.v1.json`

`media.play.query` ahora dice «o una playlist». En cambio, el lector (`_MUSIC_OWN_COLLECTION`) trata «playlist/lista» como colección propia y no como contenido, así que el decisor y los lectores leen distinto la misma palabra. `web.search` pasa a decir «nunca contactos, correos ni archivos propios», que es coherente con la regla 2.

---

## Veredicto de la raíz sobre cada hallazgo (2026-09-27 22:40)

| hallazgo | verificación | acción |
|---|---|---|
| A1 la reescritura del decisor ancla los argumentos | medido: de 94 acciones del decisor en DEV-A, 4 traen números que la persona no dijo; 3 son derivaciones correctas (17:00 por «5 de la tarde», 9:50 por «diez minutos antes» de la reunión de las 10, 18:00 por «una hora antes») y 1 inventada (A-s114: 12:00 en «convierte la hora de madrid en la de londres»); 0 en las 742 y el registro real | riesgo conocido y raro; una guarda ciega rompería las derivaciones que son el motivo de la reescritura. Se anota; no se toca sin un caso real |
| A2 «Ya está, activé tu micrófono» pasa como «ya estaba» | reproducido por el revisor | **se arregla** (mente y App): «ya está» cuenta sólo seguido de un estado, nunca como interjección |
| M1 el respaldo por cláusula abre una app de un condicional | razonado (el respaldo es de M23) | **se arregla**: el respaldo no corre si hay una condición («si», «cuando», «if», «when») |
| M2 M27 toma «porfa», «gracias», «en el living», «weon» como música a poner | razonado | **se arregla** antes de que llegue a la app real |
| M4 `_not_found_invents_a_cause` veta la causa verdadera («no devolvió resultados») | razonado | **se arregla** (los resultados son el no encontrar) |
| B1 el límite sin razón aunque pregunten «¿por qué?» | razonado | **se arregla**: si la persona pregunta el porqué, la razón no es inventada por pedirla (sigue valiendo el resto del contrato) |
| B3 «Estos fallos se deben a que Spotify no respondió» pasa | razonado | **se arregla**: una causa tras los «fallos» de la persona no es su eco |
| M3, M5, código muerto, prompts huérfanos | — | limpieza de la ley 2 en F6, medida con Full |
| B2, B4–B8, catálogo «playlist» | — | B4 y la «playlist» del catálogo se atienden con M28; el resto se anota |
