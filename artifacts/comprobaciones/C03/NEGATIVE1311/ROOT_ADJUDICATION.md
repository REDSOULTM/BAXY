# NEGATIVE1311 — adjudicación de la raíz

## NEGATIVE1311 — estado vigente 2026-09-14T02:25:33.105105+00:00

Parcial: 6 aprobados, 1 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 385/742 | 357 | 0 | >=259 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 256 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); NEGATIVE1311 añade 3. No se cuentan revalidaciones.

Siguiente acción: NEGATIVE1311: 7 ejecutados, 6 aprobados, 1 fallidos, 3 créditos (índices [0, 1, 2]). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/NEGATIVE1311/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 121.31 s acumulados; pico GPU 3497.56 MiB; pico RAM 1706.54 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 7; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0447 | passed | Reconocimiento fiel sin abrir nada; crédito con dos variantes aprobadas. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0550 | passed | Reconocimiento fiel sin abrir nada; crédito con dos variantes aprobadas. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0685 | passed | Reconocimiento fiel sin abrir nada; crédito con dos variantes aprobadas. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 3 | negative1311-dev-01 | passed | Reconocimiento fiel sin abrir nada. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | negative1311-dev-02 | passed | Reconocimiento fiel sin abrir nada. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | negative1311-boundary-01 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | negative1311-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 121.31 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1706.54 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
