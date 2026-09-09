# Recuerdo371 — historial completo no resuelve el fallo

Baseline: 2/5 útiles (tercero y consulta explícita de persistencia). Historial nativo: 2/5 útiles (Jordan y tercero). No adopción de fuente. Se recupera un caso real inglés pero no Álvaro ni el conflicto humano/asistente; además se afirma ausencia de nombre guardado donde el resultado sólo informa memoria deshabilitada.

Primera pérdida: parser fuerza memoria.recall y el compositor de errores no recibe declaración. Añadir historial completo conserva una afirmación anterior falsa del asistente sobre contexto, y el control sintético de conflicto sigue subordinando el nombre humano a memoria deshabilitada. Siguiente contraste acotado: sólo mensajes humanos ya disponibles en PreviousUserRequests, sin introducir resúmenes ni hechos extraídos. Herencia Carter R1/R2 distingue procedencia humana y prosa del asistente. Todavía no cambiar producción.

## t5 / baseline

> I don't know your name because the memory feature is disabled.

## t5 / native-dialogue

> Your name is Jordan. The operation to recall your name failed because memory was disabled.

## t10 / baseline

> No puedo decirte tu nombre porque la memoria está deshabilitada.

## t10 / native-dialogue

> No puedo decirte cómo te llamas porque la memoria está deshabilitada.

## third-party / baseline

> I don't know your name because the memory feature is disabled.

## third-party / native-dialogue

> I don't know your name because the memory feature is currently disabled.

## assistant-conflict / baseline

> I don't know your name because the memory feature is disabled.

## assistant-conflict / native-dialogue

> I couldn't tell your name because the memory feature was disabled.

## explicit-persistence / baseline

> I don't have access to private memory because it is disabled.

## explicit-persistence / native-dialogue

> I don't have a name saved in private memory because that feature is currently disabled.

