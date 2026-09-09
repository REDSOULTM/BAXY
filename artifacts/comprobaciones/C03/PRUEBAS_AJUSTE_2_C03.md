# C03 — segundo ajuste: preguntas y respuestas literales

**54 respuestas: 27 casos con base y 27 con adaptador v2. Diagnóstico, no aceptación.**

Adjudicación manual: base 10/27; adaptador 21/27. En los 18 casos reservados de desarrollo: 8/18 y 15/18. No es un porcentaje de completitud del goal. Los datos de entrenamiento son sintéticos; las respuestas de abajo proceden del modelo local y no se han corregido.

Mejoran los resultados compuestos, pero persisten fallos de idioma y precisión. **Adaptador no promovido**: el recorrido integrado posterior sigue fallando.

[PREREG.json](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-lora-pilot2-evaluation/PREREG.json>) · [RESULT.json](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-lora-pilot2-evaluation/RESULT.json>) · [replies.jsonl](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-lora-pilot2-evaluation/replies.jsonl>)

## base · day-night-es

**Entrada literal**

```text
¿Por qué hay día y noche?
```

**Respuesta literal**

```text
Porque la Tierra gira sobre su eje mientras orbita al Sol. Cuando un lugar está hacia el Sol, es día; cuando está lejos de él, es noche. Esto ocurre de forma continua y constante. El giro tarda unos 24 horas en completarse.
```

**NO APROBADO:** Confunde alejarse del Sol con quedar orientado al lado opuesto; «unos 24 horas» es incorrecto.

## base · day-night-en

**Entrada literal**

```text
Why do day and night happen?
```

**Respuesta literal**

```text
Day and night happen because the Earth rotates on its axis every 24 hours. As it spins, different parts of the planet face the Sun (day) or are turned away from it (night). This rotation creates the cycle of day and night we experience. The Earth’s axis is tilted, which also affects the length and angle of daylight, but the rotation is what causes the daily cycle.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## base · day-night-mixed

**Entrada literal**

```text
Why do we have day and night? Explícalo en spanglish.
```

**Respuesta literal**

```text
Porque la Tierra gira sobre su eje, como un giro de un balón, y cuando un lado está hacia el Sol, es día; cuando está lejos, es noche. Es como si el planeta tuviera un reloj interno que se enciende y se apaga cada 12 horas. No es un accidente, es el movimiento natural. Si no girara, todo sería luz todo el tiempo.
```

**NO APROBADO:** Sólo español; inventa un ciclo fijo de 12 horas y que sin rotación todo sería luz.

## base · heat-metal-es

**Entrada literal**

```text
¿Por qué una cuchara metálica se calienta en una sopa caliente?
```

**Respuesta literal**

```text
Porque el calor de la sopa se transmite a la cuchara metálica mediante el calor conductivo, y el metal es un buen conductor de calor, por eso se calienta rápidamente.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## base · heat-metal-en

**Entrada literal**

```text
Why does a metal spoon get hot in hot soup?
```

**Respuesta literal**

```text
Because metal conducts heat well, so the warmth from the soup travels quickly through the spoon. The atoms in the metal vibrate faster when they absorb heat, transferring energy to the handle. This makes the whole spoon warmer, especially if you're holding it in the soup. It's not magic—just science!
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## base · heat-metal-mixed

**Entrada literal**

```text
¿Por qué se calienta a metal spoon in hot soup? Responde en spanglish.
```

**Respuesta literal**

```text
Porque el calor se transmite por conducción: el metal de la cuchara absorbe el calor del sopa caliente y se calienta. El metal es un buen conductor, así que el calor se mueve rápido por su estructura. La cuchara se calienta hasta que su temperatura alcanza la del sopa. ¡Y eso es todo, amigo!
```

**NO APROBADO:** Sólo español, con «del sopa» y cierre innecesario; no satisface idioma/naturalidad.

## base · audio-holdout-0-es

**Entrada literal**

```text
¿A qué volumen está el audio y está silenciado?
```

**Respuesta literal**

```text
El audio está en 35.
```

**NO APROBADO:** Omite si está silenciado y la unidad del volumen.

## base · audio-holdout-0-en

**Entrada literal**

```text
What is the audio level, and is it muted?
```

**Respuesta literal**

```text
The audio level is 35, and it is not muted.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## base · audio-holdout-0-mixed

