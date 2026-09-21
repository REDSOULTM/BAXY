# WEATHER2031 — adjudicación de la raíz

## WEATHER2031 — estado vigente 2026-09-21T15:08:13.533394+00:00

Parcial: 7 aprobados, 1 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 663/742 | 79 | 0 | >=639 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 639 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEATHER2031 añade 0. No se cuentan revalidaciones.

Siguiente acción: WEATHER2031: 8 ejecutados, 7 aprobados, 1 fallidos, 0 créditos (índices []). Siguiente: las filas de clima restantes y las tipadas de la Fase 5.

Evidencia: `artifacts/comprobaciones/C03/WEATHER2031/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 196.95 s acumulados; pico GPU 3492.93 MiB; pico RAM 2492.89 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0034 | passed | weather.current verificada sin buscar ni preguntar; el final dice temperatura y estado y nombra la ciudad. | Turno ordinario: exactamente una weather.current completada y verificada (ubicación del pedido o la de este PC), sin navegar ni buscar; el final dice temperatura y estado leídos y nombra la ciudad; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0431 | passed | weather.current verificada sin buscar ni preguntar; el final dice temperatura y estado y nombra la ciudad. | Turno ordinario: exactamente una weather.current completada y verificada (ubicación del pedido o la de este PC), sin navegar ni buscar; el final dice temperatura y estado leídos y nombra la ciudad; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0664 | passed | weather.current verificada sin buscar ni preguntar; el final dice temperatura y estado y nombra la ciudad. | Turno ordinario: exactamente una weather.current completada y verificada (ubicación del pedido o la de este PC), sin navegar ni buscar; el final dice temperatura y estado leídos y nombra la ciudad; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0689 | passed | weather.current verificada sin buscar ni preguntar; el final dice temperatura y estado y nombra la ciudad. | Turno ordinario: exactamente una weather.current completada y verificada (ubicación del pedido o la de este PC), sin navegar ni buscar; el final dice temperatura y estado leídos y nombra la ciudad; cero confirmaciones y violaciones; pins intactos. |
| 4 | weather2031-dev-01 | failed | Falló: buscó en la web, preguntó, o el final no dijo temperatura, estado y ciudad leídos. | Turno ordinario: la lectura de clima se completó y verificó; el final no se publicó (borradores vetados); pins intactos. |
| 5 | weather2031-dev-02 | passed | weather.current verificada sin buscar ni preguntar; el final dice temperatura y estado y nombra la ciudad. | Turno ordinario: exactamente una weather.current completada y verificada (ubicación del pedido o la de este PC), sin navegar ni buscar; el final dice temperatura y estado leídos y nombra la ciudad; cero confirmaciones y violaciones; pins intactos. |
| 6 | weather2031-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | weather2031-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 196.95 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2492.89 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
