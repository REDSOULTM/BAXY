# C03 — alcance de negaciones, tramo44

Panel heredado de desarrollo: no reserva ni aceptación fresca. Mismos once textos y orden que closed-prohibition11. Registro intacto.

## Reparación parcial de conservación

Resultado: 8/11 útiles, sin mejora frente a43.106,84s; GPU3497,56MiB; RAM5499,16MiB. No se adopta como solución integrada.

[Fuente y configuración](astra-scoped-prohibition11/PREREG.json) · [Respuestas y hechos](astra-scoped-prohibition11/paired.json) · [Decisiones](astra-scoped-prohibition11/turn-audit.jsonl)

### Turno1

Entrada literal:
```text
decime cuánto volumen hay
```

Respuesta literal:
```text
El volumen es de 100. El sonido no está silenciado.
```

Terminal: published_final.

APROBADO: útil y coherente con lo pedido y con la evidencia capturada. La lectura de audio no acredita sonido físico.

### Turno2

Entrada literal:
```text
Ponlo a 100 ahora
```

Respuesta literal:
```text
Ya está a 100%.
```

Terminal: published_final.

APROBADO: útil y coherente con lo pedido y con la evidencia capturada. La lectura de audio no acredita sonido físico.

### Turno3

Entrada literal:
```text
Hola, quien sos?
```

Respuesta literal:
```text
Soy BAXY, el compañero de usuario en REDNOTE.
```

Terminal: published_final.

APROBADO: útil y coherente con lo pedido y con la evidencia capturada. La lectura de audio no acredita sonido físico.

### Turno4

Entrada literal:
```text
Dime qué dispositivo de audio está activo
```

Respuesta literal:
```text
El dispositivo de audio activo es los altavoces (Realtek(R) Audio). El volumen está en 100 y el sonido no está silenciado.
```

Terminal: published_final.

APROBADO: útil y coherente con lo pedido y con la evidencia capturada. La lectura de audio no acredita sonido físico.

### Turno5

Entrada literal:
```text
no silencies el audio
```

Respuesta literal:
```text
No silenciaré el audio, está activo y en funcionamiento.
```

Terminal: published_final.

APROBADO: útil y coherente con lo pedido y con la evidencia capturada. La lectura de audio no acredita sonido físico.

### Turno6

Entrada literal:
```text
Don't mute the audio
```

Respuesta literal:
```text
I won't mute the audio.
```

Terminal: published_final.

APROBADO: útil y coherente con lo pedido y con la evidencia capturada. La lectura de audio no acredita sonido físico.

### Turno7

Entrada literal:
```text
no subas el volumen
```

Respuesta literal:
```text
Entendido, no subiré el volumen.
```

Terminal: published_final.

APROBADO: útil y coherente con lo pedido y con la evidencia capturada. La lectura de audio no acredita sonido físico.

### Turno8

Entrada literal:
```text
¿No está silenciado el audio?
```

Respuesta literal:
```text
¿Quieres que revise si el audio está silenciado?
```

Terminal: published_final.

FALLA: vuelve a pedir autorización para la lectura ya solicitada. AUTO recupera audio.status, pero la primaria posterior dice conversación y termina en observation_not_recital.

### Turno9

Entrada literal:
```text
dime la hora, no abras Steam
```

Respuesta literal:
```text
[No hubo respuesta final visible]
```

Terminal: composition_failed.

FALLA: no hay respuesta visible. La primaria selecciona system.time; domain_grounding rechaza el texto completo por la coma y lo transforma en aclaración redundante. La composición finalmente falla.

### Turno10

Entrada literal:
```text
dime la hora y no abras Steam
```

Respuesta literal:
```text
No pude interpretar la solicitud.
```

Terminal: published_final.

FALLA: error de interpretación. La primaria propone también game.launch y la recuperación termina en error. No se ejecuta Steam.

### Turno11

Entrada literal:
```text
dime la hora
```

