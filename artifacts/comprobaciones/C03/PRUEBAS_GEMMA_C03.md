# C03 — pruebas literales de los modelos Gemma heredados

**36 respuestas directas del modelo; ninguna de estas corridas acredita aceptación del producto.** Las nueve preguntas se repiten para comparar configuraciones. Los hechos de estado provienen de una captura verificada anterior; no son nuevas lecturas del PC.

Las evaluaciones son adjudicación individual del asistente, realizada después de leer las respuestas. Criterios: utilidad, fidelidad, idioma solicitado y naturalidad. Un final generado no equivale a aprobado. No se ha promovido ninguno de estos candidatos.

| Configuración | Aprobadas en este diagnóstico |
|---|---|
| standard_base | 4/9 |
| inherited_lora | 3/9 |
| standard_base_thinking | 4/9 |
| published_baxy | 4/9 |

El control conserva los mismos payloads y sampler. La variante thinking permite hasta 1024 tokens totales y activa razonamiento nativo; las otras lo desactivan. Los payloads completos y las huellas están en PREREG.json. Aquí se muestra sólo el contenido final del modelo, no su canal interno.

## astra-gemma-inherited-ready

[PREREG.json](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-gemma-inherited-ready/PREREG.json>) · [RESULT.json](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-gemma-inherited-ready/RESULT.json>) · [replies.jsonl](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-gemma-inherited-ready/replies.jsonl>)

### standard_base · t8

**Entrada literal**

```text
Explain encryption, pero en simple
```

**Respuesta literal**

```text
Encryption is basically scrambling your data so nobody can read it without the right key. Think of it like putting a secret code on a message. You use an algorithm to turn readable data into unreadable ciphertext, and you need the same key to turn it back.
```

**NO APROBADO:** Sólo inglés; además generaliza el uso de la misma clave, que no cubre el cifrado asimétrico.

### standard_base · t9

**Entrada literal**

```text
responde en spanglish: qué es una copia de seguridad
```

**Respuesta literal**

```text
A backup is like saving your important stuff in a different place, you know? It's a copy of your data so if something bad happens to your original files, you still have a safe version to go back to. So, it's super important for security!
```

**NO APROBADO:** No respeta la petición explícita de spanglish: contesta sólo en inglés.

### standard_base · t10

**Entrada literal**

```text
Explain gravity, pero sin tecnicismos
```

**Respuesta literal**

```text
Gravity is basically a force that pulls everything towards the center of a big thing, like the Earth. It's what keeps your feet on the ground and makes things fall down instead of floating away into space. Think of it as the Earth giving everything a gentle hug and keeping it close.
```

**NO APROBADO:** No respeta la mezcla de idiomas: contesta sólo en inglés.

### standard_base · t13

**Entrada literal**

```text
Explain photosynthesis in two sentences.
```

**Respuesta literal**

```text
Photosynthesis is the process where plants use sunlight, water, and carbon dioxide to create their own food, which is sugar. This process also releases oxygen into the atmosphere as a byproduct.
```

**APROBADO:** Explicación pertinente en inglés, en dos oraciones.

### standard_base · t14

**Entrada literal**

```text
Explícame por qué el hielo flota.
```

**Respuesta literal**

```text
El hielo flota porque el agua se expande al congelarse, y esa expansión le da un poco de flotabilidad al hielo. Esto significa que el hielo es menos denso que el agua líquida, por lo que puede mantenerse a flote.
```

**APROBADO:** Explica la menor densidad del hielo en español; la comparación de peso debe entenderse a igual volumen.

### standard_base · t15

**Entrada literal**

```text
¿Qué diferencia hay entre un archivo y una carpeta? Reply in Spanglish.
```

**Respuesta literal**

```text
Okay, a file is like a single thing, like a document or a picture, you know? A folder, on the other hand, is like a container, a place where you put those files together to keep things organized. So, a file is the content, and the folder is the organization structure.
```

