# C03 — prohibiciones: selección, contexto y producto

Desarrollo consumido y controles sintéticos identificados. No es la reserva de cien turnos. Las funciones de las sondas no se ejecutan. Las respuestas literales y los fallos se conservan.

## astra-negative-current-selection

[Prerregistro y procedencia](astra-negative-current-selection/PREREG.json) · [Payloads completos](astra-negative-current-selection/posts.jsonl)

### Llamada 1 · baseline

**Entrada literal**
```text
no silencies el audio
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_audio__status",
        "arguments": "{}"
      },
      "id": "1xketYofy9EQkLlows8HhY0qkO3x2M8P"
    }
  ]
}
```

Conjunto esperado: `[]`. Coincide: `False`. Finalización: `tool_calls`.

### Llamada 2 · baseline

**Entrada literal**
```text
no subas el volumen
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_audio__status",
        "arguments": "{}"
      },
      "id": "EF3NzPvMjH45KmAtUt7ZwiDoR4HGaDhp"
    }
  ]
}
```

Conjunto esperado: `[]`. Coincide: `False`. Finalización: `tool_calls`.

### Llamada 3 · baseline

**Entrada literal**
```text
Don't mute the audio
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "The audio is already active and not muted. No action is needed."
}
```

Conjunto esperado: `[]`. Coincide: `True`. Finalización: `stop`.

### Llamada 4 · baseline

**Entrada literal**
```text
no me digas la hora
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "No se puede determinar la hora del dispositivo."
}
```

Conjunto esperado: `[]`. Coincide: `True`. Finalización: `stop`.

### Llamada 5 · baseline

**Entrada literal**
```text
no abras Steam, dime la hora
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_system__time",
        "arguments": "{}"
      },
      "id": "bCjP1DJn3B7Cu7Aa2KVGbbOfevPrcC1F"
    }
  ]
}
```

Conjunto esperado: `['system.time']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 6 · baseline

**Entrada literal**
```text
dime la hora, no abras Steam
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_system__time",
        "arguments": "{}"
      },
      "id": "KEZSN4yq4jtPmwZbRq3Z9dA2PwXI3bRl"
    }
  ]
}
```

Conjunto esperado: `['system.time']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 7 · baseline

**Entrada literal**
```text
dime la hora y no abras Steam
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_system__time",
        "arguments": "{}"
      },
      "id": "NjsM6bTafWQCZU5lna0EX6HHSfw5nVbI"
    }
  ]
}
```

Conjunto esperado: `['system.time']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 8 · baseline

**Entrada literal**
```text
no uses herramientas, dime la hora
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "No se puede determinar la hora con las herramientas disponibles. Para obtener la hora exacta, se requiere un comando específico de lectura de tiempo."
}
```

Conjunto esperado: `[]`. Coincide: `True`. Finalización: `stop`.

### Llamada 9 · baseline

**Entrada literal**
```text
¿No está silenciado el audio?
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_audio__status",
        "arguments": "{}"
      },
      "id": "085g1IIMP8RsRDXa7B1AJp4oOpxjxnxZ"
    }
  ]
}
```

Conjunto esperado: `['audio.status']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 10 · baseline

**Entrada literal**
```text
está silenciado el audio
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_audio__status",
        "arguments": "{}"
      },
      "id": "0B1K5jdWP4rQOkbkwiuhXJ54DNweoHEf"
    }
  ]
}
```

Conjunto esperado: `['audio.status']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 11 · baseline

**Entrada literal**
```text
Ponlo a 100 ahora
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_audio__volume",
        "arguments": "{}"
      },
      "id": "3RumqM9DUCvkrUr5cAQ4P4JcR4mrmLam"
    }
  ]
}
```

Conjunto esperado: `['audio.volume']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 12 · baseline

**Entrada literal**
```text
no me molesta, dime la hora
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_system__time",
        "arguments": "{}"
      },
      "id": "Agv26ggiz3bYaz7G2vKDabKyqSi46rqp"
    }
  ]
}
```

