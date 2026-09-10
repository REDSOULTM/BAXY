# Candidato787 validado, pendiente de adopción

El candidato reutiliza el máximo existente de512 tokens para inventarios verificados densos, sin cambiar los mensajes ni el muestreo. Corrige en el verificador existente la vinculación de cantidades a página, observación y total: un encabezado lejano no cambia el sentido de una cantidad; «25 observadas» no afirma un total desconocido; expresar página y total correctamente permite declarar un subconjunto.

La prueba aislada786 completó seis respuestas cortadas y pasó de30/50 a36/50. Los118 controles nuevos de787 incluyen los seis borradores completos capturados, límites de densidad, tipos inválidos, idiomas y cantidades/alcance falsos. Los nombres Qwen/K2 en pruebas con stubs comprueban la misma lógica compartida; no son inferencia ni evidencia de calidad de K2.

Validación final con el Python registrado: **2901 pass,0 fail,1 skip ambiental de STT y121 subtests pass en15,96s**; `scripts/test_source_quality.ps1 -Mode Fast`: **exit0**, Release19,70s. Comando, veinte suites y huellas en [VALIDATION.json](VALIDATION.json). El skip no cuenta como voz comprobada. Las corridas previas rojas y sus causas se conservan. No se ejecutó otro Full por este cambio sólo Python; C#764 permanece intacto y Full de cierre sigue pendiente.

La ejecución posterior788 entregó las seis respuestas completas dentro del plazo, pero reveló una lista incompleta que ahora pasa un veto numérico antes incorrecto. **787 no se adopta por sí solo:** las pruebas verdes no resuelven ese fallo de identidad/multiplicidad. [Informe y decisión788](../INVENTORY_COMPOSER788/REPORT.md).

`SOURCE_PINS.json` y `PROGRAM.json` conservan el candidato medido. `SOURCE_SNAPSHOT.json` identifica su copia privada y el parche público que reproduce todos sus bytes desde el HEAD registrado. No se repinan esas huellas después de otra edición. Sin crédito de encuesta ni promoción de modelo.
