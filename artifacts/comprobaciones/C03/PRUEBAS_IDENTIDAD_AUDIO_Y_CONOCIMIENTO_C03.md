# C03 — pruebas literales del tramo 38

Fecha: 2026-09-06. Desarrollo consumido; ninguna entrada cuenta como reserva de los cien turnos.

Tres consultas en el producto registrado y quince llamadas de diagnóstico al chat de BAXY. Las sondas conservan instrucciones, idioma y guardas de BAXY: no son el LLM solo. No se adoptó ninguna variante de prompt de estas sondas.

## Producto: nombre de la salida de audio

Fuente: [paired.json](astra-audio-endpoint-name3/paired.json), [prerregistro](astra-audio-endpoint-name3/PREREG.json), [resultado](astra-audio-endpoint-name3/RESULT.json). Endpoint predeterminado Multimedia: Altavoces (Realtek(R) Audio), nivel 100, muted=false. No demuestra qué endpoint usa cada aplicación. Tres respuestas útiles; la gramática menor no invalida la primera.

### Producto 1

**Entrada literal**
```text
Dime qué dispositivo de audio está activo
```

**Respuesta literal**
```text
El dispositivo de audio activo es los altavoces (Realtek(R) Audio). El volumen está en 100 y el sonido no está silenciado.
```

**APROBADO en desarrollo:** conserva los hechos necesarios para la consulta.

### Producto 2

**Entrada literal**
```text
mostrame el volumen
```

**Respuesta literal**
```text
El volumen de los altavoces (Realtek(R) Audio) está en 100 y no está silenciado.
```

**APROBADO en desarrollo:** conserva los hechos necesarios para la consulta.

### Producto 3

**Entrada literal**
```text
está silenciado el audio
```

**Respuesta literal**
```text
El volumen está en 100 y el audio no está silenciado.
```

**APROBADO en desarrollo:** conserva los hechos necesarios para la consulta.

## Conocimiento: política actual frente a brevedad flexible

Fuentes: [payloads y respuestas brutas](astra-knowledge-brief-policy/posts.jsonl), [respuestas del wrapper](astra-knowledge-brief-policy/replies.jsonl), [resultado](astra-knowledge-brief-policy/RESULT.json). Mismo modelo registrado, temperatura 0, historial vacío y máximo 128 tokens. Agua, aire y Steam son entradas históricas ya consumidas. SSID y explicación detallada son controles sintéticos, no uso humano acreditado.

### Sonda 1 — current

**Entrada literal**
```text
El agua es h2o?
```

**Respuesta literal**
```text
Sí, el agua es H₂O. Es una molécula compuesta por dos átomos de hidrógeno y uno de oxígeno. Es la fórmula química más conocida y fundamental para la vida.
```

ÚTIL en esta sonda: responde a la cuestión con explicación sencilla. No acredita comportamiento en producto con historial.

finish_reason de las llamadas asociadas: ['stop'].

### Sonda 2 — current

**Entrada literal**
```text
El aire es h20?
```

**Respuesta literal**
```text
No, el aire no es H2O. El aire es una mezcla de gases, principalmente nitrógeno (78%) y oxígeno (21%), mientras que H2O es el agua. El aire no contiene agua en forma líquida ni como compuesto principal.
```

PENDIENTE DE CALIDAD: distingue aire de agua, pero añade una generalización innecesaria sobre ausencia de agua líquida. No usar como aceptación del caso integrado anterior.

finish_reason de las llamadas asociadas: ['stop'].

