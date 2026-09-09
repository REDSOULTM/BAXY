# C03 — tramos64–67: recuperación de selección tras una causa precisa

Estado EN_CURSO. No promoción del selector ni cambio de modelo, catálogo o
historial. Fuente actual58 + guard del proveedor63. Goal completo pendiente.

64 repite los mismos cinco pedidos con hook47, sin alterar los paquetes:
2/5 útiles,73,06s,GPU3497,56MiB,RAM5537,27MiB,registro intacto,84354exit0.
La captura exacta es astra-files64-wire/wire-29264.jsonl. Informes legibles:
PRUEBAS_ARCHIVOS63_64.md y PRUEBAS_CONTEXTO_SELECTOR65_67.md, con sus pins.

65 reproduce el selector: capturado1/4; sin contexto4/4; instrucción sobre
alcance del fallo2/4.13,41s,GPU3497,56MiB,RAM3988,99MiB,9807exit0.
66 cambia roles de diálogo:2/4; sólo usuarios anteriores4/4.10,89s,
GPU3497,56MiB,RAM3322,62MiB,25063exit0.67 cambia únicamente descripción de
read.text para nombrar contenido/archivo/sandbox:2/4,12,42s,GPU3497,56MiB,
RAM3850,34MiB,28167exit0. Registros intactos. Ninguna propuesta adoptada.

Se abandona corregir esta recuperación mediante otra frase o formato de
historial: no han resuelto los cuatro pedidos. La ablación causal señala las
respuestas anteriores del asistente, pero borrarlas globalmente no acredita
referencias cuyo significado dependa de una oferta/explicación del asistente.
El siguiente contraste debe incluir esos casos antes de cambiar el contexto
del selector. Mantener íntegros conversación, grounding y estado de usuario.
No hay detector genérico de referencias ya probado: is_elliptical_followup
es para preguntas y excluye expresamente órdenes deícticas. No reutilizarlo
como si cubriera hazlo/close that. No se ha escrito uno nuevo.

El script c03-progress-inference64.py sigue sin ejecutar. Avería/progreso UTF8
de55 y búsqueda normal sin coincidencias siguen pendientes, además del cierre
100 humanos/8rutas/UI/voz/4GB/continuidad/Full/publicación. No bloqueos externos.

Compuerta Fast63 verde89212exit0: .\scripts\test_source_quality.ps1,
Release18,24s,0 avisos/errores. Log TEMP/c03-files63-fast.log. No Full,
ningún umbral/skip/fallback añadido. No sesiones de herramientas ni modelos
propios activos al registrar este punto. La compuerta no convierte2/5 en cierre.
