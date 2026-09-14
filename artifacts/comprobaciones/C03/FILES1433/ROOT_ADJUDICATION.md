# FILES1433 — adjudicación de la raíz

## FILES1433 — estado vigente 2026-09-14T16:07:30.289934+00:00

Parcial: 6 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 444/742 | 298 | 0 | >=318 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 317 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); FILES1433 añade 1. No se cuentan revalidaciones.

Siguiente acción: FILES1433: 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos (índices [0]); Archivos y carpetas 24/32. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/FILES1433/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 98.64 s acumulados; pico GPU 3497.56 MiB; pico RAM 1693.60 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0453 | passed | Listó la carpeta conocida pedida ordenada por fecha, dijo el total y nombró las entradas más recientes con fidelidad; crédito con dos variantes aprobadas. | Turno ordinario: filesystem.known.list de sólo lectura (order=recent) sobre la carpeta pedida, completada y verificada; cero confirmaciones; cero violaciones; pins intactos; los nombres listados quedan en recibos privados y no se publican. |
| 1 | files1433-dev-01 | passed | Listó la carpeta conocida pedida ordenada por fecha, dijo el total y nombró las entradas más recientes con fidelidad. | Turno ordinario: filesystem.known.list de sólo lectura (order=recent) sobre la carpeta pedida, completada y verificada; cero confirmaciones; cero violaciones; pins intactos; los nombres listados quedan en recibos privados y no se publican. |
| 2 | files1433-dev-02 | passed | Listó la carpeta conocida pedida ordenada por fecha, dijo el total y nombró las entradas más recientes con fidelidad. | Turno ordinario: filesystem.known.list de sólo lectura (order=recent) sobre la carpeta pedida, completada y verificada; cero confirmaciones; cero violaciones; pins intactos; los nombres listados quedan en recibos privados y no se publican. |
| 3 | files1433-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | files1433-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | files1433-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 98.64 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1693.60 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
