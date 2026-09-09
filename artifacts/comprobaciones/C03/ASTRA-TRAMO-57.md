# C03 — tramo57: causa de un resultado de operación fallida

Estado: candidata en comparación. files55-reason t3 demuestra el dato real:
situation.reason.error=invalid_utf8, pero payload.reason={outcome:failed}.
La proyección recursiva heredada de causas sólo leía cause, que es la forma
de eventos de misión; un resultado de operación usa error. Un borrador acertado
por el nombre del archivo no acredita que el hecho haya llegado al modelo.

Se reutiliza _cause_in_prose con error sólo para kind=operation/polarity=failure
sin cause explícita. Error debe ser string. No sobrescribe una causa declarada,
no cambia la polaridad de un éxito y no inventa texto visible. Se conserva el
objeto original y la proyección de reason ya existente. Los tests anteriores
de preservación de reason cubrían eventos con cause, no resultados con error.

Regresión previa:9fail/1pass/149deselected/0skips/0,70s, tres errores reales
(invalid_utf8,file_too_large,invalid_resource_id) en ES/EN/mixed. Contrastes:
éxito, evento ajeno, error mal formado y causa explícita. Tras corregir,
188pytestpass/0skips/2,00s, compose_contract/c03_request_preservation/goal06_voice,
log c03-files57-cause-python.log. No se cambia sampler, modelo ni validación verbal.

astra-files57-cause terminó77,09s,GPU3497,56MiB,RAM5316,67MiB,registro intacto,
80446exit0.2/5 útiles. t2 vuelve a publicar la lectura sin reconstruir ID.
t3 ahora recibe reason.cause=invalid utf8 y produce un borrador fiel aceptado por
Python: «The file contains invalid UTF-8 sequences, which cannot be properly read
or processed.» C# lo veta reversed_result por no reconocer cannot. El primer
borrador breve «The file contains invalid UTF-8 encoding.» aún se veta en Python
como missing_failure; los reintentos ya no inventan readonly en esta corrida.
La causa sí se conserva, pero todavía no sale prosa final. PREREG amplía huellas
a PlannerExecutionSupport,MissionPlanProposal y provider/handler filesystem.

Fast57 falló sólo whitespace en tres inicializadores del nuevo test de identidad,
5323exit1. Se corrigió el formato; compuerta integrada pendiente, no declarar verde.
No Full/UI/voz/reserva humana. Después, medir dónde el veto missing_failure
rechaza hechos correctos antes de tratarlo: fuente57 sólo conserva la causa.
