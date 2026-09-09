# C03 — reparación de argumentos y negaciones con casos reales

Comparación sobre los mismos veinte textos de desarrollo: **14 → 16 aceptados; quedan4 fallos**. Dos turnos adicionales restauran y verifican el volumen. No aceptación fresca ni porcentaje del goal.

Cambios: el valor de scope elegido por el lector existente de system.status ya no se pierde por no aparecer literalmente como nombre técnico en la petición. El valor sigue cruzando el schema autenticado. Una negación conversacional deja de clasificarse como incapacidad del producto. No se modificaron modelo, respuestas ni verificación de efectos.

La prueba inicial de «no subas el volumen» ya generaba «No subo el volumen.»; la clasificación unsupported lo rechazaba y forzaba reintentos. El problema era de la integración, no una incapacidad demostrada del modelo aislado.

1202 passed +115 subtests,0 skips,6,36s (test_system_status_scope_grounding, test_c03_request_preservation, test_turn_policy, test_planner). Se extendió la prueba de alcances para cruzar el grounding completo; antes sólo comprobaba el lector. Dos expectativas antiguas que imponían unsupported al pedir una explicación sin abrir Spotify pasan a knowledge, manteniendo cero efectos.

Runtime registrado, sin overrides;22 turnos,100,06s,GPU3499,56MiB,RAM5165,28MiB,exit0. Full pendiente. Conductor sin ventana,wake desactivado por diseño.

## 1. APROBADO

**Entrada literal**
```text
hola buenas
```

**Antes**
```text
Hola, ¿qué tal? Bienvenido.
```

**Después**
```text
Hola, ¿qué tal? Bienvenido.
```

Responde de manera útil y fiel a lo pedido.

## 2. APROBADO

**Entrada literal**
```text
Hello?
```

**Antes**
```text
Hey, what's up?
```

**Después**
```text
Hey, what's up?
```

Responde de manera útil y fiel a lo pedido.

## 3. APROBADO

**Entrada literal**
```text
cuál es la capital de francia
```

**Antes**
```text
París
```

**Después**
```text
París
```

Responde de manera útil y fiel a lo pedido.

## 4. APROBADO

**Entrada literal**
```text
El agua es h2o?
```

**Antes**
```text
Sí, el agua está compuesta por dos átomos de hidrógeno y uno de oxígeno, H₂O.
```

**Después**
```text
Sí, el agua está compuesta por dos átomos de hidrógeno y uno de oxígeno, H₂O.
```

Responde de manera útil y fiel a lo pedido.

## 5. APROBADO

**Entrada literal**
```text
El aire es h20?
```

**Antes**
```text
No, el aire no es H₂O. El aire es una mezcla de gases, principalmente nitrógeno y oxígeno, mientras que H₂O es agua.
```

**Después**
```text
No, el aire no es H₂O. El aire es una mezcla de gases, principalmente nitrógeno y oxígeno, mientras que H₂O es agua.
```

Responde de manera útil y fiel a lo pedido.

## 6. APROBADO

**Entrada literal**
```text
ahora explicame que es Steam
```

**Antes**
```text
Steam es una plataforma que permite descargar, jugar y gestionar videojuegos en línea.
```

**Después**
```text
Steam es una plataforma que permite descargar, jugar y gestionar videojuegos en línea.
```

Responde de manera útil y fiel a lo pedido.

## 7. APROBADO

**Entrada literal**
```text
Dime que hora es
```

**Antes**
```text
Son las 16 horas y 34 minutos.
```

**Después**
```text
Son las 16 horas y 53 minutos.
```

Responde de manera útil y fiel a lo pedido.

## 8. NO APROBADO

**Entrada literal**
```text
y la fecha?
```

**Antes**
```text
¿De qué fecha te refieres?
```

**Después**
```text
¿De qué fecha te refieres?
```

Después de pedir la hora, pide aclarar de qué fecha se habla. Pierde el contexto cotidiano.

## 9. APROBADO

**Entrada literal**
```text
what time is it?
```

**Antes**
```text
It's 16:34.
```

**Después**
```text
It's 16:53.
```

Responde de manera útil y fiel a lo pedido.

## 10. APROBADO

**Entrada literal**
```text
Que gpu tengo?
```

**Antes**
```text
Tengo la GPU integrada del procesador, que es Radeon Graphics.
```

**Después**
```text
Tengo una GPU NVIDIA GeForce RTX 3060 en el portátil.
```

