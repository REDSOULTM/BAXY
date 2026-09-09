# C03 — negación de resultados con sujeto omitido o impersonal — 86

84 conserva la búsqueda vacía pero veta tres borradores negativos verdaderos;
la respuesta desaparece y el siguiente porqué inventa cifrado. El fallo de
polaridad está demostrado tanto en Python como en C#: red Python2fail/21deselected,
C#3fail/9pass/0skips/1s. El contraste Python de fallo independiente inicialmente
usó petición inglesa y respuesta española; corregido el idioma del control.

Herencia74/52/58: ambos guardas ya distinguen negación de fallos de fallos
independientes y reconocen modales negativos; C# ya admitía «no se pudo».
Se adapta el mismo reconocimiento a no encontré/no se encontró/encontraron,
pudo/pudieron, después de quitar sólo la negación de fallos. La variante singular
de esa negación conserva «No se encontró ningún fallo». Se retira la comprobación
duplicada C# de «no se pudo». No se añade clasificador, prompt ni respuesta fija.

Contraste actual consultado2026-09-07: [Universal Dependencies para español](https://universaldependencies.org/es/)
documenta la negación con no, sujetos omitidos y pasivas con se. Eso fundamenta
el contraste gramatical, no demuestra el código ni convierte toda ausencia en
avería. La prueba local juzga polaridad contra hechos tipados; la fidelidad de
la causa se adjudica en el producto, no mediante este reconocimiento léxico.

Después: dos pruebas acotadas pass/21deselected/0,42s. Cuatro suites Python:
1151pass/0skips/6,42s. C03FactPreservation+PlannerAppBoundary+Goal06VisibleVoice:
181pass/0skips/15s. Logs TEMP/c03-negation86-{pytest,dotnet}.log.
Fast1604exit0, Release15,73s,0 avisos/errores; log TEMP/c03-negation86-fast.log.
files86-negation iniciado. Mismos cuatro turnos84, Qwen3.5 override sin promoción.
C03 EN_CURSO; no Full ni aceptación UI/audio/reserva humana.
