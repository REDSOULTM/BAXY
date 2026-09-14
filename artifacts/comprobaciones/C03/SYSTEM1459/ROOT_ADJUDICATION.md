# SYSTEM1459 — adjudicación de la raíz

## SYSTEM1459 — estado vigente 2026-09-14T20:34:43.687454+00:00

Parcial: 13 aprobados, 0 fallidos, 0 sin ejecutar; 4 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 462/742 | 280 | 0 | >=336 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 332 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SYSTEM1459 añade 4. No se cuentan revalidaciones.

Siguiente acción: SYSTEM1459: 13 ejecutados, 13 aprobados, 0 fallidos, 4 créditos (índices [0, 1, 2, 3]); Estado de hardware y sistema 38/40. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/SYSTEM1459/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 203.52 s acumulados; pico GPU 3497.56 MiB; pico RAM 1651.77 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 13; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0195 | passed | Leyó los monitores conectados y contestó con el dato observado; crédito con dos variantes aprobadas del grupo. | Turno ordinario: una display.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 1 | H0464 | passed | Leyó los monitores conectados y contestó con el dato observado; crédito con dos variantes aprobadas del grupo. | Turno ordinario: una display.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 2 | H0707 | passed | Leyó los monitores conectados y contestó con el dato observado; crédito con dos variantes aprobadas del grupo. | Turno ordinario: una display.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 3 | H0125 | passed | Leyó los monitores conectados y contestó con el dato observado; crédito con dos variantes aprobadas del grupo. | Turno ordinario: una display.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 4 | system1459-dev-01 | passed | Leyó los monitores conectados y contestó con el dato observado. | Turno ordinario: una display.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 5 | system1459-dev-02 | passed | Leyó los monitores conectados y contestó con el dato observado. | Turno ordinario: una display.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 6 | system1459-dev-03 | passed | Leyó los monitores conectados y contestó con el dato observado. | Turno ordinario: una display.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 7 | system1459-dev-04 | passed | Leyó los monitores conectados y contestó con el dato observado. | Turno ordinario: una display.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 8 | system1459-dev-05 | passed | Leyó los monitores conectados y contestó con el dato observado. | Turno ordinario: una display.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 9 | system1459-dev-06 | passed | Leyó los monitores conectados y contestó con el dato observado. | Turno ordinario: una display.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 10 | system1459-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | system1459-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | system1459-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 203.52 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1651.77 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