Respuesta literal:
```text
22:29
```

Terminal: published_final.

APROBADO: útil y coherente con lo pedido y con la evidencia capturada. La lectura de audio no acredita sonido físico.

## Segunda hipótesis del mismo tramo

La abstención del lector literal sigue enviando consultas completas a clasificadores posteriores. Se hace llegar la misma comparación de alcance al resolver dueño. La negación interrogativa de estado conserva su cabeza de observación y las posiciones de evidencia; no se elimina una prohibición posterior. No cambia el prompt, modelo ni catálogo. Pruebas dirigidas de lector y política completa:23pass. Segunda medición:astra-scoped-reader11, en curso.

## Reparación integrada adoptada

Resultado:11/11 útiles,65,08s; GPU3497,56MiB; RAM5142,96MiB. Registro intacto. Mismos textos/orden. No acredita pantalla ni audio físico ni reserva fresca.

[Fuente y configuración](astra-scoped-reader11/PREREG.json) · [Respuestas y hechos](astra-scoped-reader11/paired.json) · [Decisiones](astra-scoped-reader11/turn-audit.jsonl)

### Turno1

Entrada literal:
```text
decime cuánto volumen hay
```

Respuesta literal:
```text
El volumen es de 100. El sonido no está silenciado.
```

APROBADO: conserva la petición y es coherente con la evidencia capturada.

### Turno2

Entrada literal:
```text
Ponlo a 100 ahora
```

Respuesta literal:
```text
Ya está a 100%.
```

APROBADO: conserva la petición y es coherente con la evidencia capturada.

### Turno3

Entrada literal:
```text
Hola, quien sos?
```

Respuesta literal:
```text
Soy BAXY, el compañero de usuario en REDNOTE.
```

APROBADO: conserva la petición y es coherente con la evidencia capturada.

### Turno4

Entrada literal:
```text
Dime qué dispositivo de audio está activo
```

Respuesta literal:
```text
El dispositivo de audio activo es los altavoces (Realtek(R) Audio). El volumen está en 100 y el sonido no está silenciado.
```

APROBADO: conserva la petición y es coherente con la evidencia capturada.

### Turno5

Entrada literal:
```text
no silencies el audio
```

Respuesta literal:
```text
No silenciaré el audio, está activo y en funcionamiento.
```

APROBADO: conserva la petición y es coherente con la evidencia capturada.

### Turno6

Entrada literal:
```text
Don't mute the audio
```

Respuesta literal:
```text
I won't mute the audio.
```

APROBADO: conserva la petición y es coherente con la evidencia capturada.

### Turno7

Entrada literal:
```text
no subas el volumen
```

Respuesta literal:
```text
Entendido, no subiré el volumen.
```

APROBADO: conserva la petición y es coherente con la evidencia capturada.

### Turno8

Entrada literal:
```text
¿No está silenciado el audio?
```

Respuesta literal:
```text
El audio del altavoz (Realtek(R) Audio) está activo y el volumen está en 100.
```

APROBADO: observa audio.status; estado verificado muted=false y level=100, con endpoint Realtek. No pide confirmar la consulta ni modifica audio.

### Turno9

Entrada literal:
```text
dime la hora, no abras Steam
```

Respuesta literal:
```text
22:36
```

APROBADO: system.time devuelve un UTC verificado, offset−180, y la respuesta coincide con22:36. No ejecuta app.open ni game.launch.

### Turno10

Entrada literal:
```text
dime la hora y no abras Steam
```

Respuesta literal:
```text
22:36
```

APROBADO: system.time devuelve un UTC verificado, offset−180, y la respuesta coincide con22:36. No ejecuta app.open ni game.launch.

### Turno11

Entrada literal:
```text
dime la hora
```

Respuesta literal:
```text
22:36
```

APROBADO: system.time devuelve un UTC verificado, offset−180, y la respuesta coincide con22:36. No ejecuta app.open ni game.launch.
