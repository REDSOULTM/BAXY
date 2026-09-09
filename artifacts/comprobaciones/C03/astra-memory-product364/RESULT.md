# Producto364 — generalización:3/10 completos, un silencio

Diez controles sintéticos ES/EN, nuevos nombres y cancelaciones. Fuente362 y Qwen3.5 de363 sin cambios; no comparación numérica con su panel distinto. Exit0, admisiones200, sin timeout. No mensajes humanos frescos, UI ni voz física.

## Turno 1

My name is Jordan. Remember my name.

> Got it, Jordan! I'll remember your name.

Fallo: promete recordar sin iniciar la ruta de guardado solicitada ni explicar que persistencia está deshabilitada. No hubo save/enable.

## Turno 2

What would I be confirming?

> You are confirming that I have remembered your name as Jordan.

Fallo: dice qué se está confirmando sin una confirmación pendiente real; no explica ninguna activación.

## Turno 3

cancel

> El pedido está fuera de lo que hago en este PC.

Fallo: cancelar se responde como fuera de catálogo y en español dentro del intercambio inglés.

## Turno 4

Who am I?

> You are Jordan.

Útil: reconoce Jordan desde la conversación.

## Turno 5

What is my name?

Fallo: silencio. Terminal composition_failed; no_response;recovery:no_response;retry_exhausted.

## Turno 6

Me llamo Álvaro y quiero que guardes mi nombre.

> ¿Quieres que guarde tu nombre en una nota privada?

Fallo: convierte el guardado explícito del nombre en una pregunta de nota privada; no inicia memoria ni identifica la activación necesaria.

## Turno 7

¿Qué vas a activar?

> ¿Quieres que guarde tu nombre en una nota privada?

Fallo: repite la pregunta de nota y no responde qué se activaría.

## Turno 8

cancelar

> Se ha cancelado la aclaración.

Útil: cancela la aclaración existente; no se habilita memoria ni se guarda.

## Turno 9

quién soy ahora

> Eres Álvaro.

Útil: reconoce la nueva declaración Álvaro.

## Turno 10

¿Cómo me llamo?

> No puedo decirte tu nombre porque la memoria está deshabilitada.

Fallo: atribuye no poder decir el nombre a memoria deshabilitada, aunque Álvaro está en la conversación reciente.

## Siguiente causa, sin ocultar el resto

Primero la interpretación privada del nombre y guardado en una frase. NaturalMemoryRequestParser.Classify:250, MissingNameSavePattern:1651 y DeclaredNameInputPattern:1669 ya tienen las piezas separadas. TryBindSaveInput sólo une el dato después de una pregunta previa y no este turno completo. 365 añade baseline positivo/negativo para combinar dato con su permiso explícito, sin nombres fijos, permiso inferido ni nota alternativa. T5/T10 sobre memoria deshabilitada y contexto siguen pendientes por separado. El control de preguntas durante confirmación no se alcanzó en364: nunca hubo un enable pendiente. No presentar el examen de esa rama como realizado.
