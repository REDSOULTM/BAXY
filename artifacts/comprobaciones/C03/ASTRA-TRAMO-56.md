# C03 — tramo56: copiar identidad verificada de archivo

Estado: candidata. Tramo55 ya demuestra que search encuentra c03-lectura.txt
y su resourceId, pero el consumidor devuelve step_data_missing. read.text
estaba en autoridad y predecesores, no en los campos deterministas que evitan
pedir al modelo una identidad que ya está verificada.

Herencia directa: _verified_dependency_identity_arguments y
PlanObservationProjector.TryGroundIdentityArguments ya hacen esto para notas,
ventanas y otros consumidores. Se añade resourceId a ambos registros existentes.
Sin nuevo extractor, prompt, proveedor o inferencia desde ruta. Una identidad
ausente, ambigua, no verificada o de known.search no autoriza la copia.

Regresión roja Python: dos subcasos válidos fallan; cuatro rechazos conservados.
Tras editar,1080pass/121subtests/0skips/7,02s, tests planner/turn_policy/compound_missions,
log c03-files56-id-python.log. Integración160pass/0skips/13s,66075exit0.
Producto astra-files56-identity terminó:79,08s,GPU3497,56MiB,RAM5041,58MiB,
registro intacto,84311exit0.2/5 útiles, t2 vuelve a leer/publicar el contenido.
La traza de t2 ya no contiene plan.ground para reconstruir su ID. t3 conserva
el fallo UTF8, todavía sin prosa final; t1/t4 no explican límites útiles.
Se conserva identidad56 para la comparación de causa57; Fast integrado pendiente.
No resolver la causa omitida del compositor en esta misma comparación: es el
siguiente cambio discriminable, error de resultado tipado frente a cause de evento.
No Full/UI/voz/reserva100. El control exterior homónimo sigue siendo obligatorio.
