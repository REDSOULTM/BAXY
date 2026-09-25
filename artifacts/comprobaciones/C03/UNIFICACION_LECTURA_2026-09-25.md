# Unificación de la lectura del pedido (2026-09-25)

Punto 3 del plan de cierre del dueño (`USO_REAL_2026-09-23.md`, «Ajustes del dueño… versión final») y paso 7 de
`PROPUESTA_METODO_COMPRENSION_2026-09-25.md`: «toda lectura nueva del pedido va a `semantic/`. En la verificación se
listan los regex que leen texto del usuario fuera de `semantic/` y se mueven, o se explica por qué son de redacción».
Base: `b0190b9e`. Conducta idéntica: los traslados no cambian ninguna decisión (prueba abajo).

## Cómo se cuenta

`scripts/inventory_reading_outside_semantic.py` encuentra cada patrón fuera de `src/baxy_mind/semantic/` (mente) y en
`src/Baxy.App` (`re.*`, métodos de un patrón compilado, `_has`/`_match` de la gramática, `Regex.*` y regex generadas
de C#) y sigue su argumento hasta un parámetro —dentro de la función y por cada llamador de la mente— para saber de
quién es el texto: de la persona, de BAXY (borrador, respuesta, pregunta) u otro dato (hash, ruta, observación,
catálogo). Cada función que aplica un patrón a las palabras de la persona lleva una clase revisada:

| Clase | Qué es | ¿Puede quedarse fuera de `semantic/`? |
|---|---|---|
| READING | decide qué pidió la persona | no: va a su familia en `semantic/` |
| WORDING | las palabras de la persona son material de la respuesta de BAXY o de su control (un eco rechazado, una cita, un ancla) | sí |
| GROUNDING | las palabras de la persona son la evidencia literal contra la que se contrasta un valor propuesto (un número, un nombre, un identificador que la persona dijo puede repetirse) | sí |
| INPUT | habla antes de ser pedido (palabra de activación, transcripción, corrector del oído) | sí |
| INDEX | tokens para un índice léxico (pasajes de skills); ningún patrón decide un significado | sí |
| MIRROR | la App aplica, a lo que publica, guarda o ejecuta, una regla cuya lectura también hace la mente | sí, con su porqué |

`python scripts/inventory_reading_outside_semantic.py --root <árbol>` cuenta cualquier árbol (la base se contó sobre
un extracto de `b0190b9e`); `--write` regenera la parte generada de este fichero; `--check` falla si aparece una
lectura del texto de la persona sin revisar. `tests/test_reading_lives_in_semantic.py` lo exige: una lectura nueva
fuera de `semantic/` no pasa hasta moverla a su familia o escribir por qué no es lectura.

## Cifras

| | Base `b0190b9e` | Ahora |
|---|---|---|
| Patrones en la mente fuera de `semantic/` | 1 063 | 747 |
| … aplicados a las palabras de la persona | 354 sitios en 106 funciones | 46 sitios en 31 funciones |
| … de ellos, lectura del pedido (READING) | 75 funciones sin revisar, lectura en `__main__`, `llm`, `request_reading`, prosa | **0** |
| Patrones en la App | 248 | 248 (sólo cambió un comentario) |
| … aplicados a las palabras de la persona | 121 sitios en 46 métodos | igual, cada fichero con su clase y su porqué |

- **Inventariados:** 1 311 patrones (1 063 de la mente fuera de `semantic/` + 248 de la App); 475 sitios leen las
  palabras de la persona (354 + 121), en 152 funciones o métodos.
- **Movidos a `semantic/`:** 308 sitios de 75 funciones de la mente (lista abajo); los 34 de `request_reading.py`
  van incluidos (el módulo entero).
- **Borrados por duplicado (5):** el segundo lector de idioma de `first_signal` (con sus dos listas de pistas); el
  vocabulario del cargo público actual escrito en `__main__` y en `llm` (una lectura, `names_a_current_public_office`);
  el patrón «si no pasó / if it didn't happen» escrito dos veces en `llm` (`_NON_EVENT_CONFIRMATION`); «hora/time» en una
  pregunta de fecha, dos copias (`names_the_time`); «cierr/close», dos copias (`asks_to_close`).
- **Se quedan en la mente como no-lectura:** 31 funciones, 46 sitios: GROUNDING 17 (26), WORDING 6 (9), INPUT 7 (10),
  INDEX 1 (1). El porqué de cada una está en la tabla generada.
- **Lectura que queda fuera de `semantic/`:** en la mente, ninguna. En la App, 14 métodos READING (62 sitios) en los
  cinco parsers de rutas propias (memoria privada, notas rápidas, hora, apertura de apps, audio) y 28 métodos MIRROR
  (51 sitios: la política sobre lo publicado, la confirmación exacta de una operación de memoria, la elección entre
  notas listadas, la negativa a guardar secretos). El porqué va por fichero en la tabla; resumen abajo.

## Dónde fue cada lectura

| Destino | Lo que llegó |
|---|---|
| `semantic/request.py` | `request_reading.py` entero (`git mv`); el idioma de un turno de conversación y la respuesta neutra de idioma («sí», «confirmar»), de `llm` |
| `semantic/conversation.py` | de `__main__`: acto social, «no entendí», pregunta por el cargo actual, deseo sobre BAXY, pedido deíctico sin referente, factoide, aritmética, descripción de un concepto, charla personal, límite cerrado, conversación estable sin efecto, app o juego no instalado, observación en primera persona, palabra de pregunta. De `llm`: la forma de respuesta pedida y sus señales (contenido libre, risa, directiva de conducta, «cómo funciona», vocativo equivocado, tranquilización, deseo ofrecido, versus, sarcasmo, deletreo, respuesta extensa, observación, participantes de un rol), el sorteo pedido, lo que se pide repetir, «si no pasó», el asentimiento sin acción, la pregunta sí/no sobre lo propio, «¿qué es esto?», el nombre de BAXY pedido, dos acciones coordinadas, el verbo del pedido ambiguo, la frase citada para traducir, el cargo público actual |
| `semantic/dialogue.py` | el antecedente del pedido y la aclaración pendiente del historial (`__main__`) |
| `semantic/arguments.py` | el ligador de argumentos de `__main__` (`_explicit_arguments_from_evidence` y 27 definiciones más: alcance del estado del sistema, destinatario, título del recordatorio, consulta en vivo, navegación, wifi, notificación, recordatorio relativo, agenda, control de medios, presentación, notas enumeradas, correferencia ordinal, hora canónica) y lo que leían sus pasos: idioma de OCR, prompt exacto de visión, «que» del título, Spotify nombrado, cierre de la ventana activa |
| `semantic/messaging.py` | el cuerpo del mensaje de `message.send`; el envío por WhatsApp/Discord que conserva la guarda de dominio |
| `semantic/network.py` | día de la semana y valor de calendario preguntados (con el vocabulario de meses y días), «hora/time», la hora pedida |
| `semantic/web.py` | lluvia, mañana, hoy y esta tarde en el tiempo; lo que nunca es búsqueda pública (`not_a_public_lookup`, antes `__main__._names_own_data`) |
| `semantic/apps.py` | cerrar, el objeto a cerrar, instalar o desinstalar, trabajar en un programa |
| `semantic/display.py`, `notes.py`, `media.py`, `audio.py`, `ui.py`, `system.py`, `windows.py` | monitores (resolución, Hz, cuántos); título nombrado y almacén propio nombrado; qué suena; silenciar; botones y ver la pantalla; la GPU dejó de funcionar, sólo el conteo de procesos, CPU acumulada; foco, tamaño, cuántas ventanas e inventario por nombre (`window_prose_facts` y `measurement_prose_projection` consumen) |
| `semantic/normalize.py` | los pliegues de palabras y con puntuación que usaban esos lectores |

Los lectores que devolvían una decisión de turno ahora devuelven lo que leyeron (tipo de conversación e idioma, o si
la forma está); `__main__._conversation_turn_decision` arma la decisión. Los vetos, proyecciones y prompts de `llm`
consumen las lecturas por su nombre en vez de releer el texto.

## Prueba de conducta idéntica

- **Réplica determinista** (sin modelo ni GPU, `PYTHONHASHSEED=0`, reloj congelado) de los 1 257 mensajes de las 25
  tandas (74 conversaciones con su hueco de diálogo real), base contra cada paso: lectura (`reading.read`), turno
  completo (`_prepare_turn_result` con un modelo mudo: 724 conversación, 364 acción, 8 plan, 161 fallos del modelo mudo),
  argumentos de la App (`_ground_explicit_arguments`, `_stated_argument_fields`: 798), 67 lectores uno a uno (84 219
  sondas), y 2 337 borradores grabados del compositor (`compose_visible_defect`, `_payload_fact_defect`, con y sin el
  texto de la persona, `window_fact_feedback`, `_compose_situation_payload`, `_compose_shape_instruction`); más 28 911
  sondas de los vetos, proyecciones y pasos tocados. **0 diferencias** en cada paso, salvo lo esperado: el idioma de
  `first_signal` (221 mensajes; era el lector duplicado, sólo lo usa su fixture) y dos ruidos de reloj que la sonda
  no congela (el tema de curiosidad se sortea por hora; los temporizadores relativos antes de congelar la hora).
- **pytest completo** (intérprete de la mente, sin xdist): base `b0190b9e` 22 fallos + 22 errores, 18 768 pasan;
  ahora 23 fallos + 22 errores, 18 767 pasan, 11 skips ambientales. Los 44 de la base son los mismos (corpus
  históricos y sondas ausentes del worktree, `test_stt_quality_evaluators`); el único nuevo es el sello de fuentes
  `test_price_v8_veto_damage_by_cause` (SHA-256 de `__main__.py` y `llm.py`), que re-ancla la raíz. Más
  `tests/test_reading_lives_in_semantic.py` (3 pasan).
- **ruff** limpio en `src/baxy_mind`, `tests` y los scripts tocados.

## Lo que queda en la App, y por qué

- **Rutas propias (READING):** `NaturalMemoryRequestParser` (memoria privada: guardar, recordar, olvidar; SEMANTICA la
  destina a `semantic/memory.py`), `NaturalNoteRequestParser` (notas rápidas), `NaturalSystemStatusRequestParser`
  (atajo de la hora sin ida y vuelta a la mente), `NaturalApplicationRequestParser`, `NaturalAudioRequestParser`. La
  mente ya lee esos mismos pedidos: son dos lectores de lo mismo. Retirarlos exige que la App tome la decisión de la
  mente para esos turnos (un cambio de ruta y de protocolo que se mide en la ventana oficial), no un traslado de
  conducta idéntica; se dejan anotados para esa tanda.
- **Espejos (MIRROR):** `UserMessagePolicy` es la política de la App sobre todo texto que publica, también sus propias
  respuestas de respaldo: juzga si una respuesta contesta lo pedido, así que lee el pedido con gemelos de los lectores
  de la mente (partes del calendario, cuenta atrás, clítico de volumen, contenido visual, fuera del mundo). Consumir la
  lectura de la mente necesita que el resultado de `message.compose` la traiga. `MemoryOperationProtection` (confirmar
  o cancelar la invocación exacta, invariante 4; no guardar secretos) y `NoteDisambiguation` (la elección entre las
  notas que la App listó) atan la respuesta de la persona a lo que la App tiene pendiente.
- **Entrada (INPUT):** `VoiceListenCommand`, el interruptor de escucha, que funciona sin la mente.

## Hallazgos para la raíz

- `asr_fusion.py` no lo importa el producto (sólo sus pruebas y un script de revalidación): candidato a `APLAZADOS`.
- `first_signal.formulate_progress` sigue siendo un fixture con prosa fija («Sigo con…»); el producto no lo llama
  (`test_goal06_voice` lo exige). Ahora usa el único lector de idioma.
- La pista del compositor para un cierre lee «cerrá» (voseo) y el control del cierre no (`asks_to_close(voseo=True)`
  frente a `asks_to_close`): se conservó tal cual para no cambiar conducta; unificarlo es una decisión a medir.
- Los sellos `test_price_v8_veto_damage_by_cause` y `test_stt_quality_evaluators` se re-anclan en la raíz.

## Inventario generado

<!-- inventario:inicio (generado por scripts/inventory_reading_outside_semantic.py --write) -->

```json
{
 "regex_sites": {
  "mind_outside_semantic": 747,
  "app": 248
 },
 "sites_on_the_person": {
  "mind_outside_semantic": 46,
  "app": 121
 },
 "functions_on_the_person": {
  "mind_outside_semantic": 31,
  "app": 46
 },
 "functions_on_the_person_by_class": {
  "GROUNDING": 17,
  "INDEX": 1,
  "INPUT": 7,
  "MIRROR": 28,
  "OTHER": 3,
  "READING": 14,
  "WORDING": 7
 }
}
```

**Mente, fuera de `semantic/`**: cada función que aplica un patrón a las palabras de la persona.

| Fichero | Función | Líneas | Clase | Por qué |
|---|---|---|---|---|
| `asr_fusion.py` | `_exhaustive_report_language` | 62, 63, 67, 68 | INPUT | selection between ASR hypotheses; the product does not import asr_fusion (tests and a revalidation script do): a candidate for APLAZADOS, not a reader of the turn |
| `asr_fusion.py` | `_terminal_status_effect` | 190 | INPUT | selection between ASR hypotheses (not imported by the product) |
| `corrector.py` | `unintelligible_input` | 315 | INPUT | the noise check of the ear's repair, consumed by semantic.guards; decides no intention |
| `corrector.py` | `unknown_words` | 296 | INPUT | the ear's repair (lo mal dicho lo arregla BAXY): words checked against the catalog lexicon before any reading; decides no intention (module contract) |
| `voice.py` | `WakePhraseMatcher.strip` | 358 | INPUT | the transcript before it is a request: wake-word and listening checks run on speech, not on a request |
| `wake_cascade.py` | `normalize_lexical_transcript` | 570 | INPUT | the transcript before it is a request: wake-word and listening checks run on speech, not on a request |
| `wake_verifier.py` | `lexical_words` | 489 | INPUT | the transcript before it is a request: wake-word and listening checks run on speech, not on a request |
| `skill_registry.py` | `_token_sequence` | 337 | INDEX | the request tokenized to rank skill passages lexically; no pattern decides a meaning |
| `llm.py` | `_literal_reply_defect` | 2323 | GROUNDING | a number in the reply of a said-back literal or a draw must be one the person said |
| `llm.py` | `_ocr_unsupported_terms.stems` | 7822 | GROUNDING | a word of the screen report must be read on screen or said by the person |
| `llm.py` | `_screen_count_defect` | 7319 | GROUNDING | a number the person said may be repeated |
| `llm.py` | `_search_report_off_subject` | 8375 | GROUNDING | the proper names the person wrote are the subject the report must be about |
| `llm.py` | `_search_report_shows_the_search` | 8320 | GROUNDING | the person's words (and the pages read) are the evidence each word, number or name of the search report is checked against; nothing decides what was asked |
| `llm.py` | `_search_report_speaks_as_a_page` | 8222 | GROUNDING | the person's words (and the pages read) are the evidence each word, number or name of the search report is checked against; nothing decides what was asked |
| `llm.py` | `_search_report_unsourced_numbers` | 8038, 8041 | GROUNDING | the person's words (and the pages read) are the evidence each word, number or name of the search report is checked against; nothing decides what was asked |
| `llm.py` | `_search_report_unsourced_words` | 8087 | GROUNDING | the person's words (and the pages read) are the evidence each word, number or name of the search report is checked against; nothing decides what was asked |
| `llm.py` | `_shaped_conversation_answer_violates_contract` | 2701 | GROUNDING | a maker or origin the person named is theirs to repeat (_INVENTED_ORIGIN on both texts); what was asked comes from semantic.conversation readers |
| `llm.py` | `_unverified_present_fact` | 10499 | GROUNDING | a date or figure about now may only restate what the person said or what was read |
| `llm.py` | `_weather_fact_defect` | 8805 | GROUNDING | a number the person said is theirs to repeat, never a measurement; what the weather question asks is read by semantic.web |
| `llm.py` | `compose_visible_defect` | 10536, 10752, 10754, 11055, 11639 | GROUNDING | identifiers and literals the person typed are allowed in the reply, and an echo of the request is rejected; every reading of what was asked is a semantic reader it calls |
| `llm.py` | `visible_reply_claims_an_effect` | 3732 | GROUNDING | a claimed act that repeats the person's own words is not invented (asked_words) |
| `planner.py` | `_grounding_tokens` | 1018 | GROUNDING | a value the model proposed is accepted only when the person's words contain it literally |
| `planner.py` | `_number_is_grounded` | 1180, 1184 | GROUNDING | a value the model proposed is accepted only when the person's words contain it literally |
| `planner.py` | `_tokens` | 1012 | GROUNDING | a value the model proposed is accepted only when the person's words contain it literally |
| `planner.py` | `_value_is_grounded` | 1145, 1150, 1155, 1161 | GROUNDING | a value the model proposed is accepted only when the person's words contain it literally |
| `first_signal.py` | `_snippet` | 79 | WORDING | the request quoted in the fixture's progress line |
| `llm.py` | `LlmRuntime.clarify_unresolved_input` | 17288, 17412 | WORDING | the question BAXY writes must not echo the person's words (echo check); the kind of input was read by semantic.guards |
| `llm.py` | `_bare_path_name` | 12763 | WORDING | the file name of a pasted path, quoted back in the question |
| `llm.py` | `_cut_request_tail` | 12756 | WORDING | the last words of a cut message, quoted back in the question |
| `llm.py` | `_shaped_presentation_text` | 2555 | WORDING | the person's message is the material of the prompt (a numbered list kept, anchor words); the shape was read by semantic.conversation |
| `llm.py` | `_unsupported_request_anchor_token` | 12458, 12472, 12481 | WORDING | picks which of the person's words a limit must quote (an anchor), not what they asked |

El resto de los patrones de la mente fuera de `semantic/` no lee el texto de la persona:

| Fichero | WORDING (texto de BAXY) | OTHER (hashes, rutas, observaciones, catálogo) |
|---|---|---|
| `__main__.py` | 2 | 3 |
| `assets.py` | 0 | 2 |
| `catalog_operation_aliases.py` | 0 | 2 |
| `historical_intents.py` | 0 | 2 |
| `llm.py` | 236 | 78 |
| `observed_response_literals.py` | 1 | 5 |
| `planner.py` | 0 | 1 |
| `skill_registry.py` | 0 | 1 |
| `voice.py` | 0 | 2 |
| `voice_output.py` | 1 | 0 |
| `wake_cascade.py` | 0 | 2 |
| `wake_verifier.py` | 0 | 1 |
| `wakeword.py` | 0 | 4 |
| `window_prose_facts.py` | 40 | 40 |

**App (`src/Baxy.App`)**: por fichero; «sobre la persona» cuenta los sitios cuyo argumento es el texto de la persona según su nombre (userText, input, command, text…).

| Fichero | Patrones | Sobre la persona | Clase | Por qué |
|---|---|---|---|---|
| `FieldProductChannel.cs` | 3 | 0 | OTHER | model identity strings of the runtime manifest |
| `MemoryOperationProtection.cs` | 2 | 0 | MIRROR | the App runs a memory operation only on the person's explicit confirm/cancel of that exact invocation (invariant 4) and never stores a secret |
| `NaturalApplicationRequestParser.cs` | 8 | 8 | READING | App open route and the alias normalization of an extracted application argument; the mind reads the same requests (semantic.apps) |
| `NaturalAudioRequestParser.cs` | 13 | 1 | READING | App audio route (volume, audited correction); the mind reads the same requests (semantic.audio, semantic.levels) |
| `NaturalMemoryRequestParser.cs` | 81 | 64 | READING | App-owned private-memory route (save, recall, forget) decided before the mind; SEMANTICA «Destino» schedules it as semantic/memory.py. Moving it routes memory turns through the mind and re-decides where the private store's reading lives: a protocol change, not a behaviour-identical move |
| `NaturalNoteRequestParser.cs` | 29 | 4 | READING | the App's quick-note route (MainWindowViewModel, MissionInput) beside the mind's note readers (semantic/notes): two readers of one thing, kept until the App takes the mind's note decision, a routing change to measure in the window |
| `NaturalSystemStatusRequestParser.cs` | 22 | 3 | READING | shell shortcut «hora» → system.time without a mind round-trip (latency); the mind reads the same request (semantic.network); UserMessagePolicy also judges clock replies with it |
| `NoteDisambiguation.cs` | 6 | 0 | MIRROR | the person's choice among the notes the App listed, bound to that pending list |
| `ObservedResponseLiterals.cs` | 2 | 1 | WORDING | observed names masked in BAXY's own text |
| `UserMessagePolicy.cs` | 80 | 40 | MIRROR | the App's policy on every text it publishes, its own fallbacks included: a reply is judged against what was asked, so the policy reads the request with twins of the mind's readers (calendar parts, countdown, clitic volume, visual content, out-of-world); consuming the mind's reading needs the compose result to carry it |
| `VoiceListenCommand.cs` | 2 | 0 | INPUT | the listening switch, which must work without the mind |

Métodos de la App con otra clase que la de su fichero:

| Fichero | Método | Clase | Por qué |
|---|---|---|---|
| `NaturalApplicationRequestParser.cs` | `TryNormalizeKnownAlias` | GROUNDING | an application argument the mind extracted is normalized to a catalog alias |
| `NaturalMemoryRequestParser.cs` | `ContainsSensitiveMaterial` | MIRROR | the App refuses to store a secret whatever was read (also used by MemoryOperationProtection) |
| `NaturalMemoryRequestParser.cs` | `LooksLikeCredentialToken` | MIRROR | the App refuses to store a credential |
| `NaturalMemoryRequestParser.cs` | `TryCreateSensitiveSave` | MIRROR | a secret offered to the private memory is refused by the App that stores it |
| `NaturalMemoryRequestParser.cs` | `TrySafeCapturedValue` | MIRROR | the value to store is checked by the App that stores it |
| `NaturalMemoryRequestParser.cs` | `TrySafeSensitiveCapturedValue` | MIRROR | the value to store is checked by the App that stores it |
| `UserMessagePolicy.cs` | `Error` | OTHER | a stable diagnostic code, not text |
| `UserMessagePolicy.cs` | `RequiredBaxyActions` | OTHER | the situation JSON the App composed |
| `UserMessagePolicy.cs` | `RequiredLiteralFacts` | OTHER | the situation JSON the App composed |

<!-- inventario:fin -->
