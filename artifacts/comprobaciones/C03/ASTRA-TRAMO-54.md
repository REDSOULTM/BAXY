# C03 — tramo54: identificadores literales y códigos internos

Estado: reparación53/54 adoptada, C03 EN_CURSO. La lectura real del archivo en files53-boundary
produjo el texto correcto; Python descartó todos los borradores por internal_code
al confundir c03-lectura.txt con una operación. C# repetía el mismo veto.

Herencia pertinente: la excepción existente para hosts web ya separaba el span
de un nombre público de códigos añadidos alrededor. Se reutiliza ese diseño en
el mismo chequeo; un token completo proporcionado por la persona no es metadata
filtrada. Se excluye sólo de las dos expresiones de forma snake/dotted, sin cambiar
otros vetos ni conservación de hechos. Comparación exacta de tokens completos,
ignorando mayúsculas; un substring de prefijo-nombre.txt no autoriza nombre.txt.
No se introduce una lista de extensiones ni respuestas fijas.

Regresión Python roja antes:1fail/17deselected. Tres nombres con guión, subrayado
y varios puntos; códigos ajenos junto al nombre siguen rechazados. Se corrigió
un fixture de contraste notas.2026.md, que el patrón antiguo ya permitía y no
servía para demostrar esta regresión, por notas.edicion.md. Tres suites Python
178pass/0skips/2,23s, log c03-files54-literals-python-fixed.log.
Dueños .NET inicialmente151pass/1fail: un segundo chequeo snake en la misma
función omitía la excepción y seguía rechazando resumen_final.txt. Se retiró ese
chequeo duplicado; ContainsInternalCode conserva la autoridad única del veto.
C03FactPreservationTests+Goal06VisibleVoiceTests+PlannerAppBoundaryTests+
MindPlanSessionTests:152pass/0skips/12s, sesión61427exit0.
Comparación astra-files54-literals terminó:74,09s,GPU3497,56MiB,RAM5322,07MiB,
registro intacto, sesión83342exit0. **2/5 turnos útiles**, frente a1/5 antes:
t2 publica el contenido real y t5 la hora. t1/t4 siguen con error demasiado
genérico y t3composition_failed. Se adopta la reparación de dependencia/literales,
sin declarar resueltos scope, causas ni C03. PRUEBAS_ARCHIVOS53_54.md conserva
entradas, finales y progreso de los cuatro paneles; TRAMO54_PINS.json fija huellas.

Fast verde completo: scripts/test_source_quality.ps1, sesión97644exit0,
build Release17,00s,0avisos/errores; log c03-files54-fast.log. Sin Baxy/llama-server.
No UI/audio/reserva humana/Full. Los errores por scope e invalidUTF8 siguen abiertos.
