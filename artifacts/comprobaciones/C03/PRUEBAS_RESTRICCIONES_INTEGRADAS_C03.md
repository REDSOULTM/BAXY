# C03 — restricciones y aclaración de volumen: pruebas del tramo 37

2026-09-06. C03 EN_CURSO. Se conservan 37 respuestas del producto y 33 respuestas de sondas: 70 en total, con casos repetidos. Ninguna cifra representa cien casos frescos ni un porcentaje de completitud.

Los casos procedentes del pool conservan texto y referencias, pero no certifican autoría humana o frescura. Los controles sintéticos están identificados. Los enlaces contienen prompts completos, hechos, respuestas brutas y resultados, no sólo ejemplos favorables.

## astra-real-constraints12

Tiempo 69.06 s; pico GPU 3497.56 MiB; pico RAM 4915.48 MiB; registro intacto: True.

[Preregistro](astra-real-constraints12/PREREG.json) · [Recursos](astra-real-constraints12/RESULT.json)

[Procedencia y controles](astra-real-constraints12/CASES.json) · [Respuestas y hechos](astra-real-constraints12/paired.json) · [Traza del shell](astra-real-constraints12/shell-trace.jsonl) · [Composición](astra-real-constraints12/compose-audit.jsonl)

### t1

**Entrada del caso, literal**
```text
decime cuánto volumen hay
```

**Respuesta literal**
```text
El volumen es de 100. El sonido no está silenciado.
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t2

**Entrada del caso, literal**
```text
don't open chrome
```

**Respuesta literal**
```text
I'll not open Chrome.
```

**APROBADO:** Reconoce la prohibición sin afirmar cambios ejecutados; la traza no registra una invocación Core en este turno. «Nunca» en el reconocimiento no se penaliza por sí solo.

### t3

**Entrada del caso, literal**
```text
no pongas música
```

**Respuesta literal**
```text
No pondré música.
```

**APROBADO:** Reconoce la prohibición sin afirmar cambios ejecutados; la traza no registra una invocación Core en este turno. «Nunca» en el reconocimiento no se penaliza por sí solo.

### t4

**Entrada del caso, literal**
```text
nunca cierres spotify
```

**Respuesta literal**
```text
Nunca cierro Spotify.
```

**APROBADO:** Reconoce la prohibición sin afirmar cambios ejecutados; la traza no registra una invocación Core en este turno. «Nunca» en el reconocimiento no se penaliza por sí solo.

### t5

**Entrada del caso, literal**
```text
no cierres spotify
```

**Respuesta literal**
```text
Nunca cierro Spotify.
```

**APROBADO:** Reconoce la prohibición sin afirmar cambios ejecutados; la traza no registra una invocación Core en este turno. «Nunca» en el reconocimiento no se penaliza por sí solo.

### t6

**Entrada del caso, literal**
```text
no abras el navegador
```

**Respuesta literal**
```text
No abriré el navegador.
```

**APROBADO:** Reconoce la prohibición sin afirmar cambios ejecutados; la traza no registra una invocación Core en este turno. «Nunca» en el reconocimiento no se penaliza por sí solo.

### t7

**Entrada del caso, literal**
```text
no bajes el brillo
```

**Respuesta literal**
```text
No bajaré el brillo.
```

**APROBADO:** Reconoce la prohibición sin afirmar cambios ejecutados; la traza no registra una invocación Core en este turno. «Nunca» en el reconocimiento no se penaliza por sí solo.

### t8

**Entrada del caso, literal**
```text
no silencies el audio
```

**Respuesta literal**
```text
Nunca silenciaré el audio.
```

**APROBADO:** Reconoce la prohibición sin afirmar cambios ejecutados; la traza no registra una invocación Core en este turno. «Nunca» en el reconocimiento no se penaliza por sí solo.

### t9

**Entrada del caso, literal**
```text
no subas el volumen
```

**Respuesta literal**
```text
Nunca subo el volumen.
```

**APROBADO:** Reconoce la prohibición sin afirmar cambios ejecutados; la traza no registra una invocación Core en este turno. «Nunca» en el reconocimiento no se penaliza por sí solo.

### t10

**Entrada del caso, literal**
```text
no me molesta, dime la hora
```

**Respuesta literal**
```text
No pude interpretar correctamente la solicitud.
```

**NO APROBADO — control sintético:** La negación social no justifica perder la petición de consultar la hora. El producto publica un fallo de interpretación.

### t11

**Entrada del caso, literal**
```text
pon el volumen del PC al 100%
```

**Respuesta literal**
```text
El volumen del PC ya está en el 100%.
```

**RESTAURACIÓN/LECTURA APROBADA:** Audio a 100 y lectura posterior sin silencio. No cuenta como caso normal de aceptación.

### t12

**Entrada del caso, literal**
```text
decime cuánto volumen hay
```

**Respuesta literal**
```text
El volumen es de 100. El sonido no está silenciado.
```

**RESTAURACIÓN/LECTURA APROBADA:** Audio a 100 y lectura posterior sin silencio. No cuenta como caso normal de aceptación.

## astra-real-users-constraints22

Tiempo 92.08 s; pico GPU 3499.56 MiB; pico RAM 5082.68 MiB; registro intacto: True.

[Preregistro](astra-real-users-constraints22/PREREG.json) · [Recursos](astra-real-users-constraints22/RESULT.json)

[Procedencia y controles](astra-real-users-constraints22/CASES.json) · [Respuestas y hechos](astra-real-users-constraints22/paired.json) · [Traza del shell](astra-real-users-constraints22/shell-trace.jsonl) · [Composición](astra-real-users-constraints22/compose-audit.jsonl)

### t1

**Entrada del caso, literal**
```text
hola buenas
```

**Respuesta literal**
```text
Hola, ¿qué tal? Bienvenido.
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t2

