# Identidades del inventario: candidato789 sin adoptar

El candidato amplía el verificador existente para detectar títulos omitidos y repeticiones sin cantidad, y permite tanto entradas repetidas como agrupaciones con cardinalidad explícita. Las cantidades de un título se separan de las del inventario entero. La causa factual se envía por el reintento existente; no cambian el primer prompt, modelo, muestreo, presupuesto ni backend. Hereda el candidato787 preservado.

Se añadieron89 controles: nombres solapados, signos y acentos; cantidades1/2/4/7; listas, grupos, cantidades compartidas; preguntas sólo de conteo, omisiones y cantidades excesivas; referencias descriptivas y títulos vacíos. Los stubs con nombres Qwen/K2 prueban la misma lógica, no la inferencia de ambos modelos. La línea base de los primeros83 controles fue80fallos/3pass; seis controles adicionales se añadieron durante la revisión.

Validación final: **2990pass,1skip ambiental de STT y121subtests pass en17,35s**. `scripts/test_source_quality.ps1 -Mode Fast` terminó con **exit0**, Release18,24s, cero advertencias/errores. Los21 archivos de pruebas y los comandos exactos están en [VALIDATION.json](VALIDATION.json). Sesión18978 recogida con exit0;13huellas intactas. El skip no es voz comprobada. No corresponde otro Full por este cambio sóloPython; sigue pendiente el Full de cierre.

Ocho controles previos de cronología/incertidumbre contenían frases factualmente correctas pero sin las identidades de una lista solicitada. Se completaron sus entradas positivas con esos nombres, conservando las afirmaciones y los resultados esperados. Los fallos iniciales están en owners1.log; no se debilitó una aserción para aceptar listas incompletas.

**No se adopta:** la prueba real790 detiene listas incompletas pero no consigue que el modelo las complete. Además, la revisión de fuente reprodujo dos fallos: no contar la última identidad antes de otra frase y contar una anotación de proceso como una ventana sin título independiente. [Resultados790](../INVENTORY_COMPOSER790/REPORT.md), [contraejemplos](../INVENTORY_COMPOSER790/REVIEW_FINDINGS.json).

SOURCE_SNAPSHOT.json conserva trece archivos exactos en privado y SOURCE_PATCH.diff permite reconstruirlos desde64b49388. SOURCE_PINS y PROGRAM permanecen históricos e inmutables. La siguiente revisión debe corregir esos dos contraejemplos antes de cambiar la reparación del modelo. Sin crédito de encuesta ni aceptación de producto por pruebas con stubs.
