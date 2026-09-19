# UNRES1873 — adjudicación de la raíz

## UNRES1873 — estado vigente 2026-09-19T03:39:37.453369+00:00

Parcial: 7 aprobados, 1 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 682/742 | 60 | 0 | >=566 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 563 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UNRES1873 añade 3. No se cuentan revalidaciones.

Siguiente acción: UNRES1873: 8 ejecutados, 7 aprobados, 1 fallidos, 3 créditos (índices [0, 1, 2]); Entrada incompleta, ruido y control de diálogo 30/34. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UNRES1873/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 151.36 s acumulados; pico GPU 3492.93 MiB; pico RAM 2161.43 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0139 | passed | Entrada ininteligible o sin pedido: cero operaciones y un final que dijo con honestidad que no entendió y pidió repetir o precisar, sin inventar un pedido; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: cero operaciones; el final dice con honestidad que no entendió o que no encuentra un pedido y pide repetir o precisar, sin inventar un pedido ni repetir el ruido; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0246 | passed | Entrada ininteligible o sin pedido: cero operaciones y un final que dijo con honestidad que no entendió y pidió repetir o precisar, sin inventar un pedido; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: cero operaciones; el final dice con honestidad que no entendió o que no encuentra un pedido y pide repetir o precisar, sin inventar un pedido ni repetir el ruido; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0414 | passed | Entrada ininteligible o sin pedido: cero operaciones y un final que dijo con honestidad que no entendió y pidió repetir o precisar, sin inventar un pedido; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: cero operaciones; el final dice con honestidad que no entendió o que no encuentra un pedido y pide repetir o precisar, sin inventar un pedido ni repetir el ruido; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0639 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: cero violaciones; pins intactos; el final no fue fiel. |
| 4 | unres1873-dev-01 | passed | Entrada ininteligible o sin pedido: cero operaciones y un final que dijo con honestidad que no entendió y pidió repetir o precisar, sin inventar un pedido. | Turno ordinario: cero operaciones; el final dice con honestidad que no entendió o que no encuentra un pedido y pide repetir o precisar, sin inventar un pedido ni repetir el ruido; cero confirmaciones y violaciones; pins intactos. |
| 5 | unres1873-dev-02 | passed | Entrada ininteligible o sin pedido: cero operaciones y un final que dijo con honestidad que no entendió y pidió repetir o precisar, sin inventar un pedido. | Turno ordinario: cero operaciones; el final dice con honestidad que no entendió o que no encuentra un pedido y pide repetir o precisar, sin inventar un pedido ni repetir el ruido; cero confirmaciones y violaciones; pins intactos. |
| 6 | unres1873-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | unres1873-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 151.36 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2161.43 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
