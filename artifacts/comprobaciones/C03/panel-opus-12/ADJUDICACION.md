# C03 — panel de diagnóstico, ronda 12 (2026-09-05)

78 turnos por el conductor público con Granite 4.2 3B registrado.
**77 publicados, 1 agotamiento, 0 silencios.** Población: 74 de regresión más
4 casos nuevos de encargo del mundo y de reloj.

**No es una aceptación.** Toda esta población se ha usado para reparar; queda
como regresión y los cien turnos frescos del tramo D siguen pendientes.

## Reparado y verificado desde la ronda 10

| Clase | Antes | Ahora |
|---|---|---|
| Encargo del mundo | `send a parcel to Rhea` → «I will send the parcel to Rhea» | «I cannot send a parcel to Rhea because this PC does not have that capability» |
| Encargo del mundo (nuevo) | — | Encélado, pizza a la oficina y vuelo a Madrid: los tres nombran el límite |
| Reloj parafraseado | `dime la hora en este momento` → «Sébo.» | «La hora en este momento es 18:21.» |
| Pregunta del turno anterior | t66/t67 devolvían la petición previa | responden lo suyo |
| Silencio del primer turno | `filtered` con `composer_unavailable` | el turno espera su composición |
| Hueco de plantilla | «La hora actual es [hora actual en español].» | vetado |

La reparación de fondo del encargo del mundo es que ya no se lee por una lista
de planetas —que no conocía Rhea ni Encélado— sino por el acto pedido: mandar
una carta o reservar una plaza no está en el catálogo, vaya a donde vaya.

## Defectos que quedan, por clase

1. **Seguimientos sin tema** (020, 022, 032, 034, 056): «¿por qué importa?» se
   contesta en abstracto. ~~La ruta contextual de la mente sólo corre para
   `conversation_kind` `followup`/`None` y estas preguntas se clasifican
   `knowledge`.~~ **Esta causa era falsa.** La traza de composición enseña que
   el compositor recibe `{"kind":"conversation","polarity":"success"}` y nada
   más: sin la respuesta de la mente, sin historial y sin tema. Reparado y
   medido en `SEGUIMIENTOS.md`.
2. **Persona y gramática** (015 «No abres la Calculadora», 016 «¿Quieres que
   cierres…?», 042 «que te abres», 001/004 «Hello hi!»).
3. **Capacidades o límites inventados** (051 CPU/RAM, 052 sobre el idioma,
   046 y 066 rechazan preguntas que sí saben responder, 058 invierte).
4. **Eco del pedido** (043 «¿Qué resultado numérico te gustaría obtener…?»).
5. **Un agotamiento** (062).

La clase 3 vive en la generación conversacional de la mente y toca C05/C06; se
deja trazada con su evidencia, no se intenta aquí. La clase 1 sí se reparó
después de esta captura, una vez encontrada su causa real.

## Reparado después de esta captura

`panel-opus-12/011` publicó «Hago el volumen al nivel 20 y te digo que la hora
es las 18:11.» sobre un turno que sólo leyó reloj y audio. Un turno de lectura
que dice haber cambiado el estado es ahora `reversed_result`, comprobado en
`tests/test_compose_contract.py`.
