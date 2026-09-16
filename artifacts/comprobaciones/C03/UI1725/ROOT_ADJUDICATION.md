# UI1725 — adjudicación de la raíz

## UI1725 — estado vigente 2026-09-16T15:47:12.980658+00:00

Parcial: 6 aprobados, 0 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 619/742 | 123 | 0 | >=503 | 10/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 501 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1725 añade 2. No se cuentan revalidaciones.

Siguiente acción: UI1725: 6 ejecutados, 6 aprobados, 0 fallidos, 2 créditos (índices [0, 1]); Interacción dentro de aplicaciones 18/22. Siguiente: LIMITS1727 (H0077) y wifi.scan (H0302).

Evidencia: `artifacts/comprobaciones/C03/UI1725/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 104.25 s acumulados; pico GPU 3497.56 MiB; pico RAM 1691.17 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0621 | passed | calculator.expression.evaluate completada y verificada sobre la Calculadora abierta por la raíz (expresión escrita, pantalla leída por UI Automation); el final dijo la operación y el resultado mostrado; ventana cerrada por la raíz; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una calculator.expression.evaluate completada y verificada sobre la ventana de Calculadora que la raíz abrió y posee (expresión escrita por SendKeys, pantalla leída por UI Automation); la raíz releyó la pantalla y cerró su ventana; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0705 | passed | calculator.expression.evaluate completada y verificada sobre la Calculadora abierta por la raíz (expresión escrita, pantalla leída por UI Automation); el final dijo la operación y el resultado mostrado; ventana cerrada por la raíz; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una calculator.expression.evaluate completada y verificada sobre la ventana de Calculadora que la raíz abrió y posee (expresión escrita por SendKeys, pantalla leída por UI Automation); la raíz releyó la pantalla y cerró su ventana; cero confirmaciones y violaciones; pins intactos. |
| 2 | ui1725-dev-01 | passed | calculator.expression.evaluate completada y verificada sobre la Calculadora abierta por la raíz (expresión escrita, pantalla leída por UI Automation); el final dijo la operación y el resultado mostrado; ventana cerrada por la raíz. | Turno ordinario: exactamente una calculator.expression.evaluate completada y verificada sobre la ventana de Calculadora que la raíz abrió y posee (expresión escrita por SendKeys, pantalla leída por UI Automation); la raíz releyó la pantalla y cerró su ventana; cero confirmaciones y violaciones; pins intactos. |
| 3 | ui1725-dev-02 | passed | calculator.expression.evaluate completada y verificada sobre la Calculadora abierta por la raíz (expresión escrita, pantalla leída por UI Automation); el final dijo la operación y el resultado mostrado; ventana cerrada por la raíz. | Turno ordinario: exactamente una calculator.expression.evaluate completada y verificada sobre la ventana de Calculadora que la raíz abrió y posee (expresión escrita por SendKeys, pantalla leída por UI Automation); la raíz releyó la pantalla y cerró su ventana; cero confirmaciones y violaciones; pins intactos. |
| 4 | ui1725-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | ui1725-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 104.25 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1691.17 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
