# astra-product-default-kv-qwen

Entradas y respuestas literales del conductor. Las expectativas se adjudican por contenido y estado; publicación no equivale a aprobación.

## t1 — ÚTIL

**Entrada literal**
```text
¿Qué hora es?
```

**Respuesta literal**
```text
Son las 15 horas y 28 minutos.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t2 — FALLO

**Entrada literal**
```text
Dime la hora y el estado del audio.
```

**Respuesta literal**
```text
La hora local es 15:28. El audio está desactivado, con nivel de volumen en 100.
```

Audio desactivado contradice muted:false (t2); reunión y falta de tiempo inventadas (t5).

Terminal: published_final.

## t3 — ÚTIL

**Entrada literal**
```text
What time is it?
```

**Respuesta literal**
```text
It is 15:29.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t4 — ÚTIL

**Entrada literal**
```text
Tell me the time and the volume.
```

**Respuesta literal**
```text
Local clock: 15:29  
Volume level: 100  
Mute state: off
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t5 — FALLO

**Entrada literal**
```text
Dime la hora, please, en spanglish
```

**Respuesta literal**
```text
Es 3:29 p.m., ya pasó la hora de la reunión, no me queda mucho tiempo.
```

Audio desactivado contradice muted:false (t2); reunión y falta de tiempo inventadas (t5).

Terminal: published_final.

## t6 — ÚTIL

**Entrada literal**
```text
What time is it y cómo está el audio?
```

**Respuesta literal**
```text
Son 15:29 y el audio está activo con volumen en 100.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t7 — ÚTIL

**Entrada literal**
```text
Hey, buenas
```

**Respuesta literal**
```text
Hola, ¿qué tal? Bienvenido.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t8 — ÚTIL

**Entrada literal**
```text
Explain encryption, pero en simple
```

**Respuesta literal**
```text
Encryption es como poner un código a la información para que solo las personas con la clave puedan leerla. Es como si escribieras un mensaje en un libro y lo guardaras en un lugar seguro, y solo tú y la persona que tiene la clave pueden entenderlo.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t9 — ÚTIL

**Entrada literal**
```text
responde en spanglish: qué es una copia de seguridad
```

**Respuesta literal**
```text
Una copia de seguridad es como tener una copia del archivo o datos en otro lugar, para que si se pierden o se dañan, puedas recuperarlos fácilmente. Es como tener un respaldo del libro en otro lugar, en caso de que el original se pierda.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t10 — ÚTIL

**Entrada literal**
```text
Explain gravity, pero sin tecnicismos
```

**Respuesta literal**
```text
La gravedad es esa fuerza que tira todo lo que está cerca de la Tierra hacia abajo, como si hubiera un hilo invisible que lo conectara al suelo. Es por eso que cuando caes, no vuelas, sino que te acercas al piso.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t11 — ÚTIL

**Entrada literal**
```text
no abras Paint
```

**Respuesta literal**
```text
No abriré Paint.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t12 — ÚTIL

**Entrada literal**
```text
what is the capital of Peru
```

**Respuesta literal**
```text
The capital of Peru is Lima.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t13 — ÚTIL

**Entrada literal**
```text
Explain photosynthesis in two sentences.
```

**Respuesta literal**
```text
Photosynthesis is how plants use sunlight, carbon dioxide, and water to make their own food, like sugar. They also release oxygen as a byproduct, which we breathe.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t14 — ÚTIL

**Entrada literal**
```text
Explícame por qué el hielo flota.
```

**Respuesta literal**
```text
El hielo flota porque es menos denso que el agua. Cuando el agua se congela, sus moléculas se organizan en una estructura abierta que ocupa más espacio, por eso pesa menos y se eleva.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t15 — ÚTIL

**Entrada literal**
```text
¿Qué diferencia hay entre un archivo y una carpeta? Reply in Spanglish.
```

**Respuesta literal**
```text
Un archivo es un archivo de datos, como un documento o una imagen, mientras que una carpeta es como una caja donde puedes guardar varios archivos. Es como tener un libro (archivo) y una estantería (carpeta) para ponerlos.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t16 — ÚTIL

**Entrada literal**
```text
What is on my to do list?
```

**Respuesta literal**
```text
Your to-do list is empty right now.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t17 — FALLO

**Entrada literal**
```text
cierra la ventana titulada Ventana C03 de prueba
```

**Sin respuesta final.** Marcador interno del conductor: composition_failed.

No hubo respuesta final publicada.

Terminal: composition_failed.

## t18 — ÚTIL

**Entrada literal**
```text
cancelar
```

**Respuesta literal**
```text
Se canceló la solicitud de cerrar la ventana titulada "Ventana C03 de prueba". No se realizó la acción de cierre.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t19 — FALLO

**Entrada literal**
```text
cierra la ventana titulada Ventana C03 de prueba
```

**Sin respuesta final.** Marcador interno del conductor: composition_failed.

No hubo respuesta final publicada.

Terminal: composition_failed.

## t20 — ÚTIL

**Entrada literal**
```text
confirmar
```

**Respuesta literal**
```text
Se confirmó que se resolvió la ventana titulada "Ventana C03 de prueba" y se cerró correctamente.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.

## t21 — ÚTIL

**Entrada literal**
```text
What time is it?
```

**Respuesta literal**
```text
It is 15:29.
```

Responde al turno; revisar los hechos y límites de la captura enlazada.

Terminal: published_final.