**Entrada del caso, literal**
```text
Hello?
```

**Respuesta literal**
```text
Hey, what's up?
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t3

**Entrada del caso, literal**
```text
cuál es la capital de francia
```

**Respuesta literal**
```text
París
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t4

**Entrada del caso, literal**
```text
El agua es h2o?
```

**Respuesta literal**
```text
Sí, el agua está compuesta por dos átomos de hidrógeno y uno de oxígeno, H₂O.
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t5

**Entrada del caso, literal**
```text
El aire es h20?
```

**Respuesta literal**
```text
No, el aire no es H₂O. El aire es una mezcla de gases, principalmente nitrógeno y oxígeno, mientras que H₂O es agua.
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t6

**Entrada del caso, literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
Steam es una plataforma de gaming y servicios digitales desarrollada por Valve. Permite jugar a juegos en línea, comprar y descargar contenido, y también ofrece servicios como almacenamiento de juegos, streaming de contenido y acceso a aplicaciones como Steam Workshop.
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t7

**Entrada del caso, literal**
```text
Dime que hora es
```

**Respuesta literal**
```text
Son las 19 horas y 18 minutos.
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t8

**Entrada del caso, literal**
```text
y la fecha?
```

**Respuesta literal**
```text
Hoy es el 6 de septiembre de 2026.
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t9

**Entrada del caso, literal**
```text
what time is it?
```

**Respuesta literal**
```text
It's 19:18.
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t10

**Entrada del caso, literal**
```text
Que gpu tengo?
```

**Respuesta literal**
```text
Tengo una GPU NVIDIA GeForce RTX 3060 en el portátil.
```

**APROBADO:** La observación system.status incluye NVIDIA GeForce RTX 3060 Laptop GPU. La primera persona es una variación de estilo, no una GPU inventada.

### t11

**Entrada del caso, literal**
```text
no subas el volumen
```

**Respuesta literal**
```text
No subiré el volumen.
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t12

**Entrada del caso, literal**
```text
pon el volumen del PC al 35%
```

**Respuesta literal**
```text
Puse el volumen del PC al 35%. El sonido no está silenciado.
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t13

**Entrada del caso, literal**
```text
mostrame el volumen
```

**Respuesta literal**
```text
El volumen está en 35 y el sonido no está silenciado.
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t14

**Entrada del caso, literal**
```text
está silenciado el audio
```

**Respuesta literal**
```text
El volumen está en 35 y el sonido no está silenciado.
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t15

**Entrada del caso, literal**
```text
turn up the volume
```

**Respuesta literal**
```text
By how much should I increase the volume?
```

**APROBADO:** Sólo pregunta la cantidad. La traza muestra decisión clarify, sin llamada arguments ni ejecución de ajuste con una cantidad inventada.

### t16

**Entrada del caso, literal**
```text
decime cuánto volumen hay
```

**Respuesta literal**
```text
El volumen es de 35. El sonido no está silenciado.
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t17