**Entrada literal**

```text
What is the audio level y está silenciado? Reply in Spanglish.
```

**Respuesta literal**

```text
El audio está en 35. No está silenciado.
```

**NO APROBADO:** Hechos correctos, pero sólo español.

## base · audio-holdout-1-es

**Entrada literal**

```text
¿A qué volumen está el audio y está silenciado?
```

**Respuesta literal**

```text
El audio está en volumen 72.
```

**NO APROBADO:** Omite que el audio está silenciado.

## base · audio-holdout-1-en

**Entrada literal**

```text
What is the audio level, and is it muted?
```

**Respuesta literal**

```text
The audio level is 72, and it is muted.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## base · audio-holdout-1-mixed

**Entrada literal**

```text
What is the audio level y está silenciado? Reply in Spanglish.
```

**Respuesta literal**

```text
El nivel de audio es 72, y está silenciado.
```

**NO APROBADO:** Hechos correctos, pero sólo español.

## base · compound-heldout-0-es

**Entrada literal**

```text
Dime qué hora es, el volumen y si el sonido está silenciado.
```

**Respuesta literal**

```text
La hora local es 08:36. El volumen está en 64 y el sonido no está silenciado.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## base · compound-heldout-0-en

**Entrada literal**

```text
Give me the time, volume and mute status.
```

**Respuesta literal**

```text
Local clock: 08:36  
Volume level: 64  
Mute status: off
```

**NO APROBADO:** Datos conservados, pero redacción como campos técnicos; no cumple la naturalidad exigida por C03.

## base · compound-heldout-0-mixed

**Entrada literal**

```text
¿Qué hora es? Also tell me the volume and mute status, en spanglish.
```

**Respuesta literal**

```text
La hora local es 08:36. El volumen está en 64 y no está muteado.
```

**NO APROBADO:** Sólo español; el préstamo muteado no constituye frases en ambos idiomas.

## base · compound-heldout-1-es

**Entrada literal**

```text
Dime qué hora es, el volumen y si el sonido está silenciado.
```

**Respuesta literal**

```text
La hora local es 16:47. El volumen está en 29 y el sonido está silenciado.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## base · compound-heldout-1-en

**Entrada literal**

```text
Give me the time, volume and mute status.
```

**Respuesta literal**

```text
The local clock is 16:47. The audio is muted. The volume level is 29.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## base · compound-heldout-1-mixed

**Entrada literal**

```text
¿Qué hora es? Also tell me the volume and mute status, en spanglish.
```

**Respuesta literal**

```text
La hora local es 16:47. El volumen está en 29 y está muteado.
```

**NO APROBADO:** Sólo español; el préstamo muteado no constituye frases en ambos idiomas.

## base · previous-t8

**Entrada literal**

```text
Explain encryption, pero en simple
```

**Respuesta literal**

```text
Encryption es como poner un código a los mensajes para que solo las personas con la clave puedan leerlos. Es como guardar un mensaje en un cajón con llave: si no tienes la llave, no puedes abrirlo. Así, los datos se protegen de que alguien los vea sin permiso.
```

**NO APROBADO:** Una palabra inglesa aislada no cumple la combinación natural de frases ES/EN.

## base · previous-t9

**Entrada literal**

```text
responde en spanglish: qué es una copia de seguridad
```

**Respuesta literal**

```text
Una copia de seguridad es como tener un backup de tus archivos, como una copia en otro lugar para que si se pierden, los puedas recuperar fácilmente. Es como tener un duplicado de tu libro de cocina en otro lugar.
```

**NO APROBADO:** Backup como préstamo aislado no satisface el spanglish solicitado.

## base · previous-t10

**Entrada literal**

```text
Explain gravity, pero sin tecnicismos
```

**Respuesta literal**

```text
Gravity es como si todo lo que está cerca se pegara suavemente, como si la Tierra tuviera un pequeño campo de atracción que mantiene a las cosas unidas. Es por eso que las cosas caen al suelo y no vuelan.
```

**NO APROBADO:** Analogía de pegarse imprecisa y mezcla limitada al nombre inglés.

## base · previous-t13

**Entrada literal**

```text
Explain photosynthesis in two sentences.
```

