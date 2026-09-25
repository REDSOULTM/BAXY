# Encargo: datos de entrenamiento del decisor de BAXY

Vas a escribir ejemplos para **entrenar** al decisor de BAXY, un asistente tipo Jarvis que vive en un PC con Windows.
El decisor lee la conversación y decide qué hacer con el último mensaje de la persona. Tus ejemplos le enseñan a
decidir bien; por eso tienen que ser variados, naturales y **correctos según las reglas del dueño**.

## Sala limpia (obligatorio)

Lee **sólo**: `REGLAS_ORO.md`, `CATALOGO.md` y `CATALOGO_LLANO.json` (misma carpeta). No abras, busques ni listes
ningún otro fichero (ni el repositorio de BAXY, ni otras carpetas, ni salidas de otros escritores). No uses Grep ni
Glob. No copies frases de datasets públicos que recuerdes: escribe frases nuevas. Tu única escritura son tus ficheros.

## Qué escribes

Conversaciones de 1 a 6 mensajes de la persona (alrededor de un tercio de un solo mensaje, el resto de 2 a 6). Por
cada mensaje de la persona, **una** decisión correcta (la mejor según las reglas), con este formato:

```json
{"id": "T<escritor>-<n>", "speaker": "chileno", "turns": [
  {"user": "...", "target": {"request": "...", "decision": "action", "operations": ["weather.current"], "question": ""}, "assistant": "..."},
  {"user": "...", "target": {...}, "assistant": "..."}
]}
```

- `request`: el último mensaje reescrito como **pedido completo y autónomo**, con lo que aporta la conversación, en el
  idioma de la persona («¿y en Rosario?» tras el clima de Córdoba → «¿Qué tiempo hace en Rosario?»). Si ya es completo,
  igual o casi igual. Si es charla, la charla tal cual.
- `decision`: `action` (operaciones del catálogo), `clarify` (una pregunta corta porque falta algo que cambia el
  resultado), `talk` (contestar hablando: conocimiento estable, charla, escribir contenido, cálculos, conversiones,
  consejos, hablar de sí mismo, agradecer), `limit` (decir en llano que no lo hace).
- `operations`: nombres **exactos** de `CATALOGO.md`, sólo con `action` (una por cada cosa pedida, en orden); vacía
  en otro caso. Nunca pongas pasos internos («Paso interno» en `CATALOGO_LLANO.json`).
- `question`: sólo con `clarify`, una pregunta corta y concreta en el idioma de la persona; si no, `""`.
- `assistant`: lo que BAXY respondería (breve, tuteo, idioma de la persona), coherente con la decisión; si es
  contenido (código, receta, lista, conversión, traducción), inclúyelo conciso porque el siguiente mensaje puede
  reusarlo. Los datos observados (grados, marcadores) invéntalos plausibles.

## Reglas del dueño (de `REGLAS_ORO.md`, resumen)

Lo público se busca (`web.search`; el clima `weather.current`; titulares `web.news.headlines`); lo estable se contesta
(`talk`); pedir «busca/investiga» algo público es `web.search`. Lo propio no se busca en la web. Lo completo no se
repregunta. Cantidad relativa sin número → `clarify` (cuánto). Lo que un PC no hace (luces y aparatos de la casa,
llamadas telefónicas y SMS, pedir comida, taxis, compras, reservas, apps del móvil, relojes y pulseras) → `limit`; lo
que el catálogo sí hace (mensajes por una app del PC, Netflix o Disney+, abrir una app instalada) se hace. Dato
personal que falta («donde vive mi hermana») → `clarify`. Erratas, dictado y spanglish se entienden. Un mensaje que
depende de lo anterior se decide con la conversación.

## Lo que más cuesta al decisor (cúbrelo mucho, con frases tuyas)

1. **Operaciones hermanas**: pausar/seguir/siguiente (`media.control`) frente a adelantar segundos
   (`media.seek.relative`) o reproducir otra cosa; volumen a un nivel (`audio.volume`) frente a subir/bajar una cantidad
   (`audio.volume.adjust`) frente a silenciar (`audio.mute`); brillo a un nivel frente a subir/bajar; abrir una app
   (`app.open`) frente a lanzar un juego (`game.launch`) o reproducir música en ella; abrir una carpeta conocida
   (`filesystem.folder.open`) frente a listar lo que hay (`filesystem.known.list`) frente a buscar un archivo; alarma o
   recordatorio que suena (`notification.schedule`) frente a tarea pendiente (`task.create`) frente a nota
   (`note.create`); captura de pantalla frente a la de una ventana; hora de otro país (`system.time`) frente al clima.
2. **Comentarios, quejas, reacciones y tranquilizaciones** después de que BAXY hizo algo o falló («tranquilo», «qué
   mal», «¿por qué fallas?», «me gusta cómo quedó») → `talk`, aunque la conversación anterior hablara de una acción.
   Sólo un pedido nuevo o la respuesta a una pregunta de BAXY lleva a `action`.
3. **Seguimientos**: elipsis, pronombres, correcciones («no, mejor…»), respuestas cortas a una pregunta de BAXY («10»,
   «sí dale», «en YouTube»), reusar lo que BAXY respondió («ahora en javascript», «¿y en tazas?», «20 minutos antes»).
4. **Límites** claros y límites falsos: que no niegue lo que el catálogo sí hace.
5. **Preguntas de más**: si el pedido está completo, `action`; no preguntes por gusto.

## Cantidad y reparto

El encargo te dirá cuántos ejemplos y qué hablantes. Escribe **por partes pequeñas**: un fichero por cada 10
conversaciones (`<nombre>-pNN.jsonl`, una conversación por línea), en la carpeta que te indique el encargo; nunca todo
de una vez. Al terminar valida que cada línea es JSON válido, que cada `operations` existe en `CATALOGO.md` y no es un
paso interno, y que `decision` y `operations` son coherentes. Responde con 3 líneas: conversaciones, mensajes y reparto
de decisiones.
