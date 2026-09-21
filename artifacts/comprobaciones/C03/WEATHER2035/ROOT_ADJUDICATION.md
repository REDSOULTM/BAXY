# WEATHER2035 — adjudicación de la raíz

## WEATHER2035 — estado vigente 2026-09-21T17:38:45.853585+00:00

Parcial: 8 aprobados, 0 fallidos, 0 sin ejecutar; 4 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 671/742 | 71 | 0 | >=647 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 643 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEATHER2035 añade 4. No se cuentan revalidaciones.

Siguiente acción: WEATHER2035: 8 ejecutados, 8 aprobados, 0 fallidos, 4 créditos (índices [0, 1, 2, 3]). Siguiente: las tipadas de la Fase 5 (fondo de escritorio, zip, ruta pegada, conteo del Explorador, modo avión, descarga, meme, presentación) y luego winget/Steam.

Evidencia: `artifacts/comprobaciones/C03/WEATHER2035/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 238.78 s acumulados; pico GPU 3492.93 MiB; pico RAM 2420.86 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0034 | passed | weather.current verificada sin buscar ni preguntar; el final dice temperatura y estado y nombra la ciudad; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una weather.current completada y verificada (ubicación del pedido o la de este PC), sin navegar ni buscar; el final dice temperatura y estado leídos y nombra la ciudad; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0431 | passed | weather.current verificada sin buscar ni preguntar; el final dice temperatura y estado y nombra la ciudad; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una weather.current completada y verificada (ubicación del pedido o la de este PC), sin navegar ni buscar; el final dice temperatura y estado leídos y nombra la ciudad; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0664 | passed | weather.current verificada sin buscar ni preguntar; el final dice temperatura y estado y nombra la ciudad; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una weather.current completada y verificada (ubicación del pedido o la de este PC), sin navegar ni buscar; el final dice temperatura y estado leídos y nombra la ciudad; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0689 | passed | weather.current verificada sin buscar ni preguntar; el final dice temperatura y estado y nombra la ciudad; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una weather.current completada y verificada (ubicación del pedido o la de este PC), sin navegar ni buscar; el final dice temperatura y estado leídos y nombra la ciudad; cero confirmaciones y violaciones; pins intactos. |
| 4 | weather2035-dev-01 | passed | weather.current verificada sin buscar ni preguntar; el final dice temperatura y estado y nombra la ciudad. | Turno ordinario: exactamente una weather.current completada y verificada (ubicación del pedido o la de este PC), sin navegar ni buscar; el final dice temperatura y estado leídos y nombra la ciudad; cero confirmaciones y violaciones; pins intactos. |
| 5 | weather2035-dev-02 | passed | weather.current verificada sin buscar ni preguntar; el final dice temperatura y estado y nombra la ciudad. | Turno ordinario: exactamente una weather.current completada y verificada (ubicación del pedido o la de este PC), sin navegar ni buscar; el final dice temperatura y estado leídos y nombra la ciudad; cero confirmaciones y violaciones; pins intactos. |
| 6 | weather2035-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | weather2035-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 238.78 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2420.86 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
