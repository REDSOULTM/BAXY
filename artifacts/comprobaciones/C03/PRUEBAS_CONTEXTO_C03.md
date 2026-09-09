# C03: preguntas y respuestas del diagnóstico de contexto

**18 respuestas directas del modelo local; no son turnos de aceptación ni ejecuciones completas de BAXY.** Se exportan registros existentes sin ejecutar nuevas pruebas.

Se comparó el historial completo acotado (full), el historial con sólo mensajes del usuario (user_only), y la pregunta actual sin historial (isolated). Se conservaron las instrucciones de sistema. Los payloads de la primera comparación fueron reconstruidos a partir de corpus-warm usando el límite de 12 mensajes de la interfaz y el método chat del producto; no son una captura HTTP original.

Se utilizó Qwen3-4B-Instruct-2507 Q4_K_M, seed 0. Los PREREG enlazados conservan los payloads internos y las huellas de fuente/modelo. Las evaluaciones siguientes son revisión individual del asistente, posterior a la ejecución, sin convertir publicación en acierto.

**Decisión:** no adoptar ninguna poda del historial. Quitar mensajes no resuelve de forma consistente idioma o fidelidad y llega a cambiar el tema solicitado. No se modificó el historial del producto.

## astra-history-ablation-ready

Duración: 15.47 s. Pico GPU registrado: 3497.56 MiB.

[PREREG.json](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-history-ablation-ready/PREREG.json>) · [replies.jsonl](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-history-ablation-ready/replies.jsonl>) · [RESULT.json](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-history-ablation-ready/RESULT.json>)

### t8 · full

**Entrada literal**

```text
Explain encryption, pero en simple
```

**Respuesta literal del modelo**

```text
Encryption es como poner un código a los mensajes para que solo las personas con la clave puedan leerlos. Es como guardar un mensaje en un cajón con llave: si no tienes la llave, no puedes abrirlo. Así, los datos se protegen de que alguien los vea sin permiso.
```

**Evaluación:** Explicación básica pertinente; mezcla de idiomas mínima (Encryption).

### t8 · user_only

**Entrada literal**

```text
Explain encryption, pero en simple
```

**Respuesta literal del modelo**

```text
Claro, aquí va: la criptografía es como un código que convierte información en algo que solo las personas con la clave pueden entender. Es como si escribieras un mensaje en un idioma que solo tú y tu amigo conocéis — nadie más puede leerlo. Se usa para proteger datos, como contraseñas o transacciones en línea. Es como un muro que evita que los malos la vean.
```

**Evaluación:** Responde en español; sustituye cifrado por el concepto más amplio de criptografía y alarga la explicación.

### t9 · user_only

**Entrada literal**

```text
responde en spanglish: qué es una copia de seguridad
```

**Respuesta literal del modelo**

```text
Una copia de seguridad es como un backup: guarda una versión de tus archivos o datos en otro lugar, para que si algo pasa, como un error o un virus, puedas recuperarlos fácilmente. Es como tener una copia de tu libro en otra casa, así si lo pierdes, lo puedes encontrar. Se usa mucho para proteger información importante. Siempre se guarda en un lugar seguro o en la nube.
```

**Evaluación:** La finalidad es reconocible, pero «siempre» en un lugar seguro no está garantizado. Mezcla mínima.

### t9 · full

**Entrada literal**

```text
responde en spanglish: qué es una copia de seguridad
```

**Respuesta literal del modelo**

```text
Una copia de seguridad es como tener un backup de tus archivos, como un duplicado que guardas en otro lugar. Así, si pierdes o borras los originales, puedes recuperarlos fácilmente.
```

**Evaluación:** Explica correctamente la finalidad de la copia; spanglish limitado a backup.

### t10 · full

**Entrada literal**

```text
Explain gravity, pero sin tecnicismos
```

**Respuesta literal del modelo**

```text
Gravity es como si todo lo que está cerca se pegara suavemente, como si la Tierra tuviera un pequeño campo de atracción que mantiene a las cosas unidas. Es por eso que las cosas caen cuando las soltas y los planetas no se van al espacio.
```

**Evaluación:** Analogía imprecisa: gravedad no equivale a pegarse y la explicación de los planetas es insuficiente.

### t10 · user_only

**Entrada literal**

```text
Explain gravity, pero sin tecnicismos
```

**Respuesta literal del modelo**

```text
Una copia de seguridad es como tener un backup de tus archivos o datos, como si tuvieras un duplicado en otro lugar. Si algo pasa con tu dispositivo, como un error o un problema, puedes usar esa copia para recuperar lo que perdiste. Es como tener un "rescate" en caso de que se pierda todo. Así de simple.
```

**Evaluación:** Falla el tema: responde sobre copias de seguridad a una pregunta sobre gravedad.

### t13 · user_only

**Entrada literal**

```text
Explain photosynthesis in two sentences.
```

**Respuesta literal del modelo**

```text
La fotosíntesis es cómo las plantas usan la luz del sol para hacer su propio alimento y liberar oxígeno. Es como si las plantas estuvieran cocinando con la luz del sol.
```

**Evaluación:** El contenido básico es pertinente, pero cambia al español.

### t13 · full

**Entrada literal**

```text
Explain photosynthesis in two sentences.
```

**Respuesta literal del modelo**

```text
Photosynthesis is how plants use sunlight to turn carbon dioxide and water into food (sugar) and oxygen. It's like the plant is cooking with the sun's energy to grow and give us fresh air.
```

**Evaluación:** Explicación pertinente en inglés y en dos oraciones.

