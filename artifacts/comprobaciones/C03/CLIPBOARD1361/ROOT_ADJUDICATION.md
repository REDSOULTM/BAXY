# CLIPBOARD1361 — adjudicación de la raíz

## CLIPBOARD1361 — estado vigente 2026-09-14T06:39:53.433014+00:00

Parcial: 9 aprobados, 1 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 408/742 | 334 | 0 | >=282 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 280 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); CLIPBOARD1361 añade 2. No se cuentan revalidaciones.

Siguiente acción: CLIPBOARD1361: 10 ejecutados, 9 aprobados, 1 fallidos, 2 créditos (índices [0, 1]); Portapapeles 3/3. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/CLIPBOARD1361/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 180.14 s acumulados; pico GPU 3497.56 MiB; pico RAM 2321.52 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0199 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno revisado: clipboard.write.text {text: literal pedido} propuesta, aprobada por la raíz por texto exacto, completada y verificada por postlectura; una confirmación; cero violaciones; pins intactos. |
| 1 | H0356 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno revisado: clipboard.write.text {text: literal pedido} propuesta, aprobada por la raíz por texto exacto, completada y verificada por postlectura; una confirmación; cero violaciones; pins intactos. |
| 2 | clipboard1361-dev-01 | passed | Respuesta fiel y útil. | Turno revisado: clipboard.write.text {text: literal pedido} propuesta, aprobada por la raíz por texto exacto, completada y verificada por postlectura; una confirmación; cero violaciones; pins intactos. |
| 3 | clipboard1361-dev-02 | passed | Respuesta fiel y útil. | Turno revisado: clipboard.write.text {text: literal pedido} propuesta, aprobada por la raíz por texto exacto, completada y verificada por postlectura; una confirmación; cero violaciones; pins intactos. |
| 4 | clipboard1361-dev-03 | passed | Respuesta fiel y útil. | Turno revisado: clipboard.write.text {text: literal pedido} propuesta, aprobada por la raíz por texto exacto, completada y verificada por postlectura; una confirmación; cero violaciones; pins intactos. |
| 5 | clipboard1361-dev-04 | passed | Respuesta fiel y útil. | Turno revisado: clipboard.write.text {text: literal pedido} propuesta, aprobada por la raíz por texto exacto, completada y verificada por postlectura; una confirmación; cero violaciones; pins intactos. |
| 6 | clipboard1361-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos (portapapeles verificado igual antes y después por la raíz). |
| 7 | clipboard1361-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos (portapapeles verificado igual antes y después por la raíz). |
| 8 | clipboard1361-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos (portapapeles verificado igual antes y después por la raíz). |
| 9 | clipboard1361-boundary-04 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos (portapapeles verificado igual antes y después por la raíz). |

Recursos: 180.14 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2321.52 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
