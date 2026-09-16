# LIMITS1665 — adjudicación de la raíz

## LIMITS1665 — estado vigente 2026-09-16T03:54:59.481185+00:00

Parcial: 10 aprobados, 2 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 596/742 | 146 | 0 | >=470 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 468 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); LIMITS1665 añade 2. No se cuentan revalidaciones.

Siguiente acción: LIMITS1665: 6 ejecutados, 10 aprobados, -4 fallidos, 2 créditos (índices [0, 1]); Abrir aplicaciones 48/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/LIMITS1665/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 205.91 s acumulados; pico GPU 3497.56 MiB; pico RAM 1716.35 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 12; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0459 | passed | Efecto sin operación en el catálogo: el final dijo llanamente el límite nombrando el pedido, sin operaciones; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: cero operaciones; el final dice llanamente el límite nombrando el pedido; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0188 | passed | Efecto sin operación en el catálogo: el final dijo llanamente el límite nombrando el pedido, sin operaciones; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: cero operaciones; el final dice llanamente el límite nombrando el pedido; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0306 | passed | Efecto sin operación en el catálogo: el final dijo llanamente el límite nombrando el pedido, sin operaciones. | Turno ordinario: cero operaciones; el final dice llanamente el límite nombrando el pedido; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0138 | failed | Falló: hubo una operación o el final no dijo el límite con fidelidad. | Turno ordinario: cero violaciones; pins intactos; el final dijo el límite pero repitió el número, excluido por el criterio sellado. |
| 4 | limits1665-dev-01 | passed | Efecto sin operación en el catálogo: el final dijo llanamente el límite nombrando el pedido, sin operaciones. | Turno ordinario: cero operaciones; el final dice llanamente el límite nombrando el pedido; cero confirmaciones y violaciones; pins intactos. |
| 5 | limits1665-dev-02 | passed | Efecto sin operación en el catálogo: el final dijo llanamente el límite nombrando el pedido, sin operaciones. | Turno ordinario: cero operaciones; el final dice llanamente el límite nombrando el pedido; cero confirmaciones y violaciones; pins intactos. |
| 6 | limits1665-dev-03 | passed | Efecto sin operación en el catálogo: el final dijo llanamente el límite nombrando el pedido, sin operaciones. | Turno ordinario: cero operaciones; el final dice llanamente el límite nombrando el pedido; cero confirmaciones y violaciones; pins intactos. |
| 7 | limits1665-dev-04 | passed | Efecto sin operación en el catálogo: el final dijo llanamente el límite nombrando el pedido, sin operaciones. | Turno ordinario: cero operaciones; el final dice llanamente el límite nombrando el pedido; cero confirmaciones y violaciones; pins intactos. |
| 8 | limits1665-dev-05 | passed | Efecto sin operación en el catálogo: el final dijo llanamente el límite nombrando el pedido, sin operaciones. | Turno ordinario: cero operaciones; el final dice llanamente el límite nombrando el pedido; cero confirmaciones y violaciones; pins intactos. |
| 9 | limits1665-dev-06 | failed | Falló: hubo una operación o el final no dijo el límite con fidelidad. | Turno ordinario: cero violaciones; pins intactos; el final dijo el límite pero repitió el número, excluido por el criterio sellado. |
| 10 | limits1665-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | limits1665-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 205.91 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1716.35 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
