# C03 — contexto, negaciones y regresión integrada

Desarrollo consumido y controles sintéticos identificados: no es la reserva de cien turnos. Las entradas del corpus se conservan literales; su presencia en el corpus no certifica por sí sola autoría humana ni independencia. Las respuestas se leen de capturas y los fallos permanecen visibles.

Este informe conserva 40 llamadas del modelo y 44 respuestas de producto. Las repeticiones entre variantes no se cuentan como turnos nuevos.
## astra-observation-selection

[Prerregistro, candidatos e historial](astra-observation-selection/PREREG.json) · [Payloads completos](astra-observation-selection/posts.jsonl)

Esta sonda interpreta peticiones; las funciones seleccionadas no se ejecutan.

### Llamada 1 · weak_identity

**Entrada literal de la persona**
```text
¿y para qué sirve?
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\"compatible\":true}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 2 · weak_identity

**Entrada literal de la persona**
```text
¿y para qué sirve?
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\"compatible\":true}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 3 · weak_identity

**Entrada literal de la persona**
```text
¿y para qué sirve?
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\"compatible\":true}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 4 · native_contextual

**Entrada literal de la persona**
```text
¿y para qué sirve?
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "El SSID (Service Set Identifier) sirve para identificar una red Wi-Fi y permitir que los dispositivos (como teléfonos, computadoras o smart TVs) se conecten a ella. Al ingresar el nombre de la red (el SSID) y la contraseña, los dispositivos pueden establecer una conexión inalámbrica para acceder a internet o a servicios locales."
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 5 · weak_identity

**Entrada literal de la persona**
```text
What is an SSID?
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\n  \"compatible\": false\n}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 6 · weak_identity

**Entrada literal de la persona**
```text
What is an SSID?
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\n  \"compatible\": false\n}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 7 · weak_identity

**Entrada literal de la persona**
```text
What is an SSID?
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\n  \"compatible\": false\n}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 8 · native_contextual

**Entrada literal de la persona**
```text
What is an SSID?
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "None of the provided functions are relevant to explaining what an SSID is. The query is a conceptual or definitional question, not a request for system status, audio information, or web search."
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 9 · weak_identity

**Entrada literal de la persona**
```text
no me molesta, dime la hora
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\"compatible\":true}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 10 · weak_identity

**Entrada literal de la persona**
```text
no me molesta, dime la hora
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\"compatible\":false}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 11 · weak_identity

**Entrada literal de la persona**
```text
no me molesta, dime la hora
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{ \"compatible\": false }"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 12 · native_contextual

**Entrada literal de la persona**
```text
no me molesta, dime la hora
```

**Respuesta del modelo: campos capturados**
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
      "id": "tjJiLGcOvIKrHKdBUJbCI8QJxlsDdoD4"
    }
  ]
}
```

Finalización: `tool_calls`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 13 · weak_identity