**NO APROBADO:** Distingue archivo y carpeta, pero ignora la petición explícita de spanglish.

### standard_base · t2

**Entrada literal**

```text
Dime la hora y el estado del audio.
```

**Respuesta literal**

```text
La hora local es 12:18. El audio no está silenciado y el volumen es 100.
```

**APROBADO:** Conserva hora, volumen y ausencia de silencio; no afirma haberlos cambiado.

### standard_base · t4

**Entrada literal**

```text
Tell me the time and the volume.
```

**Respuesta literal**

```text
The time is 12:18 and the volume is 100, not muted.
```

**APROBADO:** Conserva la hora y el volumen solicitados, en inglés.

### standard_base · t6

**Entrada literal**

```text
What time is it y cómo está el audio?
```

**Respuesta literal**

```text
La hora local es 12:18 y el audio está sin silenciar con un nivel de 100.
```

**NO APROBADO:** Conserva los datos, pero responde sólo en español; no satisface spanglish.

### inherited_lora · t8

**Entrada literal**

```text
Explain encryption, pero en simple
```

**Respuesta literal**

```text
Encryption is like putting a secret code on your message so only the person with the key can read it. It scrambles the message so hackers can't read it if they intercept it. Basically, it makes your data unreadable to anyone else.
```

**NO APROBADO:** No respeta la mezcla de idiomas: contesta sólo en inglés.

### inherited_lora · t9

**Entrada literal**

```text
responde en spanglish: qué es una copia de seguridad
```

**Respuesta literal**

```text
A backup is like making a photocopy of your important stuff and keeping it in a safe place. If your original gets lost, you can always use the copy to get it back. So, it's a safety net for all your data.
```

**NO APROBADO:** No respeta la petición explícita de spanglish: contesta sólo en inglés.

### inherited_lora · t10

**Entrada literal**

```text
Explain gravity, pero sin tecnicismos
```

**Respuesta literal**

```text
Gravity is what pulls everything down to the center of the Earth. It's the force that keeps us on the ground and the planets orbiting the sun. That's what makes things fall instead of floating away.
```

**NO APROBADO:** No respeta la mezcla de idiomas: contesta sólo en inglés.

### inherited_lora · t13

**Entrada literal**

```text
Explain photosynthesis in two sentences.
```

**Respuesta literal**

```text
Photosynthesis is the process where plants use sunlight, water, and carbon dioxide to create their own food (glucose) and release oxygen into the atmosphere. This process is vital for almost all life on Earth.
```

**APROBADO:** Explicación pertinente en inglés, en dos oraciones.

### inherited_lora · t14

**Entrada literal**

```text
Explícame por qué el hielo flota.
```

**Respuesta literal**

```text
El hielo flota porque, cuando se forma, el agua se expande un poco al congelarse, lo que reduce su densidad y permite que el hielo quede en la superficie del agua líquida.
```

**APROBADO:** Explica la menor densidad del hielo en español; la comparación de peso debe entenderse a igual volumen.

### inherited_lora · t15

**Entrada literal**

```text
¿Qué diferencia hay entre un archivo y una carpeta? Reply in Spanglish.
```

**Respuesta literal**

```text
A file is a single item, like a picture or a document, but a folder is like a box where you put many files and other folders inside. So, a file is the thing itself, and a folder is the container for things.
```

**NO APROBADO:** Distingue archivo y carpeta, pero ignora la petición explícita de spanglish.

### inherited_lora · t2

**Entrada literal**

```text
Dime la hora y el estado del audio.
```

**Respuesta literal**

```text
La hora es 12:18 y el volumen está al 100 por ciento.
```

**NO APROBADO:** Omite si el audio está silenciado: sólo comunica hora y volumen.

### inherited_lora · t4

**Entrada literal**

```text
Tell me the time and the volume.
```

**Respuesta literal**

```text
The time is 12:18 and the volume is 100.
```

