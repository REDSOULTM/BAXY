# MEMORY1501 — adjudicación de la raíz

## MEMORY1501 — estado vigente 2026-09-15T00:45:41.672770+00:00

Parcial: 3 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 494/742 | 248 | 0 | >=368 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 368 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MEMORY1501 añade 0. No se cuentan revalidaciones.

Siguiente acción: MEMORY1501: 6 ejecutados, 3 aprobados, 3 fallidos, 0 créditos (índices []); Memoria personal 7/10. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/MEMORY1501/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 96.00 s acumulados; pico GPU 3497.56 MiB; pico RAM 1663.91 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0174 | failed | Falló: cero operaciones, pero tomó la afirmación como pedido o no la reconoció. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; el final atribuyó al asistente gustos propios en vez de reconocer los del usuario. |
| 1 | memory1501-dev-01 | failed | Falló: cero operaciones, pero tomó la afirmación como pedido o no la reconoció. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; el final atribuyó al asistente un gusto propio. |
| 2 | memory1501-dev-02 | failed | Falló: cero operaciones, pero tomó la afirmación como pedido o no la reconoció. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; el final ofreció servir la bebida en vez de reconocer la preferencia. |
| 3 | memory1501-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | memory1501-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | memory1501-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 96.00 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1663.91 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
