# astra-registered-development-recovery-qwen

Pruebas conocidas de desarrollo. Publicación y utilidad se evalúan por separado. Las inyecciones no cuentan como turnos normales.

## t1 — FALLO

**Entrada literal**
```text
¿Qué hora es?
```

**Sin respuesta final.** Estado de producto: `composition_failed`.

Sin respuesta: borrador correcto con horas/minutos rechazado.

## t2 — ÚTIL

**Entrada literal**
```text
Dime la hora y el estado del audio.
```

**Respuesta literal**
```text
La hora local es 16:09. El audio está desactivado de muteo y el nivel de volumen es 100.
```

Hora16:09,volumen100 y muteo desactivado conservados; redacción mejorable.

## t3 — ÚTIL

**Entrada literal**
```text
What time is it?
```

**Respuesta literal**
```text
It's 16:09.
```

Hora16:09 correcta, inglés.

## t4 — ÚTIL

**Entrada literal**
```text
Tell me the time and the volume.
```

**Respuesta literal**
```text
The local clock is 16:09. The volume level is 100. The audio is not muted.
```

Hora16:09,volumen100,muted:false conservados en inglés.

## t5 — FALLO

**Entrada literal**
```text
Dime la hora, please, en spanglish
```

**Sin respuesta final.** Estado de producto: `composition_failed`.

Sin respuesta: conversiones16:09→4:09 sin PM, reintento inventa un día de Ana.

## t6 — ÚTIL

**Entrada literal**
```text
What time is it y cómo está el audio?
```

**Respuesta literal**
```text
Es 16:09. El audio está activo y el volumen está en 100.
```

Hora16:09,audio activo y nivel100 conservados.

## t7 — ÚTIL

**Entrada literal**
```text
Hey, buenas
```

**Respuesta literal**
```text
¡Hola! Bienvenido. ¿Cómo estás?
```

Saludo natural; bienvenida y pregunta social admitidas por el dueño.

## t8 — ÚTIL

**Entrada literal**
```text
Explain encryption, pero en simple
```

**Respuesta literal**
```text
Encryption es como poner un código a la información para que solo las personas con la clave puedan leerla. Es como cerrar un mensaje en una caja con un candado: si no tienes la llave, no puedes abrirlo. Así se protege la privacidad de los datos.
```

Explicación sencilla del cifrado con clave y analogía de candado; útil bajo la rúbrica del dueño.

## t9 — ÚTIL

**Entrada literal**
```text
responde en spanglish: qué es una copia de seguridad
```

**Respuesta literal**
```text
Una copia de seguridad es como tener una copia del archivo o datos en otro lugar, para que si se pierden o se dañan, puedas recuperarlos fácilmente. Es como tener un backup del libro en otro lugar si lo pierdes.
```

Copia en otro lugar para recuperar datos perdidos o dañados; definición simple suficiente.

## t10 — ÚTIL

**Entrada literal**
```text
Explain gravity, pero sin tecnicismos
```

**Respuesta literal**
```text
Gravity es esa fuerza que mantiene todo lo que está en la Tierra pegado al suelo. Es como si todo lo que tienes en tus manos, como un libro o un lápiz, tuviera un hilo invisible que lo mantiene allí. Sin esa fuerza, todo se iría volando.
```

Explicación cotidiana de atracción hacia la Tierra; hilo presentado como analogía, no hecho literal.

## t11 — ÚTIL

**Entrada literal**
```text
no abras Paint
```

**Respuesta literal**
```text
No abriré Paint.
```

Respeta no abrir Paint; no anuncia ejecución.

## t12 — ÚTIL

**Entrada literal**
```text
what is the capital of Peru
```

**Respuesta literal**
```text
Lima
```

Lima es la capital de Perú.

## t13 — ÚTIL

**Entrada literal**
```text
Explain photosynthesis in two sentences.
```

**Respuesta literal**
```text
Photosynthesis is when plants use sunlight to convert carbon dioxide and water into glucose and oxygen. It's like nature's way of making food and releasing fresh air.
```

Dos oraciones; fotosíntesis explica luz,agua,CO2,glucosa y oxígeno.

## t14 — ÚTIL

**Entrada literal**
```text
Explícame por qué el hielo flota.
```

**Respuesta literal**
```text
El hielo flota porque es menos denso que el agua líquida. Cuando el agua se congela, sus moléculas se alejan y ocupan más espacio, así que el hielo pesa menos por volumen y flota.
```

