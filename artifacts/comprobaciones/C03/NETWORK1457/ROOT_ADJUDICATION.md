# NETWORK1457 — adjudicación de la raíz

## NETWORK1457 — estado vigente 2026-09-14T20:04:06.687409+00:00

Parcial: 7 aprobados, 0 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 458/742 | 284 | 0 | >=332 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 330 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); NETWORK1457 añade 2. No se cuentan revalidaciones.

Siguiente acción: NETWORK1457: 7 ejecutados, 7 aprobados, 0 fallidos, 2 créditos (índices [0, 1]); Red y Bluetooth 15/21. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/NETWORK1457/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 112.84 s acumulados; pico GPU 3497.56 MiB; pico RAM 1887.06 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 7; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0445 | passed | Leyó el estado de la radio Bluetooth y lo dijo con fidelidad; crédito con dos variantes aprobadas del grupo. | Turno ordinario: una bluetooth.radio.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 1 | H0466 | passed | Leyó el estado de la radio Bluetooth y lo dijo con fidelidad; crédito con dos variantes aprobadas del grupo. | Turno ordinario: una bluetooth.radio.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 2 | network1457-dev-01 | passed | Leyó el estado de la radio Bluetooth y lo dijo con fidelidad. | Turno ordinario: una bluetooth.radio.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 3 | network1457-dev-02 | passed | Leyó el estado de la radio Bluetooth y lo dijo con fidelidad. | Turno ordinario: una bluetooth.radio.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 4 | network1457-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | network1457-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | network1457-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 112.84 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1887.06 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
