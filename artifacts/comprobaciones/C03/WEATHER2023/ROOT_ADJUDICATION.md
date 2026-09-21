# WEATHER2023 — adjudicación de la raíz

## WEATHER2023 — estado vigente 2026-09-21T12:49:46.499840+00:00

Parcial: 6 aprobados, 2 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 656/742 | 86 | 0 | >=632 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 632 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEATHER2023 añade 0. No se cuentan revalidaciones.

Siguiente acción: WEATHER2023: 8 ejecutados, 6 aprobados, 2 fallidos, 0 créditos (índices []). Siguiente: las demás tipadas (noticias, winget, Steam, energía, wifi de casa…) y msgany.

Evidencia: `artifacts/comprobaciones/C03/WEATHER2023/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 166.12 s acumulados; pico GPU 3492.93 MiB; pico RAM 1882.36 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0415 | passed | weather.current verificada sin buscar ni preguntar; el final dice temperatura y estado y nombra la ciudad. | Turno ordinario: exactamente una weather.current completada y verificada (ubicación del pedido o la de este PC), sin navegar ni buscar; el final dice temperatura y estado leídos y nombra la ciudad; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0339 | passed | weather.current verificada sin buscar ni preguntar; el final dice temperatura y estado y nombra la ciudad. | Turno ordinario: exactamente una weather.current completada y verificada (ubicación del pedido o la de este PC), sin navegar ni buscar; el final dice temperatura y estado leídos y nombra la ciudad; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0617 | passed | weather.current verificada sin buscar ni preguntar; el final dice temperatura y estado y nombra la ciudad. | Turno ordinario: exactamente una weather.current completada y verificada (ubicación del pedido o la de este PC), sin navegar ni buscar; el final dice temperatura y estado leídos y nombra la ciudad; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0708 | passed | weather.current verificada sin buscar ni preguntar; el final dice temperatura y estado y nombra la ciudad. | Turno ordinario: exactamente una weather.current completada y verificada (ubicación del pedido o la de este PC), sin navegar ni buscar; el final dice temperatura y estado leídos y nombra la ciudad; cero confirmaciones y violaciones; pins intactos. |
| 4 | weather2023-dev-01 | passed | weather.current verificada sin buscar ni preguntar; el final dice temperatura y estado y nombra la ciudad. | Turno ordinario: exactamente una weather.current completada y verificada (ubicación del pedido o la de este PC), sin navegar ni buscar; el final dice temperatura y estado leídos y nombra la ciudad; cero confirmaciones y violaciones; pins intactos. |
| 5 | weather2023-dev-02 | failed | Falló: buscó en la web, preguntó, o el final no dijo temperatura, estado y ciudad leídos. | Turno ordinario: cero operaciones; el final preguntó si quería el clima; pins intactos. |
| 6 | weather2023-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | weather2023-boundary-02 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 166.12 s de segmentos; pico GPU 3492.93 MiB; pico RAM 1882.36 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
