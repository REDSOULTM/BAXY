# 343 — aclaración operativa dentro de una petición con pregunta

Diagnóstico descubierto en338: «What can you do? Remember my name.» con situación
privada kindclarification/polaritypending/missingValue recibe knowledge_question
al preguntar el dato obligatorio. El guard sólo mira la forma de la petición y
desconoce el dato pendiente tipado de la operación. 338 arregló otra causa (can)
y dejó ésta expresamente pendiente; no se declara resuelta por la prueba de payload.

Hipótesis: una pregunta de conocimiento no debe convertirse en repregunta vacía,
pero una aclaración operativa con dato faltante explícito sí debe preguntar ese
dato. Heredar el campo missingValue emitido por PrivateOperationNarration336 y
el guard de conocimiento actual; no usar nombres/literales o causas de memoria
como excepciones. Contrastar los tipos/polaridad/valor ausente, respuestas que
afirman guardado y la pregunta de conocimiento sin parámetro pendiente.

Baseline de tests durante producto341, sin modificar fuente/runtime de esa corrida.
No editar fuente343 hasta terminar341/342. La variante inglesa es control sintético
de generalización declarado, no procedencia humana ni aceptación fresca.