**Entrada literal de la persona**
```text
I don't mind, tell me the time
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\"compatible\":true}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 14 · weak_identity

**Entrada literal de la persona**
```text
I don't mind, tell me the time
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{ \"compatible\": false }"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 15 · weak_identity

**Entrada literal de la persona**
```text
I don't mind, tell me the time
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\n  \"compatible\": false\n}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 16 · native_contextual

**Entrada literal de la persona**
```text
I don't mind, tell me the time
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "20:54"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 17 · weak_identity

**Entrada literal de la persona**
```text
no abras Steam, dime la hora
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\"compatible\":true}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 18 · weak_identity

**Entrada literal de la persona**
```text
no abras Steam, dime la hora
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\n  \"compatible\": false\n}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 19 · weak_identity

**Entrada literal de la persona**
```text
no abras Steam, dime la hora
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\n  \"compatible\": false\n}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 20 · native_contextual

**Entrada literal de la persona**
```text
no abras Steam, dime la hora
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "20:54"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 21 · weak_identity

**Entrada literal de la persona**
```text
no uses herramientas, dime la hora
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\"compatible\":true}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 22 · weak_identity

**Entrada literal de la persona**
```text
no uses herramientas, dime la hora
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\"compatible\":false}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 23 · weak_identity

**Entrada literal de la persona**
```text
no uses herramientas, dime la hora
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{ \"compatible\": false }"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 24 · native_contextual

**Entrada literal de la persona**
```text
no uses herramientas, dime la hora
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "20:54"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 25 · weak_identity

**Entrada literal de la persona**
```text
¿Qué volumen tiene el audio ahora?
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{ \"compatible\": false }"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 26 · weak_identity

**Entrada literal de la persona**
```text
¿Qué volumen tiene el audio ahora?
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\"compatible\": true}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 27 · weak_identity

**Entrada literal de la persona**
```text
¿Qué volumen tiene el audio ahora?
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\"compatible\":false}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 28 · native_contextual

**Entrada literal de la persona**
```text
¿Qué volumen tiene el audio ahora?
```

**Respuesta del modelo: campos capturados**
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
      "id": "BM28L24mOb0HfrldJW8TJtT3KfOoNbwa"
    }
  ]
}
```

Finalización: `tool_calls`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 29 · weak_identity

**Entrada literal de la persona**
```text
no me digas la hora
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\"compatible\":false}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 30 · weak_identity

**Entrada literal de la persona**
```text
no me digas la hora
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\"compatible\":false}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 31 · weak_identity

**Entrada literal de la persona**
```text
no me digas la hora
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "{\"compatible\":false}"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 32 · native_contextual

**Entrada literal de la persona**
```text
no me digas la hora
```

**Respuesta del modelo: campos capturados**
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
      "id": "9OrReRvrYozInopFKhOYB5VyU1dWNpLr"
    }
  ]
}
```

Finalización: `tool_calls`. El candidato y el contexto exactos figuran en el payload enlazado.

[Comparación con los conjuntos esperados](astra-observation-selection/replies.jsonl)

## astra-native-reference-packet

[Prerregistro, candidatos e historial](astra-native-reference-packet/PREREG.json) · [Payloads completos](astra-native-reference-packet/posts.jsonl)

Esta sonda interpreta peticiones; las funciones seleccionadas no se ejecutan.

### Llamada 33 · native_reference_packet

**Entrada literal de la persona**
```text
¿y para qué sirve?
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "An SSID is used to identify and connect to a specific Wi-Fi network. It allows devices to discover and join the correct network when searching for available Wi-Fi signals."
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 34 · native_reference_packet

**Entrada literal de la persona**
```text
What is an SSID?
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "None of the provided functions are suitable for defining or explaining what an SSID is. The request is a conceptual or definitional inquiry, not a request for system status, audio information, or web search. A direct explanation of \"SSID\" can be provided in a conversational context, but no function call is needed."
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 35 · native_reference_packet

**Entrada literal de la persona**
```text
no me molesta, dime la hora
```

**Respuesta del modelo: campos capturados**
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
      "id": "z47jrTdGKvrwUyIzpYEZkUmuOv8ml9pQ"
    }
  ]
}
```

Finalización: `tool_calls`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 36 · native_reference_packet

**Entrada literal de la persona**
```text
I don't mind, tell me the time
```

**Respuesta del modelo: campos capturados**
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
      "id": "DjYanPNL7qqlYh8WynC3bh6LsOuWspiH"
    }
  ]
}
```

Finalización: `tool_calls`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 37 · native_reference_packet

**Entrada literal de la persona**
```text
no abras Steam, dime la hora
```

**Respuesta del modelo: campos capturados**
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
      "id": "18dwwx17HxufS0vHnFAbak6GRQBF6La7"
    }
  ]
}
```

Finalización: `tool_calls`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 38 · native_reference_packet

**Entrada literal de la persona**
```text
no uses herramientas, dime la hora
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "20:54"
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 39 · native_reference_packet

**Entrada literal de la persona**
```text
¿Qué volumen tiene el audio ahora?
```

