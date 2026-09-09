# C03 — prueba de intensidad del adaptador

**27 respuestas directas, 16 aprobadas y 11 no aprobadas. No son aceptación.** El adaptador v2 completo obtuvo 21/27 en estos mismos casos; la escala 0,5 pierde calidad de idioma. Se descarta esta escala. El runtime registrado no se modificó.

La evaluación es manual. No se corrigió ninguna respuesta y no se cuentan los errores de arranque como respuestas.

## day-night-es

**Entrada literal**

```text
¿Por qué hay día y noche?
```

**Respuesta literal**

```text
La Tierra gira sobre su eje cada 24 horas, lo que hace que una parte esté iluminada por el Sol mientras la otra está en la sombra. Esto crea el ciclo diurno y nocturno que experimentamos.
```

**APROBADO:** Respuesta útil, fiel y en el idioma solicitado.

## day-night-en

**Entrada literal**

```text
Why do day and night happen?
```

**Respuesta literal**

```text
Earth spins on its axis, and as it rotates, different parts face the Sun, causing day and night. The Earth takes about 24 hours to complete one full rotation.
```

**APROBADO:** Respuesta útil, fiel y en el idioma solicitado.

## day-night-mixed

**Entrada literal**

```text
Why do we have day and night? Explícalo en spanglish.
```

**Respuesta literal**

```text
La Tierra gira sobre su eje y eso hace que un lado se vea iluminado y otro oscurecido. When the Earth rotates, one side faces the Sun and gets light; the other side is turned away and it’s dark.
```

**NO APROBADO:** Repite la explicación completa en inglés después del español.

## heat-metal-es

**Entrada literal**

```text
¿Por qué una cuchara metálica se calienta en una sopa caliente?
```

**Respuesta literal**

```text
La cuchara metálica se calienta porque el calor de la sopa se transmite al metal a través de la conducción térmica. El metal es un buen conductor de calor, por eso se calienta rápidamente.
```

**APROBADO:** Respuesta útil, fiel y en el idioma solicitado.

## heat-metal-en

**Entrada literal**

```text
Why does a metal spoon get hot in hot soup?
```

**Respuesta literal**

```text
The metal spoon gains heat from the soup through conduction. Metal is a good conductor of heat, so it transfers the thermal energy from the soup to the spoon quickly. The spoon's atoms vibrate more due to this heat transfer, increasing the temperature of the spoon.
```

**APROBADO:** Respuesta útil, fiel y en el idioma solicitado.

## heat-metal-mixed

**Entrada literal**

```text
¿Por qué se calienta a metal spoon in hot soup? Responde en spanglish.
```

**Respuesta literal**

```text
El metal se calienta porque transmite el calor del caldo; the spoon warms up because it conducts the soup’s heat.
```

**NO APROBADO:** Traduce otra vez la misma explicación completa.

## audio-holdout-0-es

**Entrada literal**

```text
¿A qué volumen está el audio y está silenciado?
```

**Respuesta literal**

```text
El audio está al 35% y no está silenciado.
```

**APROBADO:** Respuesta útil, fiel y en el idioma solicitado.

## audio-holdout-0-en

**Entrada literal**

```text
What is the audio level, and is it muted?
```

**Respuesta literal**

```text
The audio level is 35%; it is not muted.
```

**APROBADO:** Respuesta útil, fiel y en el idioma solicitado.

## audio-holdout-0-mixed

**Entrada literal**

```text
What is the audio level y está silenciado? Reply in Spanglish.
```

**Respuesta literal**

```text
El volumen está al 35% y no está silenciado.
```

**NO APROBADO:** Sólo español.

## audio-holdout-1-es

**Entrada literal**

```text
¿A qué volumen está el audio y está silenciado?
```

**Respuesta literal**

```text
El volumen está al 72% y el audio está silenciado.
```

**APROBADO:** Respuesta útil, fiel y en el idioma solicitado.

## audio-holdout-1-en

**Entrada literal**

```text
What is the audio level, and is it muted?
```

**Respuesta literal**

```text
The audio level is 72, and it is muted.
```

**APROBADO:** Respuesta útil, fiel y en el idioma solicitado.

## audio-holdout-1-mixed

**Entrada literal**

```text
What is the audio level y está silenciado? Reply in Spanglish.
```

**Respuesta literal**

```text
El volumen está al 72% y está silenciado.
```

**NO APROBADO:** Sólo español.

## compound-heldout-0-es

**Entrada literal**

```text
Dime qué hora es, el volumen y si el sonido está silenciado.
```

**Respuesta literal**

```text
Son las 08:36, el volumen está al 64% y el sonido no está silenciado.
```