**Entrada del caso, literal**
```text
Ponlo a 100 ahora
```

**Respuesta literal**
```text
El volumen se puso a 100. El sonido no está silenciado.
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t18

**Entrada del caso, literal**
```text
Hola, quien sos?
```

**Respuesta literal**
```text
Soy BAXY, el compañero del PC. ¿Cómo estás?
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t19

**Entrada del caso, literal**
```text
Dime qué dispositivo de audio está activo
```

**Respuesta literal**
```text
¿Estás preguntando por el dispositivo de audio actual en el sistema o por el que está configurado como predeterminado?
```

**PENDIENTE DE CONTINUIDAD:** Aclaración de alcance plausible, sin inventar identidad. No demuestra que pueda identificar después el dispositivo. No contar como identificación resuelta ni dar por verde todo el panel.

### t20

**Entrada del caso, literal**
```text
no silencies el audio
```

**Respuesta literal**
```text
No silenciaré el audio nunca.
```

**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.

### t21

**Entrada del caso, literal**
```text
pon el volumen al 100
```

**Respuesta literal**
```text
El volumen ya está en el 100%.
```

**RESTAURACIÓN/LECTURA APROBADA:** 100 y muted:false confirmados; fuera del grupo de veinte casos normales.

### t22

**Entrada del caso, literal**
```text
mostrame el volumen
```

**Respuesta literal**
```text
El volumen está en 100 y el sonido no está silenciado.
```

**RESTAURACIÓN/LECTURA APROBADA:** 100 y muted:false confirmados; fuera del grupo de veinte casos normales.

## astra-air-device-followup3

Tiempo 66.12 s; pico GPU 3497.56 MiB; pico RAM 4865.65 MiB; registro intacto: True.

[Preregistro](astra-air-device-followup3/PREREG.json) · [Recursos](astra-air-device-followup3/RESULT.json)

[Procedencia y controles](astra-air-device-followup3/CASES.json) · [Respuestas y hechos](astra-air-device-followup3/paired.json) · [Traza del shell](astra-air-device-followup3/shell-trace.jsonl) · [Composición](astra-air-device-followup3/compose-audit.jsonl)

### t1

**Entrada del caso, literal**
```text
El aire es h20?
```

**Respuesta literal**
```text
No, el aire no es H2O. El aire es una mezcla de gases, principalmente nitrógeno (78%) y oxígeno (21%), mientras que el H2O es vapor de agua. El aire no contiene agua en forma líquida ni en forma de compuesto H2O en cantidades significativas.
```

**NO APROBADO EN PRECISIÓN:** La conclusión principal —aire distinto de agua, mayormente nitrógeno y oxígeno— es correcta. La explicación añadida presenta H₂O como vapor y generaliza sobre ausencia de agua sin tratar la humedad; no es una descripción general adecuada del agua o del aire. No es un rechazo por idioma o brevedad.

### t2

**Entrada del caso, literal**
```text
Dime qué dispositivo de audio está activo
```

**Respuesta literal**
```text
El dispositivo de audio activo está con el volumen en 100 y no está silenciado.
```

**NO APROBADO:** Informa volumen y silencio, pero no identifica el dispositivo pedido. AudioStatusReceipt sólo transporta hash/objetivo/volumen/silencio, sin nombre visible: falta ese hecho en la fuente, no sólo una frase mejor.

### t3

**Entrada del caso, literal**
```text
el predeterminado
```

**Respuesta literal**
```text
El pedido está fuera de lo que hago en este PC.
```

**CONTROL CON PRECONDICIÓN NO OBSERVADA:** Era una respuesta sintética prevista para una pregunta de alcance, pero en esta corrida el turno anterior no formuló esa pregunta. Conservar la salida; no usarla como prueba de continuidad de la aclaración de la otra corrida.

## astra-negative-conversation-purpose

Tiempo 7.78 s; pico GPU 3493.56 MiB; pico RAM 2822.30 MiB; registro intacto: True.

[Preregistro](astra-negative-conversation-purpose/PREREG.json) · [Recursos](astra-negative-conversation-purpose/RESULT.json)

[Todos los mensajes reales enviados y devueltos](astra-negative-conversation-purpose/posts.jsonl) · [Resultado de la API de BAXY](astra-negative-conversation-purpose/replies.jsonl)