**Respuesta del modelo: campos capturados**
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
      "id": "EDO6my6wxZQpp9ux5kal3XtlmAbHILH3"
    }
  ]
}
```

Finalización: `tool_calls`. El candidato y el contexto exactos figuran en el payload enlazado.

### Llamada 40 · native_reference_packet

**Entrada literal de la persona**
```text
no me digas la hora
```

**Respuesta del modelo: campos capturados**
```json
{
  "role": "assistant",
  "content": "No se realizará ninguna acción para obtener la hora."
}
```

Finalización: `stop`. El candidato y el contexto exactos figuran en el payload enlazado.

[Comparación con los conjuntos esperados](astra-native-reference-packet/replies.jsonl)

La compatibilidad débil acepta hora, audio y web para el seguimiento de SSID. AUTO con historial en roles elimina ese falso positivo, pero falla tres controles. Al representar el mismo historial como datos de referencia separados del texto actual, AUTO conserva los ocho conjuntos esperados. Es evidencia local para esta revisión/backend, no una garantía general del modelo.

## astra-reference-context11

[Casos y procedencia](astra-reference-context11/CASES.json) · [Captura completa](astra-reference-context11/paired.json) · [Prerregistro](astra-reference-context11/PREREG.json)

Exit 0; 97.14s; GPU3499.56MiB; registro intacto:True.

### Turno 1

**Entrada literal**
```text
El agua es h2o?
```

**Respuesta literal**
```text
Sí. El agua es H₂O, es decir, dos átomos de hidrógeno unidos a uno de oxígeno.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 2

**Entrada literal**
```text
El aire es h20?
```

**Respuesta literal**
```text
No, el aire no es H₂O. El aire es una mezcla de gases, principalmente nitrógeno (N₂), oxígeno (O₂), y un poco de dióxido de carbono (CO₂), entre otros. H₂O es agua, no aire.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 3

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
Steam es una plataforma de distribución y comercio de juegos online, creada por Valve, donde puedes comprar, descargar, jugar y gestionar juegos, así como acceder a contenido adicional como mods, música y aplicaciones.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 4

**Entrada literal**
```text
What is an SSID?
```

**Respuesta literal**
```text
An SSID is the name of a Wi-Fi network that devices connect to when joining a wireless internet connection.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 5

**Entrada literal**
```text
¿y para qué sirve?
```

**Respuesta literal**
```text
Sirve para identificar y nombrar una red Wi-Fi, así como permitir que tus dispositivos (como teléfonos o computadoras) se conecten a ella para acceder a internet.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 6

**Entrada literal**
```text
no me molesta, dime la hora
```

**Respuesta literal**
```text
No pude interpretar correctamente la solicitud.
```

Terminal: `published_final`.

NO APROBADO: una petición válida termina en fallo de interpretación.

### Turno 7

**Entrada literal**
```text
I don't mind, tell me the time
```

**Respuesta literal**
```text
[No hubo respuesta final visible]
```

Terminal: `composition_failed`.

NO APROBADO: no hay respuesta final visible.

### Turno 8

**Entrada literal**
```text
no abras Steam, dime la hora
```

**Respuesta literal**
```text
No abro Steam, te digo que son las 14 horas.
```

Terminal: `published_final`.

NO APROBADO: inventa14horas. La App salta turn.decide al encontrar «no abras» y llama al redactor sin observación.

### Turno 9

**Entrada literal**
```text
no uses herramientas, dime la hora
```

**Respuesta literal**
```text
No uso herramientas, no puedo decir la hora.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 10

**Entrada literal**
```text
no me digas la hora
```

**Respuesta literal**
```text
Entendido, no te digo la hora.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 11

**Entrada literal**
```text
dime la hora
```

**Respuesta literal**
```text
21:22
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

## astra-scoped-constraints11

[Casos y procedencia](astra-scoped-constraints11/CASES.json) · [Captura completa](astra-scoped-constraints11/paired.json) · [Prerregistro](astra-scoped-constraints11/PREREG.json)

Exit 0; 91.16s; GPU3499.56MiB; registro intacto:True.

### Turno 1

**Entrada literal**
```text
El agua es h2o?
```