**APROBADO:** Conserva la hora y el volumen solicitados, en inglés.

### inherited_lora · t6

**Entrada literal**

```text
What time is it y cómo está el audio?
```

**Respuesta literal**

```text
Es las 12:18 y el audio está al 100%.
```

**NO APROBADO:** Omite el estado de silencio y no produce spanglish natural; «Es las» es incorrecto.

## astra-gemma-standard-thinking

[PREREG.json](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-gemma-standard-thinking/PREREG.json>) · [RESULT.json](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-gemma-standard-thinking/RESULT.json>) · [replies.jsonl](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-gemma-standard-thinking/replies.jsonl>)

### standard_base_thinking · t8

**Entrada literal**

```text
Explain encryption, pero en simple
```

**Respuesta literal**

```text
Encryption is basically turning your data into a secret code, like a secret language. It makes the information unreadable to anyone who tries to peek at it, which is super secure. When you send something online, encryption protects it so hackers can't read your private stuff. It's all about keeping your data safe, you know?
```

**NO APROBADO:** Sólo inglés; además presenta el cifrado con garantías excesivas de seguridad.

### standard_base_thinking · t9

**Entrada literal**

```text
responde en spanglish: qué es una copia de seguridad
```

**Respuesta literal**

```text
A backup, es when you save a copy of your data in a different place. If your original files get corrupted or you lose your device, you can use that backup to restore everything. It's super important for safety, you know?
```

**NO APROBADO:** La mezcla «A backup, es when» es forzada y no logra la naturalidad exigida.

### standard_base_thinking · t10

**Entrada literal**

```text
Explain gravity, pero sin tecnicismos
```

**Respuesta literal**

```text
Gravity is that invisible force that pulls everything towards everything else. Es lo que te mantiene en el suelo y hace que las cosas caigan, ¿entiendes? The bigger something is, the stronger the pull, so it keeps planets orbiting and keeps us all together. Simple, right?
```

**NO APROBADO:** Sí mezcla idiomas, pero equipara tamaño con intensidad de atracción sin aclarar masa o distancia. No se acepta la precisión conceptual.

### standard_base_thinking · t13

**Entrada literal**

```text
Explain photosynthesis in two sentences.
```

**Respuesta literal**

```text
Photosynthesis is the process where plants use sunlight, water, and carbon dioxide to create their own food, which is glucose, and in the process, they release oxygen into the atmosphere. This process is essential for most life on Earth.
```

**APROBADO:** Explicación pertinente en inglés, en dos oraciones.

### standard_base_thinking · t14

**Entrada literal**

```text
Explícame por qué el hielo flota.
```

**Respuesta literal**

```text
El hielo flota porque el agua se expande y se vuelve menos densa cuando se congela. Esto significa que el hielo pesa menos por volumen que el agua líquida, por lo que es más ligero y flota en la superficie.
```

**APROBADO:** Explica la menor densidad del hielo en español; la comparación de peso debe entenderse a igual volumen.

### standard_base_thinking · t15

**Entrada literal**

```text
¿Qué diferencia hay entre un archivo y una carpeta? Reply in Spanglish.
```

**Respuesta literal**

```text
A file is the actual data, like your document or picture, you know? The folder, on the other hand, is just the container, like a box, where you put all your files to keep things organized. So, the file is the *stuff*, and the folder is the *organizer*.
```

**NO APROBADO:** Distingue archivo y carpeta, pero ignora la petición explícita de spanglish.

### standard_base_thinking · t2

**Entrada literal**

```text
Dime la hora y el estado del audio.
```

**Respuesta literal**

```text
La hora local es 12:18. El audio no está silenciado y el nivel es 100.
```

**APROBADO:** Conserva hora, volumen y ausencia de silencio; no afirma haberlos cambiado.

### standard_base_thinking · t4

**Entrada literal**

```text
Tell me the time and the volume.
```

**Respuesta literal**

