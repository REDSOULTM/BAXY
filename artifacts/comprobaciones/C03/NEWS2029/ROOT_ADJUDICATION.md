# NEWS2029 — adjudicación de la raíz

## NEWS2029 — estado vigente 2026-09-21T14:32:43.233558+00:00

Parcial: 7 aprobados, 1 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 663/742 | 79 | 0 | >=639 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 636 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); NEWS2029 añade 3. No se cuentan revalidaciones.

Siguiente acción: NEWS2029: 8 ejecutados, 7 aprobados, 1 fallidos, 3 créditos (índices [0, 1, 2]). Siguiente: WEATHER2031/2033 (las ocho filas de clima restantes) y las tipadas de la Fase 5.

Evidencia: `artifacts/comprobaciones/C03/NEWS2029/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 247.34 s acumulados; pico GPU 3492.93 MiB; pico RAM 2458.44 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0033 | passed | web.news.headlines verificada sin buscar ni preguntar; el final cita titulares con su fuente; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una web.news.headlines completada y verificada (tema del pedido si lo nombra), sin navegar ni buscar; el final cita al menos tres titulares leídos con su fuente; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0374 | passed | web.news.headlines verificada sin buscar ni preguntar; el final cita titulares con su fuente; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una web.news.headlines completada y verificada (tema del pedido si lo nombra), sin navegar ni buscar; el final cita al menos tres titulares leídos con su fuente; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0509 | passed | web.news.headlines verificada sin buscar ni preguntar; el final cita titulares con su fuente; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una web.news.headlines completada y verificada (tema del pedido si lo nombra), sin navegar ni buscar; el final cita al menos tres titulares leídos con su fuente; cero confirmaciones y violaciones; pins intactos. |
| 3 | news2029-dev-01 | failed | Falló: buscó en la web, preguntó, o el final no citó titulares leídos con su fuente. | Turno ordinario: la lectura de titulares se completó y verificó; el final no se publicó (borradores vetados); pins intactos. |
| 4 | news2029-dev-02 | passed | web.news.headlines verificada sin buscar ni preguntar; el final cita titulares con su fuente. | Turno ordinario: exactamente una web.news.headlines completada y verificada (tema del pedido si lo nombra), sin navegar ni buscar; el final cita al menos tres titulares leídos con su fuente; cero confirmaciones y violaciones; pins intactos. |
| 5 | news2029-dev-03 | passed | web.news.headlines verificada sin buscar ni preguntar; el final cita titulares con su fuente. | Turno ordinario: exactamente una web.news.headlines completada y verificada (tema del pedido si lo nombra), sin navegar ni buscar; el final cita al menos tres titulares leídos con su fuente; cero confirmaciones y violaciones; pins intactos. |
| 6 | news2029-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | news2029-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 247.34 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2458.44 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
