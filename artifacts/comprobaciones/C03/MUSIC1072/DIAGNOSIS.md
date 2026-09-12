# MUSIC1072 — narración pasada convertida en fallo interpretativo

Caso original music1037-boundary-05, índice22 de MUSIC1069: «Ayer detuve la música antes de salir.». Es un límite de desarrollo antes inédito; no se etiqueta regresión ni genera crédito. Fuente medida31e7d33a62292ba496a2839acf7b5bd09ab96031.

Evidencia exacta en C:/Users/usuario/AppData/Local/BAXY/C03-music1069-proposal/private/run-22: turns.jsonl contiene session.new y el texto original; shell-trace muestra saludo inicial y ninguna llamada media.control. turn-audit request8 registra dos raw_attempt de decision_path=explicit_conversation, conversation_kind=unsupported, cero efectos y candidatos vacíos. No es una clasificación raw del modelo.

La primera clasificación equivocada tiene costura estática: _explicit_stable_no_effect_turn_decision en __main__.py:3383 detecta past_or_hypothetical usando la gramática existente, pero el selector de conversation_kind:3528–3560 no le asigna una clase conversacional propia y cae en unsupported. El lector posterior apply_non_effect_conversation_classification:1378–1492 ya reconoce narración positiva y la reconduce a followup sin efectos.

No hay etapas finales intermedias capturadas en el intento fallido: el audit conserva failure_stage=conversation_reply y failure_reason=_resolve_contextual_answer:6792, ValueError, dos veces. Por lectura del caller y del contrato, la ruta de seguimiento acaba en el resolvedor elíptico. No se atribuye un contenido concreto a sus borradores internos: no están capturados y no existe raw-replies.jsonl. La excepción final identifica una salida vacía, repetida o sólo interrogativa, sin distinguir cuál ocurrió aquí.

La costura reparable está en llm.chat: ya existe _conversation_presentation_shape:1891–1914 con observation_ack para followup narrativo sin historial, excluyendo preguntas e instrucciones de conocimiento y exigiendo _reads_as_an_observation. Sin embargo has_history=bool(prior_messages) cuenta el saludo inicial; contextual_history:6945 también usa last_assistant como prueba de continuidad. Esto desvía un primer relato autónomo hacia un contrato elíptico que exige explicar el mensaje anterior del asistente.

Total recovery termina semantic_clarification/turn_runtime_failure. compose-audit t1 recibe operationAttempted=false, retryable=true y cause=request interpretation failed; genera «No pude detener la música como querías. El sistema no entendió la solicitud.». Ésta es la consecuencia visible, no una operación fallida ni una razón para modificar el proveedor. La sesión pausada posterior no se atribuye a BAXY.

## Propuesta mínima

DIFF.patch sólo conecta las piezas existentes de presentación: se considera historial de conversación previo si quedó un mensaje de usuario tras retirar el actual; un saludo de startup solo no lo acredita. Un formato cerrado ya identificado tiene precedencia frente al resolvedor contextual. La recuperación literal explícita mantiene su precedencia y con usuario previo se conserva la elegibilidad anterior de observation_ack.

No se añade detector por «ayer», música o el literal. No se modifica prompt, respuesta fija, requisito factual, kernel/proveedor ni autoridad de efecto. El formato observation_ack heredado reconoce lo dicho por la persona sin presentarlo como resultado verificado del PC. Sigue sujeto a sus validaciones existentes. No se cambia aquí la clasificación inicial general past/hypothetical: el mecanismo posterior ya corrige narración y la propuesta evita perder esa corrección en presentación.

Base del parche: fb4d5c528b64517daf5866efefb90bcdf0798a9e, llm SHA6ff34912ed018566a1dabf402644c9b7054e5537223275fbdd650ada42853f8c, que incluye1070 adoptado durante la lectura. DIFF no contiene ni modifica su hunk morfológico: sólo los callers de formato/continuidad6911 y6941. La causa medida sigue ligada a31e7; se declara esta diferencia en IDENTITY.json.

Revisión manual, sin imports de producto/AST/pruebas/build/Core/GPU/efectos ni cambios canónicos/registro. Validación útil real pendiente de raíz; ningún éxito ni crédito prometido. Los hashes de evidencia y propuestas están en IDENTITY.json.
