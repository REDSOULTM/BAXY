# SEARCH2015 — adjudicación de la raíz

## SEARCH2015 — estado vigente 2026-09-21T10:58:05.436971+00:00

Parcial: 7 aprobados, 1 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 655/742 | 87 | 0 | >=631 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 631 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SEARCH2015 añade 0. No se cuentan revalidaciones.

Siguiente acción: SEARCH2015: 8 ejecutados, 7 aprobados, 1 fallidos, 0 créditos (índices []). Siguiente: las tandas de las tipadas de la Fase 5 y msgany.

Evidencia: `artifacts/comprobaciones/C03/SEARCH2015/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 275.14 s acumulados; pico GPU 3492.93 MiB; pico RAM 2519.56 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0098 | failed | Falló: no buscó, navegó, preguntó, o el final no nombró resultados pertinentes con su sitio. | Turno ordinario: una web.search verificada con resultados pertinentes; ningún final publicado (los borradores se vetaron por palabras del propio informe); pins intactos. |
| 1 | search2015-dev-01 | passed | web.search verificada sin preguntar; el final nombra al menos dos resultados pertinentes con su sitio. | Turno ordinario: exactamente una web.search completada y verificada con resultados sobre lo pedido, sin navegar ni preguntar; el final nombra al menos dos resultados pertinentes con su sitio y lo que dicen; cero confirmaciones y violaciones; pins intactos. |
| 2 | search2015-dev-02 | passed | web.search verificada sin preguntar; el final nombra al menos dos resultados pertinentes con su sitio. | Turno ordinario: exactamente una web.search completada y verificada con resultados sobre lo pedido, sin navegar ni preguntar; el final nombra al menos dos resultados pertinentes con su sitio y lo que dicen; cero confirmaciones y violaciones; pins intactos. |
| 3 | search2015-dev-03 | passed | web.search verificada sin preguntar; el final nombra al menos dos resultados pertinentes con su sitio. | Turno ordinario: exactamente una web.search completada y verificada con resultados sobre lo pedido, sin navegar ni preguntar; el final nombra al menos dos resultados pertinentes con su sitio y lo que dicen; cero confirmaciones y violaciones; pins intactos. |
| 4 | search2015-dev-04 | passed | web.search verificada sin preguntar; el final nombra al menos dos resultados pertinentes con su sitio. | Turno ordinario: exactamente una web.search completada y verificada con resultados sobre lo pedido, sin navegar ni preguntar; el final nombra al menos dos resultados pertinentes con su sitio y lo que dicen; cero confirmaciones y violaciones; pins intactos. |
| 5 | search2015-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | search2015-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | search2015-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 275.14 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2519.56 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
