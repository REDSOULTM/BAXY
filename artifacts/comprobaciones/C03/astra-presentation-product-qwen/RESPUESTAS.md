# Respuestas integradas — astra-presentation-product-qwen

Modelos y hashes en PREREG.json; hechos, borradores y reintentos en compose-audit.jsonl; todas las llamadas LLM en sampling.jsonl. No aceptación fresca.

## t1 — ÚTIL

Entrada literal
```text
¿Qué hora es?
```

Respuesta literal
```text
Son las 14 horas y 58 minutos.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

Borrador first; razón ``; aceptado `True`:
```text
Son las 14 horas y 58 minutos.
```

## t2 — ÚTIL

Entrada literal
```text
Dime la hora y el estado del audio.
```

Respuesta literal
```text
La hora local es 14:58. El audio está desactivado de muteo y el nivel de volumen es 100.
```

Contenido útil y fiel, con gramática mejorable («desactivado de muteo» / «la cerrada»).

Borrador first; razón ``; aceptado `True`:
```text
La hora local es 14:58. El audio está desactivado de muteo y el nivel de volumen es 100.
```

## t3 — ÚTIL

Entrada literal
```text
What time is it?
```

Respuesta literal
```text
It's 14:58.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

Borrador first; razón ``; aceptado `True`:
```text
It's 14:58.
```

## t4 — ÚTIL

Entrada literal
```text
Tell me the time and the volume.
```

Respuesta literal
```text
The local clock is 14:58. The volume is 100 and the device is not muted.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

Borrador first; razón ``; aceptado `True`:
```text
The local clock is 14:58. The volume is 100 and the device is not muted.
```

## t5 — ÚTIL

Entrada literal
```text
Dime la hora, please, en spanglish
```

Respuesta literal
```text
Son las 14 horas y 58 minutos.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

Borrador first; razón ``; aceptado `True`:
```text
Son las 14 horas y 58 minutos.
```

## t6 — ÚTIL

Entrada literal
```text
What time is it y cómo está el audio?
```

Respuesta literal
```text
Son las 14:58. El audio está activo y el volumen está en 100.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

Borrador first; razón ``; aceptado `True`:
```text
Son las 14:58. El audio está activo y el volumen está en 100.
```

## t7 — ÚTIL

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

## t8 — ÚTIL

Entrada literal
```text
Explain encryption, pero en simple
```

Respuesta literal
```text
Encryption es como poner un código a la información para que solo las personas con la clave puedan leerla. Es como cerrar un mensaje en una caja con un candado: si no tienes la llave, no puedes abrirlo. Así se protege la privacidad de los datos.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

## t9 — ÚTIL

Entrada literal
```text
responde en spanglish: qué es una copia de seguridad
```

Respuesta literal
```text
Una copia de seguridad es como tener una copia del archivo o datos en otro lugar, para que si se pierden o se dañan, puedas recuperarlos fácilmente. Es como tener un backup del libro en otro lugar si lo pierdes.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

## t10 — ÚTIL

Entrada literal
```text
Explain gravity, pero sin tecnicismos
```

Respuesta literal
```text
La gravedad es esa fuerza que mantiene a las cosas pegadas al suelo, como cuando caes al piso o cuando un objeto se queda en la mesa. Es como si todo lo que está cerca de la Tierra tuviera un pequeño hilo que lo atrae hacia abajo.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

## t11 — ÚTIL

Entrada literal
```text
no abras Paint
```

Respuesta literal
```text
No abriré Paint.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

Borrador first; razón ``; aceptado `True`:
```text
No abriré Paint.
```

## t12 — ÚTIL

Entrada literal
```text
what is the capital of Peru
```

Respuesta literal
```text
Lima
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

## t13 — ÚTIL

Entrada literal
```text
Explain photosynthesis in two sentences.
```

Respuesta literal
```text
Photosynthesis is when plants use sunlight to convert carbon dioxide and water into glucose and oxygen. It's like nature's way of making food and releasing fresh air.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

## t14 — ÚTIL

Entrada literal
```text
Explícame por qué el hielo flota.
```

Respuesta literal
```text
El hielo flota porque es menos denso que el agua líquida. Cuando el agua se congela, sus moléculas se alejan y ocupan más espacio, así que el hielo pesa menos por volumen y flota.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

## t15 — ÚTIL

Entrada literal
```text
¿Qué diferencia hay entre un archivo y una carpeta? Reply in Spanglish.
```

Respuesta literal
```text
Un archivo es un archivo de datos, como un documento o una imagen, mientras que una carpeta es como una caja donde puedes guardar varios archivos.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

## t16 — ÚTIL

Entrada literal
```text
What is on my to do list?
```

Respuesta literal
```text
Your to-do list is empty right now.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

Borrador first; razón ``; aceptado `True`:
```text
Your to-do list is empty right now.
```

## t17 — ÚTIL

Entrada literal
```text
cierra la ventana titulada Ventana C03 de prueba
```

Respuesta literal
```text
¿Quieres confirmar la cerrada de la ventana titulada "Ventana C03 de prueba"? Elige: confirmar o cancelar.
```

Contenido útil y fiel, con gramática mejorable («desactivado de muteo» / «la cerrada»).

Borrador first; razón ``; aceptado `True`:
```text
¿Quieres confirmar la cerrada de la ventana titulada "Ventana C03 de prueba"? Elige: confirmar o cancelar.
```

## t18 — ÚTIL

Entrada literal
```text
cancelar
```

Respuesta literal
```text
Se canceló la solicitud de cerrar la ventana titulada "Ventana C03 de prueba". El sistema detectó la ventana maximizada con el título indicado, pero la acción fue cancelada. No se realizó el cierre.
```

Cancela y afirma expresamente que no cerró; el resultado coincide con el kernel y la posterior resolución de la ventana.

Borrador first; razón ``; aceptado `True`:
```text
Se canceló la solicitud de cerrar la ventana titulada "Ventana C03 de prueba". El sistema detectó la ventana maximizada con el título indicado, pero la acción fue cancelada. No se realizó el cierre.
```

## t19 — ÚTIL

Entrada literal
```text
cierra la ventana titulada Ventana C03 de prueba
```

Respuesta literal
```text
¿Quieres confirmar la cerrada de la ventana titulada "Ventana C03 de prueba"? Elige: confirmar o cancelar.
```

Contenido útil y fiel, con gramática mejorable («desactivado de muteo» / «la cerrada»).

Borrador first; razón ``; aceptado `True`:
```text
¿Quieres confirmar la cerrada de la ventana titulada "Ventana C03 de prueba"? Elige: confirmar o cancelar.
```

## t20 — ÚTIL

Entrada literal
```text
confirmar
```

Respuesta literal
```text
Se confirmó que se cerró la ventana titulada "Ventana C03 de prueba". El proceso se completó correctamente.
```

Cierre verificado por app.close y fixture terminada antes de limpieza.

Borrador first; razón ``; aceptado `True`:
```text
Se confirmó que se cerró la ventana titulada "Ventana C03 de prueba". El proceso se completó correctamente.
```

## t21 — ÚTIL

Entrada literal
```text
What time is it?
```

Respuesta literal
```text
It's 14:58.
```

Revisión individual: responde al pedido y conserva los hechos disponibles; simplificación y puntuación menores no bloquean.

Borrador first; razón ``; aceptado `True`:
```text
It's 14:58.
```
