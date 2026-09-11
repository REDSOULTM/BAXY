# 991 — contrato de lectura media.status
Fuente989:988 publicado9bc1c38d; effect_intent.py leído coincide con snapshot canónico e078c1438403548e61f490e694371cc074bda5acfac8fe42905a4e4f65ce98e1. No se ha editado fuente.

## Pérdida demostrada y asociación exacta
Shell105 enlaza turn.decide.id.26 con t4. Panel989 índice3: music-status965-dev-02, «Is anything playing right now, and which track is it?».
turn-audit7/9: raw action media.status, one/primary, operación en shortlist. Líneas8/10: PlannerContractError, stage compound_conservation, failure_reason apply_compound_effect_conservation_veto:1875. El caller __main__.py6363–6369 llega al veto; línea1875 lanza unresolved_compound_effects después de no acreditar la conservación. Esto demuestra el primer rechazo terminal; no es un fallo de provider ni de selección inicial del modelo.
No se capturaron el objeto CompoundEffectContract, assignments ni la razón interna de compatibility; no atribuyo retrospectivamente un resultado de ese verificador.
Compose t4 first published=true todavía dice «Nothing is playing right now. The request could not be interpreted validly.» sin recibo y con operationAttempted=false. La afirmación de ausencia no es una lectura válida ni consecuencia del estado actual.

## Discrepancia estática concreta anterior al veto
_COVERAGE_ACTION_HEAD incluye which (effect_intent.py6991); _request_clauses12037–12062 usa esa cabeza como frontera después de and. La pregunta queda separada en «is anything playing right now» y «which track is it?».
El dominio completo _curated_domain_is_grounded1876–1896 sí reconoce metadata track + playing en cualquier orden. Pero media_state9258–9283 exige formas que no cubren la primera mitad sin un nombre media/music, ni la segunda mitad sin un predicado de reproducción; su alternativa track…playing tampoco reconoce el orden playing…track del texto completo.
resolve_explicit_effects no acredita el conjunto como una sola lectura. unresolved_compound_contract14381–14438, cuando resolved=None, cuenta las cláusulas positivas pendientes como efectos separados. Es una discrepancia entre los campos que una lectura aporta y la unidad sintáctica usada para contar efectos; el contrato no conserva que estado e identidad pertenecen a la misma sesión.
La conclusión sobre la segmentación y los predicados es lectura de código, no ejecución de funciones. El recibo demuestra el raise externo concreto y es congruente con ese recorrido.

## Otros errores989, separados del contrato anterior
| Request / trace / caso | Causa capturada |
|---|---|
|37/t6/media-status989-dev-state-en — «Which track is loaded, and is it playing or paused?»|ConversationReplyContractError/truncated_structured_reply, conversation_reply, dos intentos. Raw conversa unsupported y la recuperación se trunca. El predicado _has_contradictory_correction7083 trata or como alternativa global; no es el raise1875 medido en t4.|
|48/t8/media-status970-boundary-quotation|PlannerContractError/_prepare_turn_result:6629. Raw devuelve únicamente «What song is currently playing?»; ese raise verifica precisamente explicación reducida a pregunta. Errorcompose vuelve a fallar missing_failure. No habilitar media.status para esta cita.|
|59/t9/media-status970-boundary-future|ConversationReplyContractError/truncated_structured_reply. Raw expresa incapacidad y recuperación vacía; sigue sin autoridad para lectura actual.|
Los enlaces request→trace salen de shell151/195/225. No se mezclan estos fallos como un único defecto ni se adjudica ningún crédito.

## Reparación mínima propuesta; sin parche especulativo
No retirar apply_compound_effect_conservation_veto ni devolver None sólo porque el modelo propone una lectura. Tampoco basta añadir la coincidencia global track+playing a media_state: la segunda cláusula podría solicitar otra observación y seguiría faltando conservación.
La corrección viable debe conservar una sola unidad cuando las cláusulas describen exclusivamente campos de UNA lectura acreditada (estado e identidad de la sesión), y usar esa misma descripción en el lector y en la segmentación. La costura existente está en _request_clauses/_normalize_dependent_clauses y _strict_catalog_request; el tratamiento equivalente de system.status ya demuestra que una lectura puede cubrir varios atributos sin contar operaciones por conjunciones.
La pieza que falta aquí es un reconocimiento cerrado de esos atributos y su referente compartido, con cobertura de toda la cláusula. Los helpers actuales sólo prueban vocabulario de dominio, no que una pregunta adicional pertenezca al mismo objeto. Resolverla exige ampliar esa gramática y retirar la comparación direccional que sustituya, no una exención global readonly ni un alias del literal observado.
En esta iteración no hay una reutilización que por sí sola demuestre esa conservación general. Por eso no se entrega repair.patch: un bypass con lo ya existente autorizaría un subconjunto no probado. Ownership no se amplía a __main__; negativos, citas, futuros y efectos coordinados conservan sus vetos. Raíz puede autorizar la ampliación gramatical acotada como implementación siguiente.

## SHA256
Base archivos: C:/Users/usuario/AppData/Local/BAXY/C03-media-status989-private/run/.
turn-audit.jsonl:4cf71ddd68f477cbe85f29278ff026696ceb639e5486889aae969ca086c88875
raw-replies.jsonl:c94ee743a97f73886c3c18c91ed2d6ec685a5d5da308b4250c67db0b7889bbd6
shell-trace.jsonl:5edcd77bcf653152df33a9c5590d8e6ca37a5888d2924e073959afb9c9325197
compose-audit.jsonl:90ce50f9e49b883bc264861d413e686c9702bf51f68aacae8b061dfad1fc7c75
Sin tests/imports/AST/build/GPU/producto/HTTP, efectos, cambios canónicos, registro ni commit. Spotify962 sigue incierto; no se reejecuta.