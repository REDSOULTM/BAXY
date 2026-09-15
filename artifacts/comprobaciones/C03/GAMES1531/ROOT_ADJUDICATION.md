# GAMES1531 — adjudicación de la raíz

## GAMES1531 — estado vigente 2026-09-15T03:09:03.390179+00:00

Parcial: 6 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 514/742 | 228 | 0 | >=388 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 387 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); GAMES1531 añade 1. No se cuentan revalidaciones.

Siguiente acción: GAMES1531: 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos (índices [0]); Bibliotecas y fichas de juegos 1/6. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/GAMES1531/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 109.16 s acumulados; pico GPU 3497.56 MiB; pico RAM 1515.03 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0274 | passed | Respuesta fiel: listó en local la biblioteca de Steam y dijo cuántos juegos hay y sus nombres tal cual, sin abrir Steam; crédito con dos variantes aprobadas del grupo. | Turno ordinario: una game.catalog.list de sólo lectura completada y verificada sobre los manifiestos locales, sin abrir Steam; cero confirmaciones; cero violaciones; pins intactos. |
| 1 | games1531-dev-01 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: una game.catalog.list de sólo lectura completada y verificada sobre los manifiestos locales, sin abrir Steam; cero confirmaciones; cero violaciones; pins intactos. |
| 2 | games1531-dev-02 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: una game.catalog.list de sólo lectura completada y verificada sobre los manifiestos locales, sin abrir Steam; cero confirmaciones; cero violaciones; pins intactos. |
| 3 | games1531-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | games1531-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | games1531-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 109.16 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1515.03 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
