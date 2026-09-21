# SEARCH2019 — adjudicación de la raíz

## SEARCH2019 — estado vigente 2026-09-21T11:25:00.592397+00:00

Parcial: 7 aprobados, 1 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 656/742 | 86 | 0 | >=632 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 631 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SEARCH2019 añade 1. No se cuentan revalidaciones.

Siguiente acción: SEARCH2019: 8 ejecutados, 7 aprobados, 1 fallidos, 1 créditos (índices [0]). Siguiente: las tandas de las tipadas de la Fase 5 y msgany.

Evidencia: `artifacts/comprobaciones/C03/SEARCH2019/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 283.06 s acumulados; pico GPU 3492.93 MiB; pico RAM 2546.20 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0098 | passed | web.search verificada sin preguntar; el final nombra al menos dos resultados pertinentes con su sitio; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una web.search completada y verificada con resultados sobre lo pedido, sin navegar ni preguntar; el final nombra al menos dos resultados pertinentes con su sitio y lo que dicen; cero confirmaciones y violaciones; pins intactos. |
| 1 | search2019-dev-01 | passed | web.search verificada sin preguntar; el final nombra al menos dos resultados pertinentes con su sitio. | Turno ordinario: exactamente una web.search completada y verificada con resultados sobre lo pedido, sin navegar ni preguntar; el final nombra al menos dos resultados pertinentes con su sitio y lo que dicen; cero confirmaciones y violaciones; pins intactos. |
| 2 | search2019-dev-02 | passed | web.search verificada sin preguntar; el final nombra al menos dos resultados pertinentes con su sitio. | Turno ordinario: exactamente una web.search completada y verificada con resultados sobre lo pedido, sin navegar ni preguntar; el final nombra al menos dos resultados pertinentes con su sitio y lo que dicen; cero confirmaciones y violaciones; pins intactos. |
| 3 | search2019-dev-03 | failed | Falló: no buscó, navegó, preguntó, o el final no nombró resultados pertinentes con su sitio. | Turno ordinario: una web.search verificada con resultados pertinentes; ningún final publicado (un borrador con una palabra sin fuente y reintentos con direcciones pegadas); pins intactos. |
| 4 | search2019-dev-04 | passed | web.search verificada sin preguntar; el final nombra al menos dos resultados pertinentes con su sitio. | Turno ordinario: exactamente una web.search completada y verificada con resultados sobre lo pedido, sin navegar ni preguntar; el final nombra al menos dos resultados pertinentes con su sitio y lo que dicen; cero confirmaciones y violaciones; pins intactos. |
| 5 | search2019-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | search2019-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | search2019-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 283.06 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2546.20 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
