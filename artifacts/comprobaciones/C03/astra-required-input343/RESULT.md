# 343 — dato requerido, controles verdes; nativo pendiente

Baseline3fail5pass0skip0,59s: dos preguntas operativas válidas devuelven silencio;
una afirmación falsa de guardado pasa compose_visible_defect. La misma regla de
conocimiento causa ambos errores: veta preguntas e ignora que falta el dato.

_required_compose_input reconoce missingValue no vacío sólo con kindclarification
y polaritypending. El mismo dato llega a la proyección, instrucción por rol y
validación. No hay lista de nombres, frases históricas ni causas como excepción.
La pregunta de conocimiento sin dato operativo sigue exigiendo respuesta; el
guardado afirmado sin completar la aclaración ahora falla.

Dueñas:1031pass0fail0skip6,14s con pytest tests/test_turn_policy.py
tests/test_compose_contract.py -q -x --tb=short. Fast verde:build2,09s,
0errores/advertencias. Producto343 en curso: dos controles sintéticos declarados,
pregunta inglesa con dato requerido y cancelación; modelo registrado sin override.
Producto343 terminó1/2: cancelación publicada; pregunta inglesa termina en silencio
model_response_rejected. Python ya acepta el retry «What’s your name again?», pero
ModelMessageComposer.AcceptPublishedConversation aplica luego la política de
conversación sin dato pendiente y la vuelve a rechazar por knowledge_not_answered.
No atribuir el silencio a truncamiento ni afirmar que Python basta para la App.

Baseline de esa frontera:4fail2pass0skip589ms; tres preguntas válidas bloqueadas y
una afirmación de guardado incorrectamente aceptada. Source343b (en el mismo
tramo) pasa HasRequiredInput desde el draft tipado a la política de publicación;
conserva las otras comprobaciones y el requisito de pregunta mientras falta el dato.
No permite repreguntar ante conocimiento sin dato requerido. Dueñas de la App:
217pass0fail0skip16s. Fast343b verde:build19,43s0errores/advertencias. Los mismos
dos controles nativos343b terminaron2/2útiles,0silencios. Se publica
«What’s your name again?» y la cancelación. Sin otro modelo/prompt en ese paso.
RESULT/PINS en astra-memory-product343b. No es UI física ni aceptación fresca.

No Full durante reparación;340/341/342 se ejecutaron ANTES de editar esta fuente.
