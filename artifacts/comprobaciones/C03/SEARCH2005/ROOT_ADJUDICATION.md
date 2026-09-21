# SEARCH2005 — adjudicación de la raíz

## SEARCH2005 — estado vigente 2026-09-21T09:59:47.664978+00:00

Parcial: 5 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 654/742 | 88 | 0 | >=630 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 630 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SEARCH2005 añade 0. No se cuentan revalidaciones.

Siguiente acción: SEARCH2005: 8 ejecutados, 5 aprobados, 3 fallidos, 0 créditos (índices []). Siguiente: las tandas de las tipadas de la Fase 5 y msgany.

Evidencia: `artifacts/comprobaciones/C03/SEARCH2005/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 221.20 s acumulados; pico GPU 3492.93 MiB; pico RAM 2546.51 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0098 | passed | web.search verificada sin preguntar; el final nombra al menos dos resultados pertinentes con su sitio. | Turno ordinario: exactamente una web.search completada y verificada con resultados sobre lo pedido, sin navegar ni preguntar; el final nombra al menos dos resultados pertinentes con su sitio y lo que dicen; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0380 | passed | web.search verificada sin preguntar; el final nombra al menos dos resultados pertinentes con su sitio. | Turno ordinario: exactamente una web.search completada y verificada con resultados sobre lo pedido, sin navegar ni preguntar; el final nombra al menos dos resultados pertinentes con su sitio y lo que dicen; cero confirmaciones y violaciones; pins intactos. |
| 2 | search2005-dev-01 | failed | Falló: no buscó, navegó, preguntó, o el final no nombró resultados pertinentes con su sitio. | Turno ordinario: una web.search verificada con resultados pertinentes; el final en inglés listó títulos sin sitio; pins intactos. |
| 3 | search2005-dev-02 | failed | Falló: no buscó, navegó, preguntó, o el final no nombró resultados pertinentes con su sitio. | Turno ordinario: cero operaciones; el final dijo que no podía buscar; pins intactos. |
| 4 | search2005-dev-03 | passed | web.search verificada sin preguntar; el final nombra al menos dos resultados pertinentes con su sitio. | Turno ordinario: exactamente una web.search completada y verificada con resultados sobre lo pedido, sin navegar ni preguntar; el final nombra al menos dos resultados pertinentes con su sitio y lo que dicen; cero confirmaciones y violaciones; pins intactos. |
| 5 | search2005-dev-04 | failed | Falló: no buscó, navegó, preguntó, o el final no nombró resultados pertinentes con su sitio. | Turno ordinario: una web.search verificada cuya consulta arrastró la cortesía final; el final nombró un resultado no pertinente; pins intactos. |
| 6 | search2005-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | search2005-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 221.20 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2546.51 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
