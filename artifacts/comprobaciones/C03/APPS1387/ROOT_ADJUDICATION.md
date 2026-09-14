# APPS1387 — adjudicación de la raíz

## APPS1387 — estado vigente 2026-09-14T08:52:04.412976+00:00

Parcial: 5 aprobados, 5 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 419/742 | 323 | 0 | >=293 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 293 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); APPS1387 añade 0. No se cuentan revalidaciones.

Siguiente acción: APPS1387: 10 ejecutados, 5 aprobados, 5 fallidos, 0 créditos (índices []); Abrir aplicaciones 39/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/APPS1387/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 216.20 s acumulados; pico GPU 3497.56 MiB; pico RAM 2132.11 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0183 | failed | Falló: no ejecutó ambas cosas o el final no informó la apertura y la hora observadas. | Turno ordinario: app.open de la Calculadora y luego system.time completadas y verificadas; cero confirmaciones y violaciones; pins intactos; Calculadora lanzada cerrada después por la raíz. |
| 1 | apps1387-dev-01 | failed | Falló: no ejecutó ambas cosas o el final no informó la apertura y la hora observadas. | Turno ordinario: app.open de la Calculadora y luego system.time completadas y verificadas; cero confirmaciones y violaciones; pins intactos; Calculadora lanzada cerrada después por la raíz. |
| 2 | apps1387-dev-02 | passed | Abrió la calculadora, leyó la hora y lo dijo todo. | Turno ordinario: app.open de la Calculadora y luego system.time completadas y verificadas; cero confirmaciones y violaciones; pins intactos; Calculadora lanzada cerrada después por la raíz. |
| 3 | apps1387-dev-03 | failed | Falló: no ejecutó ambas cosas o el final no informó la apertura y la hora observadas. | Turno ordinario: app.open de la Calculadora y luego system.time completadas y verificadas; cero confirmaciones y violaciones; pins intactos; Calculadora lanzada cerrada después por la raíz. |
| 4 | apps1387-dev-04 | failed | Falló: no ejecutó ambas cosas o el final no informó la apertura y la hora observadas. | Turno ordinario: app.open de la Calculadora y luego system.time completadas y verificadas; cero confirmaciones y violaciones; pins intactos; Calculadora lanzada cerrada después por la raíz. |
| 5 | apps1387-dev-05 | failed | Falló: no ejecutó ambas cosas o el final no informó la apertura y la hora observadas. | Turno ordinario: app.open de la Calculadora y luego system.time completadas y verificadas; cero confirmaciones y violaciones; pins intactos; Calculadora lanzada cerrada después por la raíz. |
| 6 | apps1387-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | apps1387-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | apps1387-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | apps1387-boundary-04 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 216.20 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2132.11 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