Conjunto esperado: `['system.time']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 13 · current_request_policy

**Entrada literal**
```text
no silencies el audio
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_audio__status",
        "arguments": "{}"
      },
      "id": "RX4vTnMtNl7ukceNgoQ0PSLBZH3aej5W"
    }
  ]
}
```

Conjunto esperado: `[]`. Coincide: `False`. Finalización: `tool_calls`.

### Llamada 14 · current_request_policy

**Entrada literal**
```text
no subas el volumen
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "El dispositivo de audio activo es los altavoces (Realtek(R) Audio). El volumen está en 100 y el sonido no está silenciado. No se realizará ningún cambio en el volumen."
}
```

Conjunto esperado: `[]`. Coincide: `True`. Finalización: `stop`.

### Llamada 15 · current_request_policy

**Entrada literal**
```text
Don't mute the audio
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "No se realizará ninguna acción de silenciar el audio, ya que la solicitud es simplemente \"Don't mute the audio\". El dispositivo de audio actual sigue activo y el volumen está en 100."
}
```

Conjunto esperado: `[]`. Coincide: `True`. Finalización: `stop`.

### Llamada 16 · current_request_policy

**Entrada literal**
```text
no me digas la hora
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "No se realiza ninguna acción relacionada con la hora. La solicitud no requiere un cambio ni una observación de estado de tiempo."
}
```

Conjunto esperado: `[]`. Coincide: `True`. Finalización: `stop`.

### Llamada 17 · current_request_policy

**Entrada literal**
```text
no abras Steam, dime la hora
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_system__time",
        "arguments": "{}"
      },
      "id": "elsdZSsLur7hBTlV3me8wgP6UkgSsk6E"
    }
  ]
}
```

Conjunto esperado: `['system.time']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 18 · current_request_policy

**Entrada literal**
```text
dime la hora, no abras Steam
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_system__time",
        "arguments": "{}"
      },
      "id": "heqCFwXQagfXvsuzZ74LFmGF8DvuB4Qh"
    }
  ]
}
```

Conjunto esperado: `['system.time']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 19 · current_request_policy

**Entrada literal**
```text
dime la hora y no abras Steam
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_system__time",
        "arguments": "{}"
      },
      "id": "HcZaFWhRXZkRQ6RA8NKjmxhHSUjNRWS9"
    }
  ]
}
```

Conjunto esperado: `['system.time']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 20 · current_request_policy

**Entrada literal**
```text
no uses herramientas, dime la hora
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "No uso herramientas para responder. La hora actual es 14:38."
}
```

Conjunto esperado: `[]`. Coincide: `True`. Finalización: `stop`.

### Llamada 21 · current_request_policy

**Entrada literal**
```text
¿No está silenciado el audio?
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_audio__status",
        "arguments": "{}"
      },
      "id": "jZqVZqqt9RgTGZocTVVzAjYgiW5Ocd04"
    }
  ]
}
```

Conjunto esperado: `['audio.status']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 22 · current_request_policy

**Entrada literal**
```text
está silenciado el audio
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_audio__status",
        "arguments": "{}"
      },
      "id": "TcoDrxHYq66cduo1HFBQHON5o9ez0Ese"
    }
  ]
}
```

Conjunto esperado: `['audio.status']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 23 · current_request_policy

**Entrada literal**
```text
Ponlo a 100 ahora
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_audio__volume",
        "arguments": "{}"
      },
      "id": "tJLc1vFJzL8khyiDqQn0RteXo0Rq8XqE"
    }
  ]
}
```

Conjunto esperado: `['audio.volume']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 24 · current_request_policy

**Entrada literal**
```text
no me molesta, dime la hora
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_system__time",
        "arguments": "{}"
      },
      "id": "E9ZhoBKX57IDNdSHLdq54zOMtvls84Ly"
    }
  ]
}
```

Conjunto esperado: `['system.time']`. Coincide: `True`. Finalización: `tool_calls`.

## astra-negative-no-history

[Prerregistro y procedencia](astra-negative-no-history/PREREG.json) · [Payloads completos](astra-negative-no-history/posts.jsonl)

### Llamada 25 · without_history

**Entrada literal**
```text
no silencies el audio
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_audio__status",
        "arguments": "{}"
      },
      "id": "mdyajcTJJmQd74wFM3yedWjKQfsS4DMm"
    }
  ]
}
```

Conjunto esperado: `[]`. Coincide: `False`. Finalización: `tool_calls`.

### Llamada 26 · without_history

**Entrada literal**
```text
no subas el volumen
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "None of the provided functions directly relate to the request \"no subas el volumen\" (do not increase the volume). The closest function would be one that controls volume, but since the request is to *not* increase the volume, and no function is available to explicitly prevent an action, no function call is necessary. \n\nThus, no action is taken."
}
```

Conjunto esperado: `[]`. Coincide: `True`. Finalización: `stop`.

### Llamada 27 · without_history

**Entrada literal**
```text
Don't mute the audio
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "None of the provided functions are relevant to the request \"Don't mute the audio\". The request is a directive rather than a concrete action that can be executed by any of the available functions. Therefore, no function call is made."
}
```

Conjunto esperado: `[]`. Coincide: `True`. Finalización: `stop`.

### Llamada 28 · without_history

**Entrada literal**
```text
no me digas la hora
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "No puedo proporcionar la hora solicitada. Si necesitas información sobre el estado del sistema o otra acción específica, por favor indícalo."
}
```

Conjunto esperado: `[]`. Coincide: `True`. Finalización: `stop`.

### Llamada 29 · without_history

**Entrada literal**
```text
no abras Steam, dime la hora
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_system__time",
        "arguments": "{}"
      },
      "id": "9F4g5IthcqDUpnTpUyccGat99qBc8IJW"
    }
  ]
}
```

Conjunto esperado: `['system.time']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 30 · without_history