Identifica RTX3060 desde adapters de scope gpu_identity verificado, no desde el nombre del CPU.

## 11. APROBADO

**Entrada literal**
```text
no subas el volumen
```

**Antes**
```text
composition_failed
```

**Después**
```text
Got it, volume no sube.
```

Reconoce la restricción negativa sin proponer efectos. Mezcla idiomática torpe registrada; no hay silencio ni inversión del pedido. Evaluación de utilidad de desarrollo, no aceptación final de naturalidad.

## 12. APROBADO

**Entrada literal**
```text
pon el volumen del PC al 35%
```

**Antes**
```text
Puse el volumen del PC al 35%. El sonido no está silenciado.
```

**Después**
```text
Puse el volumen del PC al 35%. El sonido no está silenciado.
```

Responde de manera útil y fiel a lo pedido.

## 13. APROBADO

**Entrada literal**
```text
mostrame el volumen
```

**Antes**
```text
El volumen está en 35 y el sonido no está silenciado.
```

**Después**
```text
El volumen está en 35 y el sonido no está silenciado.
```

Responde de manera útil y fiel a lo pedido.

## 14. APROBADO

**Entrada literal**
```text
está silenciado el audio
```

**Antes**
```text
El volumen está en 35 y el sonido no está silenciado.
```

**Después**
```text
El volumen está en 35 y el sonido no está silenciado.
```

Responde de manera útil y fiel a lo pedido.

## 15. APROBADO

**Entrada literal**
```text
turn up the volume
```

**Antes**
```text
how much and in which direction should the volume be adjusted?
```

**Después**
```text
how much and in which direction should the volume be adjusted?
```

Aceptada con observación: solicita una cantidad que no se especificó. Preguntar además la dirección es redundante, porque up ya la indica; no se convierte esa torpeza aislada en un bloqueo.

## 16. APROBADO

**Entrada literal**
```text
decime cuánto volumen hay
```

**Antes**
```text
El volumen es de 35. El sonido no está silenciado.
```

**Después**
```text
El volumen es de 35. El sonido no está silenciado.
```

Responde de manera útil y fiel a lo pedido.

## 17. NO APROBADO

**Entrada literal**
```text
Ponlo a 100 ahora
```

**Antes**
```text
Este pedido está fuera de lo que hago en este PC.
```

**Después**
```text
Este pedido está fuera de lo que hago en este PC.
```

Tras consultar el volumen, rechaza ponerlo a 100 como fuera de sus funciones. No ejecuta la restauración: pierde el referente.

## 18. NO APROBADO

**Entrada literal**
```text
Hola, quien sos?
```

**Antes**
```text
¿En qué puedo ayudarte?
```

**Después**
```text
¿En qué puedo ayudarte?
```

Saluda pero omite responder quién es. El problema es la pregunta ignorada, no el estilo del saludo.

## 19. APROBADO

**Entrada literal**
```text
Dime qué dispositivo de audio está activo
```

**Antes**
```text
¿Estás refiriéndote al dispositivo de salida de audio (como altavoces o auriculares) o al micrófono?
```

**Después**
```text
¿Estás refiriéndote al dispositivo de salida de audio (como altavoces o auriculares) o al micrófono?
```

Aclaración aceptable: dispositivo de audio puede referirse a salida o micrófono. No se penaliza una ambigüedad razonable.

## 20. NO APROBADO

**Entrada literal**
```text
no silencies el audio
```

**Antes**
```text
¿Te refieres al dispositivo de salida de audio (como altavoces o auriculares) o al micrófono?
```

**Después**
```text
¿Te refieres al dispositivo de salida de audio (como altavoces o auriculares) o al micrófono?
```

Repite la aclaración sobre dispositivos del turno anterior; no reconoce la nueva restricción de no silenciar el audio.

## 21. APROBADO

**Entrada literal**
```text
pon el volumen al 100
```

**Después**
```text
Puse el volumen al 100. El sonido no está silenciado.
```

Restauración100 aplicada y verificada (t21); lectura independiente100/no silenciado (t22).

## 22. APROBADO

**Entrada literal**
```text
mostrame el volumen
```

**Después**
```text
El volumen está en 100 y el sonido no está silenciado.
```

Restauración100 aplicada y verificada (t21); lectura independiente100/no silenciado (t22).

## Continuación

Persisten fecha tras hora,referente volumen,identidad y nueva restricción durante aclaración. Revisar contexto y resolución antes de añadir variantes de frases. No se ha resuelto C03 ni se han consumido100 de aceptación.
