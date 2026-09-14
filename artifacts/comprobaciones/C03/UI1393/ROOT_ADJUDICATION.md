# UI1393 — adjudicación de la raíz

## UI1393 — estado vigente 2026-09-14T11:28:50.064106+00:00

Parcial: 3 aprobados, 7 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 422/742 | 320 | 0 | >=296 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 296 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1393 añade 0. No se cuentan revalidaciones.

Siguiente acción: UI1393: 10 ejecutados, 3 aprobados, 7 fallidos, 0 créditos (índices []); Interacción dentro de aplicaciones 4/22. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UI1393/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 176.78 s acumulados; pico GPU 3497.56 MiB; pico RAM 1626.11 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0472 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado rechazado por la App (review_pending_not_supported) tras una app.open de la Calculadora completada y verificada; ninguna propuesta llegó al revisor; cero clics; cero violaciones; pins intactos; Calculadora lanzada cerrada por la raíz. |
| 1 | ui1393-dev-01 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado rechazado por la App (review_pending_not_supported) tras una app.open de la Calculadora completada y verificada; ninguna propuesta llegó al revisor; cero clics; cero violaciones; pins intactos; Calculadora lanzada cerrada por la raíz. |
| 2 | ui1393-dev-02 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado rechazado por la App (review_pending_not_supported) tras una app.open de la Calculadora completada y verificada; ninguna propuesta llegó al revisor; cero clics; cero violaciones; pins intactos; Calculadora lanzada cerrada por la raíz. |
| 3 | ui1393-dev-03 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado rechazado por la App (review_pending_not_supported) tras una app.open de la Calculadora completada y verificada; ninguna propuesta llegó al revisor; cero clics; cero violaciones; pins intactos; Calculadora lanzada cerrada por la raíz. |
| 4 | ui1393-dev-04 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado rechazado por la App (review_pending_not_supported) tras una app.open de la Calculadora completada y verificada; ninguna propuesta llegó al revisor; cero clics; cero violaciones; pins intactos; Calculadora lanzada cerrada por la raíz. |
| 5 | ui1393-dev-05 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado rechazado por la App (review_pending_not_supported) tras una app.open de la Calculadora completada y verificada; ninguna propuesta llegó al revisor; cero clics; cero violaciones; pins intactos; Calculadora lanzada cerrada por la raíz. |
| 6 | ui1393-dev-06 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado rechazado por la App (review_pending_not_supported) tras una app.open de la Calculadora completada y verificada; ninguna propuesta llegó al revisor; cero clics; cero violaciones; pins intactos; Calculadora lanzada cerrada por la raíz. |
| 7 | ui1393-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | ui1393-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | ui1393-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 176.78 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1626.11 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
