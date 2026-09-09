# C03 — volumen contextual: pruebas literales

2026-09-06. C03 EN_CURSO. Desarrollo consumido; no reserva de cien turnos.
El conductor usa el runtime registrado sin ventana ni wake; no acredita UI ni audio físico.

## astra-real-users-contracts22

Proceso código 0; 92.09 s; VRAM 3499.56 MiB; registro intacto: True.

### t1

Entrada literal:
```text
hola buenas
```

Respuesta literal:
```text
Hola, ¿qué tal? Bienvenido.
```

APROBADO: contenido pertinente; en lecturas/efectos coincide con la evidencia del turno.

Hechos entregados al generador:
```json
{"kind": "welcome"}
```

### t2

Entrada literal:
```text
Hello?
```

Respuesta literal:
```text
Hey, what's up?
```

APROBADO: contenido pertinente; en lecturas/efectos coincide con la evidencia del turno.

Hechos entregados al generador:
```json
{"kind": "welcome"}
```

### t3

Entrada literal:
```text
cuál es la capital de francia
```

Respuesta literal:
```text
París
```

APROBADO: contenido pertinente; en lecturas/efectos coincide con la evidencia del turno.

### t4

Entrada literal:
```text
El agua es h2o?
```

Respuesta literal:
```text
Sí, el agua está compuesta por dos átomos de hidrógeno y uno de oxígeno, H₂O.
```

APROBADO: contenido pertinente; en lecturas/efectos coincide con la evidencia del turno.

### t5

Entrada literal:
```text
El aire es h20?
```

Respuesta literal:
```text
No, el aire no es H₂O. El aire es una mezcla de gases, principalmente nitrógeno y oxígeno, mientras que H₂O es agua.
```

APROBADO: contenido pertinente; en lecturas/efectos coincide con la evidencia del turno.

### t6

Entrada literal:
```text
ahora explicame que es Steam
```

Respuesta literal:
```text
Steam es una plataforma de gaming y servicios digitales desarrollada por Valve. Permite jugar a juegos en línea, comprar y descargar contenido, y también ofrece servicios como almacenamiento de juegos, streaming de contenido y acceso a aplicaciones como Steam Workshop.
```

APROBADO con nota de precisión: explicación útil; Steam Workshop es una función/servicio, no una aplicación aparte. No se presenta como respuesta técnica exhaustiva.

### t7

Entrada literal:
```text
Dime que hora es
```

Respuesta literal:
```text
Son las 18 horas y 30 minutos.
```

APROBADO: contenido pertinente; en lecturas/efectos coincide con la evidencia del turno.

Hechos entregados al generador:
```json
{"clock": "18:30"}
```

### t8

Entrada literal:
```text
y la fecha?
```

Respuesta literal:
```text
Hoy es el 6 de septiembre de 2026.
```

APROBADO: contenido pertinente; en lecturas/efectos coincide con la evidencia del turno.

Hechos entregados al generador:
```json
{"date": "2026-09-06"}
```

### t9

Entrada literal:
```text
what time is it?
```

Respuesta literal:
```text
It's 18:30.
```

APROBADO: contenido pertinente; en lecturas/efectos coincide con la evidencia del turno.

Hechos entregados al generador:
```json
{"clock": "18:30"}
```

### t10

Entrada literal:
```text
Que gpu tengo?
```

Respuesta literal:
```text
Tengo una GPU NVIDIA GeForce RTX 3060 en el portátil.
```

APROBADO: contenido pertinente; en lecturas/efectos coincide con la evidencia del turno.

Hechos entregados al generador:
```json
{"seen": {"scope": "gpu_identity", "adapters": [{"adapterIndex": 0, "name": "NVIDIA GeForce RTX 3060 Laptop GPU", "vendorId": 4318, "dedicatedVideoMemoryBytes": 6287261696, "dedicatedSystemMemoryBytes": 0, "sharedSystemMemoryLimitBytes": 8269754368}, {"adapterIndex": 1, "name": "AMD Radeon(TM) Graphics", "vendorId": 4098, "dedicatedVideoMemoryBytes": 519847936, "dedicatedSystemMemoryBytes": 0, "sharedSystemMemoryLimitBytes": 8269754368}, {"adapterIndex": 2, "name": "AMD Radeon(TM) Graphics", "vendorId": 4098, "dedicatedVideoMemoryBytes": 519847936, "dedicatedSystemMemoryBytes": 0, "sharedSystemMemoryLimitBytes": 8269754368}, {"adapterIndex": 3, "name": "NVIDIA GeForce RTX 3060 Laptop GPU", "vendorId": 4318, "dedicatedVideoMemoryBytes": 6287261696, "dedicatedSystemMemoryBytes": 0, "sharedSystemMemoryLimitBytes": 8269754368}, {"adapterIndex": 4, "name": "AMD Radeon(TM) Graphics", "vendorId": 4098, "dedicatedVideoMemoryBytes": 519847936, "dedicatedSystemMemoryBytes": 0, "sharedSystemMemoryLimitBytes": 8269754368}], "failures": []}}
```

