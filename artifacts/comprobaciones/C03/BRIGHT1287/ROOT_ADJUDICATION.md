# BRIGHT1287 — adjudicación de la raíz

## BRIGHT1287 — estado vigente 2026-09-14T00:38:15.634688+00:00

Parcial: 10 aprobados, 3 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 372/742 | 370 | 0 | >=246 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 243 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); BRIGHT1287 añade 3. No se cuentan revalidaciones.

Siguiente acción: BRIGHT1287: 13 ejecutados, 10 aprobados, 3 fallidos, 3 créditos (índices [0, 1, 3]). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/BRIGHT1287/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 209.23 s acumulados; pico GPU 3497.56 MiB; pico RAM 1643.04 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 13; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0109 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno revisado: system.settings.set (brightness, valor pedido) propuesta, aprobada por la raíz por valor exacto, completada y verificada por WMI; una confirmación; cero violaciones; pins intactos. |
| 1 | H0255 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno revisado: system.settings.set (brightness, valor pedido) propuesta, aprobada por la raíz por valor exacto, completada y verificada por WMI; una confirmación; cero violaciones; pins intactos. |
| 2 | H0430 | failed | Falló: el final no fue fiel (vocabulario interno) o no preguntó la cantidad conservando la dirección. | Turno revisado: system.settings.set (brightness, valor pedido) propuesta, aprobada por la raíz por valor exacto, completada y verificada por WMI; una confirmación; cero violaciones; pins intactos. |
| 3 | H0196 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno revisado: system.settings.set (brightness, valor pedido) propuesta, aprobada por la raíz por valor exacto, completada y verificada por WMI; una confirmación; cero violaciones; pins intactos. |
| 4 | H0123 | passed | Respuesta fiel y útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0193 | passed | Respuesta fiel y útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | H0627 | passed | Respuesta fiel y útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | bright1287-dev-01 | passed | Respuesta fiel y útil. | Turno revisado: system.settings.set (brightness, valor pedido) propuesta, aprobada por la raíz por valor exacto, completada y verificada por WMI; una confirmación; cero violaciones; pins intactos. |
| 8 | bright1287-dev-02 | passed | Respuesta fiel y útil. | Turno revisado: system.settings.set (brightness, valor pedido) propuesta, aprobada por la raíz por valor exacto, completada y verificada por WMI; una confirmación; cero violaciones; pins intactos. |
| 9 | bright1287-dev-03 | passed | Respuesta fiel y útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | bright1287-dev-04 | failed | Falló: el final no fue fiel (vocabulario interno) o no preguntó la cantidad conservando la dirección. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | bright1287-boundary-01 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | bright1287-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 209.23 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1643.04 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
