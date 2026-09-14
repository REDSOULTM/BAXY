# NETWORK1293 — adjudicación de la raíz

## NETWORK1293 — estado vigente 2026-09-14T01:24:31.123110+00:00

Parcial: 10 aprobados, 3 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 376/742 | 366 | 0 | >=250 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 249 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); NETWORK1293 añade 1. No se cuentan revalidaciones.

Siguiente acción: NETWORK1293: 13 ejecutados, 10 aprobados, 3 fallidos, 1 créditos (índices [3]). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/NETWORK1293/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 220.94 s acumulados; pico GPU 3497.56 MiB; pico RAM 1610.29 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 13; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0071 | passed | Respuesta fiel y útil. | Turno ordinario: bluetooth.radio.set (radio propia del PC, sin dispositivos en uso; estado previo fijado por la raíz y restaurado después) completada y verificada por la API oficial de radios; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0179 | passed | Respuesta fiel y útil. | Turno ordinario: bluetooth.radio.set (radio propia del PC, sin dispositivos en uso; estado previo fijado por la raíz y restaurado después) completada y verificada por la API oficial de radios; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0537 | passed | Respuesta fiel y útil. | Turno ordinario: bluetooth.radio.set (radio propia del PC, sin dispositivos en uso; estado previo fijado por la raíz y restaurado después) completada y verificada por la API oficial de radios; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0230 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno ordinario: wifi.status de sólo lectura completada y verificada (dos lecturas coherentes); cero confirmaciones y violaciones; pins intactos. |
| 4 | H0302 | failed | Falló: la operación no se completó y verificó, o el final no fue fiel a lo observado. | Final publicado; wifi.status verificada; el final afirmó un estado de red no observado; pins intactos. |
| 5 | network1293-dev-01 | failed | Falló: la operación no se completó y verificó, o el final no fue fiel a lo observado. | Final publicado; ninguna operación; pidió el estado ya dicho; pins intactos. |
| 6 | network1293-dev-02 | passed | Respuesta fiel y útil. | Turno ordinario: bluetooth.radio.set (radio propia del PC, sin dispositivos en uso; estado previo fijado por la raíz y restaurado después) completada y verificada por la API oficial de radios; cero confirmaciones y violaciones; pins intactos. |
| 7 | network1293-dev-03 | failed | Falló: la operación no se completó y verificó, o el final no fue fiel a lo observado. | Final publicado; ninguna operación; pidió el estado ya dicho; pins intactos. |
| 8 | network1293-dev-04 | passed | Respuesta fiel y útil. | Turno ordinario: bluetooth.radio.set (radio propia del PC, sin dispositivos en uso; estado previo fijado por la raíz y restaurado después) completada y verificada por la API oficial de radios; cero confirmaciones y violaciones; pins intactos. |
| 9 | network1293-dev-05 | passed | Respuesta fiel y útil. | Turno ordinario: wifi.status de sólo lectura completada y verificada (dos lecturas coherentes); cero confirmaciones y violaciones; pins intactos. |
| 10 | network1293-dev-06 | passed | Respuesta fiel y útil. | Turno ordinario: wifi.status de sólo lectura completada y verificada (dos lecturas coherentes); cero confirmaciones y violaciones; pins intactos. |
| 11 | network1293-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | network1293-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 220.94 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1610.29 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
