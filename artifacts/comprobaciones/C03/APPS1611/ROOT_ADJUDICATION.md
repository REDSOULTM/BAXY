# APPS1611 — adjudicación de la raíz

## APPS1611 — estado vigente 2026-09-15T21:24:33.647380+00:00

Parcial: 6 aprobados, 0 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 550/742 | 192 | 0 | >=424 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 422 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); APPS1611 añade 2. No se cuentan revalidaciones.

Siguiente acción: APPS1611: 6 ejecutados, 6 aprobados, 0 fallidos, 2 créditos (índices [0, 1]); Abrir aplicaciones 48/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/APPS1611/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 121.91 s acumulados; pico GPU 3497.56 MiB; pico RAM 1738.63 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0487 | passed | Steam abierto por el producto y verificado; final fiel; cerrado por la raíz al terminar; crédito con dos variantes aprobadas. | Turno ordinario: app.open de Steam completada y verificada; Steam cerrado por la raíz al terminar; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0544 | passed | Steam abierto por el producto y verificado; final fiel; cerrado por la raíz al terminar; crédito con dos variantes aprobadas. | Turno ordinario: app.open de Steam completada y verificada; Steam cerrado por la raíz al terminar; cero confirmaciones y violaciones; pins intactos. |
| 2 | apps1611-dev-01 | passed | Steam abierto por el producto y verificado; final fiel; cerrado por la raíz al terminar. | Turno ordinario: app.open de Steam completada y verificada; Steam cerrado por la raíz al terminar; cero confirmaciones y violaciones; pins intactos. |
| 3 | apps1611-dev-02 | passed | Steam abierto por el producto y verificado; final fiel; cerrado por la raíz al terminar. | Turno ordinario: app.open de Steam completada y verificada; Steam cerrado por la raíz al terminar; cero confirmaciones y violaciones; pins intactos. |
| 4 | apps1611-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | apps1611-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 121.91 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1738.63 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
