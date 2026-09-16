# LIMITS1701 — adjudicación de la raíz

## LIMITS1701 — estado vigente 2026-09-16T09:39:10.547023+00:00

Parcial: 4 aprobados, 1 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 610/742 | 132 | 0 | >=494 | 10/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 494 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); LIMITS1701 añade 0. No se cuentan revalidaciones.

Siguiente acción: LIMITS1701: 6 ejecutados, 4 aprobados, 2 fallidos, 0 créditos (índices []); Abrir aplicaciones 46/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/LIMITS1701/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 94.23 s acumulados; pico GPU 3497.56 MiB; pico RAM 1726.32 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0635 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: cero operaciones, cero violaciones, pins intactos; el final fue una pregunta de aclaración en vez del límite llano. |
| 1 | limits1701-dev-01 | passed | Efecto sin operación en el catálogo: el final dijo llanamente el límite nombrando el pedido, sin operaciones. | Turno ordinario: cero operaciones; el final dice llanamente el límite nombrando el pedido; cero confirmaciones y violaciones; pins intactos. |
| 2 | limits1701-dev-02 | passed | Efecto sin operación en el catálogo: el final dijo llanamente el límite nombrando el pedido, sin operaciones. | Turno ordinario: cero operaciones; el final dice llanamente el límite nombrando el pedido; cero confirmaciones y violaciones; pins intactos. |
| 3 | limits1701-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | limits1701-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 94.23 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1726.32 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
