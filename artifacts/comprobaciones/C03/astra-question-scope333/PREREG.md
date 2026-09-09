# 333 — alcance de una pregunta al final de una respuesta

Producto331: 103 genera un saludo útil en HTTP23/27 y lo pierde en
`__main__.py:6457`. La guarda considera toda respuesta terminada en «?» como
pregunta única si no tiene punto o exclamación seguido de espacio. El signo
inicial «¿» sí delimita una pregunta aunque haya contenido antes sin punto.
La misma aproximación está duplicada en llm.py.

Hipótesis: reconocer las preguntas delimitadas por sus dos signos conservará
el contenido anterior sin depender de nombres, saludos o literales del corpus.
Sustituir la aproximación duplicada por una función estructural compartida;
conservar el comportamiento sin signo de apertura y los demás validadores.
Esto no acredita verdad o pertinencia semántica de cualquier prefijo.

Fuente primaria consultada2026-09-08: [RAE, puntuación y mayúsculas](https://www.rae.es/ortografía-básica/uso-de-las-mayúsculas/la-mayúscula-condicionada-por-la-puntuación)
explica que una pregunta puede comenzar dentro de un enunciado. No se introduce
dependencia lingüística ni nueva generación del modelo. Herencia local: el guard
de reformulación en llm.py:2334 ya examina preguntas por separado por esta causa.

Controles: respuesta con pregunta final, preguntas puras múltiples, preguntas
sin signo inicial, emojis que no constituyen respuesta, explicación descartada
y saludo recuperado a través de _prepare_turn_result. Pruebas dueñas, Fast y
repetición del producto sobre los mismos seis mensajes. No Full durante reparación.
Sólo aceptar si mejora sin regresiones observadas;330 sigue sin promoción integrada
tras331(1/6 frente a2/6 en327). Continuidad privada sigue pendiente, xhigh.