La entrada de caso se inserta en el payload del enlace; la respuesta de abajo es el content literal del servidor, antes de la evaluación del producto. No se ejecutaron sus argumentos.

### 1. constraint_purpose

**Entrada del caso, literal**
```text
don't open chrome
```

**Respuesta literal**
```text
I won't open Chrome.
```

**APROBADO EN ESTA SONDA:** Responde al sentido del caso sin inventar un estado observado.

### 2. constraint_purpose

**Entrada del caso, literal**
```text
no pongas música
```

**Respuesta literal**
```text
No pondré música.
```

**APROBADO EN ESTA SONDA:** Responde al sentido del caso sin inventar un estado observado.

### 3. constraint_purpose

**Entrada del caso, literal**
```text
nunca cierres spotify
```

**Respuesta literal**
```text
Entendido, nunca cierro Spotify.
```

**APROBADO EN ESTA SONDA:** Responde al sentido del caso sin inventar un estado observado.

### 4. constraint_purpose

**Entrada del caso, literal**
```text
no cierres spotify
```

**Respuesta literal**
```text
No cierro Spotify. Estaré atento a tu mensaje para no cerrarlo.
```

**APROBADO EN ESTA SONDA:** Responde al sentido del caso sin inventar un estado observado.

### 5. constraint_purpose

**Entrada del caso, literal**
```text
no abras el navegador
```

**Respuesta literal**
```text
No abriré el navegador.
```

**APROBADO EN ESTA SONDA:** Responde al sentido del caso sin inventar un estado observado.

### 6. constraint_purpose

**Entrada del caso, literal**
```text
no bajes el brillo
```

**Respuesta literal**
```text
No subiré el brillo.
```

**NO APROBADO:** Invierte bajar por subir.

### 7. constraint_purpose

**Entrada del caso, literal**
```text
no silencies el audio
```

**Respuesta literal**
```text
No silenciaré el audio.
```

**APROBADO EN ESTA SONDA:** Responde al sentido del caso sin inventar un estado observado.

### 8. constraint_purpose

**Entrada del caso, literal**
```text
no subas el volumen
```

**Respuesta literal**
```text
No subiré el volumen.
```

**APROBADO EN ESTA SONDA:** Responde al sentido del caso sin inventar un estado observado.

### 9. constraint_purpose

**Entrada del caso, literal**
```text
no entiendo
```

**Respuesta literal**
```text
Claro, ¿en qué estás teniendo dificultades? Estaré encantado de ayudarte.
```

**APROBADO EN ESTA SONDA:** Responde al sentido del caso sin inventar un estado observado.

### 10. constraint_purpose

**Entrada del caso, literal**
```text
no sé qué es Steam
```

**Respuesta literal**
```text
No sé qué es Steam, pero puedo explicártelo si quieres. ¿Te interesa saber qué es?
```

**NO APROBADO:** Confunde la falta de conocimiento del usuario con la del asistente y no explica Steam.

### 11. constraint_purpose

**Entrada del caso, literal**
```text
no funciona el audio
```

**Respuesta literal**
```text
Entiendo, estaré revisando el problema del audio. ¿Puedes confirmar si el sonido está activo en el sistema o si hay algún mensaje de error?
```

**NO APROBADO:** Promete una revisión no iniciada y devuelve al usuario comprobaciones sin diagnosticar. Esta sonda no tiene observaciones ni ejecución.

### 12. constraint_purpose

**Entrada del caso, literal**
```text
don't open Chrome; explain what a browser is
```

**Respuesta literal**
```text
I won't open Chrome. A browser is a software application that lets you access and view websites on the internet. It works like a window into the web—where you can type in addresses, search for information, or watch videos. Browsers like Chrome, Firefox, or Safari help you navigate online content safely and efficiently.
```

**APROBADO EN ESTA SONDA:** Responde al sentido del caso sin inventar un estado observado.

## astra-clarification-operation-ids

Tiempo 5.09 s; pico GPU 3493.56 MiB; pico RAM 2819.11 MiB; registro intacto: True.

[Preregistro](astra-clarification-operation-ids/PREREG.json) · [Recursos](astra-clarification-operation-ids/RESULT.json)

[Todos los mensajes reales enviados y devueltos](astra-clarification-operation-ids/posts.jsonl) · [Resultado de la API de BAXY](astra-clarification-operation-ids/replies.jsonl)