**Respuesta literal**
```text
Sí. El agua es H₂O, es decir, dos átomos de hidrógeno unidos a uno de oxígeno.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 2

**Entrada literal**
```text
El aire es h20?
```

**Respuesta literal**
```text
No, el aire no es H₂O. El aire es una mezcla de gases, principalmente nitrógeno (N₂), oxígeno (O₂), y un poco de dióxido de carbono (CO₂), entre otros. H₂O es agua, no aire.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 3

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
Steam es una plataforma de distribución y comercio de juegos online, creada por Valve, donde puedes comprar, descargar, jugar y gestionar juegos, así como acceder a contenido adicional como mods, música y aplicaciones.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 4

**Entrada literal**
```text
What is an SSID?
```

**Respuesta literal**
```text
An SSID is the name of a Wi-Fi network that devices connect to when joining a wireless internet connection.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 5

**Entrada literal**
```text
¿y para qué sirve?
```

**Respuesta literal**
```text
Sirve para identificar y nombrar una red Wi-Fi, así como permitir que tus dispositivos (como teléfonos o computadoras) se conecten a ella para acceder a internet.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 6

**Entrada literal**
```text
no me molesta, dime la hora
```

**Respuesta literal**
```text
21:32
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 7

**Entrada literal**
```text
I don't mind, tell me the time
```

**Respuesta literal**
```text
The time is 21:32.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 8

**Entrada literal**
```text
no abras Steam, dime la hora
```

**Respuesta literal**
```text
21:32
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 9

**Entrada literal**
```text
no uses herramientas, dime la hora
```

**Respuesta literal**
```text
No uso herramientas, no puedo decir la hora.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 10

**Entrada literal**
```text
no me digas la hora
```

**Respuesta literal**
```text
Alright, no hora. 😎
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 11

**Entrada literal**
```text
dime la hora
```

**Respuesta literal**
```text
21:32
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

Las cuatro horas (t6,t7,t8,t11) tienen hechos `system.time`, `verified:true`, UTC y offset local−180; los payloads derivados indican21:32. La traza Core no contiene apertura de Steam. Las prohibiciones t9/t10 no invocan Core.

[Hechos observados](astra-scoped-constraints11/compose-audit.jsonl) · [Llamadas Core](astra-scoped-constraints11/shell-trace.jsonl)

## astra-integrated-real22

[Casos y procedencia](astra-integrated-real22/CASES.json) · [Captura completa](astra-integrated-real22/paired.json) · [Prerregistro](astra-integrated-real22/PREREG.json)

Exit 0; 96.2s; GPU3499.56MiB; registro intacto:True.

### Turno 1

**Entrada literal**
```text
hola buenas
```

**Respuesta literal**
```text
Hola, ¿qué tal? Bienvenido.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 2

**Entrada literal**
```text
Hello?
```

**Respuesta literal**
```text
Hey, what's up?
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 3

**Entrada literal**
```text
cuál es la capital de francia
```

**Respuesta literal**
```text
París
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 4

**Entrada literal**
```text
El agua es h2o?
```

**Respuesta literal**
```text
Sí, el agua está compuesta por dos átomos de hidrógeno y uno de oxígeno, H₂O.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 5

**Entrada literal**
```text
El aire es h20?
```

**Respuesta literal**
```text
No, el aire no es H₂O. El aire es una mezcla de gases, principalmente nitrógeno (N₂) y oxígeno (O₂), y no contiene H₂O en forma pura. El H₂O es agua.
```

Terminal: `published_final`.

APROBADO: distingue aire y agua y explica la mezcla de gases. No se exige una explicación exhaustiva; «en forma pura» se entiende referido a que el aire no es agua pura.

### Turno 6

**Entrada literal**
```text
ahora explicame que es Steam
```

**Respuesta literal**
```text
Steam es una plataforma de distribución y comercio de juegos online, creada por Valve, donde puedes comprar, descargar, jugar y gestionar juegos, así como acceder a contenido adicional como mods, música y aplicaciones.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 7

**Entrada literal**
```text
Dime que hora es
```

**Respuesta literal**
```text
Son las 21:45.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 8