**APROBADO:** Respuesta útil, fiel y en el idioma solicitado.

## compound-heldout-0-en

**Entrada literal**

```text
Give me the time, volume and mute status.
```

**Respuesta literal**

```text
The local time is 08:36, volume is 64%, and the audio is not muted.
```

**APROBADO:** Respuesta útil, fiel y en el idioma solicitado.

## compound-heldout-0-mixed

**Entrada literal**

```text
¿Qué hora es? Also tell me the volume and mute status, en spanglish.
```

**Respuesta literal**

```text
Son las 08:36; the volume is 64% and audio is not muted.
```

**APROBADO:** Respuesta útil, fiel y en el idioma solicitado.

## compound-heldout-1-es

**Entrada literal**

```text
Dime qué hora es, el volumen y si el sonido está silenciado.
```

**Respuesta literal**

```text
Son las 16:47, el volumen está al 29% y el audio está silenciado.
```

**APROBADO:** Respuesta útil, fiel y en el idioma solicitado.

## compound-heldout-1-en

**Entrada literal**

```text
Give me the time, volume and mute status.
```

**Respuesta literal**

```text
The local time is 16:47, the volume is 29%, and the audio is muted.
```

**APROBADO:** Respuesta útil, fiel y en el idioma solicitado.

## compound-heldout-1-mixed

**Entrada literal**

```text
¿Qué hora es? Also tell me the volume and mute status, en spanglish.
```

**Respuesta literal**

```text
Son las 16:47, el volumen está al 29% y el audio está silenciado.
```

**NO APROBADO:** Sólo español.

## previous-t8

**Entrada literal**

```text
Explain encryption, pero en simple
```

**Respuesta literal**

```text
La criptografía protege los datos como un código secreto; solo las personas con la clave pueden leerlos.
```

**NO APROBADO:** Sólo español.

## previous-t9

**Entrada literal**

```text
responde en spanglish: qué es una copia de seguridad
```

**Respuesta literal**

```text
Una copia de seguridad es una copia de tus archivos guardada en otro lugar para protegerlos si algo falla. It's like having a backup of your documents in case the original gets lost or damaged.
```

**NO APROBADO:** La segunda parte vuelve a explicar lo mismo en inglés; traducción repetida.

## previous-t10

**Entrada literal**

```text
Explain gravity, pero sin tecnicismos
```

**Respuesta literal**

```text
Gravity is like a invisible hand that pulls things toward each other. It's what makes apples fall to the ground and keeps the Moon in orbit around Earth.
```

**NO APROBADO:** Sólo inglés y error gramatical «a invisible».

## previous-t13

**Entrada literal**

```text
Explain photosynthesis in two sentences.
```

**Respuesta literal**

```text
Photosynthesis is when plants use sunlight to convert carbon dioxide and water into sugar and oxygen. It's like a natural factory that produces food and fresh air for living things.
```

**APROBADO:** Respuesta útil, fiel y en el idioma solicitado.

## previous-t14

**Entrada literal**

```text
Explícame por qué el hielo flota.
```

**Respuesta literal**

```text
El hielo flota porque es menos denso que el agua líquida, como un trasto que flota en el agua. Al congelarse, el agua se expande y deja de ser tan compacta.
```

**APROBADO:** Respuesta útil, fiel y en el idioma solicitado.

## previous-t15

**Entrada literal**

```text
¿Qué diferencia hay entre un archivo y una carpeta? Reply in Spanglish.
```

**Respuesta literal**

```text
Un archivo es un documento, imagen o archivo; una carpeta es como una caja que guarda varios archivos. Una carpeta puede contener muchos archivos, pero un archivo no puede contener otros archivos como una carpeta.
```

**NO APROBADO:** Definición circular de archivo y sólo español; también omite que un archivo contenedor puede almacenar otros.

## previous-t2

**Entrada literal**

```text
Dime la hora y el estado del audio.
```

**Respuesta literal**

```text
La hora es 12:18, el audio está activo y el volumen está al 100%.
```

**NO APROBADO:** «Audio activo» no responde de forma inequívoca al estado de silencio; puede sugerir reproducción que no se observó.

## previous-t4

**Entrada literal**

```text
Tell me the time and the volume.
```

**Respuesta literal**

```text
The time is 12:18 and the volume is 100%. The audio is not muted.
```

**APROBADO:** Respuesta útil, fiel y en el idioma solicitado.

## previous-t6

**Entrada literal**

```text
What time is it y cómo está el audio?
```

**Respuesta literal**

```text
Son las 12:18, audio a 100% y no está muteado.
```

**NO APROBADO:** Sólo español; muteado como préstamo no cumple mezcla natural de frases.