### t14 · full

**Entrada literal**

```text
Explícame por qué el hielo flota.
```

**Respuesta literal del modelo**

```text
El hielo flota porque es menos denso que el agua líquida. Cuando el agua se congela, sus moléculas se alejan unas de otras y ocupan más espacio, lo que hace que el hielo sea más ligero que el agua.
```

**Evaluación:** Identifica la menor densidad; «más ligero» necesita la comparación a igual volumen.

### t14 · user_only

**Entrada literal**

```text
Explícame por qué el hielo flota.
```

**Respuesta literal del modelo**

```text
El hielo flota porque es menos denso que el agua líquida. Cuando el agua se congela, sus moléculas se alejan y ocupan más espacio, por eso el hielo pesa menos por volumen y flota.
```

**Evaluación:** Explica correctamente la menor densidad y aclara peso por volumen.

### t15 · user_only

**Entrada literal**

```text
¿Qué diferencia hay entre un archivo y una carpeta? Reply in Spanglish.
```

**Respuesta literal del modelo**

```text
Un archivo es un archivo, como un documento o imagen, y una carpeta es como una caja donde guardas varios archivos. Es como tener un libro (archivo) y una bolsa (carpeta) para poner varios libros.
```

**Evaluación:** Definición inicial circular y omisión de la petición explícita de spanglish.

### t15 · full

**Entrada literal**

```text
¿Qué diferencia hay entre un archivo y una carpeta? Reply in Spanglish.
```

**Respuesta literal del modelo**

```text
Un archivo es un archivo de datos, como un documento o una imagen, mientras que una carpeta es como una caja que guarda varios archivos. Es como tener un libro (archivo) y una estantería (carpeta) para ponerlos.
```

**Evaluación:** Definición inicial circular y omisión de la petición explícita de spanglish.

## astra-history-isolated

Duración: 11.03 s. Pico GPU registrado: 3497.56 MiB.

[PREREG.json](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-history-isolated/PREREG.json>) · [replies.jsonl](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-history-isolated/replies.jsonl>) · [RESULT.json](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-history-isolated/RESULT.json>)

### t8 · isolated

**Entrada literal**

```text
Explain encryption, pero en simple
```

**Respuesta literal del modelo**

```text
Okay, imagine you have a secret message and you want only your friend to read it. So you use a special code — like shifting letters or mixing them up — so even if someone else sees the message, they can't understand it. That's encryption. It scrambles data so only people with the right key can decode it. Simple, right? 😎🔐
```

**Evaluación:** Contenido básico pertinente, pero sólo inglés y extensión excesiva frente a las instrucciones de la prueba.

### t9 · isolated

**Entrada literal**

```text
responde en spanglish: qué es una copia de seguridad
```

**Respuesta literal del modelo**

```text
Una copia de seguridad es un backup que guarda una copia del dato original, como archivos o datos del sistema, para protegerlos en caso de pérdida o daño. Se puede hacer en un disco externo, nube o servidor. Si el original se borra o se daña, puedes restaurar el archivo desde la copia. Es como tener un "doble" de tu información, así no te pierdes nada.
```

**Evaluación:** Finalidad pertinente; mezcla mínima limitada a backup, sin mejora clara de naturalidad.

### t10 · isolated

**Entrada literal**

```text
Explain gravity, pero sin tecnicismos
```

**Respuesta literal del modelo**

```text
Gravedad es como si todo lo que hay en el universo estuviera pegado por un hilo invisible. Lo que te mantiene en el suelo no es magia, es la atracción natural de los objetos hacia el centro de lo que está más cerca, como la Tierra. Es como si el mundo tuviera un pequeño campo de gravedad que arrastra todo lo que está cerca. Sin eso, todo se iría volando como un helado en la heladera.
```

**Evaluación:** Explicación física imprecisa y analogía final sin sentido; no respeta la mezcla de idiomas.

### t13 · isolated

**Entrada literal**

```text
Explain photosynthesis in two sentences.
```

**Respuesta literal del modelo**

```text
Photosynthesis is the process by which green plants use sunlight, carbon dioxide, and water to produce glucose and oxygen. It mainly happens in the leaves, where chlorophyll captures light energy to power the chemical reactions.
```

**Evaluación:** Explicación pertinente en inglés y en dos oraciones.

### t14 · isolated

**Entrada literal**

```text
Explícame por qué el hielo flota.
```

**Respuesta literal del modelo**

```text
El hielo flota porque es menos denso que el agua líquida. Cuando el agua se congela, sus moléculas se organizan en una estructura abierta y más espaciosa, lo que reduce su densidad. Esto significa que el hielo ocupará más volumen por unidad de masa que el agua líquida, por eso flota. Es un fenómeno único en la naturaleza.
```

**Evaluación:** La densidad está bien explicada, pero añade una afirmación falsa de exclusividad en la naturaleza.

### t15 · isolated

**Entrada literal**

```text
¿Qué diferencia hay entre un archivo y una carpeta? Reply in Spanglish.
```

**Respuesta literal del modelo**

```text
Un archivo es un archivo de datos, como un documento o imagen, y una carpeta es como una caja que organiza esos archivos. El archivo es lo que contiene la información, y la carpeta es solo el lugar donde lo guardas. Es como tener un libro (archivo) y una bolsa (carpeta) para meterlo. No se puede guardar un archivo sin una carpeta, pero sí puedes tener muchas carpetas sin archivos.
```

**Evaluación:** Circular, sólo español pese a pedir spanglish, y afirma una restricción universal injustificada sobre guardar archivos.