### Sonda 3 — current

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
Steam es una plataforma de distribución y comercio de juegos online, creada por Valve. Permite descargar, jugar, comprar y gestionar juegos, además de ofrecer servicios como actualizaciones automáticas, soporte técnico y comunidad de jugadores. También incluye aplicaciones como Steam Workshop para crear y compartir contenido personalizado. Es muy popular en el mundo del gaming por su amplia selección y facilidad de uso.
```

ÚTIL en esta sonda: responde a la cuestión con explicación sencilla. No acredita comportamiento en producto con historial.

finish_reason de las llamadas asociadas: ['stop'].

### Sonda 4 — current

**Entrada literal**
```text
What is an SSID?
```

**Respuesta literal**
```text
An SSID is the name of a Wi-Fi network. It's what you see when you scan for available networks on your device. You need to enter the SSID to connect to a Wi-Fi network. It's like a password for your wireless connection, but instead of a password, it's a name.
```

NO APROBADO: la comparación con una contraseña confunde el nombre de red con autenticación.

finish_reason de las llamadas asociadas: ['stop'].

### Sonda 5 — current

**Entrada literal**
```text
Explica con detalle de qué gases se compone el aire y qué papel tiene la humedad.
```

**Respuesta literal**
```text
El aire se compone principalmente de nitrógeno (78%), oxígeno (21%), argón (0,9%), dióxido de carbono (0,04%) y pequeñas cantidades de gases inanimados como helio, neón, metano y vapor de agua. La humedad, o vapor de agua, es un componente variable que influye en el clima, la temperatura percibida y la capacidad del aire para retener gases como el CO₂. Aumenta la conductividad térmica y afecta la evaporación y la condensación
```

NO APROBADO: salida cortada al alcanzar 128 tokens (finish_reason=length); no completa el detalle solicitado. La brevedad no resuelve este límite.

finish_reason de las llamadas asociadas: ['length'].

### Sonda 6 — brief_by_request

**Entrada literal**
```text
El agua es h2o?
```

**Respuesta literal**
```text
Sí, el agua es H₂O. Dos átomos de hidrógeno unidos a uno de oxígeno.
```

ÚTIL en esta sonda: responde a la cuestión con explicación sencilla. No acredita comportamiento en producto con historial.

finish_reason de las llamadas asociadas: ['stop'].

### Sonda 7 — brief_by_request

**Entrada literal**
```text
El aire es h20?
```

**Respuesta literal**
```text
No, el aire no es H2O. El aire es una mezcla de gases, principalmente nitrógeno (aproximadamente el 78%) y oxígeno (aproximadamente el 21%), mientras que H2O es el agua.
```

ÚTIL en esta sonda: responde a la cuestión con explicación sencilla. No acredita comportamiento en producto con historial.

finish_reason de las llamadas asociadas: ['stop'].

### Sonda 8 — brief_by_request

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
Steam es una plataforma de distribución y comercio de juegos online, creada por Valve Corporation. Allí puedes comprar, descargar, jugar y gestionar juegos, además de acceder a contenido como mods, juegos en desarrollo, música y software. También tiene funciones como una comunidad, chat, almacenamiento en la nube y soporte para juegos en streaming. Es muy popular en el mundo del gaming por su amplia selección y facilidad de uso.
```

ÚTIL en esta sonda: responde a la cuestión con explicación sencilla. No acredita comportamiento en producto con historial.

finish_reason de las llamadas asociadas: ['stop'].

### Sonda 9 — brief_by_request

**Entrada literal**
```text
What is an SSID?
```

**Respuesta literal**
```text
An SSID is the name of a Wi-Fi network. When you see it on your device, it's what you type in to connect to the network. It's like a password for your wireless internet.
```

NO APROBADO: la comparación con una contraseña confunde el nombre de red con autenticación.

finish_reason de las llamadas asociadas: ['stop'].

### Sonda 10 — brief_by_request

**Entrada literal**
```text
Explica con detalle de qué gases se compone el aire y qué papel tiene la humedad.
```

**Respuesta literal**
```text
El aire que respiramos está compuesto principalmente por **nitrógeno (78%)**, **oxígeno (21%)**, y pequeñas cantidades de otros gases como **argon (0.93%)**, **dióxido de carbono (0.04%)**, **helio**, **neón**, **hidrógeno** y **metano**, entre otros. Además, el aire contiene **vapor de agua**, que es el componente que varía según la humedad.

La **humedad** se refiere al contenido de **vapor de agua** en el
```

