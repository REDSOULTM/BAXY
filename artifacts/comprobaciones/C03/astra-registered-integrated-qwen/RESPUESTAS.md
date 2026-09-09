# astra-registered-integrated-qwen

Pruebas conocidas de desarrollo. Publicación y utilidad se evalúan por separado. Las inyecciones no cuentan como turnos normales.

## t1 — ÚTIL

**Entrada literal**
```text
¿Qué hora es?
```

**Respuesta literal**
```text
Son las 16 horas y 17 minutos.
```

Hora16:17 equivalente al reloj observado; unidades horas/minutos conservadas.

## t2 — FALLO

**Entrada literal**
```text
Dime la hora y el estado del audio.
```

**Respuesta literal**
```text
La hora local es 16:17. El audio está desmudo, con un nivel de volumen de 100.
```

FALLO DE NATURALIDAD: conserva16:17,volumen100 y desactivación de muteo, pero inventa/desforma el término desmudo. No aprobado como prosa natural.

## t3 — ÚTIL

**Entrada literal**
```text
What time is it?
```

**Respuesta literal**
```text
It's 16:17.
```

Hora16:17 correcta, inglés.

## t4 — ÚTIL

**Entrada literal**
```text
Tell me the time and the volume.
```

**Respuesta literal**
```text
The local clock is 16:17. The volume is 100, and the device is not muted.
```

Hora16:17,volumen100,muted:false conservados en inglés.

## t5 — ÚTIL

**Entrada literal**
```text
Dime la hora, please, en spanglish
```

**Respuesta literal**
```text
Ahora son las 16:17.
```

Hora16:17 correcta; español válido para petición mixta.

## t6 — ÚTIL

**Entrada literal**
```text
What time is it y cómo está el audio?
```

**Respuesta literal**
```text
Son las 16:17. El audio está activo y a nivel 100.
```

