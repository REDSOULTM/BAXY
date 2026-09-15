# MEMORY1503 — adjudicación de la raíz

## MEMORY1503 — estado vigente 2026-09-15T00:56:28.616749+00:00

Parcial: 6 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 495/742 | 247 | 0 | >=369 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 368 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MEMORY1503 añade 1. No se cuentan revalidaciones.

Siguiente acción: MEMORY1503: 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos (índices [0]); Memoria personal 8/10. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/MEMORY1503/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 97.98 s acumulados; pico GPU 3497.56 MiB; pico RAM 1679.41 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0174 | passed | Reconoció la preferencia sin tomarla como pedido ni operaciones; crédito con dos variantes aprobadas del grupo. | Turno ordinario: cero operaciones; cero confirmaciones; cero violaciones; pins intactos; acuse fiel de la afirmación. |
| 1 | memory1503-dev-01 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: cero operaciones; cero confirmaciones; cero violaciones; pins intactos; acuse fiel de la afirmación. |
| 2 | memory1503-dev-02 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: cero operaciones; cero confirmaciones; cero violaciones; pins intactos; acuse fiel de la afirmación. |
| 3 | memory1503-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | memory1503-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | memory1503-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 97.98 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1679.41 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
