# Respuestas integradas — astra-clarification-error-qwen

Modelos y hashes en PREREG.json; hechos, borradores y reintentos en compose-audit.jsonl; todas las llamadas LLM en sampling.jsonl. No aceptación fresca.

## t1 — REVISAR CONTINUIDAD

Entrada literal
```text
Ajusta el volumen.
```

Respuesta literal
```text
¿Cuánto deseas ajustar el volumen y en qué dirección (subir o bajar)?
```

Solicita precisar volumen. Falta probar la respuesta con un nivel y la ejecución posterior; esta captura cancela la aclaración. t7 además usa composición conversacional.

## t2 — ÚTIL

Entrada literal
```text
cancelar
```

Respuesta literal
```text
La clarificación fue cancelada.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

Borrador first; razón ``; aceptado `True`:
```text
La clarificación fue cancelada.
```

## t3 — ÚTIL

Entrada literal
```text
Abre EstudioC03Inexistente.
```

Respuesta literal
```text
Este pedido está fuera de lo que hago en este PC.
```

Límite de capacidad sin afirmar ausencia. Misma clasificación unsupported que el caso inglés; difiere la reparación/presentación, no la decisión principal.

Borrador first; razón `missing_failure`; aceptado `False`:
```text
Ese texto no está dentro de mis tareas.
```

Borrador retry; razón ``; aceptado `True`:
```text
Este pedido está fuera de lo que hago en este PC.
```

## t4 — REVISAR CONTINUIDAD

Entrada literal
```text
Set the volume.
```

Respuesta literal
```text
How much and in which direction should the volume be adjusted?
```

Solicita precisar volumen. Falta probar la respuesta con un nivel y la ejecución posterior; esta captura cancela la aclaración. t7 además usa composición conversacional.

## t5 — ÚTIL

Entrada literal
```text
cancel
```

Respuesta literal
```text
La clarificación fue cancelada.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

Borrador first; razón ``; aceptado `True`:
```text
La clarificación fue cancelada.
```

## t6 — FALLO

Entrada literal
```text
Open EstudioC03Inexistente.
```

Respuesta literal
```text
I cannot open EstudioC03Inexistente as it does not exist.
```

Afirma inexistencia sin lectura del PC: ruta explicit_conversation/unsupported, cero operaciones. No es un app_not_found verificado.

## t7 — REVISAR CONTINUIDAD

Entrada literal
```text
Set the volume, por favor.
```

Respuesta literal
```text
¿A qué volumen te refieres?
```

Solicita precisar volumen. Falta probar la respuesta con un nivel y la ejecución posterior; esta captura cancela la aclaración. t7 además usa composición conversacional.

Borrador first; razón ``; aceptado `True`:
```text
¿A qué volumen te refieres?
```

## t8 — ÚTIL

Entrada literal
```text
cancelar
```

Respuesta literal
```text
Entendido, se cancela.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

Borrador first; razón ``; aceptado `True`:
```text
Entendido, se cancela.
```

## t9 — ÚTIL

Entrada literal
```text
Open EstudioC03Inexistente, por favor.
```

Respuesta literal
```text
No puedo abrir EstudioC03Inexistente, eso está fuera de mi ámbito.
```

Límite de capacidad sin afirmar ausencia. Misma clasificación unsupported que el caso inglés; difiere la reparación/presentación, no la decisión principal.

Borrador first; razón ``; aceptado `True`:
```text
No puedo abrir EstudioC03Inexistente, eso está fuera de mi ámbito.
```

## t10 — ÚTIL

Entrada literal
```text
Hey, buenas
```

Respuesta literal
```text
¡Hola! Bienvenido. ¿Cómo estás?
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

Borrador first; razón ``; aceptado `True`:
```text
¡Hola! Bienvenido. ¿Cómo estás?
```

## t11 — ÚTIL

Entrada literal
```text
What time is it?
```

Respuesta literal
```text
It's 15:01.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

Borrador first; razón ``; aceptado `True`:
```text
It's 15:01.
```

## t12 — ÚTIL

Entrada literal
```text
¿Cómo está el audio?
```

Respuesta literal
```text
El audio está activo y el volumen está en 100.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

Borrador first; razón ``; aceptado `True`:
```text
El audio está activo y el volumen está en 100.
```
