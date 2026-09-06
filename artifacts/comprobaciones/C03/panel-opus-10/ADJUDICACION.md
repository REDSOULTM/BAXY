# C03 — panel de diagnóstico, ronda 10 (2026-09-05)

70 turnos por el conductor público con Granite 4.2 3B registrado. 66 publicados,
3 `composition_failed`, 1 `filtered` (silencio). Población: 62 de regresión de
las rondas anteriores más 8 casos nuevos de conocimiento y reloj.

**No es una aceptación.** Toda esta población se ha usado para reparar, así que
queda como regresión: los cien turnos frescos del tramo D siguen pendientes.

## Reparado y verificado en esta ronda

| Antes | Ahora |
|---|---|
| `explícame qué es un router en una frase` → agotamiento | `Un router enruta el tráfico de red entre dispositivos y el Internet.` |
| `what is a core dump in one sentence` → «I cannot answer that request» | responde |
| `hi, what time is it?` → agotamiento | `The time is 16:36.` |
| bienvenida de arranque → `…la situación.greeting…` | `Hola.` |
| `qué no puedes hacer en este PC` → agotamiento | responde el límite |

La causa común de los tres primeros era la misma: la lista de jerga interna
(`router`, `core`, `tool`, `operación`, `catálogo`…) se aplicaba por subcadena
sin mirar el pedido, y hacía imposible responder a una pregunta sobre esas
palabras. Ahora un término deja de ser jerga cuando la persona pregunta por él,
en los dos lados de la frontera y también en la instrucción al modelo.

## Defectos que quedan, por clase

1. **Seguimientos sin tema** (t20, t22, t32, t34, t56): «¿por qué importa?» se
   contesta «porque entender por qué importa ayuda a decidir». La mente recibe
   el historial y aun así responde en abstracto: la ruta contextual sólo corre
   para `conversation_kind` `followup`/`None`, y estas preguntas se clasifican
   como `knowledge`. **Esta causa era falsa**; la real está en `SEGUIMIENTOS.md`.
   Forzarla (hipótesis medida en `seguimiento-3`) no mejoró y
   contaminó otro turno, así que la reparación pertenece al contrato de
   decisión de la mente, no a otro veto de composición.
2. **Respuesta del turno anterior** (t52, t66, t67): el turno contesta la
   pregunta previa. Aparece con preguntas de conocimiento seguidas.
3. **Devolver la tarea** (t23 «You need to post a letter to Eris.») y refusales
   sin límite (t46, t58, t60).
4. **Capacidades inventadas** (t51: límites de hardware que nadie leyó).
5. **Agotamientos y silencio** (t10, t40, t62, t42): 4 de 70.

Las clases 1 y 2 son de la ruta conversacional de la mente y tocan C05/C06; se
dejan trazadas aquí con su evidencia, no se intentan en C03.

## Instrumentación disponible

`compose-audit.jsonl` trae por etapa el turno, idioma, saludo, payload real,
borrador sin recortar, motivo exacto y `finish_reason`. `paired.json` añade
`mindReplyRejection`: por qué el shell descartó la respuesta que la mente había
redactado, con nombre (`unsafe_language:<término>`, `looks_like_failure`,
`stuttered_token`, `no_reply_for_kind:<clase>`). Sin esos dos nombres, cada
diagnóstico exigía relanzar la campaña.