NO APROBADO: salida cortada al alcanzar 128 tokens (finish_reason=length); no completa el detalle solicitado. La brevedad no resuelve este límite.

finish_reason de las llamadas asociadas: ['length'].

## Conocimiento: una frase con excepción para detalle

Fuentes: [payloads y respuestas brutas](astra-knowledge-one-sentence/posts.jsonl), [respuestas del wrapper](astra-knowledge-one-sentence/replies.jsonl), [resultado](astra-knowledge-one-sentence/RESULT.json). Mismo modelo registrado, temperatura 0, historial vacío y máximo 128 tokens. Agua, aire y Steam son entradas históricas ya consumidas. SSID y explicación detallada son controles sintéticos, no uso humano acreditado.

### Sonda 1 — brief_by_request

**Entrada literal**
```text
El agua es h2o?
```

**Respuesta literal**
```text
Sí, el agua es H₂O.
```

ÚTIL en esta sonda: responde a la cuestión con explicación sencilla. No acredita comportamiento en producto con historial.

finish_reason de las llamadas asociadas: ['stop'].

### Sonda 2 — brief_by_request

**Entrada literal**
```text
El aire es h20?
```

**Respuesta literal**
```text
No, el aire no es H2O. El aire es una mezcla de gases, principalmente nitrógeno (78%) y oxígeno (21%), mientras que H2O es el agua.
```

ÚTIL en esta sonda: responde a la cuestión con explicación sencilla. No acredita comportamiento en producto con historial.

finish_reason de las llamadas asociadas: ['stop'].

### Sonda 3 — brief_by_request

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
Steam es una plataforma de distribución y comercio de juegos online, creada por Valve, donde puedes comprar, descargar, jugar y gestionar juegos, así como acceder a contenido adicional como mods, música y aplicaciones.
```

ÚTIL en esta sonda: responde a la cuestión con explicación sencilla. No acredita comportamiento en producto con historial.

finish_reason de las llamadas asociadas: ['stop'].

### Sonda 4 — brief_by_request

**Entrada literal**
```text
What is an SSID?
```

**Respuesta literal**
```text
An SSID is the name of a Wi-Fi network that devices connect to when joining a wireless internet connection.
```

ÚTIL en esta sonda: responde a la cuestión con explicación sencilla. No acredita comportamiento en producto con historial.

finish_reason de las llamadas asociadas: ['stop'].

### Sonda 5 — brief_by_request

**Entrada literal**
```text
Explica con detalle de qué gases se compone el aire y qué papel tiene la humedad.
```

**Respuesta literal**
```text
El aire se compone principalmente de nitrógeno (78%), oxígeno (21%), argón (0.9%), dióxido de carbono (0.04%) y pequeñas cantidades de gases inanimados como helio, neón, metano y vapor de agua. La humedad, o vapor de agua, es un componente variable que influye en la temperatura, la sensación térmica y en procesos como la evaporación y la precipitación. Aunque no es un gas fijo, el vapor de agua afecta directamente el clima
```

NO APROBADO: salida cortada al alcanzar 128 tokens (finish_reason=length); no completa el detalle solicitado. La brevedad no resuelve este límite.

finish_reason de las llamadas asociadas: ['length'].

## Decisión y límites

La lectura nativa del nombre sí está integrada y verificada. Las variantes de prosa no se promovieron: la segunda mejora las definiciones breves, pero el control detallado sigue cortado. La siguiente hipótesis debe tratar el presupuesto efectivo de salida y comprobar calidad, latencia y producto; no encadenar una tercera variante de redacción.

Validación: 138 pruebas de proveedor y 131 de integración pasan, cero skips. Core NativeAOT publicado localmente; Fast verde, cero errores y avisos de compilación. La corrida de audio terminó con código 0, 58,06 s, 3497,56 MiB de VRAM y 4608,77 MiB de RAM. No hay Full final ni nueva prueba de UI con voz.
