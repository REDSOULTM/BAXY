# Encargo del cuarto ajuste: el mensaje suelto dicho como habla la gente

Lee primero `ENTRENAMIENTO.md` (misma carpeta): formato, sala limpia, reglas y validación son los mismos. Este encargo
cambia **sólo qué escribes**: mensajes que llegan solos (la conversación empieza con ellos o cambia de tema) y que hoy
se deciden mal porque no suenan a una orden limpia. Los ejemplos de abajo muestran la **forma**; no los copies:
escribe frases tuyas.

## Escritor de autocorrecciones y muletillas

- La persona se corrige dentro del mismo mensaje («…a las 5, no, mejor a las 6», «pon la de Queen, digo, la de
  ABBA», «oops I meant…», «bueno no, mejor…») → se decide sobre **lo corregido**, en `request` sólo lo corregido. Si lo
  corregido no lo hace el PC → `limit`; si lo hace → su operación.
- Muletillas, repeticiones y dictado roto («eeem», «este…», «o sea», palabras dobladas, frases cortadas por la mitad
  que igual se entienden) → se entienden; `clarify` sólo si de verdad falta lo que cambia el resultado.
- Contraste (una de cada cinco): la corrección deja el pedido incompleto («ponme una alarma a las… no, espera») →
  `clarify`.

## Escritor de mensajes largos

- Mensajes largos con contexto personal que igual piden **una** cosa a BAXY («hoy tengo una reunión a las 10 y estoy
  cansado, así que ponme una alarma…») → esa cosa.
- Preguntas de conocimiento largas y técnicas («en modelado 3D, explícame…», «¿qué diferencia hay entre…?») → `talk`
  (o `web.search` si es público y cambiante).
- Contraste real (una de cada cuatro): conversación ajena que el micrófono captó — dos personas hablando entre ellas,
  con nombres de otros, sin dirigirse a BAXY ni pedirle nada («y entonces le dije a la Cata que no fuera, ¿tú qué
  crees?») → `clarify` con una pregunta como «No encuentro un pedido para mí en eso; ¿necesitas algo?».

## Escritor de servicios ajenos

- Pedidos a apps y servicios que no están en el catálogo, nombrados por su marca o por lo que hacen (apps de ejercicio,
  transporte, delivery, bancos, domótica, apps del celular: «regístrame 20 flexiones en la app de ejercicio», «pídeme un
  auto a casa», «transfiere 5 lucas a mi hermano») → `limit`, **nunca** `web.search` ni otra operación que se le
  parezca.
- Contraste (una de cada cuatro): una pregunta de información pública sobre esa marca o servicio («¿cuánto cuesta el
  plan premium de esa app?») → `web.search`; abrir una app del PC que sí está instalada → `app.open`.

## Cantidad

100 conversaciones por escritor, 10 partes de 10 (`<nombre>-pNN.jsonl`). La mitad de las conversaciones son de **un
solo mensaje**; el resto, de 2 a 4, empieza por el mensaje suelto y sigue con un seguimiento natural. Hablantes
variados (chileno, rioplatense, mexicano, colombiano, España, inglés, spanglish), registros variados.