**Entrada literal**
```text
dime la hora, no abras Steam
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_system__time",
        "arguments": "{}"
      },
      "id": "mHxcHWCApJrKXeyqE3M2FoqiEQw1SXos"
    }
  ]
}
```

Conjunto esperado: `['system.time']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 31 · without_history

**Entrada literal**
```text
dime la hora y no abras Steam
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_system__time",
        "arguments": "{}"
      },
      "id": "8v90U26XCRJb0wxfdMMWTGFQ4c7it0Ma"
    }
  ]
}
```

Conjunto esperado: `['system.time']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 32 · without_history

**Entrada literal**
```text
no uses herramientas, dime la hora
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "La hora actual es 14:30."
}
```

Conjunto esperado: `[]`. Coincide: `True`. Finalización: `stop`.

### Llamada 33 · without_history

**Entrada literal**
```text
¿No está silenciado el audio?
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_audio__status",
        "arguments": "{}"
      },
      "id": "8sUxR4UDolhgaAOLVvmcYBIudmOY2R3X"
    }
  ]
}
```

Conjunto esperado: `['audio.status']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 34 · without_history

**Entrada literal**
```text
está silenciado el audio
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_audio__status",
        "arguments": "{}"
      },
      "id": "faumtcm5qxNeSTa6fwBHi5UgsofRdO4w"
    }
  ]
}
```

Conjunto esperado: `['audio.status']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 35 · without_history

**Entrada literal**
```text
Ponlo a 100 ahora
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_audio__volume",
        "arguments": "{}"
      },
      "id": "Tr1PhHbxX3Npt6B2r4mznRKRZJcGqBM4"
    }
  ]
}
```

Conjunto esperado: `['audio.volume']`. Coincide: `True`. Finalización: `tool_calls`.

### Llamada 36 · without_history

**Entrada literal**
```text
no me molesta, dime la hora
```

**Respuesta literal del modelo (campos capturados)**
```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "baxy_system__time",
        "arguments": "{}"
      },
      "id": "5xPj4qoUM3EdCkp7KOfa1d0xGViXdMiY"
    }
  ]
}
```

Conjunto esperado: `['system.time']`. Coincide: `True`. Finalización: `tool_calls`.

La política original obtiene 10/12; aclararla obtiene 11/12 y retirar historial obtiene 11/12. Las tres variantes siguen proponiendo audio.status ante «no silencies el audio». No se adoptan las dos variantes. El acierto de «Ponlo» sin historial no prueba resolución del referente: es un control de pérdida de contexto.

## astra-closed-prohibition11

[Casos](astra-closed-prohibition11/CASES.json) · [Captura](astra-closed-prohibition11/paired.json) · [Fuente y runtime](astra-closed-prohibition11/PREREG.json)

Exit 0; 99.22 s; GPU 3497.56 MiB; registro intacto: True.

### Turno 1

**Entrada literal**
```text
decime cuánto volumen hay
```

**Respuesta literal**
```text
El volumen es de 100. El sonido no está silenciado.
```

Terminal: `published_final`.

APROBADO: respuesta útil y coherente con la petición y el contexto observado.

### Turno 2

**Entrada literal**
```text
Ponlo a 100 ahora
```

**Respuesta literal**
```text
Ya está a 100%.
```

Terminal: `published_final`.

APROBADO: respuesta útil y coherente con la petición y el contexto observado.

### Turno 3

**Entrada literal**
```text
Hola, quien sos?
```

**Respuesta literal**
```text
Soy BAXY, el compañero de usuario en REDNOTE.
```

Terminal: `published_final`.

APROBADO: respuesta útil y coherente con la petición y el contexto observado.

### Turno 4

**Entrada literal**
```text
Dime qué dispositivo de audio está activo
```

**Respuesta literal**
```text
El dispositivo de audio activo es los altavoces (Realtek(R) Audio). El volumen está en 100 y el sonido no está silenciado.
```

Terminal: `published_final`.

APROBADO: respuesta útil y coherente con la petición y el contexto observado.

### Turno 5

**Entrada literal**
```text
no silencies el audio
```

**Respuesta literal**
```text
No silenciaré el audio, está activo y en funcionamiento.
```

Terminal: `published_final`.

APROBADO para la petición: reconoce la prohibición. Añade estado coherente con la lectura inmediatamente anterior; no demuestra reproducción física. Se elimina ese arrastre de contexto en la variante posterior, sin convertir esta preferencia de concisión en un fallo semántico.

### Turno 6

**Entrada literal**
```text
Don't mute the audio
```

