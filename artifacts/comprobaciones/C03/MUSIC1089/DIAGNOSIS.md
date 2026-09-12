# MUSIC1089 — contrato de composición del transporte verificado

Fuente medida: HEAD88fae0028cd8cb834ab9bdacb40c1e656bfd74b2, MUSIC1086. Revisión externa de una iteración, sin ejecución/imports/tests/GPU/Core ni edición canónica. Se hereda REVIEW1064: la proyección de sourceAppUserModelId, título, artista y estado ya estaba comprobada; no se atribuye este fallo al provider ni a pérdida de esos campos.

## Hechos observados

Case3 music1037-dev-06: media.control completó verificado la invocación f346d8f3-93e1-46b8-a2ba-a0125fa4fbf7, Aurora→Rio. La situación enviada al compositor declara success, verified=true, succeeded=true, authority=windows_smtc, identidad real, Rio de cristal, artista y playing. El primer borrador afirma falsamente incapacidad y que no hubo acción; asserted_failure lo rechaza correctamente. Retry «Moved forward to the next track in the playlist.» y third «I skipped forward to the next track.» omiten nombres: ambos missing_name. No hubo resultado publicado para ese efecto.

Case5 music1086-dev-next-es: invocación ac6d88a8-f357-4e63-a2e6-e86329f1fb02 verificada, Rio→Sendero. First/retry «Vamos a la siguiente pista.» omiten nombres y se rechazan missing_name. Third «Ya pasé a la siguiente pista en "Sendero azul" de Original BAXY preparation composition.» conserva título y artista pero omite playbackStatus, por lo que se rechaza missing_state. Ambos casos terminan composition_failed, no_response;recovery:no_response;retry_exhausted. El efecto verificado no convierte estos casos en aprobados.

Como control de la comparación, los literales1/2 sí generaron nombres, artista y estado, con published=true. Esas adjudicaciones corresponden a raíz; no se reevalúa aquí su mérito. La diferencia no se reduce al idioma. Las repeticiones del mismo hash en auditoría no se cuentan como nuevos éxitos ni como nuevas invocaciones.

## Primera divergencia y costura demostrada

La primera salida incorrecta está en generación: contradicción del éxito en3 y omisión de hechos en5. Los fatos observados llegan completos; no hay prueba de una transformación posterior que elimine un texto fiel. Los vetos conservan el contrato correctamente.

La costura de preparación de la respuesta es concreta: _compose_shape_instruction, llm.py3736–3743, explica el contrato de título/artista/playbackStatus únicamente cuando operation==media.status. El validador5092–5167 ya exige ese mismo contrato para media.control verificado con identidad SMTC y estado conocido. Así, los controles tienen obligaciones que la instrucción existente no les comunica, pese a disponer de los datos.

La recuperación tampoco garantiza corregir la nueva omisión: requiredFacts/actions/words están vacíos en estos recibos; contract_hint10562–10595 sólo examina esas listas, y third10774–10780 conserva retry_hint del primer defecto. En3 no actualiza a missing_name; en5 el estado falta al agotar la tercera salida. Esto no justifica aceptar texto incompleto ni ampliar reintentos a ciegas.

## Propuesta mínima, un owner

DIFF.patch sólo extiende el predicado de la instrucción existente en _compose_shape_instruction al mismo media.control verificado que reconoce el validador: verified/succeeded verdaderos, authority windows_smtc, sourceAppUserModelId no vacío y playbackStatus playing/paused/stopped. Se reutiliza literalmente la instrucción de datos existente; no se añaden respuestas visibles, nombres, frases de encuesta, ejemplos, otra capa o provider. No cambia ningún filtro, autoridad, operación ni estado admitido.

La instrucción se conserva también en retry/third mediante turn_instructions10504 y retry_system_base10724–10728. Esto comunica desde el primer intento y en los siguientes las tres obligaciones ya vigentes, sin exigir estado inventado ni convertir play en stop. Operaciones fallidas/no verificadas, confirmaciones y aclaraciones quedan fuera; closed conserva su limitación previa fuera de esta reparación.

Es una hipótesis de reparación sustentada en código y fallos observados, no éxito demostrado. La evidencia siguiente necesaria es ejecutar las variantes3/5 intactas con candidato adoptado y comprobar efecto único, títulos/artista/estado y terminal útil; los literales deben acreditarse conforme a candidato y pares exigidos por raíz. Afecta la familia next de H0351/H0567 y podría beneficiar H0311 bajo el mismo contrato; no se afirma reparación ni crédito de tres casos.

No es el fallo1077 de perfil pendiente: aquí los perfiles son independientes y todos los borradores del resultado propio son rechazados. raw-replies.jsonl no existe en run03; se usa compose-audit v2 con borradores y hashes, sin fingir un raw ausente. EVIDENCE.json fija trazas exactas y estados únicos. MUSIC1088 queda sin sello final y no debe arrancar con la procedencia provisional.
