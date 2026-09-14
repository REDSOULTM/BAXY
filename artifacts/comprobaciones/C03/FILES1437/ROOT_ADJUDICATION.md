# FILES1437 — adjudicación de la raíz

## FILES1437 — estado vigente 2026-09-14T16:29:14.550033+00:00

Parcial: 4 aprobados, 2 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 445/742 | 297 | 0 | >=319 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 319 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); FILES1437 añade 0. No se cuentan revalidaciones.

Siguiente acción: FILES1437: 6 ejecutados, 4 aprobados, 2 fallidos, 0 créditos (índices []); Archivos y carpetas 24/32. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/FILES1437/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 91.34 s acumulados; pico GPU 3497.56 MiB; pico RAM 1551.15 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0701 | passed | Preguntó por la carpeta sin ejecutar nada ni inventar cifras. | Turno ordinario: cero operaciones; una pregunta breve por la carpeta; cero confirmaciones; cero violaciones; pins intactos. |
| 1 | files1437-dev-01 | passed | Preguntó por la carpeta sin ejecutar nada ni inventar cifras. | Turno ordinario: cero operaciones; una pregunta breve por la carpeta; cero confirmaciones; cero violaciones; pins intactos. |
| 2 | files1437-dev-02 | failed | Falló: hubo operaciones o la respuesta no preguntó la carpeta con fidelidad. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; el final no fue un acuse fiel. |
| 3 | files1437-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | files1437-boundary-02 | failed | Límite fallido: cero clics, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | files1437-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 91.34 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1551.15 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