```text
The local clock is 12:18. The audio is not muted, and the volume level is 100.
```

**APROBADO:** Conserva la hora y el volumen solicitados, en inglés.

### standard_base_thinking · t6

**Entrada literal**

```text
What time is it y cómo está el audio?
```

**Respuesta literal**

```text
La hora local es 12:18. El audio no está muteado y el nivel es 100.
```

**NO APROBADO:** Datos conservados; «muteado» aislado no satisface el contrato de combinar frases de ambos idiomas.

## astra-gemma-published

[PREREG.json](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-gemma-published/PREREG.json>) · [RESULT.json](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-gemma-published/RESULT.json>) · [replies.jsonl](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-gemma-published/replies.jsonl>)

### published_baxy · t8

**Entrada literal**

```text
Explain encryption, pero en simple
```

**Respuesta literal**

```text
Encryption is basically scrambling data so no one can read it unless they have the secret key. Think of it like writing a secret message in code. Easy peasy. 😉
```

**NO APROBADO:** No respeta la mezcla de idiomas: contesta sólo en inglés.

### published_baxy · t9

**Entrada literal**

```text
responde en spanglish: qué es una copia de seguridad
```

**Respuesta literal**

```text
A backup is like having a spare copy of your stuff, so if the original gets messed up, you can just use the copy. It keeps everything safe.
```

**NO APROBADO:** Sólo inglés y termina con una garantía excesiva: «It keeps everything safe».

### published_baxy · t10

**Entrada literal**

```text
Explain gravity, pero sin tecnicismos
```

**Respuesta literal**

```text
Gravity is basically the force that pulls everything towards everything else. Like the Earth pulling you down, and you pulling the Earth up. It's what keeps us on the ground and stops us from floating away into space.
```

**NO APROBADO:** No respeta la mezcla de idiomas: contesta sólo en inglés.

### published_baxy · t13

**Entrada literal**

```text
Explain photosynthesis in two sentences.
```

**Respuesta literal**

```text
Photosynthesis is how plants make their own food using sunlight, water, and carbon dioxide. They release oxygen as a byproduct, which we breathe.
```

**APROBADO:** Explicación pertinente en inglés, en dos oraciones.

### published_baxy · t14

**Entrada literal**

```text
Explícame por qué el hielo flota.
```

**Respuesta literal**

```text
El hielo flota porque, cuando se congela, sus moléculas se ordenan en una estructura que es menos densa que el agua líquida, por eso el hielo es menos pesado y flota.
```

**APROBADO:** Explica la menor densidad del hielo en español; la comparación de peso debe entenderse a igual volumen.

### published_baxy · t15

**Entrada literal**

```text
¿Qué diferencia hay entre un archivo y una carpeta? Reply in Spanglish.
```

**Respuesta literal**

```text
A file is like a single thing, like a picture or a document, but a folder is like a box where you put lots of files and other folders inside it, so you can organize stuff better.
```

**NO APROBADO:** Distingue archivo y carpeta, pero ignora la petición explícita de spanglish.

### published_baxy · t2

**Entrada literal**

```text
Dime la hora y el estado del audio.
```

**Respuesta literal**

```text
La hora es 12:18 y el audio no está silenciado, el volumen es 100.
```

**APROBADO:** Conserva hora, volumen y ausencia de silencio; no afirma haberlos cambiado.

### published_baxy · t4

**Entrada literal**

```text
Tell me the time and the volume.
```

**Respuesta literal**

```text
The local clock is 12:18 and the volume is 100%.
```

**APROBADO:** Conserva la hora y el volumen solicitados, en inglés.

### published_baxy · t6

**Entrada literal**

```text
What time is it y cómo está el audio?
```

**Respuesta literal**

```text
Listo, respondo de forma natural en spanglish.
```

**NO APROBADO:** Copia una intención de redacción en vez de contestar: omite hora, volumen y estado del audio.

