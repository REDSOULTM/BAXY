# Reglas para escribir el «oro de decisión» de BAXY

Lees esto porque vas a escribir o revisar qué **debería decidir** BAXY ante cada mensaje de una persona. No necesitas
(ni debes) ver el código de BAXY: el oro describe la conducta correcta según las decisiones del dueño del producto.

## Qué es BAXY

Un asistente tipo Jarvis que vive en un PC con Windows, local y privado. Habla español, inglés y spanglish; tutea;
responde breve y cálido y confirma lo que comprobó («Listo, subí el volumen a 45»). Actúa sobre el PC con un
**catálogo cerrado de operaciones** (fichero `CATALOGO.md` al lado de éste: nombre, argumentos, riesgo y qué hace). Lo
que no está en el catálogo no lo hace. Puede **buscar en la web** (entra información; nunca envía datos de la persona).

## Qué decide BAXY en cada turno (una de estas)

| etiqueta | significa | se cumple si BAXY… |
|---|---|---|
| `op:<nombre>` | ejecutar esa operación del catálogo (nombre exacto) | decide una acción o un plan que incluye esa operación |
| `op:<prefijo>*` | cualquier operación que empiece así (`op:media.play*`, `op:window*`, `op:note*`) | ídem |
| `plan:<a>+<b>` | varias operaciones en el mismo turno | decide un plan que incluye todas |
| `web` | buscar lo público: `web.search`, `weather.current` o `web.news.headlines` (cualquiera) | decide alguna de ellas |
| `talk` | contestar hablando, sin tocar el PC: conocimiento estable, charla, escribir contenido (código, recetas, listas, cuentos, traducciones), cálculo y conversiones, consejos, hablar de sí mismo, agradecer | responde como conversación que no es un límite |
| `limit` | decir en llano que eso no lo hace («Eso no lo hago: no puedo pedir comida») | responde como conversación de límite |
| `ask` | hacer **una** pregunta corta porque falta de verdad algo que cambia el resultado | pide una aclaración |

El oro de un turno es la **lista de todas las decisiones aceptables** (a veces hay más de una razonable). Ejemplos:
`["op:weather.current"]`, `["ask", "op:audio.volume.adjust"]`, `["web", "talk"]`, `["limit"]`.

## Reglas del dueño (mandan sobre tu intuición)

1. **Lo público se busca.** Lo que cambia o no se sabe de memoria con seguridad —clima, noticias, deportes
   (resultados, próximos partidos, tablas), precios, tipo de cambio, bolsa, horarios, estrenos, tráfico, datos de una
   persona, empresa, lugar o producto concretos, «¿qué tal es la peli X?»— es `web` (el clima puede ser
   `op:weather.current`, que ya cuenta como `web`). **Hechos estables** (qué es la fotosíntesis, capital de Francia,
   cuánto es 15 % de 80, traducir una frase, convertir unidades, explicar cómo se hace algo) → `talk`; si un hecho
   concreto se podría verificar, acepta `web` también (`["talk", "web"]`).
2. **Lo propio no se busca en la web.** Datos de la persona (sus notas, recordatorios, alarmas, tareas, listas,
   agenda, archivos, lo que suena en su PC), preguntas sobre BAXY mismo o sobre lo que BAXY acaba de decir → la
   operación del catálogo que lo lee, o `talk`, o `ask`; **nunca** `web`.
3. **Lo completo no se repregunta.** Si el mensaje trae lo necesario, el oro es actuar (no `ask`). Ante un valor por
   defecto razonable (el clima «de aquí» = la ubicación del PC; «pon música» = algo de música), se actúa.
4. **Cantidad relativa sin número se pregunta.** «Súbele un poco», «baja el brillo», «más fuerte» sin cuánto →
   `["ask"]` (sólo eso). Con cantidad («súbele 10», «bájalo a 30», «ponlo al máximo») → la operación de ajuste o de
   nivel.
5. **El límite se dice en llano.** BAXY vive en un PC: no controla luces ni aparatos de la casa, no hace llamadas ni
   SMS, no pide comida, taxis ni compras, no maneja relojes/pulseras/apps del móvil, no reserva nada → `limit`. Si
   el catálogo tiene algo que sí sirve (abrir una app instalada del PC, buscar en la web), acéptalo también.
6. **Dato de la persona que falta → se pregunta.** «¿Llueve donde vive mi hermana?», «¿a qué hora es mi cita?» sin
   agenda que lo diga → `ask` (o la operación que lo leería del PC, si existe).
7. **Lo mal dicho lo arregla BAXY.** Erratas, sin tildes, dictado sin puntuación, spanglish: se entienden como la
   persona quiso decir; no son motivo para preguntar.
8. **Seguimientos.** Un mensaje que depende de lo anterior («¿y en Santiago?», «ahora en javascript», «20 minutos
   antes de eso», «súbele otro poco», «esa no, otra», «sí, dale», «10») se decide con el contexto: la misma
   operación con el valor nuevo, o la conversación que reusa lo que BAXY respondió. Si BAXY acaba de preguntar algo y
   la persona contesta, el oro es completar el pedido pendiente.
9. **Charla, gracias, quejas y reacciones** («jaja», «gracias», «qué respuesta más rara», «¿me escuchas?») → `talk`.
10. **Nada destructivo por error**: borrar, cerrar, enviar o comprar sólo si se pidió claramente.

## Operaciones frecuentes (mira `CATALOGO.md` para el resto)

- Volumen: `audio.volume` (nivel absoluto), `audio.volume.adjust` (subir/bajar N), `audio.mute`, `audio.status`;
  por aplicación `audio.app.volume.*`. Brillo: `system.settings.adjust` / `system.settings.set` (usa
  `op:system.settings*`).
- Música y video: `media.play.query` / `media.play.exact` (Spotify), `media.play.youtube`, `streaming.play.named`
  (Netflix, Disney+); controlar lo que suena: `media.control` (pausa, sigue, siguiente, anterior), `media.status`
  (qué suena). Usa `op:media.play*` cuando valga cualquier reproductor.
- Alarmas, recordatorios, temporizadores: `notification.schedule` o `reminder.create` (acepta ambos:
  `["op:notification.schedule", "op:reminder.create"]`); listar: `notification.list`, `reminder.list`; cancelar:
  `notification.cancel.*`. Tareas y listas: `task.*`; notas: `note.*`.
- Hora y fecha (también de otro país): `system.time`. Clima: `weather.current`. Noticias: `web.news.headlines`.
  Todo lo demás público: `web.search`.
- Apps y ventanas: `app.open`, `window.*` (usa `op:window*`), `window.minimize.all`; capturas: `capture.*`;
  archivos en carpetas conocidas: `filesystem.known.*`; calculadora de Windows: `calculator.expression.evaluate`
  (una cuenta simple también puede ser `talk`).

## Argumentos clave (opcional)

Cuando el acierto depende de un valor —sobre todo en un seguimiento— añade `args`: para una etiqueta del oro, una
lista de grupos; cada grupo es una lista de formas aceptables (minúsculas, sin tildes) y **alguna** debe aparecer en
los argumentos de la operación. Ejemplo tras hablar del clima de Curicó, «¿y en santiago?» →
`"gold": ["op:weather.current"], "args": {"op:weather.current": [["santiago"]]}`. Úsalo sólo para el valor que prueba
que se entendió (lugar, cantidad, artista o título, nombre de la app, idioma del código no aplica porque es `talk`).