La entrada de caso se inserta en el payload del enlace; la respuesta de abajo es el content literal del servidor, antes de la evaluación del producto. No se ejecutaron sus argumentos.

### 1. current_clarifier

**Entrada del caso, literal**
```text
baja el volumen
```

**Respuesta literal**
```text
{"requested_fields":["amount"],"question":"¿Cuánto deseas bajar el volumen?"}
```

**APROBADO EN ESTA SONDA:** Pide sólo cantidad. La ruta existente ya acierta; retirar identificadores no demuestra reparar el fallo de la otra ruta. Variante no promovida.

### 2. current_clarifier

**Entrada del caso, literal**
```text
turn up the volume
```

**Respuesta literal**
```text
{"requested_fields":["amount"],"question":"By how much should I increase the volume?"}
```

**APROBADO EN ESTA SONDA:** Pide sólo cantidad. La ruta existente ya acierta; retirar identificadores no demuestra reparar el fallo de la otra ruta. Variante no promovida.

### 3. current_clarifier

**Entrada del caso, literal**
```text
sube el volumen
```

**Respuesta literal**
```text
{"requested_fields":["amount"],"question":"¿Cuánto quieres aumentar el volumen?"}
```

**APROBADO EN ESTA SONDA:** Pide sólo cantidad. La ruta existente ya acierta; retirar identificadores no demuestra reparar el fallo de la otra ruta. Variante no promovida.

### 4. without_operation_ids

**Entrada del caso, literal**
```text
baja el volumen
```

**Respuesta literal**
```text
{"requested_fields":["amount"],"question":"¿Cuánto deseas bajar el volumen?"}
```

**APROBADO EN ESTA SONDA:** Pide sólo cantidad. La ruta existente ya acierta; retirar identificadores no demuestra reparar el fallo de la otra ruta. Variante no promovida.

### 5. without_operation_ids

**Entrada del caso, literal**
```text
turn up the volume
```

**Respuesta literal**
```text
{"requested_fields":["amount"],"question":"By how much should I turn up the volume?"}
```

**APROBADO EN ESTA SONDA:** Pide sólo cantidad. La ruta existente ya acierta; retirar identificadores no demuestra reparar el fallo de la otra ruta. Variante no promovida.

### 6. without_operation_ids

**Entrada del caso, literal**
```text
sube el volumen
```

**Respuesta literal**
```text
{"requested_fields":["amount"],"question":"¿Cuánto quieres aumentar el volumen?"}
```

**APROBADO EN ESTA SONDA:** Pide sólo cantidad. La ruta existente ya acierta; retirar identificadores no demuestra reparar el fallo de la otra ruta. Variante no promovida.

## astra-direct-missing-fields

Tiempo 8.06 s; pico GPU 3493.56 MiB; pico RAM 2830.50 MiB; registro intacto: True.

[Preregistro](astra-direct-missing-fields/PREREG.json) · [Recursos](astra-direct-missing-fields/RESULT.json)

[Todos los mensajes reales enviados y devueltos](astra-direct-missing-fields/posts.jsonl) · [Resultado de la API de BAXY](astra-direct-missing-fields/replies.jsonl)

La entrada de caso se inserta en el payload del enlace; la respuesta de abajo es el content literal del servidor, antes de la evaluación del producto. No se ejecutaron sus argumentos.

### 1. current_direct

**Entrada del caso, literal**
```text
baja el volumen
```

**Respuesta literal**
```text
{"grounded":true,"arguments":{"amount":1,"direction":"down"},"fallback_question":"cuánto y en qué dirección quieres ajustar el volumen?"}
```

**NO APROBADO COMO EXTRACCIÓN:** El pedido no da cantidad, pero la salida inventa amount=1. La guarda independiente del producto rechazó ese valor en el caso integrado anterior. La pregunta se estudia aparte; ninguna de estas variantes se promovió.

### 2. current_direct

**Entrada del caso, literal**
```text
turn up the volume
```

**Respuesta literal**
```text
{"grounded":true,"arguments":{"amount":1,"direction":"up"},"fallback_question":"how much and in which direction should the volume be adjusted?"}
```

**NO APROBADO COMO EXTRACCIÓN:** El pedido no da cantidad, pero la salida inventa amount=1. La guarda independiente del producto rechazó ese valor en el caso integrado anterior. La pregunta se estudia aparte; ninguna de estas variantes se promovió.

