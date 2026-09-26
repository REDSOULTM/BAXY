# Encargo del segundo ajuste: planes, reacciones en conversación y lo propio

Lee primero `ENTRENAMIENTO.md` (misma carpeta): formato, sala limpia, reglas y validación son los mismos. Este encargo
cambia **sólo qué escribes**. El primer ajuste falló en tres frentes; tus ejemplos los cubren con frases tuyas.

## Escritor de planes (varios efectos en un mensaje)

Pedidos con **dos o tres cosas que hacer** en un mismo mensaje, en el orden en que se dicen: `operations` lleva una
operación por cada cosa pedida («abre Spotify y pon algo de rock» → `app.open`, `media.play.query`; «baja el volumen
a 20, silencia el micro y pausa la música» → tres). Mezcla: dos acciones del mismo tipo con objetos distintos, una
acción seguida de una búsqueda, abrir algo y operar dentro, pedidos largos y dictados sin puntuación, spanglish.
Contraste (una de cada cuatro conversaciones): mensajes largos que sólo piden **una** cosa aunque nombren otras
(«pon la música que escuchaba ayer cuando estaba en la oficina» es una sola), y dos cosas donde una no la hace el PC
(esa conversación es un plan con lo que sí se hace si lo demás es independiente, o un límite si todo depende de lo
que no se hace; sigue `REGLAS_ORO.md`).

## Escritor de conversación y de lo propio

Conversaciones de 2 a 5 mensajes donde BAXY acaba de hacer, contestar o fallar algo y la persona:
- agradece, aprueba, comenta o se queja («gracias, así está bien», «me gusta cómo quedó», «qué mal, otra vez
  falló», «ya no importa») → `talk`, nunca `clarify` ni una acción;
- pide algo nuevo después del comentario → la acción de ese pedido nuevo.

Y mensajes sobre **lo propio de la persona**:
- dar un dato propio para recordar («guardá que mi cumpleaños es el 5 de mayo», «acuérdate de que soy alérgico al
  maní») → la operación de memoria del catálogo que guarda un dato (no una nota, no un recordatorio);
- preguntar un dato propio («¿cómo me llamo?», «¿cuál era mi color favorito?») → la operación que lo recuerda, o
  `talk` si está en la conversación;
- instrucciones permanentes («nunca cierres Spotify», «de ahora en adelante háblame de usted») → `talk` que lo
  reconoce, no una pregunta;
- aparatos de la casa y cosas que no son del PC con palabras que suenan a una operación («desactiva la alarma de la
  casa», «apaga el aire», «sube la persiana») → `limit`; y su contraste real («desactiva la alarma de las 7» →
  cancelar esa alarma del PC).

Nunca inventes datos que la persona no dio: si falta lo que cambia el resultado, `clarify`.

## Cantidad

100 conversaciones, 10 partes de 10 (`<nombre>-pNN.jsonl`), hablantes variados (chileno, rioplatense, mexicano,
colombiano, España, inglés, spanglish), registros variados.
