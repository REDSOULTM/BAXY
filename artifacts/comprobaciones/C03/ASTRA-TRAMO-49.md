# C03 — tramo 49: conservar las consultas coordinadas

Estado: lector adoptado. C03 sigue EN_CURSO; no cierre, commit ni publicación.

La confirmación del dueño «Son turnos validos» ya está registrada en
ADMISIBILIDAD_DUENO_2026-09-06.md para los tres textos preguntados. No se extiende
al resto del pool y no hay una pregunta de procedencia pendiente.

## Causa y reparación

El panel compound-shell48 perdió la hora en tres peticiones con audio. La primera
transformación equivocada era el lector literal: el separador conservaba ambas
peticiones en una cláusula y el lector estricto encontraba sólo audio.status.
Se reutiliza la normalización existente de coordinaciones de estado y su regla
de conservar todas las cláusulas antes de autorizar el conjunto.

- Los objetos nominales admiten hora/fecha, time/date, volumen y «estado del audio».
  El patrón sigue anclado a la cláusula completa; no separa títulos ni calificadores
  como «time needed to download it» o «fecha de la reunión».
- Una pregunta de estado coordinada conserva su propio encabezamiento interrogativo.
- La gramática existente de reloj admite el pedido directo de fecha/hora con
  dime, muestra, show y tell me. Los calificadores ajenos al reloj siguen excluidos.
- El mapeo nominal usado por la composición reutiliza _nominal_datetime_query.

No hay otro clasificador hora/audio ni plan fijo. Sin cambios de prompt, modelo,
sampler, historial, proveedor o catálogo. La referencia de herencia y diagnóstico
es ASTRA-TRAMO-48.md; la reparación opera antes de selección/inferencia.

Primer intento retirado: añadir detección de reloj al lector estricto reconocía
los pares, pero dejaba ejecutar sólo audio si faltaba system.time en el catálogo.
Pasó 2536 pruebas existentes en 43,68 s; ese verde no acreditaba conservación.
No se promovió ni se midió en producto. La solución por cláusulas conserva orden
y se abstiene si falta cualquiera de las operaciones requeridas.

## Validación

Siete suites: test_effect_intent, test_turn_policy, test_compound_missions,
test_planner, test_request_reading, test_system_status_scope_grounding y
test_compose_contract, con el Python registrado y pytest -q.

La primera ejecución de la solución por cláusulas: 2956 pass, 115 subtests,
1 fallo nuevo: «Show the date and the volume». La lectura simple «Show the date»
tampoco existía. Corregida la gramática del lector de reloj, el test fallido pasa
y la repetición completa da **2957 pass, 115 subtests, 0 skips, 45,09 s**, exit 0.
Logs temporales c03-clock49-owners-final.log, c03-clock49-repair.log y
c03-clock49-owners-corrected.log. No se suprimió ni relajó el control.

Producto completado: sesión99750 exit 0, scratchpad/c03-clock49.py. Copia literal de
los mismos siete inputs y CASES de compound-shell48; PREREG conserva huellas.
Sólo la fuente del lector cambia. Los defectos conocidos de progreso inventado
y rechazo de «No hay fallos registrados» se mantienen para aislar el cambio.
No contar una respuesta final fiel como turno válido si el progreso es falso.
Sin reserva humana, UI ni audio físico; no Full durante esta reparación.

Resultado: 70,09 s, GPU3497,56 MiB, RAM4635,18 MiB, registro intacto. Los tres
pares ES/EN/mezcla ya ejecutan hora/audio y publican sus hechos. Seis de siete
respuestas finales son fieles; hora/CPU sigue sin publicar por reversed_result.
Al contar progreso, sólo **4/7 turnos completos cumplen**: t3, t4, t5 y t7.
t1 inventa medidas y t2 afirma que la hora no está disponible antes de leerla.
t4 declara desconocimiento durante el trabajo y después responde con los hechos.
PRUEBAS_RELOJ_COORDINADO49.md conserva las siete entradas/respuestas/etiquetas
literales y su adjudicación; paired.json conserva las observaciones originales.

Fast verde, build Release 16,93 s, 0 avisos y errores, sesión49897 exit 0,
log c03-clock49-fast.log. TRAMO49_PINS.json fija la fuente adoptada. No Full.
Todas las sesiones49 están cerradas. Continúa50 con captura nativa del progreso;
los defectos de composición/polaridad permanecen abiertos, no se aplazan.
