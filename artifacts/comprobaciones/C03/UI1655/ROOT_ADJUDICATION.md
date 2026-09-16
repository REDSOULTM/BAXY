# UI1655 — adjudicación de la raíz

## UI1655 — estado vigente 2026-09-16T02:53:20.202475+00:00

Parcial: 1 aprobados, 7 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 588/742 | 154 | 0 | >=462 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 462 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1655 añade 0. No se cuentan revalidaciones.

Siguiente acción: UI1655: 6 ejecutados, 1 aprobados, 5 fallidos, 0 créditos (índices []); Abrir aplicaciones 46/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UI1655/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 149.86 s acumulados; pico GPU 3497.56 MiB; pico RAM 2320.43 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0232 | failed | Falló: hubo una operación o el final no ofreció el micrófono del sistema con fidelidad. | Turno ordinario: cero violaciones; pins intactos; la pregunta nombró el micrófono del sistema pero pidió confirmar un estado en vez de ofrecer silenciarlo. |
| 1 | H0325 | failed | Falló: hubo una operación o el final no ofreció el micrófono del sistema con fidelidad. | Turno ordinario: cero violaciones; pins intactos; la pregunta pidió confirmar un estado en vez de ofrecer el silencio del sistema. |
| 2 | H0368 | failed | Falló: hubo una operación o el final no ofreció el micrófono del sistema con fidelidad. | Turno ordinario: cero violaciones; pins intactos; la pregunta no ofreció el micrófono del sistema. |
| 3 | H0128 | failed | Falló: hubo una operación o el final no ofreció el micrófono del sistema con fidelidad. | Turno ordinario: cero violaciones; pins intactos; las dos redacciones de la pregunta fueron rechazadas y no hubo respuesta. |
| 4 | ui1655-dev-01 | failed | Falló: hubo una operación o el final no ofreció el micrófono del sistema con fidelidad. | Turno ordinario: cero violaciones; pins intactos; la pregunta pidió confirmar un estado en vez de ofrecer el silencio del sistema. |
| 5 | ui1655-dev-02 | failed | Falló: hubo una operación o el final no ofreció el micrófono del sistema con fidelidad. | Turno ordinario: cero violaciones; pins intactos; la pregunta pidió confirmar cuál micrófono en vez de ofrecer el silencio del sistema. |
| 6 | ui1655-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | ui1655-boundary-02 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 149.86 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2320.43 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