### t11

Entrada literal:
```text
no subas el volumen
```

Respuesta literal:
```text
Ya está bajado, no subo el volumen.
```

NO APROBADO: «Ya está bajado» afirma un estado/cambio sin lectura ni ejecución en este turno.

### t12

Entrada literal:
```text
pon el volumen del PC al 35%
```

Respuesta literal:
```text
Puse el volumen del PC al 35%. El sonido no está silenciado.
```

APROBADO: contenido pertinente; en lecturas/efectos coincide con la evidencia del turno.

Hechos entregados al generador:
```json
{"effect": "applied", "seen": {"baseline": {"volumePercent": 100, "muted": false}, "final": {"volumePercent": 35, "muted": false}, "applied": true, "reconciled": false, "muted": false, "level": 35}}
```

### t13

Entrada literal:
```text
mostrame el volumen
```

Respuesta literal:
```text
El volumen está en 35 y el sonido no está silenciado.
```

APROBADO: contenido pertinente; en lecturas/efectos coincide con la evidencia del turno.

Hechos entregados al generador:
```json
{"seen": {"muted": false, "level": 35}}
```

### t14

Entrada literal:
```text
está silenciado el audio
```

Respuesta literal:
```text
El volumen está en 35 y el sonido no está silenciado.
```

APROBADO: contenido pertinente; en lecturas/efectos coincide con la evidencia del turno.

Hechos entregados al generador:
```json
{"seen": {"muted": false, "level": 35}}
```

### t15

Entrada literal:
```text
turn up the volume
```

Respuesta literal:
```text
how much and in which direction should the volume be adjusted?
```

NO APROBADO: preguntar cuánto falta es útil, pero vuelve a preguntar una dirección que «up» ya especificó.

### t16

Entrada literal:
```text
decime cuánto volumen hay
```

Respuesta literal:
```text
El volumen es de 35. El sonido no está silenciado.
```

APROBADO: contenido pertinente; en lecturas/efectos coincide con la evidencia del turno.

Hechos entregados al generador:
```json
{"seen": {"muted": false, "level": 35}}
```

### t17

Entrada literal:
```text
Ponlo a 100 ahora
```

Respuesta literal:
```text
¿A qué cosa quieres poner en 100?
```

NO APROBADO: aclaración innecesaria después de consultar el volumen; la primaria eligió correctamente audio.volume y el veto de dominio la retiró.

Hechos entregados al generador:
```json
{"kind": "clarification", "cause": "unclear request"}
```

### t18

Entrada literal:
```text
Hola, quien sos?
```

Respuesta literal:
```text
¿A qué cosa quieres poner en 100?
```

NO APROBADO: repite la aclaración del volumen ante una pregunta de identidad.

### t19

Entrada literal:
```text
Dime qué dispositivo de audio está activo
```

Respuesta literal:
```text
El dispositivo de audio activo es el altavoz principal, con sonido activo y volumen en 35. La hora local es 18:30.
```

NO APROBADO: ofrece volumen/hora y un nombre genérico; no identifica de forma demostrada el dispositivo solicitado.

Hechos entregados al generador:
```json
{"kind": "status", "completedRequest": "Ponlo a 100 ahora\nAclaración confiable del usuario: Hola, quien sos?\nAclaración confiable del usuario: Dime qué dispositivo de audio está activo", "outcome": "completed", "completedStepsInOrder": [{"operation": "system.time", "resultAtThisStep": {"readOnly": true, "clock": "18:30"}}, {"operation": "audio.status", "resultAtThisStep": {"readOnly": true, "seen": {"muted": false, "level": 35}}}]}
```

### t20

Entrada literal:
```text
no silencies el audio
```

Respuesta literal:
```text
El audio ya no está silenciado. El volumen está en 35.
```

NO APROBADO: «ya no está silenciado» implica una transición no ejecutada; sólo había una restricción.

### t21

Entrada literal:
```text
pon el volumen al 100
```

Respuesta literal:
```text
Puse el volumen al 100. El sonido no está silenciado.
```

APROBADO: contenido pertinente; en lecturas/efectos coincide con la evidencia del turno.

Hechos entregados al generador:
```json
{"effect": "applied", "seen": {"baseline": {"volumePercent": 35, "muted": false}, "final": {"volumePercent": 100, "muted": false}, "applied": true, "reconciled": false, "muted": false, "level": 100}}
```

