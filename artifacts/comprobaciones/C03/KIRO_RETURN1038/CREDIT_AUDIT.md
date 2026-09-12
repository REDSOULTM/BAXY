# Auditoría de28 créditos Kiro recuperados

Los28 créditos revisados tienen evidencia concordante: literal exacto en registro/panel/captura, resultado publicado útil y coherente con recibo, y al menos dos variantes pertinentes aprobadas. No se encontró una discrepancia invalidante en este alcance. Esta conclusión audita las tandas históricas; no acredita que cada literal se haya vuelto a ejecutar con la fuente posterior1036.

| Tanda | Créditos confirmados |
|---|---:|
| SYSTEM1028 | 4 |
| APPS1029 | 3 |
| REPAIR1032 | 4 |
| REPAIR1033 | 7 |
| CLOCK1034 | 10 |


Sello de panel, todos sus archivos, runner, preparación, manifiesto candidato y HEAD coinciden con PREREG en las cinco tandas; terminales recuperados coinciden con ROOT_ADJUDICATION. Las filas literales coinciden exactamente con el registro recuperado58986cb8…; los28 estaban abiertos en el snapshot local126. Se contrastó cada recibo seleccionado con el journal de su máquina de origen, estado completed/verified y datos del payload vinculado al trace de composición. Invocaciones explícitas de apps se recuperaron de receipt/invocation_id o de la razón pública; las variantes con esos IDs coinciden también.

RAM: H0539/H0655 usan las variantes previas system1022-dev-03/dev-04, ambas verificadas contra los archivos originales del portátil y su propio candidato/sello. Entonces fueron17.18GB; enREDPC los nuevos literales informan34.36GB decimales. No se trasladan valores entre máquinas. Disco coincide con availableBytes convertido aGB; identidad coincide con domain/userName/qualifiedName. Para identidad hay varias lecturas de valores idénticos; el vínculo del turno se sostiene en trace/payload, no en elegir una invocación arbitraria por su posición.

Reloj: los diez literales y dos variantes inglesas se contrastaron por observed_utc único del clock_check y journal, calculando UTC+offset-180 al minuto:03:01 en todos. Los fallos de variantes españolas siguen siendo fallos; no anulan las dos variantes pertinentes inglesas ni se presentan como generalización perfecta.

Apps: recibos contienen identidad, HWND y estado previo coherentes con lo publicado. Las aperturas que declaran además que ya estaban en ejecución se leen como operación de apertura/reutilización, no como afirmación de crear otro proceso. La frase deH0588 «now it is active» no se usa para acreditar foco: los recibos verifican ventana visible y apertura, no foreground. Steam1033 repite prosa generada sobre hechos iguales bajo su criterio acotado sellado antes de ejecutar; no hay aquí evidencia de plantilla fijada por código.

## Primeras altas en24 horas

28 altas nuevas verificadas en el tramo Kiro, entre2026-09-12T03:30:04.335580+00:00 y2026-09-12T06:05:51.146025+00:00: delta de filas open→covered y fechas reales de REGISTRY_UPDATE. No se contabilizan controles ni verification_updated_at.

No afirmo un total exacto de primeras altas de toda la encuesta en24h. Un rastreo acotado de referencias exactas encuentra66 filas actuales con adjudicación explícita fechada en la ventana, pero eso por sí solo no demuestra primera alta histórica;88 filas usan formatos anteriores sin fecha de primera alta uniforme en esa lectura. Publicar128 por filas actualizadas sería incorrecto. Para el checkpoint, usar28 como incremento Kiro verificado y mantener la métrica global como pendiente de reconstrucción, sin convertir66 en cifra exacta.

No hubo ejecución del producto, GPU, pruebas automatizadas, re-adjudicación por modelo ni modificación del registro. JSON compacto: CREDIT_AUDIT.json; vínculos detallados: RECEIPT_LINK_AUDIT.json.
