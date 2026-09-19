# UNRES1855 — adjudicación de la raíz

## UNRES1855 — estado vigente 2026-09-19T00:53:28.698409+00:00

Parcial: 6 aprobados, 5 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 670/742 | 72 | 0 | >=554 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 554 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UNRES1855 añade 0. No se cuentan revalidaciones.

Siguiente acción: UNRES1855: 11 ejecutados, 6 aprobados, 5 fallidos, 0 créditos (índices []); Entrada incompleta, ruido y control de diálogo 27/34. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UNRES1855/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 212.17 s acumulados; pico GPU 3492.93 MiB; pico RAM 2326.27 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 11; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0139 | passed | Entrada ininteligible o sin pedido: cero operaciones y un final que dijo con honestidad que no entendió y pidió repetir o precisar, sin inventar un pedido. | Turno ordinario: cero operaciones; el final dice con honestidad que no entendió o que no encuentra un pedido y pide repetir o precisar, sin inventar un pedido ni repetir el ruido; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0160 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: cero violaciones; pins intactos; el final no fue fiel. |
| 2 | H0210 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: cero violaciones; pins intactos; el final no fue fiel. |
| 3 | H0246 | passed | Entrada ininteligible o sin pedido: cero operaciones y un final que dijo con honestidad que no entendió y pidió repetir o precisar, sin inventar un pedido. | Turno ordinario: cero operaciones; el final dice con honestidad que no entendió o que no encuentra un pedido y pide repetir o precisar, sin inventar un pedido ni repetir el ruido; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0404 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: cero violaciones; pins intactos; el final no fue fiel. |
| 5 | H0414 | passed | Entrada ininteligible o sin pedido: cero operaciones y un final que dijo con honestidad que no entendió y pidió repetir o precisar, sin inventar un pedido. | Turno ordinario: cero operaciones; el final dice con honestidad que no entendió o que no encuentra un pedido y pide repetir o precisar, sin inventar un pedido ni repetir el ruido; cero confirmaciones y violaciones; pins intactos. |
| 6 | H0639 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: cero violaciones; pins intactos; el final no fue fiel. |
| 7 | unres1855-dev-01 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: cero violaciones; pins intactos; el final no fue fiel. |
| 8 | unres1855-dev-02 | passed | Entrada ininteligible o sin pedido: cero operaciones y un final que dijo con honestidad que no entendió y pidió repetir o precisar, sin inventar un pedido. | Turno ordinario: cero operaciones; el final dice con honestidad que no entendió o que no encuentra un pedido y pide repetir o precisar, sin inventar un pedido ni repetir el ruido; cero confirmaciones y violaciones; pins intactos. |
| 9 | unres1855-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | unres1855-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 212.17 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2326.27 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
