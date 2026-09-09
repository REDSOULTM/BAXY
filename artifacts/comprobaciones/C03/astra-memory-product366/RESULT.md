# Producto366 — 3/10 útiles completos; un silencio

Mismos diez controles sintéticos de364, candidato Qwen3.5 y perfil limpio; sólo fuente365 cambia. Exit0, todas las admisiones200, ningún timeout. Sin promoción, humanos frescos, UI ni voz física.

La ruta privada ahora intenta guardar ambos nombres y ofrece activación con consentimiento. No aumenta el total de turnos útiles: permanecen errores de explicación/recuerdo y cambian algunas respuestas. No sustituir adjudicación por suites verdes.

## Turno 1

My name is Jordan. Remember my name.

> Jordan, I remember your name. The save operation failed because memory was disabled.

> Jordan, I'm ready to enable your private local memory. Do you want to confirm this action or cancel it?

Útil: el conjunto del turno explica que guardar falló por memoria deshabilitada y pide confirmar su activación. «I remember» sólo es cierto en esta conversación; no acredita persistencia.

## Turno 2

What would I be confirming?

> What would you like to confirm or cancel? Please choose either confirm or cancel.

Fallo: no explica la acción cuya confirmación está pendiente.

## Turno 3

cancel

> Cancelado.

Fallo: cancelación real, pero respuesta en español durante el intercambio inglés y sin alcance.

## Turno 4

Who am I?

> You are Jordan, a user who just tried to enable private local memory but canceled the action.

Útil: reconoce Jordan desde la conversación; añade un comentario pasado innecesario pero cierto.

## Turno 5

What is my name?

Fallo: silencio; composition_failed, no_response;recovery:no_response;retry_exhausted.

## Turno 6

Me llamo Álvaro y quiero que guardes mi nombre.

> Hola Álvaro, no puedo guardar tu nombre porque la memoria está deshabilitada.

> Hola Álvaro, ¿te gustaría que active mi memoria privada para guardarte tu nombre? Por favor, dime si quieres confirmar o cancelar.

Útil: explica por qué no guardó y ofrece activar memoria mediante confirmación.

## Turno 7

¿Qué vas a activar?

> ¿Qué vas a activar? ¿Confirmar o cancelar?

Fallo: repite la pregunta sin explicar qué se activaría.

## Turno 8

cancelar

> Se ha cancelado la memoria.

Fallo: se canceló la activación pendiente, pero «Se ha cancelado la memoria» no identifica esa acción. El estado real sí conserva memoria deshabilitada sin guardar.

## Turno 9

quién soy ahora

> Eres Álvaro, pero como cancelaste la activación de la memoria privada, no tengo guardado tu nombre en mi contexto actual.

Fallo: reconoce Álvaro pero afirma que no está en su contexto actual, pese a que la declaración humana está presente en el payload.

## Turno 10

¿Cómo me llamo?

> No puedo decirte tu nombre porque la memoria está deshabilitada.

Fallo: memoria persistente deshabilitada no impide responder con el nombre declarado en la conversación.

## Primera pérdida localizada

T2/T7: MemoryTurnSession.HandleConfirmationAsync Invalid produce confirm_or_cancel sin pendingAction. La narración inicial ya dispone del helper seguro; sólo debe transmitir operación y destino público, nunca argumentos, tokens o IDs. Cancelación/idioma y recall siguen separados.

Se comprobó además HTTP34: la declaración humana «Me llamo Álvaro y quiero que guardes mi nombre.» sí llega como role=user al selector para «quién soy ahora». Se descarta la hipótesis de que365 ocultara esa declaración antes del historial. El problema de T9 no puede atribuirse a esa supuesta pérdida.

BAXY y llama-server ausentes al cerrar. Handles finalizados; encuesta intacta. Últimas dueñas365:1926pass0skip, Fast18,06s verde. C03 íntegro sigue EN_CURSO.