**Respuesta literal**

```text
Photosynthesis is how plants use sunlight to turn carbon dioxide and water into sugar and oxygen. It's like the plant is eating the sun's energy to grow and give us fresh air.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## base · previous-t14

**Entrada literal**

```text
Explícame por qué el hielo flota.
```

**Respuesta literal**

```text
El hielo flota porque es menos denso que el agua líquida. Cuando el agua se congela, sus moléculas se alejan unas de otras y ocupan más espacio, lo que la hace más ligera.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## base · previous-t15

**Entrada literal**

```text
¿Qué diferencia hay entre un archivo y una carpeta? Reply in Spanglish.
```

**Respuesta literal**

```text
Un archivo es un archivo de datos, como un documento o una imagen, mientras que una carpeta es como una caja que guarda varios archivos organizados. Es como tener un libro (archivo) y una estantería (carpeta) para guardarlos.
```

**NO APROBADO:** Definición inicial circular y sólo español pese a pedir spanglish.

## base · previous-t2

**Entrada literal**

```text
Dime la hora y el estado del audio.
```

**Respuesta literal**

```text
La hora local es 12:18. El audio está desmudado y el nivel de volumen es 100.
```

**NO APROBADO:** Introduce la palabra inexistente «desmudado».

## base · previous-t4

**Entrada literal**

```text
Tell me the time and the volume.
```

**Respuesta literal**

```text
The local clock is 12:18. The volume level is 100. The mute state is off.
```

**NO APROBADO:** Datos correctos, pero redacción técnica innecesaria («mute state is off») en vez de narración natural.

## base · previous-t6

**Entrada literal**

```text
What time is it y cómo está el audio?
```

**Respuesta literal**

```text
Es 12:18, el audio está activo y en volumen 100.
```

**NO APROBADO:** Sólo español; no satisface spanglish.

## pilot_lora · day-night-es

**Entrada literal**

```text
¿Por qué hay día y noche?
```

**Respuesta literal**

```text
La Tierra gira sobre su eje y su rotación nos da día y noche.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · day-night-en

**Entrada literal**

```text
Why do day and night happen?
```

**Respuesta literal**

```text
Earth spins on its axis once every 24 hours; when it faces the Sun, it's daytime; when it's away from the Sun, it's nighttime.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · day-night-mixed

**Entrada literal**

```text
Why do we have day and night? Explícalo en spanglish.
```

**Respuesta literal**

```text
La Tierra gira sobre su eje; that causes one side to face the Sun and the other to face away.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · heat-metal-es

**Entrada literal**

```text
¿Por qué una cuchara metálica se calienta en una sopa caliente?
```

**Respuesta literal**

```text
La cuchara se calienta al absorber calor de la sopa; el metal conduce el calor rápidamente.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · heat-metal-en

**Entrada literal**

```text
Why does a metal spoon get hot in hot soup?
```

**Respuesta literal**

```text
The metal spoon absorbs heat from the soup and transfers it to your hand.
```

**NO APROBADO:** Añade transferencia a una mano sin que se indique contacto y no explica la conducción del metal.

## pilot_lora · heat-metal-mixed

**Entrada literal**

```text
¿Por qué se calienta a metal spoon in hot soup? Responde en spanglish.
```

**Respuesta literal**

```text
El cuchillo se calienta al pasar calor del caldo; the metal conducts heat well.
```

**NO APROBADO:** Cambia la cuchara preguntada por un cuchillo.

## pilot_lora · audio-holdout-0-es

**Entrada literal**

```text
¿A qué volumen está el audio y está silenciado?
```

**Respuesta literal**

```text
El volumen está al 35% y el audio no está silenciado.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · audio-holdout-0-en

**Entrada literal**

```text
What is the audio level, and is it muted?
```

**Respuesta literal**

```text
The audio level is 35%; it is not muted.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · audio-holdout-0-mixed

**Entrada literal**

```text
What is the audio level y está silenciado? Reply in Spanglish.
```

**Respuesta literal**

```text
El volumen está al 35%; audio is not muted.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · audio-holdout-1-es

**Entrada literal**

```text
¿A qué volumen está el audio y está silenciado?
```

**Respuesta literal**

```text
El volumen está al 72% y el audio está silenciado.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · audio-holdout-1-en

