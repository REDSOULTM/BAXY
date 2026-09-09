# 330 — finalidad de recuerdo, no ejecución diferida

329 aisló owner99 con un único override de diagnóstico: devolver False desde
_has_unsupported_deferred_effect para el literal original. No fue fuente adoptada,
ni se cambió modelo, muestreo, prompts o permisos. Resultado: de silencio327 a
«¡Claro que sí! Me encantaría recordar tu nombre. ¿Puedes darme tu nombre ahora? 😎».
La respuesta no afirma un guardado. Los selectores seguían proponiendo ninguna
operación y su prosa genérica negativa no fue la respuesta final. La redacción
conversacional pudo contestar sin la orden espuria de rechazar.

330 sustituye el override por una delimitación de alcance en el detector existente:
la subordinada de futura pregunta gobernada por recordar/remember no programa la
escritura. Se conserva cualquier mañana/tomorrow previo y no se cruza a una acción
independiente coordinada con y/and. No se añade el literal del dueño a producción.
No se corrigen aquí la persistencia ni la continuidad del valor: siguen pendientes.

Baseline: seis controles ES/EN/mixtos fallan por falsa programación. Seis órdenes
realmente diferidas se conservan. Un séptimo control inicial de «recuérdame» tenía
expectativa errónea: este detector ya delega recordatorios al programador, cuyo
contrato valida el disparador. Se separa ese control conservando su comportamiento
previo. Baseline original7fail6pass1,43s y focal inicial1fail12pass0,75s se conservan.

Contraste externo consultado2026-09-08: [parámetros requeridos de Dialogflow CX](https://docs.cloud.google.com/dialogflow/cx/docs/concept/parameter)
distinguen recoger datos faltantes de ejecutar la tarea; [formularios de Rasa OSS](https://legacy-docs-oss.rasa.com/docs/rasa/forms/)
separan extracción, interrupciones y cancelación del formulario. Son referencias
de mecanismo, no dependencias adoptadas ni mediciones de BAXY. El flujo privado
existente sigue siendo la base para el siguiente tramo de continuidad. Mantener
razonamiento alto para esa decisión transversal; validación rutinaria acotada.

Aceptación de esta tanda: suites dueñas de alcance/compuestos/turnos/composición,
Fast y los mismos seis turnos completos sin override. Nunca acreditar persistencia
porque el modelo ofreció recibir el nombre. C03 conserva todos sus requisitos.

Revisión posterior al primer verde2681pass/Fast: se detectó que la delimitación
cruzaba «and then» y aceptaba «remember to open». Controles comparables con la
función anterior dieron True→False en cuatro órdenes realmente diferidas. No se
ejecutó producto con esa variante. Se impide absorber la acción infinitiva, la
coordinación con luego/then y una nueva cláusula tras coma. Focal final18pass0skip
0,92s. Se repiten owners/Fast por esta preocupación nueva, no por rutina.
