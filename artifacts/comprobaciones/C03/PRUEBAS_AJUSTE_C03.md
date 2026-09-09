# C03 — piloto de ajuste: preguntas y respuestas literales

**42 respuestas directas: 21 casos repetidos con base y adaptador. No son aceptación ni nuevas lecturas del PC.**

Revisión individual del asistente: base 7/21 útiles, fieles y adecuados al idioma; piloto 12/21. En los 12 casos reservados del piloto: 5/12 frente a 9/12. Hay mejora parcial, pero el adaptador invierte el silencio al combinar hora/audio y sigue fallando en idioma con historial. **No promovido.**

La pérdida de entrenamiento y el uso de memoria no cuentan como aciertos. Los objetivos de entrenamiento fueron escritos por el asistente; las respuestas siguientes sí proceden del modelo local.

[PREREG.json](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-lora-pilot-evaluation/PREREG.json>) · [RESULT.json](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-lora-pilot-evaluation/RESULT.json>) · [replies.jsonl](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-lora-pilot-evaluation/replies.jsonl>)

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

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

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

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

## base · heat-metal-en

**Entrada literal**

```text
Why does a metal spoon get hot in hot soup?
```

**Respuesta literal**

```text
Because metal conducts heat well, so the warmth from the soup travels quickly through the spoon. The atoms in the metal vibrate faster when they absorb heat, transferring energy to the handle. This makes the whole spoon warmer, especially if you're holding it in the soup. It's not magic—just science!
```

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

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

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

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

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

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

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

## base · previous-t14

**Entrada literal**

```text
Explícame por qué el hielo flota.
```

**Respuesta literal**