**Respuesta literal**
```text
I won't mute the audio.
```

Terminal: `published_final`.

APROBADO: respuesta útil y coherente con la petición y el contexto observado.

### Turno 7

**Entrada literal**
```text
no subas el volumen
```

**Respuesta literal**
```text
Entendido, no subiré el volumen.
```

Terminal: `published_final`.

APROBADO: respuesta útil y coherente con la petición y el contexto observado.

### Turno 8

**Entrada literal**
```text
¿No está silenciado el audio?
```

**Respuesta literal**
```text
¿Quieres que revise si el audio está silenciado?
```

Terminal: `published_final`.

NO APROBADO: pide confirmar la lectura que la persona ya solicitó mediante una pregunta negativa.

### Turno 9

**Entrada literal**
```text
dime la hora, no abras Steam
```

**Respuesta literal**
```text
[No hubo respuesta final visible]
```

Terminal: `composition_failed`.

NO APROBADO: no hubo respuesta final visible.

### Turno 10

**Entrada literal**
```text
dime la hora y no abras Steam
```

**Respuesta literal**
```text
No pude interpretar la solicitud.
```

Terminal: `published_final`.

NO APROBADO: una petición de hora con prohibición independiente termina en error de interpretación.

### Turno 11

**Entrada literal**
```text
dime la hora
```

**Respuesta literal**
```text
22:09
```

Terminal: `published_final`.

APROBADO: respuesta útil y coherente con la petición y el contexto observado.

[Observaciones y composición](astra-closed-prohibition11/compose-audit.jsonl) · [Decisiones y rechazos](astra-closed-prohibition11/turn-audit.jsonl) · [Ejecución Core](astra-closed-prohibition11/shell-trace.jsonl)

## astra-closed-prohibition7

[Casos](astra-closed-prohibition7/CASES.json) · [Captura](astra-closed-prohibition7/paired.json) · [Fuente y runtime](astra-closed-prohibition7/PREREG.json)

Exit 0; 63.08 s; GPU 3497.56 MiB; registro intacto: True.

### Turno 1

**Entrada literal**
```text
decime cuánto volumen hay
```

**Respuesta literal**
```text
El volumen es de 100. El sonido no está silenciado.
```

Terminal: `published_final`.

APROBADO: respuesta útil y coherente con la petición y el contexto observado.

### Turno 2

**Entrada literal**
```text
Ponlo a 100 ahora
```

**Respuesta literal**
```text
Ya está a 100%.
```

Terminal: `published_final`.

APROBADO: respuesta útil y coherente con la petición y el contexto observado.

### Turno 3

**Entrada literal**
```text
Hola, quien sos?
```

**Respuesta literal**
```text
Soy BAXY, el compañero de usuario en REDNOTE.
```

Terminal: `published_final`.

APROBADO: respuesta útil y coherente con la petición y el contexto observado.

### Turno 4

**Entrada literal**
```text
Dime qué dispositivo de audio está activo
```

**Respuesta literal**
```text
El dispositivo de audio activo es los altavoces (Realtek(R) Audio). El volumen está en 100 y el sonido no está silenciado.
```

Terminal: `published_final`.

APROBADO: respuesta útil y coherente con la petición y el contexto observado.

### Turno 5

**Entrada literal**
```text
no silencies el audio
```

**Respuesta literal**
```text
No silenciaré el audio, siempre estaré presente sin interrupciones.
```

Terminal: `published_final`.

NO APROBADO: reconoce la prohibición pero añade una promesa universal de presencia sin interrupciones que BAXY no puede garantizar.

### Turno 6

**Entrada literal**
```text
Don't mute the audio
```

**Respuesta literal**
```text
I'll make sure the audio stays loud and clear for you.
```

Terminal: `published_final`.

NO APROBADO: cambia no silenciar por garantizar audio fuerte y claro. La persona no pidió elevar el volumen ni se midió claridad física.

### Turno 7

**Entrada literal**
```text
no subas el volumen
```

**Respuesta literal**
```text
Entendido, no subiré el volumen.
```

Terminal: `published_final`.

APROBADO: respuesta útil y coherente con la petición y el contexto observado.

[Observaciones y composición](astra-closed-prohibition7/compose-audit.jsonl) · [Decisiones y rechazos](astra-closed-prohibition7/turn-audit.jsonl) · [Ejecución Core](astra-closed-prohibition7/shell-trace.jsonl)

Conserva 36 llamadas del modelo y 18 respuestas de producto. Las repeticiones no son casos frescos. closed-prohibition11: 8/11 útiles; quedan pregunta negativa y orden de cláusulas. La variante de siete turnos obtiene 5/7: retirar historial empeora dos reconocimientos. Se revierte únicamente ese cambio; se conserva el cierre de prohibiciones en la decisión. Tampoco resuelve aquellos tres controles.