**Entrada literal**

```text
What is the audio level, and is it muted?
```

**Respuesta literal**

```text
The volume is 72% and audio is muted.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · audio-holdout-1-mixed

**Entrada literal**

```text
What is the audio level y está silenciado? Reply in Spanglish.
```

**Respuesta literal**

```text
El volumen está al 72%; el audio está silenciado.
```

**NO APROBADO:** Conserva los hechos, pero responde sólo en español.

## pilot_lora · compound-heldout-0-es

**Entrada literal**

```text
Dime qué hora es, el volumen y si el sonido está silenciado.
```

**Respuesta literal**

```text
Son las 08:36, el volumen está al 64% y el audio no está silenciado.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · compound-heldout-0-en

**Entrada literal**

```text
Give me the time, volume and mute status.
```

**Respuesta literal**

```text
The time is 08:36, the volume is 64% and the audio is not muted.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · compound-heldout-0-mixed

**Entrada literal**

```text
¿Qué hora es? Also tell me the volume and mute status, en spanglish.
```

**Respuesta literal**

```text
Son las 08:36; the volume is 64% and audio is not muted.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · compound-heldout-1-es

**Entrada literal**

```text
Dime qué hora es, el volumen y si el sonido está silenciado.
```

**Respuesta literal**

```text
Son las 16:47, el volumen está al 29% y el audio está silenciado.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · compound-heldout-1-en

**Entrada literal**

```text
Give me the time, volume and mute status.
```

**Respuesta literal**

```text
The time is 16:47, audio volume is 29% and audio is muted.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · compound-heldout-1-mixed

**Entrada literal**

```text
¿Qué hora es? Also tell me the volume and mute status, en spanglish.
```

**Respuesta literal**

```text
Son las 16:47; the volume is 29% and audio is muted.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · previous-t8

**Entrada literal**

```text
Explain encryption, pero en simple
```

**Respuesta literal**

```text
La criptografía hace que el texto se convierta en algo que solo una persona con la clave puede descifrar.
```

**NO APROBADO:** Responde sólo en español pese a la petición mixta.

## pilot_lora · previous-t9

**Entrada literal**

```text
responde en spanglish: qué es una copia de seguridad
```

**Respuesta literal**

```text
Una copia de seguridad es un backup de tus datos; it can be used to restore them if something goes wrong.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · previous-t10

**Entrada literal**

```text
Explain gravity, pero sin tecnicismos
```

**Respuesta literal**

```text
La gravedad tira hacia abajo: todo lo que está cerca de la Tierra se atrae a ella. Esto hace que las cosas caigan cuando se sueltan.
```

**NO APROBADO:** Explicación pertinente, pero sólo en español.

## pilot_lora · previous-t13

**Entrada literal**

```text
Explain photosynthesis in two sentences.
```

**Respuesta literal**

```text
Plants take sunlight, carbon dioxide, and water to make food and release oxygen. The process happens mainly in the leaves and helps oxygenate the air we breathe.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · previous-t14

**Entrada literal**

```text
Explícame por qué el hielo flota.
```

**Respuesta literal**

```text
El hielo flota porque es menos denso que el agua líquida; cuando se congela, sus moléculas se separan y ocupan más espacio.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · previous-t15

**Entrada literal**

```text
¿Qué diferencia hay entre un archivo y una carpeta? Reply in Spanglish.
```

**Respuesta literal**

```text
Un archivo es un dato; una carpeta organiza archivos y otras carpetas.
```

**NO APROBADO:** Sólo español y definición poco informativa de archivo como un dato.

## pilot_lora · previous-t2

**Entrada literal**

```text
Dime la hora y el estado del audio.
```

**Respuesta literal**

```text
Son las 12:18. El volumen está al 100%; audio no está silenciado.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · previous-t4

**Entrada literal**

```text
Tell me the time and the volume.
```

**Respuesta literal**

```text
The time is 12:18; audio volume is 100% and audio is not muted.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

## pilot_lora · previous-t6

**Entrada literal**

```text
What time is it y cómo está el audio?
```

**Respuesta literal**

```text
Son las 12:18; el volumen está al 100%; audio is not muted.
```

**APROBADO:** Responde de forma útil y fiel, en el idioma solicitado.

