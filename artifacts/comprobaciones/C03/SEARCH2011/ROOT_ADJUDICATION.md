# SEARCH2011 — adjudicación de la raíz

## SEARCH2011 — estado vigente 2026-09-21T10:30:47.491377+00:00

Parcial: 5 aprobados, 3 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 655/742 | 87 | 0 | >=631 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 630 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SEARCH2011 añade 1. No se cuentan revalidaciones.

Siguiente acción: SEARCH2011: 8 ejecutados, 5 aprobados, 3 fallidos, 1 créditos (índices [1]). Siguiente: las tandas de las tipadas de la Fase 5 y msgany.

Evidencia: `artifacts/comprobaciones/C03/SEARCH2011/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 330.49 s acumulados; pico GPU 3492.93 MiB; pico RAM 2539.54 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0098 | failed | Falló: no buscó, navegó, preguntó, o el final no nombró resultados pertinentes con su sitio. | Turno ordinario: una web.search verificada con resultados pertinentes; ningún final publicado (borradores vetados); pins intactos. |
| 1 | H0380 | passed | web.search verificada sin preguntar; el final nombra al menos dos resultados pertinentes con su sitio; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una web.search completada y verificada con resultados sobre lo pedido, sin navegar ni preguntar; el final nombra al menos dos resultados pertinentes con su sitio y lo que dicen; cero confirmaciones y violaciones; pins intactos. |
| 2 | search2011-dev-01 | passed | web.search verificada sin preguntar; el final nombra al menos dos resultados pertinentes con su sitio. | Turno ordinario: exactamente una web.search completada y verificada con resultados sobre lo pedido, sin navegar ni preguntar; el final nombra al menos dos resultados pertinentes con su sitio y lo que dicen; cero confirmaciones y violaciones; pins intactos. |
| 3 | search2011-dev-02 | failed | Falló: no buscó, navegó, preguntó, o el final no nombró resultados pertinentes con su sitio. | Turno ordinario: cero operaciones; el final dijo que no podía buscar; pins intactos. |
| 4 | search2011-dev-03 | passed | web.search verificada sin preguntar; el final nombra al menos dos resultados pertinentes con su sitio. | Turno ordinario: exactamente una web.search completada y verificada con resultados sobre lo pedido, sin navegar ni preguntar; el final nombra al menos dos resultados pertinentes con su sitio y lo que dicen; cero confirmaciones y violaciones; pins intactos. |
| 5 | search2011-dev-04 | failed | Falló: no buscó, navegó, preguntó, o el final no nombró resultados pertinentes con su sitio. | Turno ordinario: una web.search verificada cuya consulta arrastró la cortesía; ningún final publicado; pins intactos. |
| 6 | search2011-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | search2011-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 330.49 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2539.54 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
