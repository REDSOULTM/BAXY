# 1006 — aclaración, conocimiento y falsa incapacidad

Fuente 04ae6daa2c28cf711eaca78b77affd7126bcd67e. Muestra limitada a índices 0/5/7/10/13 de DIALOGUE1004 y 15 de KNOWLEDGE998. Sin ejecución, cambios de fuente ni adjudicación. Los archivos 1004 estaban en captura; los hashes inferiores identifican el estado leído, no un sello final de la corrida.

## Primera pérdida por caso

| Caso / texto | Enlace real | Primera pérdida observada |
|---|---|---|
| H0216, «¡Abre este!» | 1004 index0, t1, request8 | decision_path=explicit_conversation y raw unsupported, cero operaciones. Todas las etapas conservan ese contrato. Final «Este pedido está fuera de lo que hago en este PC». No fue un veto tardío del provider ni una decisión unsupported del selector del modelo. |
| H0493, símbolos `@#$%^&*()` | index5, t6, request35 | raw del modelo knowledge; explicit_contract, dominio, conservación y action_grounding lo conservan. Cambia a unsupported en conversation_presentation. El chat recibe ese contrato y produce incapacidad; shell luego compone out_of_catalog. |
| H0570, `1234567890` | index7, t8, request47 | raw knowledge dos veces; no llega a audit final de etapas. Raw chat ya está condicionado como unsupported. Cada intento genera una negativa y su retry estructurado queda vacío; dos errores conversation_reply/truncated_structured_reply, luego total_recovery. Final explica fallo de interpretación. |
| dialogue1004-dev-01, «Abre aquella, la que te digo.» | index10, t11, request65 | explicit_conversation/unsupported desde raw; ninguna operación ni etapa cambia esa lectura. Final «Ese pedido está fuera de lo que hago en este PC». |
| dialogue1004-dev-04, «Use the usual one instead.» | index13, t14, request81 | raw y todas las etapas knowledge, cero operaciones; no entra aclaración de referente. Chat nativo produce SIEMPRE y pasa a visible_text. |
| knowledge998-dev-06, «Convierte veinte grados Celsius a Fahrenheit; indica la fórmula y el resultado.» | 998 index15, t16, request83 | explicit_conversation/unsupported desde raw. Todas las etapas lo conservan. La composición posterior recibe out_of_catalog, propone «No hago conversiones de temperatura», se rechaza por missing_failure y termina con negativa genérica. |

No hay una misma pérdida de composición para los seis casos. «Fuera de lo que hago» es a veces una composición fiel a un contrato previo equivocado; cambiar sólo esa frase dejaría el fallo de interpretación intacto.

## Costuras concretas existentes

1. **Referente ausente tratado como identidad de juego inexistente.** `__main__._catalog_unavailable_turn_decision:5631–5697` toma abrir/open+operando como game_request y, sin `_authenticated_game_target`, devuelve unsupported. No distingue en esa rama un pronombre sin referente de un título literal de juego. Es una discrepancia estática pertinente a H0216/dev01; el audit no registra cuál de los predicados previos creó explicit_conversation, por lo que no se etiqueta retrospectivamente como único predicado medido.
   El aclarador YA existe en `__main__:6499` (`llm.clarify_missing_referent`) con validación y cero efectos. Su lector `_standalone_deictic_request:2818–2837` reconoce eso/esto/aquello y formas inglesas estrechas, pero no este/aquella ni una elección habitual sin antecedente. Además, su regex no consume el signo inicial de exclamación. Primero consulta `read_request(...).has(INTENT_AMBIGUOUS_ACTION)`; en los recibos no aparece la etapa de aclaración, de modo que ese reconocimiento no cerró estos casos.
   Propuesta futura mínima: reconciliar reconocimiento de referente ausente con ese aclarador antes de declarar identidad fuera de catálogo, reutilizando el lector de solicitud. Conservar negación, cita, contexto válido, identidad real y cero ejecución. No convertir toda operación unsupported en aclaración ni usar los textos del panel como reglas.

2. **Input sin petición promovido a efecto por un verificador secundario.** `apply_conversation_effect_presentation:1310–1334` puede cambiar knowledge a unsupported cuando `_verify_semantic_effect_shape` responde complete/not_complete. H0493 demuestra exactamente la transición de etapa; los valores devueltos por ese verificador no están auditados individualmente. La rutina posterior `apply_non_effect_conversation_classification:1337` no deshace toda falsa incapacidad: requiere evidencia de pregunta/observación y conserva restricciones de autoridad/PC.
   Para H0570, el salto knowledge→unsupported se observa indirectamente entre raw_decision y el parámetro registrado del chat; no hay final de etapas porque aborta. El fallo terminal sí está aislado: `llm.py:7240–7251`, retry con finish_reason=length, raw vacío, excepción `truncated_structured_reply`. No es un provider ni el veto de conservación. Una futura corrección debe conservar conversación/aclaración de entrada sin acto identificado, sin promover operaciones; aumentar tokens o cambiar el mensaje de error no resuelve el contrato unsupported que precede al retry.