Hora16:17,audio activo y nivel100 conservados.

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
Una copia de seguridad es como tener una copia del archivo o datos en otro lugar, para que si se pierden o se dañan, puedas recuperarlos fácilmente. Es como tener un respaldo del libro en otro lugar si lo pierdes.
```

Copia en otro lugar para recuperar datos perdidos o dañados; definición simple suficiente.

## t10 — ÚTIL

**Entrada literal**
```text
Explain gravity, pero sin tecnicismos
```

**Respuesta literal**
```text
Gravity es esa fuerza que mantiene a las cosas pegadas al suelo, como cuando caes de una silla o un objeto se queda en el piso. Es como si todo lo que está cerca de la Tierra tuviera un pequeño hilo que lo atrae hacia abajo.
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
¿Quieres confirmar o cancelar la acción de cerrar la ventana titulada Ventana C03 de prueba?
```

Pregunta por confirmar/cancelar el cierre de la ventana concreta, antes del efecto.

## t18 — ÚTIL

**Entrada literal**
```text
cancelar
```

**Respuesta literal**
```text
Se canceló la solicitud de cerrar la ventana titulada "Ventana C03 de prueba". El sistema detectó la ventana correspondiente, pero la acción fue cancelada. No se realizó el cierre.
```

Cancela la solicitud, conserva que no se cerró la ventana.

## t19 — ÚTIL

**Entrada literal**
```text
cierra la ventana titulada Ventana C03 de prueba
```

**Respuesta literal**
```text
¿Quieres confirmar o cancelar la acción de cerrar la ventana titulada Ventana C03 de prueba?
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
It's 16:17.
```

Hora16:17 en inglés; sesión continúa tras cierre.

## t22 — ÚTIL

**Entrada literal**
```text
¿Cómo está el audio?
```

**Respuesta literal**
```text
El audio está activo y el volumen está en 100.
```

Estado real inicial: volumen100,muted:false.

## t23 — ÚTIL

**Entrada literal**
```text
Ajusta el volumen.
```

**Respuesta literal**
```text
¿Cuánto deseas ajustar el volumen y en qué dirección (subir o bajar)?
```

Pregunta por nivel/dirección faltantes y conserva objetivo pendiente.

## t24 — ÚTIL

**Entrada literal**
```text
Déjalo al 80%.
```

**Respuesta literal**
```text
El volumen se bajó al 80%. No está muteado.
```

Nivel80 aplicado,verified+succeeded+observed.applied verdaderos; sin muteo.

## t25 — ÚTIL

**Entrada literal**
```text
¿A qué volumen está?
```

**Respuesta literal**
```text
Está en volumen 80, no está mutado.
```

Lectura posterior80 coincide. Mutado es un préstamo/errata poco elegante; el nivel solicitado y la ausencia de muteo se entienden.

## t26 — ÚTIL

**Entrada literal**
```text
Set the volume.
```

**Respuesta literal**
```text
How much and in which direction should the volume be adjusted?
```

Pregunta en inglés por ajuste faltante y conserva objetivo.

## t27 — ÚTIL

**Entrada literal**
```text
Set it to 60%.
```

**Respuesta literal**
```text
The volume was set to 60%, and it is not muted.
```

Nivel60 realmente aplicado y narrado en inglés, sin muteo.

## t28 — ÚTIL

**Entrada literal**
```text
What is the volume?
```

**Respuesta literal**
```text
The volume is 60. Mute is off.
```

Lectura posterior60 con mute off coincide.

## t29 — ÚTIL

**Entrada literal**
```text
Set the volume, por favor.
```

**Respuesta literal**
```text
What level should the volume be set to?
```

Pregunta concreta por nivel; comprende petición mixta y conserva objetivo.

## t30 — ÚTIL

**Entrada literal**
```text
Al 40%, please.
```

**Respuesta literal**
```text
El volumen fue reducido al 40%, y no está muteado.
```

Fragmento40% resuelve aclaración; efecto verificado y narración correcta.

## t31 — ÚTIL

**Entrada literal**
```text
¿Cómo está el audio?
```

**Respuesta literal**
```text
El audio está activo y el volumen está en 40.
```

Lectura posterior40 coincide.

## t32 — ÚTIL

**Entrada literal**
```text
Pon el volumen al 100%.
```

**Respuesta literal**
```text
Puse el volumen al 100% y el sonido está activo.
```

Restauración real al100%,verificada y narrada.

## t33 — ÚTIL

**Entrada literal**
```text
¿Cómo está el audio?
```

**Respuesta literal**
```text
El audio está activo y el volumen está en 100.
```

Lectura final100,muted:false; estado original restaurado.

## t34 — AVERÍA INYECTADA — ESTADO RECUPERABLE

**Entrada literal**
```text
¿Qué hora es?
```

**Sin respuesta final.** Estado de producto: `composition_failed`.

Sin prosa por avería forzada. Estado composition_failed visible en protocolo, causa conservada y controles usables; no es una respuesta normal aprobada.

## t35 — RECUPERACIÓN ÚTIL

**Entrada literal**
```text
¿Qué hora es?
```

**Respuesta literal**
```text
Son las 16 horas y 18 minutos.
```

Tras restore, responde la hora correcta en la misma sesión y retira el error; se conserva fuera de la muestra normal.

## t36 — AVERÍA INYECTADA — ESTADO RECUPERABLE

**Entrada literal**
```text
What time is it?
```

**Sin respuesta final.** Estado de producto: `composition_failed`.

Sin prosa por avería forzada. Estado composition_failed visible en protocolo, causa conservada y controles usables; no es una respuesta normal aprobada.

## t37 — RECUPERACIÓN ÚTIL

**Entrada literal**
```text
What time is it?
```

**Respuesta literal**
```text
It's 16:18.
```

Tras restore, responde la hora correcta en la misma sesión y retira el error; se conserva fuera de la muestra normal.

## t38 — AVERÍA INYECTADA — ESTADO RECUPERABLE

**Entrada literal**
```text
Dime la hora, please.
```

**Sin respuesta final.** Estado de producto: `composition_failed`.

Sin prosa por avería forzada. Estado composition_failed visible en protocolo, causa conservada y controles usables; no es una respuesta normal aprobada.

## t39 — RECUPERACIÓN ÚTIL

**Entrada literal**
```text
Dime la hora, please.
```

**Respuesta literal**
```text
Son las 16 horas y 18 minutos.
```

Tras restore, responde la hora correcta en la misma sesión y retira el error; se conserva fuera de la muestra normal.
