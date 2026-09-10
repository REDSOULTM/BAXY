# BAXY conserva el contexto de las consultas encadenadas al reloj

Tras una pregunta explícita de hora, «¿y la fecha?» y «¿y la hora?», BAXY perdía el antecedente humano y dejaba de consultar el reloj. Ahora recorre únicamente la cadena contigua de preguntas nominales de fecha/hora y se detiene al cambiar de tema. No toma la prosa del asistente ni una hora recordada como autorización. Las demás consultas conservan el último texto humano inmediato. Modelo, prompt, muestreo y validador de valores no cambian.

La regresión dueña pasó 3.403 pruebas, con una omisión ambiental de STT, en 67,45 s. Fast terminó en verde; Release en 18,82 s, sin advertencias ni errores. Incluye 62 controles nuevos de continuidad, cambios de tema y límites de autoridad. No se ejecutó un nuevo Full para este cambio exclusivamente Python; sigue pendiente el Full final exigido por el objetivo.

782 repite los mismos 50 casos de779 y añade 24 turnos encadenados: 73/74 correctos y 74 lecturas frescas, sin reintentos. El turno que antes decía desconocer la hora ahora la consulta y responde en 375,295 ms. Los 24 nuevos turnos pasan y recogen el cambio real de minuto. Persiste «Marka» en t46: dato correcto, ortografía incorrecta. Tampoco se ha corregido todavía el veto de780 a «las 12 del mediodía»; es un defecto separado del validador de BAXY. No se añaden filtros literales para ocultar ninguno.

Se acreditan H0180 y H0499, consultas de fecha local: variantes del producto en español, inglés y mezcla, modalidad, orden y referencias; más 25 fechas sintéticas780 con distintos valores y offsets, sobre el compositor que permanece intacto. La decisión es individual y explícita: los defectos pendientes de hora no invalidan la conducta de fecha. Registro: 28 cubiertos, 714 abiertos, 0 no aplicables de742; expectativas y procedencia preservadas.

La comparación nativa699 y el contraste de instrucciones737 siguen separados.737 observó tres aciertos directos de K2 que empeoraron al añadir el prompt de BAXY, en una pasada por caso. No es una comparación completa de modelos ni prueba de causalidad de una regla individual. Qwen sigue provisional; los fallos de integración no descartan K2.
