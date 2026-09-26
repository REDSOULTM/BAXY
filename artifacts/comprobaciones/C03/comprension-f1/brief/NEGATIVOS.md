# Encargo adicional: negativos difíciles para el decisor de BAXY

Lee primero `ENTRENAMIENTO.md` (misma carpeta): formato, sala limpia, reglas y validación son los mismos. Este encargo
cambia **sólo qué escribes**.

El primer piloto aprendió a elegir bien entre operaciones hermanas, pero quedó con ganas de actuar: ante pedidos que
**se parecen** a una operación del catálogo y no lo son, actuó; ante pedidos a los que les falta algo, actuó en vez de
preguntar. Tus ejemplos enseñan justo la frontera (los «irrelevance» y «near-miss» de Hammer, ToolACE y xLAM).

## Qué escribes

Conversaciones de 1 a 4 mensajes de la persona (la mitad de un solo mensaje). En cada conversación, **al menos un
mensaje** es del tipo que te toca; los demás mensajes pueden ser de cualquier decisión (así el decisor ve también el
contraste en la misma conversación).

**Escritor de límites (`limit`)**: pedidos que un PC con este catálogo no hace pero **suenan** a una operación que sí
existe. Ejemplos de la frontera (escribe los tuyos, no estos): cancelar un viaje de una app de taxis (no es cancelar un
recordatorio); añadir algo a la lista de deseos de una tienda (no es reproducir ni crear una tarea); registrar
ejercicio o calorías en una app del móvil (no es una tarea ni una nota); conectar una cámara, un parlante inteligente o
la tele (no es una red wifi ni bluetooth del PC, salvo que sea claramente un dispositivo bluetooth del PC); apagar
«el aparato» o las luces de la casa (no es el brillo de la pantalla); quitar o sumar tiempo a un temporizador que el
catálogo no deja editar; votar o dar «me gusta» en un servicio; comprar, reservar, pagar, pedir comida, llamar por
teléfono, mandar un SMS, cosas del reloj o la pulsera. Mezcla también **límites falsos** (lo que sí se hace, con la
operación correcta) para que la frontera quede nítida: más o menos 3 límites por cada 1 falso.

**Escritor de preguntas (`clarify`)**: pedidos a los que les falta de verdad algo que cambia el resultado, según
`REGLAS_ORO.md`. Frases cortadas o incompletas («crear una nueva lista de…», «nueva dirección»); deícticos sin
referente en la conversación («¿dónde es este evento?», «bájale a esa», cuando nada anterior dice cuál); cantidad
relativa sin número (brillo, volumen); dato personal que falta («¿llueve donde vive mi tía?»); pedido que encaja en
dos operaciones distintas con resultados distintos y nada decide cuál. La `question` es **una** pregunta corta y
concreta. Mezcla también **preguntas de más** (el pedido está completo, así que se actúa sin preguntar): más o menos 3
preguntas por cada 1 pedido completo.

## Cantidad

100 conversaciones, en 10 partes de 10 (`<nombre>-pNN.jsonl`), variando hablantes (chileno, rioplatense, mexicano,
colombiano, España, inglés, spanglish), registros (dictado sin puntuación, erratas, formal) y temas. Nada de repetir la
misma plantilla cambiando una palabra.
