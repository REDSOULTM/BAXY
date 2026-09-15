# APPS1613 — adjudicación de la raíz

## APPS1613 — estado vigente 2026-09-15T21:42:49.960054+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 551/742 | 191 | 0 | >=425 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 424 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); APPS1613 añade 1. No se cuentan revalidaciones.

Siguiente acción: APPS1613: 6 ejecutados, 5 aprobados, 1 fallidos, 1 créditos (índices [0]); Abrir aplicaciones 47/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/APPS1613/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 109.92 s acumulados; pico GPU 3497.56 MiB; pico RAM 1858.75 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0275 | passed | Steam abierto por el producto y el juego nombrado comprobado en los manifiestos locales; final fiel; cerrado por la raíz al terminar; crédito con dos variantes aprobadas. | Turno ordinario: app.open de Steam y game.installed.named del título nombrado completadas y verificadas; Steam cerrado por la raíz al terminar; cero confirmaciones y violaciones; pins intactos. |
| 1 | apps1613-dev-01 | passed | Steam abierto por el producto y el juego nombrado comprobado en los manifiestos locales; final fiel; cerrado por la raíz al terminar. | Turno ordinario: app.open de Steam y game.installed.named del título nombrado completadas y verificadas; Steam cerrado por la raíz al terminar; cero confirmaciones y violaciones; pins intactos. |
| 2 | apps1613-dev-02 | passed | Steam abierto por el producto y el juego nombrado comprobado en los manifiestos locales; final fiel; cerrado por la raíz al terminar. | Turno ordinario: app.open de Steam y game.installed.named del título nombrado completadas y verificadas; Steam cerrado por la raíz al terminar; cero confirmaciones y violaciones; pins intactos. |
| 3 | apps1613-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | apps1613-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 109.92 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1858.75 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
