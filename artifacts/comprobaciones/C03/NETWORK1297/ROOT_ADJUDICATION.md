# NETWORK1297 — adjudicación de la raíz

## NETWORK1297 — estado vigente 2026-09-14T01:42:22.112433+00:00

Parcial: 5 aprobados, 4 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 377/742 | 365 | 0 | >=251 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 251 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); NETWORK1297 añade 0. No se cuentan revalidaciones.

Siguiente acción: NETWORK1297: 9 ejecutados, 5 aprobados, 4 fallidos, 0 créditos (índices []). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/NETWORK1297/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 172.34 s acumulados; pico GPU 3497.56 MiB; pico RAM 2062.00 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0071 | passed | Respuesta fiel y útil. | Turno ordinario: bluetooth.radio.set (radio propia del PC, sin dispositivos en uso; estado previo fijado por la raíz y restaurado después) completada y verificada por la API oficial de radios; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0179 | passed | Respuesta fiel y útil. | Turno ordinario: bluetooth.radio.set (radio propia del PC, sin dispositivos en uso; estado previo fijado por la raíz y restaurado después) completada y verificada por la API oficial de radios; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0302 | failed | Falló: la operación no se completó y verificó, o el final no fue fiel a lo observado. | Final no publicado (composición agotada); wifi.status verificada; pins intactos. |
| 3 | network1297-dev-01 | failed | Falló: la operación no se completó y verificó, o el final no fue fiel a lo observado. | Final publicado; bluetooth.radio.set completada y verificada; el final atribuyó la acción al usuario; pins intactos. |
| 4 | network1297-dev-02 | passed | Respuesta fiel y útil. | Turno ordinario: bluetooth.radio.set (radio propia del PC, sin dispositivos en uso; estado previo fijado por la raíz y restaurado después) completada y verificada por la API oficial de radios; cero confirmaciones y violaciones; pins intactos. |
| 5 | network1297-dev-03 | failed | Falló: la operación no se completó y verificó, o el final no fue fiel a lo observado. | Final no publicado (composición agotada); wifi.status verificada; pins intactos. |
| 6 | network1297-dev-04 | failed | Falló: la operación no se completó y verificó, o el final no fue fiel a lo observado. | Final no publicado (composición agotada); wifi.status verificada; pins intactos. |
| 7 | network1297-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | network1297-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 172.34 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2062.00 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