### 3. current_direct

**Entrada del caso, literal**
```text
sube el volumen
```

**Respuesta literal**
```text
{"grounded":true,"arguments":{"amount":1,"direction":"up"},"fallback_question":"cuánto y en qué dirección quieres ajustar el volumen?"}
```

**NO APROBADO COMO EXTRACCIÓN:** El pedido no da cantidad, pero la salida inventa amount=1. La guarda independiente del producto rechazó ese valor en el caso integrado anterior. La pregunta se estudia aparte; ninguna de estas variantes se promovió.

### 4. current_direct

**Entrada del caso, literal**
```text
turn up the volume by 10%
```

**Respuesta literal**
```text
{"grounded":true,"arguments":{"amount":10,"direction":"up"},"fallback_question":"how much and in which direction to adjust the volume?"}
```

**CONTROL SINTÉTICO — ARGUMENTOS CORRECTOS:** Conserva cantidad y dirección explícitas. fallback_question no es una respuesta normal visible cuando esos argumentos se aceptan; no contarla como una aclaración necesaria.

### 5. current_direct

**Entrada del caso, literal**
```text
baja el volumen en 5 puntos
```

**Respuesta literal**
```text
{"grounded": true, "arguments": {"amount": 5, "direction": "down"}, "fallback_question": "cuánto y en qué dirección se ajusta el volumen?"}
```

**CONTROL SINTÉTICO — ARGUMENTOS CORRECTOS:** Conserva cantidad y dirección explícitas. fallback_question no es una respuesta normal visible cuando esos argumentos se aceptan; no contarla como una aclaración necesaria.

### 6. missing_only

**Entrada del caso, literal**
```text
baja el volumen
```

**Respuesta literal**
```text
{"grounded":true,"arguments":{"amount":1,"direction":"down"},"fallback_question":"¿cuánto quieres bajar el volumen?"}
```

**NO APROBADO COMO EXTRACCIÓN:** El pedido no da cantidad, pero la salida inventa amount=1. La guarda independiente del producto rechazó ese valor en el caso integrado anterior. La pregunta se estudia aparte; ninguna de estas variantes se promovió.

### 7. missing_only

**Entrada del caso, literal**
```text
turn up the volume
```

**Respuesta literal**
```text
{"grounded":true,"arguments":{"amount":1,"direction":"up"},"fallback_question":"¿Cuánto quieres aumentar el volumen?"}
```

**NO APROBADO COMO EXTRACCIÓN:** El pedido no da cantidad, pero la salida inventa amount=1. La guarda independiente del producto rechazó ese valor en el caso integrado anterior. La pregunta se estudia aparte; ninguna de estas variantes se promovió.

### 8. missing_only

**Entrada del caso, literal**
```text
sube el volumen
```

**Respuesta literal**
```text
{"grounded":true,"arguments":{"amount":1,"direction":"up"},"fallback_question":"¿Cuánto quieres subir el volumen?"}
```

**NO APROBADO COMO EXTRACCIÓN:** El pedido no da cantidad, pero la salida inventa amount=1. La guarda independiente del producto rechazó ese valor en el caso integrado anterior. La pregunta se estudia aparte; ninguna de estas variantes se promovió.

### 9. missing_only

**Entrada del caso, literal**
```text
turn up the volume by 10%
```

**Respuesta literal**
```text
{"grounded":true,"arguments":{"amount":10,"direction":"up"},"fallback_question":"How much should the volume be adjusted and in which direction?"}
```

**CONTROL SINTÉTICO — ARGUMENTOS CORRECTOS:** Conserva cantidad y dirección explícitas. fallback_question no es una respuesta normal visible cuando esos argumentos se aceptan; no contarla como una aclaración necesaria.

### 10. missing_only

**Entrada del caso, literal**
```text
baja el volumen en 5 puntos
```

**Respuesta literal**
```text
{"grounded":true,"arguments":{"amount":5,"direction":"down"},"fallback_question":"¿Cuánto y en qué dirección se debe ajustar el volumen?"}
```

**CONTROL SINTÉTICO — ARGUMENTOS CORRECTOS:** Conserva cantidad y dirección explícitas. fallback_question no es una respuesta normal visible cuando esos argumentos se aceptan; no contarla como una aclaración necesaria.

## astra-direct-missing-language

Tiempo 6.64 s; pico GPU 3497.56 MiB; pico RAM 2828.97 MiB; registro intacto: True.

