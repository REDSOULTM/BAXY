# C03 — tramo 52: negación de fallos sin inversión de resultado

Estado: reparación adoptada, Fast verde. Sin cambios Python/modelo/catálogo/proveedor.

## Causa demostrada

En compound-shell48, clock49 y progress51, el proveedor devuelve hora/CPU con
failures=[] y el modelo compone una respuesta fiel. UserMessagePolicy rechaza
«No hay fallos registrados/reportados» como reversed_result por Contains("fallo").
El fallo está después de la inferencia; no se ajustan instrucciones ni muestreo.
La comparación pertinente es conservar el detector de fallos existentes frente
a interpretar la negación local, demostrada por los mismos datos y texto.

La candidata conserva el ownership de LooksLikeFailure y los hechos tipados de
polarity como autoridad. Antes de buscar fallo/failed como palabras completas,
retira sólo la afirmación negada: ausencia de fallos o de detección/registro,
negación verbal y cuantificación negativa. No retira la frase entera ni los
marcadores independientes de fracaso. La cláusula «pero no pude leer la CPU»
sigue contando como fallo; lo mismo que un segundo check failed tras but.
No se añade otra capa de validación ni se prescribe la respuesta del modelo.

## Pruebas

C03FactPreservationTests añade16 controles de polaridad en ambas direcciones:
seis ausencias de fallos compatibles con lectura correcta, siete fallos afirmados
que siguen contradiciendo éxito y tres negaciones que no pueden reemplazar una
avería real. Los controles pasan por ModelResponseRejectionReason, no una copia
de la implementación privada.

Reproducción sin arreglo: **9 fail,40 pass,0 skips**,648 ms, sesión14636 exit0
del wrapper; el proceso dotnet reportó prueba fallida. Log c03-polarity52-red.log.
Tras corregir, C03FactPreservationTests + Goal06VisibleVoiceTests +
NaturalSystemStatusRequestParserTests: **173 pass,0 skips,8 s**, sesión86876
exit0, log c03-polarity52-owners.log. Release compilado para la medición.

Producto astra-polarity52 en ejecución, sesión98797: mismos siete turnos de51,
registrados antes de ejecutar con huellas en PREREG. Se evalúa el turno entero,
incluyendo el progreso ya corregido. Sin consumo de reserva humana ni afirmación
de UI/voz. No Fast52/Full ni publicación hasta esta anotación. C03 EN_CURSO.

Producto terminado, sesión98797 exit0: **7/7 turnos completos útiles** frente
a6/7 de51,4/7 de49 y2/7 de48. Progreso fiel, pares completos ES/EN/mezcla y
hora/CPU publicado con «No hay fallos reportados». Valores cotejados con
completedStepsInOrder: hora00:52,CPU13,125% en t1 y14,58333%→14,58% en t6,
16 procesadores lógicos, modelo observado, failures=[]. Audio100/no silenciado.
63,09 s,GPU3497,56 MiB,RAM4677,24 MiB,registro intacto. Sin UI/voz ni reserva.

Fast completado, sesión84205 exit0, Release16,10s,0avisos/errores; log
c03-polarity52-fast.log. TRAMO52_PINS y PRUEBAS_POLARIDAD52 fijan fuente y siete
pares literales. CHECKPOINT/HANDOFF condensados, versiones anteriores guardadas
íntegras en archivos HISTORICO. No Full durante reparación. Siguiente: aclaración equivocada
ante ruta literal de archivo47 y ruta de errores con causa/prosa, luego cierre
integral; no repetir el panel7 por azar.

Precisión de alcance para53, inspección sin editar: Core.Program:97 configura
LocalFilesystemProvider con dataRoot/filesystem-sandbox; ReadText:84 resuelve
resourceId en su propio diccionario (ResolveHandle:345). Los IDs de
filesystem.known.search no deben suponerse compatibles con este consumidor.
La dependencia list ya aparece en planner._dependency_operations:1144, pero
falta read.text en _required_predecessors:974, usado por action_grounding para
pasar una identidad pendiente al plan. No ampliar capacidad sólo para pasar
un fixture: resolver dentro del alcance real y narrar el límite útil fuera.
