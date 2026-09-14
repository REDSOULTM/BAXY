# AUDIO1461 — adjudicación de la raíz

## AUDIO1461 — estado vigente 2026-09-14T20:46:24.396268+00:00

Parcial: 7 aprobados, 2 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 463/742 | 279 | 0 | >=337 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 336 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); AUDIO1461 añade 1. No se cuentan revalidaciones.

Siguiente acción: AUDIO1461: 9 ejecutados, 7 aprobados, 2 fallidos, 1 créditos (índices [1]); Audio y volumen 44/51. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/AUDIO1461/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 138.91 s acumulados; pico GPU 3497.56 MiB; pico RAM 1694.71 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0530 | passed | Preguntó la cantidad que faltaba conservando la dirección, sin operar. | Turno ordinario de aclaración: cero operaciones; cero confirmaciones; cero violaciones; pins intactos. |
| 1 | H0075 | passed | Preguntó la cantidad que faltaba conservando la dirección, sin operar; crédito con dos variantes aprobadas del grupo. | Turno ordinario de aclaración: cero operaciones; cero confirmaciones; cero violaciones; pins intactos. |
| 2 | audio1461-dev-01 | failed | Falló: preguntó sólo la cantidad del volumen y omitió el brillo pedido en la misma solicitud. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; el final no fue un acuse fiel. |
| 3 | audio1461-dev-02 | failed | Falló: preguntó sólo la cantidad del volumen y omitió el brillo pedido en la misma solicitud. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; el final no fue un acuse fiel. |
| 4 | audio1461-dev-03 | passed | Preguntó la cantidad que faltaba conservando la dirección, sin operar. | Turno ordinario de aclaración: cero operaciones; cero confirmaciones; cero violaciones; pins intactos. |
| 5 | audio1461-dev-04 | passed | Preguntó la cantidad que faltaba conservando la dirección, sin operar. | Turno ordinario de aclaración: cero operaciones; cero confirmaciones; cero violaciones; pins intactos. |
| 6 | audio1461-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | audio1461-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | audio1461-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 138.91 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1694.71 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