[Preregistro](astra-direct-missing-language/PREREG.json) · [Recursos](astra-direct-missing-language/RESULT.json)

[Todos los mensajes reales enviados y devueltos](astra-direct-missing-language/posts.jsonl) · [Resultado de la API de BAXY](astra-direct-missing-language/replies.jsonl)

La entrada de caso se inserta en el payload del enlace; la respuesta de abajo es el content literal del servidor, antes de la evaluación del producto. No se ejecutaron sus argumentos.

### 1. missing_only

**Entrada del caso, literal**
```text
baja el volumen
```

**Respuesta literal**
```text
{"grounded": true, "arguments": {"amount": 1, "direction": "down"}, "fallback_question": "¿cuánto quieres bajar el volumen?"}
```

**NO APROBADO COMO EXTRACCIÓN:** El pedido no da cantidad, pero la salida inventa amount=1. La guarda independiente del producto rechazó ese valor en el caso integrado anterior. La pregunta se estudia aparte; ninguna de estas variantes se promovió.

### 2. missing_only

**Entrada del caso, literal**
```text
turn up the volume
```

**Respuesta literal**
```text
{"grounded":true,"arguments":{"amount":1,"direction":"up"},"fallback_question":"How much should I adjust the volume and in which direction?"}
```

**NO APROBADO COMO EXTRACCIÓN:** El pedido no da cantidad, pero la salida inventa amount=1. La guarda independiente del producto rechazó ese valor en el caso integrado anterior. La pregunta se estudia aparte; ninguna de estas variantes se promovió.

### 3. missing_only

**Entrada del caso, literal**
```text
sube el volumen
```

**Respuesta literal**
```text
{"grounded":true,"arguments":{"amount":1,"direction":"up"},"fallback_question":"¿Cuánto y en qué dirección quieres ajustar el volumen?"}
```

**NO APROBADO COMO EXTRACCIÓN:** El pedido no da cantidad, pero la salida inventa amount=1. La guarda independiente del producto rechazó ese valor en el caso integrado anterior. La pregunta se estudia aparte; ninguna de estas variantes se promovió.

### 4. missing_only

**Entrada del caso, literal**
```text
turn up the volume by 10%
```

**Respuesta literal**
```text
{"grounded": true, "arguments": {"amount": 10, "direction": "up"}, "fallback_question": "By how much and in which direction should the volume be adjusted?"}
```

**CONTROL SINTÉTICO — ARGUMENTOS CORRECTOS:** Conserva cantidad y dirección explícitas. fallback_question no es una respuesta normal visible cuando esos argumentos se aceptan; no contarla como una aclaración necesaria.

### 5. missing_only

**Entrada del caso, literal**
```text
baja el volumen en 5 puntos
```

**Respuesta literal**
```text
{"grounded": true, "arguments": {"amount": 5, "direction": "down"}, "fallback_question": "¿Cuánto y en qué dirección quieres ajustar el volumen?"}
```

**CONTROL SINTÉTICO — ARGUMENTOS CORRECTOS:** Conserva cantidad y dirección explícitas. fallback_question no es una respuesta normal visible cuando esos argumentos se aceptan; no contarla como una aclaración necesaria.

## Qué cambió y qué sigue pendiente

Se integró la presentación de prohibiciones con el prompt de alcance medido en el tramo36. Se heredó el vocabulario de acciones para reconocer la flexión negativa sin convertir toda negación en una orden. No se añadieron llamadas al modelo ni un nuevo verificador por frases.

Para volumen se reutilizó la ruta de aclaración explícita: se amplió su reconocimiento a los verbos compuestos ingleses sin cantidad. Esta ruta sustituye en esos casos la extracción especulativa y pide sólo amount. Los cambios de prompt de extracción fallidos se conservaron como evidencia y no se adoptaron.

La pregunta por dispositivo requiere investigar la lectura del nombre del endpoint; el contrato actual sólo tiene objetivo/hash/volumen/silencio. La precisión del aire en sesión limpia y la negación social seguida de una petición positiva siguen pendientes. Cien frescos, UI y Full final no se han completado.

Validación final de esta fuente: 2804 pruebas Python pass, 0 skips, 44,64 s; Fast terminal0 con build Release sin errores/avisos; git diff --check. Ver ASTRA-TRAMO-37.md para comandos, hashes y límites.
