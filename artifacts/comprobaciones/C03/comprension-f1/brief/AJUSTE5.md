# Encargo del quinto ajuste: seguimientos que se refieren a lo que BAXY acaba de hacer o decir

Lee primero `ENTRENAMIENTO.md` (misma carpeta): formato, sala limpia, reglas y validación son los mismos. Este encargo
cambia **sólo qué escribes**: conversaciones de 3 a 6 mensajes donde el último mensaje de la persona sólo se entiende
con lo anterior. Los ejemplos de abajo muestran la **forma**; no los copies: escribe frases tuyas.

## Escritor de remates y precisiones

BAXY acaba de hacer algo (subió el brillo, abrió una app, puso una canción, creó un recordatorio) y la persona agrega un
fragmento que sólo precisa o remata lo ya hecho: el objeto nombrado de nuevo, un «eso», un «así», un «ese mismo», un
lugar o una cantidad que coincide con lo hecho → `talk` que confirma lo hecho en una frase («Sí, ya quedó en 80»),
nunca `clarify` ni repetir la acción. Contraste (una de cada tres): el fragmento cambia algo (otra cantidad, otro
objeto, otro lugar) → la acción con el cambio.

## Escritor de preguntas sobre la conversación misma

La persona pregunta por el estado de la charla o de lo último: si BAXY sigue ahí, si escuchó, si lo último se hizo o
no, que diga si algo no pasó, qué fue lo último que hizo, por qué respondió así → `talk` que contesta con lo que la
conversación muestra (sin inventar nada que no esté en ella), nunca `clarify`. Contraste (una de cada cuatro): la
pregunta pide un dato nuevo del PC («¿y sigue abierto?» cuando hay que mirarlo) → la operación que lo lee.

## Escritor de encargos sobre el tema ya hablado

Después de hablar de algo concreto (una película, un equipo, una serie, un lugar, un producto), la persona pide
averiguar, buscar, fijarse o investigar algo de **ese tema** sin nombrarlo («fijate qué dijeron», «averiguá cuándo
sale», «busca cuánto cuesta») → `web.search` con `request` que nombra el tema completo, nunca `clarify` preguntando
de qué. Contraste (una de cada cinco): en la conversación hubo dos temas y no se sabe cuál → `clarify` corto.

## Cantidad

100 conversaciones por escritor, 10 partes de 10 (`<nombre>-pNN.jsonl`), de 3 a 6 mensajes; todos los mensajes llevan
su decisión correcta, no sólo el último. Hablantes variados (chileno, rioplatense, mexicano, colombiano, España,
inglés, spanglish), registros variados.
