# APPS1391 — adjudicación de la raíz

## APPS1391 — estado vigente 2026-09-14T09:17:41.204507+00:00

Parcial: 10 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 420/742 | 322 | 0 | >=294 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 293 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); APPS1391 añade 1. No se cuentan revalidaciones.

Siguiente acción: APPS1391: 10 ejecutados, 10 aprobados, 0 fallidos, 1 créditos (índices [0]); Abrir aplicaciones 40/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/APPS1391/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 191.31 s acumulados; pico GPU 3497.56 MiB; pico RAM 1781.95 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0183 | passed | Abrió la calculadora, leyó la hora y lo dijo todo; crédito con dos variantes aprobadas. | Turno ordinario: app.open de la Calculadora y luego system.time completadas y verificadas; cero confirmaciones y violaciones; pins intactos; Calculadora lanzada cerrada después por la raíz. |
| 1 | apps1391-dev-01 | passed | Abrió la calculadora, leyó la hora y lo dijo todo. | Turno ordinario: app.open de la Calculadora y luego system.time completadas y verificadas; cero confirmaciones y violaciones; pins intactos; Calculadora lanzada cerrada después por la raíz. |
| 2 | apps1391-dev-02 | passed | Abrió la calculadora, leyó la hora y lo dijo todo. | Turno ordinario: app.open de la Calculadora y luego system.time completadas y verificadas; cero confirmaciones y violaciones; pins intactos; Calculadora lanzada cerrada después por la raíz. |
| 3 | apps1391-dev-03 | passed | Abrió la calculadora, leyó la hora y lo dijo todo. | Turno ordinario: app.open de la Calculadora y luego system.time completadas y verificadas; cero confirmaciones y violaciones; pins intactos; Calculadora lanzada cerrada después por la raíz. |
| 4 | apps1391-dev-04 | passed | Abrió la calculadora, leyó la hora y lo dijo todo. | Turno ordinario: app.open de la Calculadora y luego system.time completadas y verificadas; cero confirmaciones y violaciones; pins intactos; Calculadora lanzada cerrada después por la raíz. |
| 5 | apps1391-dev-05 | passed | Abrió la calculadora, leyó la hora y lo dijo todo. | Turno ordinario: app.open de la Calculadora y luego system.time completadas y verificadas; cero confirmaciones y violaciones; pins intactos; Calculadora lanzada cerrada después por la raíz. |
| 6 | apps1391-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | apps1391-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | apps1391-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | apps1391-boundary-04 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 191.31 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1781.95 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