3. **Contenido matemático imperativo fuera del reconocimiento de contenido.** `effect_intent.conversation_only_content_request:2096–2146` permite calcula/calculate, pero no la forma de conversión de magnitudes. `__main__:5917–5944` puede seleccionar unsupported cuando `unresolved_compound_contract` y autoridad positiva coinciden, antes del selector. El texto tiene conversión más petición de explicar fórmula, ambas de contenido conversacional. `unresolved_compound_contract:14263` conserva cláusulas positivas no reconocidas como efectos pendientes; ese mecanismo no debe retirar operaciones genuinas, pero tampoco contar instrucciones matemáticas como efectos de PC.
   El audit confirma explicitunsupported temprano, NO un error lanzado por apply_compound_effect_conservation_veto. No registra non_target_language/unresolved_compound_effects/catalog_unavailable de ese intento: la rama exacta es inferencia estática, no dato capturado. La propuesta dirigida sería reconocer una conversión autocontenida de cantidad/unidades y su explicación mediante el contrato de contenido existente, sin temperatura especial en la respuesta, cálculo fijo, acceso al PC ni retiro general del veto.

## Origen de SIEMPRE

El texto exacto del panel, «Use the usual one instead.», tiene request_sha256 `44e9e0c254d7ed168b57a1e3bfa0a8fccab3b5c7575a1c2d77ae6b84f76bc395`. El registro correspondiente en raw-replies.jsonl dice attempt=1, stage=pre_veto, conversation_kind=knowledge, presentation_shape vacío, history_users=0, raw_reply=`SIEMPRE`, raw_reply_sha256=`c84b7401c1fa378c9ac67bcb3d87e9369ca2f7cdf82c7cd75345d5585998da40`. Coincide con visible_text del audit de request81.
`llm.py:7038–7054` captura directamente `response.choices[0].message.content` devuelto por `_post`, antes de los verificadores de conversación. No es una transformación posterior del transporte ni una salida del compositor de operaciones. No hubo historia de usuario registrada para justificar una referencia habitual. La primera pérdida funcional es no pedir el referente; la generación knowledge luego entrega una respuesta ajena.
La fuente contiene SIEMPRE en una instrucción de idioma (`llm.py:107`), pero esa coincidencia NO demuestra que el modelo la copiara: el payload efectivo de esa generación no está retenido aquí. No se atribuye contaminación de prompt, traducción o una causa interna del modelo sin ese dato. Tampoco se propone vetar la palabra SIEMPRE como arreglo.

## Próxima reparación acotada

La reutilización más concreta para abrir un grupo de casos es el aclarador de referente existente, con mejor distinción referencia/identidad antes de las clausuras unsupported. H0216 y dev01 muestran el mismo síntoma temprano; dev04 comparte referente ausente pero su camino observado es knowledge. Símbolos/números y conversión requieren contratos distintos y no deben contarse como desbloqueados por ese ajuste. No se acredita ninguno aquí ni se propone un parche global de negativas.

## Evidencia retenida, SHA256

- 1004 turn-audit.jsonl: be226347e1d12f3e6c6ef54d604c74d7ba405aca58e0183ca893fc0358868791.
- 1004 shell-trace.jsonl: 040dfaed482667d5202c83e175c3fa3d9d5f6f729a91fa089a8f6451b7a44e70.
- 1004 compose-audit.jsonl: c4062968c8183babafc348a968ed7f1301637af19579f1e119553341db3870da.
- 1004 raw-replies.jsonl: 7c51cd602c9602b3d4030226b28ac7420d39b467b88297949774eaceff52414c.
- 998 turn-audit.jsonl: 89ff18bc9e2322b0713bbf81b46252098b25d179a8cada14a77c478f7289ab97.
- 998 shell-trace.jsonl: 84fc66549a54ff29792ed80c90e12dff9abbbeeada6771e0eedec9f657028f768.
- 998 compose-audit.jsonl: e725bedf13975c04a7decd24b088b4be7daad8d968cf6c6da4c9b1606adb85b3.

Rutas 1004: `C:/Users/usuario/AppData/Local/BAXY/C03-dialogue1004-private/run/`; rutas 998: `C:/Users/usuario/AppData/Local/BAXY/C03-knowledge998-private/run/`. Material exacto en los respectivos proposal/panel.json; sólo los seis objetos indicados fueron usados.