### t22

Entrada literal:
```text
mostrame el volumen
```

Respuesta literal:
```text
El volumen está en 100 y el sonido no está silenciado.
```

APROBADO: contenido pertinente; en lecturas/efectos coincide con la evidencia del turno.

Hechos entregados al generador:
```json
{"seen": {"muted": false, "level": 100}}
```

[Entradas y salidas completas](astra-real-users-contracts22/paired.json) · [Procedencia](astra-real-users-contracts22/CASES.json) · [Trazas](astra-real-users-contracts22/shell-trace.jsonl)

## astra-real-volume-context6

Proceso código 0; 63.05 s; VRAM 3497.56 MiB; registro intacto: True.

### t1

Entrada literal:
```text
pon el volumen del PC al 35%
```

Respuesta literal:
```text
Puse el volumen del PC al 35%. El sonido no está silenciado.
```

APROBADO: responde al pedido y conserva los hechos observados.

Hechos entregados al generador:
```json
{"effect": "applied", "seen": {"baseline": {"volumePercent": 100, "muted": false}, "final": {"volumePercent": 35, "muted": false}, "applied": true, "reconciled": false, "muted": false, "level": 35}}
```

### t2

Entrada literal:
```text
decime cuánto volumen hay
```

Respuesta literal:
```text
El volumen es de 35. El sonido no está silenciado.
```

APROBADO: responde al pedido y conserva los hechos observados.

Hechos entregados al generador:
```json
{"seen": {"muted": false, "level": 35}}
```

### t3

Entrada literal:
```text
Ponlo a 100 ahora
```

Respuesta literal:
```text
El volumen se puso a 100. El sonido no está silenciado.
```

APROBADO: responde al pedido y conserva los hechos observados.

Hechos entregados al generador:
```json
{"effect": "applied", "seen": {"baseline": {"volumePercent": 35, "muted": false}, "final": {"volumePercent": 100, "muted": false}, "applied": true, "reconciled": false, "muted": false, "level": 100}}
```

### t4

Entrada literal:
```text
Hola, quien sos?
```

Respuesta literal:
```text
Soy BAXY, tu compañero en el PC. ¿Cómo va la jornada? 😎
```

APROBADO: responde a la pregunta de identidad.

### t5

Entrada literal:
```text
pon el volumen al 100
```

Respuesta literal:
```text
El volumen ya está en el 100%.
```

APROBADO: responde al pedido y conserva los hechos observados.

Hechos entregados al generador:
```json
{"seen": {"baseline": {"volumePercent": 100, "muted": false}, "final": {"volumePercent": 100, "muted": false}, "applied": false, "reconciled": false}}
```

### t6

Entrada literal:
```text
mostrame el volumen
```

Respuesta literal:
```text
El volumen está en 100 y el sonido no está silenciado.
```

APROBADO: responde al pedido y conserva los hechos observados.

Hechos entregados al generador:
```json
{"seen": {"muted": false, "level": 100}}
```

[Entradas y salidas completas](astra-real-volume-context6/paired.json) · [Procedencia](astra-real-volume-context6/CASES.json) · [Trazas](astra-real-volume-context6/shell-trace.jsonl)

## Diagnósticos de interpretación

Se conservaron treinta llamadas sobre cinco textos consumidos y dieciséis llamadas de control sintético. Los controles no representan usuarios ni cuentan para aceptación. Los payloads enlazados contienen las instrucciones, historial, parámetros y respuestas completas.

### astra-context-contracts

[Prerregistro y casos](astra-context-contracts/PREREG.json) · [Payloads y respuestas brutas](astra-context-contracts/posts.jsonl)

**json_current / t3**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"mode\": \"conversation\",\n  \"question\": \"\",\n  \"conversation_kind\": \"knowledge\",\n  \"effect_operations\": [],\n  \"response_language\": \"es\"\n}"}
```

**json_current / t8**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"mode\": \"action\",\n  \"question\": \"\",\n  \"conversation_kind\": \"\",\n  \"effect_operations\": [\n    \"system.time\"\n  ],\n  \"response_language\": \"es\"\n}"}
```

**json_current / t17**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"mode\": \"action\",\n  \"question\": \"\",\n  \"conversation_kind\": \"\",\n  \"effect_operations\": [\n    \"audio.volume.adjust\"\n  ],\n  \"response_language\": \"es\"\n}"}
```

**json_current / t18**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"mode\": \"conversation\",\n  \"question\": \"\",\n  \"conversation_kind\": \"social\",\n  \"effect_operations\": [],\n  \"response_language\": \"es\"\n}"}
```

