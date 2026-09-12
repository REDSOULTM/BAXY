# CLOSE1055 — diagnóstico y reparación externa
Sólo llm.py propuesto; effect_intent.py intacto (ownership WEB1054). Base HEAD943e937d65d5d7364402d2bb6817b3a3b27f2899. Copias completas base/proposal, DIFF.patch y hashes de las12fuentes exactas en IDENTITY.json. Sin pruebas, imports, builds, GPU, efectos ni cambios canónicos.

## Enlace y primera pérdida
run-08 index8/H0407 «nunca cierres spotify» y run-09 index9/H0427 «no cierres spotify» corresponden en ambos procesos a t1/turn.decide request8. capture/events meta fija HEAD943e937d y PYTHONPATH al src canónico. case-observations confirma terminal published_final idéntico y admission200; no es un texto inventado por la adjudicación.
Ambos auditan explicit_conversation, knowledge, cerooperaciones. El chat entra correctamente en constraint_ack: NO comparte la pérdida de reconocimiento de AUDIO1051/SIEMPRE. No se requiere modificar parser de negación.
H0427 raw pre_veto intento1: «Entendido, no cerraré Spotify. 😊», SHA7bebbf1e2e61b6a61f06ac044b7b9ce0cd1dda964cb9fecd9d0c90905223e44a. Es reconocimiento natural en primera persona de la prohibición, sin afirmar cierre ni estado observado. El primer retry ya viene vacío; audit registra ConversationReplyContractError/truncated_structured_reply.
Segundo intento de turno genera «Entendido, no cierro Spotify. Todo está bien.», SHAe36909a81bed74167c4972c810cdf7edcab4dee9de8ff4d093ab829f8994eb29: son dos proposiciones y la segunda no está acreditada. Su rechazo no debe eliminarse. Otro retry vacío termina en total_recovery.
H0407 genera dos veces «Entendido, nunca cierre Spotify. 😊», SHAd7f20ee159d75da12c345be730174cb21368880d6f8c36f1d7e41234f1bb22aa, y sendos retries vacíos. Además del emoji, «nunca cierre» cambia el rol a una orden al interlocutor: este diagnóstico NO lo califica de respuesta válida ni promete resolver H0407.

## Predicado fuente concreto
llm._shaped_conversation_answer_violates_contract:2098–2105 contiene re.search(r"[.!…]\s+\S", content). El punto, espacio y emoji de ambas primeras respuestas satisfacen determinísticamente esa condición: el validador confunde decoración final con segunda oración. El audit no registra flags individuales del rechazo; la identificación del predicado se obtiene por lectura directa del código contra el raw exacto, no se presenta como reason telemétrico capturado.
llm.chat:7245–7275 aplica ese verificador y deriva a retry. En7390–7404, finish_reason length lanza truncated_structured_reply aunque content esté vacío. No borrar ese control ni aumentar tokens: el primer raw fiel de H0427 no debía necesitar retry.
Tras dos errores, compose t1 recibe outcome failed/cause request interpretation failed/operationAttempted false. El primer draft de error se rechaza por missing_failure; retry genera el terminal «La causa del fallo es que el sistema no pudo interpretar la solicitud para cerrar Spotify.» SHA9c1d21730f6e6dc1cfa6cf79b216d9bfaa84b2c650cbc492535a6e5f40b87356. Es consecuencia del fallo de presentación, no de una operación app.close ni de identidad ausente de Spotify.

## Cambio mínimo
Se sustituye SOLO el detector de segunda oración por [.!…]\s+\W*\w: requiere contenido léxico tras el límite, incluso si entre ambos hay decoración. No se modifica ni recorta el texto visible; no se introducen nombres, frases de panel ni respuestas fijas.
La decoración final sin letras/cifras no provoca por sí sola otro intento. Una segunda proposición, incluso precedida por emoji, sigue rechazándose. Siguen vigentes los controles anteriores de capacidad, estado no observado, eco, infinitivo inventado, stall, idioma, pregunta, saltos de línea y referencia literal. No es una excepción general de constraint_ack ni un bypass por cerooperaciones.
Revisión manual de forma: oración seguida sólo por emoji deja de contar como dos; oración +emoji+texto sigue contando como dos; dos frases con texto sinemoji siguen rechazadas. No se ejecutaron esas expresiones ni tests de producto.
Limitación importante: no se añade aquí un verificador de rol/primera persona; la orientación generativa existente ya lo pide y H0407 la incumple. Su utilidad se juzga en producto por raíz. No se afirma2créditos ni recuperación medida; H0427 es el candidato directamente beneficiado por remover el falso veto demostrado. H0407 puede seguir fallando por sujeto/imperativo.

## Entrega
DIFF3+/1−; git diff --no-index --check sin incidencias de whitespace (sólo aviso normal CRLF/LF). Fuente canónica no editada. Integración, validación y adjudicación pertenecen a raíz.
Patch SHA90b6a97f9a2a3db6c44476651318ba3ee64c001f1cdbb6ecfdef170fd7c3053f.
Base llm SHA dbc5d1454da8700f18af7b2ef05f4b69fe04aa0696d7e1b56789695d65243d00; propuesta90cd02cc192c102ac46df7f67226daaecc78dda6a013fd03a5dec8275cc4d2af.