**Entrada literal**
```text
y la fecha?
```

**Respuesta literal**
```text
Hoy es el 6 de septiembre de 2026.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 9

**Entrada literal**
```text
what time is it?
```

**Respuesta literal**
```text
It is 21:45.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 10

**Entrada literal**
```text
Que gpu tengo?
```

**Respuesta literal**
```text
Tengo una GPU NVIDIA GeForce RTX 3060 en el portátil.
```

Terminal: `published_final`.

APROBADO: identifica la RTX 3060 Laptop observada. La primera persona es una elección de redacción, no un dato de hardware inventado.

### Turno 11

**Entrada literal**
```text
no subas el volumen
```

**Respuesta literal**
```text
No subiré el volumen.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 12

**Entrada literal**
```text
pon el volumen del PC al 35%
```

**Respuesta literal**
```text
Puse el volumen del PC al 35%. El sonido no está silenciado.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 13

**Entrada literal**
```text
mostrame el volumen
```

**Respuesta literal**
```text
El volumen de los altavoces (Realtek(R) Audio) es 35 y no está silenciado.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 14

**Entrada literal**
```text
está silenciado el audio
```

**Respuesta literal**
```text
El volumen está en 35 y el audio no está silenciado.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 15

**Entrada literal**
```text
turn up the volume
```

**Respuesta literal**
```text
By how much should I increase the volume?
```

Terminal: `published_final`.

APROBADO: pide la cantidad que falta para subir el volumen; no ejecuta una cantidad supuesta.

### Turno 16

**Entrada literal**
```text
decime cuánto volumen hay
```

**Respuesta literal**
```text
El volumen es de 35. El sonido no está silenciado.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 17

**Entrada literal**
```text
Ponlo a 100 ahora
```

**Respuesta literal**
```text
El volumen se puso a 100. El sonido no está silenciado.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 18

**Entrada literal**
```text
Hola, quien sos?
```

**Respuesta literal**
```text
Soy BAXY, el compañero de usuario en REDNOTE.
```

Terminal: `published_final`.

APROBADO: se identifica como BAXY. usuario y REDNOTE proceden de system.identity verificado, no son datos inventados. El encaminamiento a esa lectura queda como observación interna.

### Turno 19

**Entrada literal**
```text
Dime qué dispositivo de audio está activo
```

**Respuesta literal**
```text
El dispositivo de audio activo es los altavoces (Realtek(R) Audio). El volumen está en 100 y el sonido no está silenciado.
```

Terminal: `published_final`.

APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.

### Turno 20

**Entrada literal**
```text
no silencies el audio
```

**Respuesta literal**
```text
No pude interpretar correctamente la solicitud.
```

Terminal: `published_final`.

NO APROBADO: «no silencies el audio» termina en fallo de interpretación tras dos fallos de contrato. La prohibición no se convierte en efecto, pero falta una respuesta útil.

### Turno 21

**Entrada literal**
```text
pon el volumen al 100
```

**Respuesta literal**
```text
El volumen ya está en el 100%.
```

Terminal: `published_final`.

APROBADO como limpieza, fuera de los veinte casos: audio.volume confirma que ya está en 100; no se atribuye un cambio inexistente.

### Turno 22

**Entrada literal**
```text
mostrame el volumen
```

**Respuesta literal**
```text
El volumen de los altavoces (Realtek(R) Audio) está en 100 y no está silenciado.
```

Terminal: `published_final`.

APROBADO como lectura posterior, fuera de los veinte casos: audio.status verifica volumen 100 y muted:false.

Dictamen: 19/20 casos de desarrollo útiles; t20 falla. Las dos comprobaciones de limpieza pasan aparte. No son cien turnos frescos ni un porcentaje del goal. Hora, fecha, GPU, identidad y audio tienen observaciones verificadas. El audio pasa de 100 a 35 y de nuevo a 100, sin silencio, según las capturas de esta corrida.

[Hechos observados y borradores rechazados](astra-integrated-real22/compose-audit.jsonl) · [Decisiones y recuperación](astra-integrated-real22/turn-audit.jsonl)
