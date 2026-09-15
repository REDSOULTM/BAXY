# BROWSER1493 — adjudicación de la raíz

## BROWSER1493 — estado vigente 2026-09-15T00:08:04.675112+00:00

Parcial: 4 aprobados, 2 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 489/742 | 253 | 0 | >=363 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 362 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); BROWSER1493 añade 1. No se cuentan revalidaciones.

Siguiente acción: BROWSER1493: 6 ejecutados, 4 aprobados, 2 fallidos, 1 créditos (índices [0]); Navegación y búsqueda web 41/46. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/BROWSER1493/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 103.17 s acumulados; pico GPU 3497.56 MiB; pico RAM 2229.80 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0084 | passed | Abrió una pestaña nueva en el navegador propio, verificada, y lo dijo con verdad; crédito con dos variantes aprobadas del grupo. | Turno ordinario: browser.control new_tab completada y verificada en el navegador propio del producto (cerrado por la raíz después); cero confirmaciones; cero violaciones; pins intactos; final fiel. |
| 1 | browser1493-dev-01 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: browser.control new_tab completada y verificada en el navegador propio del producto (cerrado por la raíz después); cero confirmaciones; cero violaciones; pins intactos; final fiel. |
| 2 | browser1493-dev-02 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: browser.control new_tab completada y verificada en el navegador propio del producto (cerrado por la raíz después); cero confirmaciones; cero violaciones; pins intactos; final fiel. |
| 3 | browser1493-boundary-01 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | browser1493-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | browser1493-boundary-03 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 103.17 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2229.80 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
