# C03 — tramo55: localizar la excepción del plan

Estado: diagnóstico localizado; reparación del consumidor en preparación. files54-literals
dio2/5 útiles; t1/t4 usan result_unverified y t3 pierde respuesta. En los tres,
shell-trace turn.error sólo conserva invalid. La traza exige minúsculas, pero
MainWindowViewModel enviaba ExceptionType.Method con mayúsculas.

Se normaliza únicamente esa etiqueta estable con ToLowerInvariant antes del
sanitizador existente. No se amplían caracteres admitidos ni se registra el
mensaje de excepción. El build App Release precede al mismo panel de cinco
controles técnicos con perfil nuevo, astra-files55-trace. Sesión95521: recoger
RESULT.json y shell-trace antes de editar fuente o inferir la causa.

Traza55 terminó82,12s,GPU3497,56MiB,RAM4539,06MiB,registro intacto,95521exit0.
Build App11,28s,0avisos/errores. La etiqueta ahora conserva
invalidoperationexception.throwjsonelementwrongtypeexception. Esta corrida dio
1/5 útil: t2 también llegó a error, variación conservada sin presentarla como
regresión causada por lowercasing. No declarar estable el éxito de lectura por
una sola corrida. paired.json conserva los cinco finales.

Primera causa localizada: MissionNarration ya conserva reason como JsonObject,
pero UserMessagePolicy.CollectStructuredLiterals llama value.GetString sin
comprobar ValueKind cuando encuentra reason. El fallo ocurre antes de componer
el error; la captura anterior sólo veía el reemplazo result_unverified.
La prueba de herencia MissionFailureKeepsTheStructuredReasonForTheComposer
comprobaba el JSON, pero no lo entregaba a UserMessagePolicy.Create.
Se amplía esa prueba y dos contrastes con invalid_utf8/step_data_missing y título
anidado para conservar datos del usuario sin exigir el código interno como literal.

Prueba roja:2fail/1pass/0skips/53ms,69682exit1, log c03-files55-reason-red.log.
La pila confirma CollectStructuredLiterals:2545 al recoger los literales requeridos
(Create por sí solo no reproduce la excepción). Candidata: comprobar String antes
de GetString y recorrer únicamente reason cuando es objeto, conservando títulos
y razones textuales anidados. El objeto completo sigue llegando al compositor.
154 tests de integración pass/0skips/13s,3615exit0, c03-files55-reason-owners.log.

Contraste primario consultado2026-09-07: [GetString](https://learn.microsoft.com/en-us/dotnet/api/system.text.json.jsonelement.getstring?view=net-10.0)
documenta InvalidOperationException para tipos distintos de String/Null;
[ValueKind](https://learn.microsoft.com/en-us/dotnet/api/system.text.json.jsonelement.valuekind?view=net-10.0)
expone el tipo. La reproducción local .NET10 confirma ese contrato. No hace falta
convertir el objeto a prosa/JSON plano ni modificar el modelo para este bloqueo.

astra-files55-reason terminó80,09s,GPU3497,56MiB,RAM4893,38MiB,registro intacto,
77475exit0.1/5 útil (hora). La excepción se corrige y los hechos reales llegan
a composición, pero no mejora el panel: t2 tiene una entrada verificada con ID
y aun así termina step_data_missing; los campos deterministas de identidad
omiten read.text tanto en Python como en App. No volver a pedir ese ID al modelo
cuando ya está en un único resultado verificado del productor declarado.

t3 conserva error=invalid_utf8 en situation.reason, pero la proyección Python
conserva sólo outcome=failed: lee cause e ignora error de un resultado tipado.
El primer borrador nombra correctamente UTF8 (también visible en el nombre de
fixture), por lo que no demuestra conservación causal: missing_failure lo veta.
El reintento inventa que el sandbox es readonly. Progreso t3 también infiere fallo
por el nombre antes de observación y no debe contarse fiel. Siguientes owners:
identidad determinista, proyección error/cause y polaridad verbal; no otro modelo.

Fast55 verde,35783exit0,Release15,53s,0avisos/errores,log c03-files55-fast.log.
Se conserva el arreglo de tipo y la traza; los finales55 siguen1/5, C03 no cierra.
No Full. Diagnóstico y arreglos no acreditan UI/audio/reserva100.

54 sigue adoptado: Fast verde, pruebas dueñas verdes, reserva/UI/voz/Full abiertos.