```text
El hielo flota porque es menos denso que el agua líquida. Cuando el agua se congela, sus moléculas se alejan unas de otras y ocupan más espacio, lo que la hace más ligera.
```

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

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
La Tierra gira alrededor de su propio eje y el Sol solo puede iluminar la mitad de su superficie a la vez.
```

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

## pilot_lora · day-night-en

**Entrada literal**

```text
Why do day and night happen?
```

**Respuesta literal**

```text
Earth's rotation on its axis causes day and night.
```

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

## pilot_lora · day-night-mixed

**Entrada literal**

```text
Why do we have day and night? Explícalo en spanglish.
```

**Respuesta literal**

```text
El Sol ilumina la Tierra en un lado, mientras el otro lado está en la noche. The Earth rotates around its axis, creating day and night.
```

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

## pilot_lora · heat-metal-es

**Entrada literal**

```text
¿Por qué una cuchara metálica se calienta en una sopa caliente?
```

**Respuesta literal**

```text
La cuchara metálica se calienta porque el calor se transmite al metal a través del contacto directo con la sopa caliente.
```

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

## pilot_lora · heat-metal-en

**Entrada literal**

```text
Why does a metal spoon get hot in hot soup?
```

**Respuesta literal**

```text
The metal spoon transfers heat from the soup to the spoon.
```

**NO APROBADO:** Explicación tautológica y poco natural: la cuchara transfiere calor desde la sopa a la cuchara, sin explicar la conducción.

## pilot_lora · heat-metal-mixed

**Entrada literal**

```text
¿Por qué se calienta a metal spoon in hot soup? Responde en spanglish.
```

**Respuesta literal**

```text
El metal spoon se calienta al contacto directo con el calentamiento de la sopa; the spoon absorbs the heat of the soup.
```

**NO APROBADO:** Mezcla forzada «El metal spoon» y «contacto directo con el calentamiento»; no logra naturalidad.

## pilot_lora · audio-holdout-0-es

**Entrada literal**

```text
¿A qué volumen está el audio y está silenciado?
```

**Respuesta literal**

```text
El volumen del audio está al 35% y el audio no está silenciado.
```

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

## pilot_lora · audio-holdout-0-en

**Entrada literal**

```text
What is the audio level, and is it muted?
```

**Respuesta literal**

```text
The audio level is 35% and it is not muted.
```

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

## pilot_lora · audio-holdout-0-mixed

**Entrada literal**

```text
What is the audio level y está silenciado? Reply in Spanglish.
```

**Respuesta literal**

```text
El volumen está al 35% and the audio is not muted.
```

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

## pilot_lora · audio-holdout-1-es

**Entrada literal**

```text
¿A qué volumen está el audio y está silenciado?
```

**Respuesta literal**

```text
El volumen del audio está al 72% y está silenciado.
```

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

## pilot_lora · audio-holdout-1-en

**Entrada literal**

```text
What is the audio level, and is it muted?
```

**Respuesta literal**

```text
The audio level is 72%, and the audio is muted.
```

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

## pilot_lora · audio-holdout-1-mixed

**Entrada literal**

```text
What is the audio level y está silenciado? Reply in Spanglish.
```

**Respuesta literal**

```text
El volumen está al 72% y el audio está silenciado.
```

**NO APROBADO:** Conserva los hechos, pero sólo español.

## pilot_lora · previous-t8

**Entrada literal**

```text
Explain encryption, pero en simple
```

**Respuesta literal**

```text
La criptografía se usa para proteger datos. Se convierte la información en algo que solo las personas autorizadas pueden entender.
```

**NO APROBADO:** Sólo español y sustituye cifrado por el concepto más amplio de criptografía.

## pilot_lora · previous-t9

**Entrada literal**

```text
responde en spanglish: qué es una copia de seguridad
```

**Respuesta literal**

```text
A backup is a copy of your data, saved to a safe place. Una copia de seguridad es una copia de tus datos guardada en un lugar seguro.
```

**NO APROBADO:** Repite una traducción completa, expresamente excluida por el contrato de spanglish.

## pilot_lora · previous-t10

**Entrada literal**

```text
Explain gravity, pero sin tecnicismos
```

**Respuesta literal**

```text
Gravity is like an invisible force that pulls things toward each other, like how the Earth pulls you down to the ground.
```

**NO APROBADO:** La explicación mejora, pero responde sólo en inglés.

## pilot_lora · previous-t13

**Entrada literal**

```text
Explain photosynthesis in two sentences.
```

**Respuesta literal**

```text
Photosynthesis is when plants use sunlight to make food, like sugar, from carbon dioxide and water. It also produces oxygen as a byproduct.
```

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

## pilot_lora · previous-t14

**Entrada literal**

```text
Explícame por qué el hielo flota.
```

**Respuesta literal**

```text
El hielo flota porque el agua sólida (el hielo) es menos densa que el agua líquida.
```

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

## pilot_lora · previous-t15

**Entrada literal**

```text
¿Qué diferencia hay entre un archivo y una carpeta? Reply in Spanglish.
```

**Respuesta literal**

```text
Un archivo es un documento, como una foto o un texto, mientras que una carpeta es un contenedor que almacena varios archivos.
```

**NO APROBADO:** Sólo español; además reduce archivo a documento, aunque puede contener otros datos.

## pilot_lora · previous-t2

**Entrada literal**

```text
Dime la hora y el estado del audio.
```

**Respuesta literal**

```text
La hora es 12:18, el volumen está al 100% y el audio está desactivado.
```

**NO APROBADO:** Afirma audio desactivado cuando muted=false: inversión de un hecho verificado.

## pilot_lora · previous-t4

**Entrada literal**

```text
Tell me the time and the volume.
```

**Respuesta literal**

```text
The local clock is 12:18, the volume is 100% and the audio is not muted.
```

**APROBADO:** Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.

## pilot_lora · previous-t6

**Entrada literal**

```text
What time is it y cómo está el audio?
```

**Respuesta literal**

```text
La hora local es 12:18 y el audio está activo, al 100%.
```

**NO APROBADO:** Hechos conservados, pero sólo español.