Menor densidad del hielo por expansión: explicación correcta.

## t15 — ÚTIL

**Entrada literal**
```text
¿Qué diferencia hay entre un archivo y una carpeta? Reply in Spanglish.
```

**Respuesta literal**
```text
Un archivo es un archivo de datos, como un documento o una imagen, mientras que una carpeta es como una caja donde puedes guardar varios archivos.
```

Ejemplos distinguen archivo de contenedor; definición circular inicial mejorable, pero diferencia útil.

## t16 — ÚTIL

**Entrada literal**
```text
What is on my to do list?
```

**Respuesta literal**
```text
Your to-do list is empty right now.
```

Lista vacía en el perfil de prueba según lectura real; no extrapolar al resto de perfiles.

## t17 — ÚTIL

**Entrada literal**
```text
cierra la ventana titulada Ventana C03 de prueba
```

**Respuesta literal**
```text
¿Quieres confirmar la cerrada de la ventana titulada "Ventana C03 de prueba"? Elige: confirmar o cancelar.
```

Pregunta por confirmar/cancelar el cierre de la ventana concreta, antes del efecto.

## t18 — ÚTIL

**Entrada literal**
```text
cancelar
```

**Respuesta literal**
```text
Se canceló la solicitud de cerrar la ventana titulada "Ventana C03 de prueba". El sistema detectó la ventana maximizada con el título indicado, pero la acción fue cancelada. No se realizó el cierre.
```

Cancela la solicitud, conserva que no se cerró la ventana.

## t19 — ÚTIL

**Entrada literal**
```text
cierra la ventana titulada Ventana C03 de prueba
```

**Respuesta literal**
```text
¿Quieres confirmar la cerrada de la ventana titulada "Ventana C03 de prueba"? Elige: confirmar o cancelar.
```

Nueva pregunta de confirmación para la ventana concreta; no reutiliza autorización cancelada.

## t20 — ÚTIL

**Entrada literal**
```text
confirmar
```

**Respuesta literal**
```text
Se confirmó que se cerró la ventana titulada "Ventana C03 de prueba". El proceso se completó correctamente.
```

Cierre de fixture propio confirmado por producto y por su proceso terminado antes de limpieza.

## t21 — ÚTIL

**Entrada literal**
```text
What time is it?
```

**Respuesta literal**
```text
It's 16:10.
```

Hora16:10 en inglés; sesión continúa tras cierre.

## t22 — AVERÍA INYECTADA — ESTADO RECUPERABLE

**Entrada literal**
```text
¿Qué hora es?
```

**Sin respuesta final.** Estado de producto: `composition_failed`.

Sin prosa por avería forzada. Estado composition_failed visible en protocolo, causa conservada y controles usables; no es una respuesta normal aprobada.

## t23 — RECUPERACIÓN ÚTIL

**Entrada literal**
```text
¿Qué hora es?
```

**Respuesta literal**
```text
Son las 16 horas y 10 minutos.
```

Tras restore, responde la hora correcta en la misma sesión y retira el error; se conserva fuera de la muestra normal.

## t24 — AVERÍA INYECTADA — ESTADO RECUPERABLE

**Entrada literal**
```text
What time is it?
```

**Sin respuesta final.** Estado de producto: `composition_failed`.

Sin prosa por avería forzada. Estado composition_failed visible en protocolo, causa conservada y controles usables; no es una respuesta normal aprobada.

## t25 — RECUPERACIÓN ÚTIL

**Entrada literal**
```text
What time is it?
```

**Respuesta literal**
```text
It's 16:10.
```

Tras restore, responde la hora correcta en la misma sesión y retira el error; se conserva fuera de la muestra normal.

## t26 — AVERÍA INYECTADA — ESTADO RECUPERABLE

**Entrada literal**
```text
Dime la hora, please.
```

**Sin respuesta final.** Estado de producto: `composition_failed`.

Sin prosa por avería forzada. Estado composition_failed visible en protocolo, causa conservada y controles usables; no es una respuesta normal aprobada.

## t27 — RECUPERACIÓN ÚTIL

**Entrada literal**
```text
Dime la hora, please.
```

**Respuesta literal**
```text
Son las 16 horas y 10 minutos.
```

Tras restore, responde la hora correcta en la misma sesión y retira el error; se conserva fuera de la muestra normal.