**json_current / t20**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"mode\": \"conversation\",\n  \"question\": \"\",\n  \"conversation_kind\": \"knowledge\",\n  \"effect_operations\": [],\n  \"response_language\": \"es\"\n}"}
```

**json_inherited_boundaries / t3**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"mode\": \"conversation\",\n  \"question\": \"\",\n  \"conversation_kind\": \"knowledge\",\n  \"effect_operations\": [],\n  \"response_language\": \"es\"\n}"}
```

**json_inherited_boundaries / t8**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"mode\": \"action\",\n  \"question\": \"\",\n  \"conversation_kind\": \"\",\n  \"effect_operations\": [\n    \"system.time\"\n  ],\n  \"response_language\": \"es\"\n}"}
```

**json_inherited_boundaries / t17**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"mode\": \"action\",\n  \"question\": \"\",\n  \"conversation_kind\": \"\",\n  \"effect_operations\": [\n    \"audio.volume\"\n  ],\n  \"response_language\": \"es\"\n}"}
```

**json_inherited_boundaries / t18**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"mode\": \"conversation\",\n  \"question\": \"\",\n  \"conversation_kind\": \"social\",\n  \"effect_operations\": [],\n  \"response_language\": \"es\"\n}"}
```

**json_inherited_boundaries / t20**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"mode\": \"conversation\",\n  \"question\": \"\",\n  \"conversation_kind\": \"knowledge\",\n  \"effect_operations\": [],\n  \"response_language\": \"es\"\n}"}
```

**native_auto / t3**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "La capital de Francia es París."}
```

**native_auto / t8**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "Hoy es el 5 de abril de 2024."}
```

**native_auto / t17**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": "baxy_audio__volume", "arguments": "{}"}, "id": "smoTQPJo6tlyJ0zuZKwPS4uBRSUqxUia"}]}
```

**native_auto / t18**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "Soy BAXY, tu asistente de sistema. ¿En qué puedo ayudarte?"}
```

**native_auto / t20**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": "baxy_audio__status", "arguments": "{}"}, "id": "Ez4NPWL7auc4pSvCSfnbLFgaE25NgmDm"}]}
```

**count_current / t3**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"one\" }"}
```

**count_current / t8**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"effect_count\": \"one\"\n}"}
```

**count_current / t17**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"effect_count\": \"multiple\"\n}"}
```

**count_current / t18**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"effect_count\": \"one\"\n}"}
```

**count_current / t20**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"effect_count\": \"one\"\n}"}
```

**count_dialogue / t3**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\"effect_count\": \"one\"}"}
```

**count_dialogue / t8**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\"effect_count\": \"one\"}"}
```

**count_dialogue / t17**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\"effect_count\": \"one\"}"}
```

**count_dialogue / t18**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"effect_count\": \"one\"\n}"}
```

**count_dialogue / t20**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"effect_count\": \"multiple\"\n}"}
```

**count_scoped_context / t3**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"one\" }"}
```

**count_scoped_context / t8**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"one\" }"}
```

**count_scoped_context / t17**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"one\" }"}
```

**count_scoped_context / t18**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"one\" }"}
```

**count_scoped_context / t20**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"one\" }"}
```


### astra-context-count-controls

[Prerregistro y casos](astra-context-count-controls/PREREG.json) · [Payloads y respuestas brutas](astra-context-count-controls/posts.jsonl)

**count_current / control-1**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"effect_count\": \"multiple\"\n}"}
```

**count_current / control-2**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"one\" }"}
```

**count_current / control-3**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"multiple\" }"}
```

**count_current / control-4**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"effect_count\": \"one\"\n}"}
```

**count_current / control-5**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\"effect_count\": \"multiple\"}"}
```

**count_current / control-6**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{\n  \"effect_count\": \"multiple\"\n}"}
```

**count_current / control-7**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"multiple\" }"}
```

**count_current / control-8**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"multiple\" }"}
```

**count_scoped_context / control-1**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"one\" }"}
```

**count_scoped_context / control-2**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"one\" }"}
```

**count_scoped_context / control-3**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"multiple\" }"}
```

**count_scoped_context / control-4**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"multiple\" }"}
```

**count_scoped_context / control-5**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"one\" }"}
```

**count_scoped_context / control-6**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"one\" }"}
```

**count_scoped_context / control-7**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"one\" }"}
```

**count_scoped_context / control-8**

Respuesta bruta del modelo:
```json
{"role": "assistant", "content": "{ \"effect_count\": \"multiple\" }"}
```


## Conclusión acotada

La secuencia corta verifica el cambio de 35 a 100 mediante audio.volume, y la identidad posterior responde correctamente. Las negaciones no están resueltas. La corrida larga conserva fallos de contexto, dispositivo y aclaración. No se deduce un porcentaje global de C03.
