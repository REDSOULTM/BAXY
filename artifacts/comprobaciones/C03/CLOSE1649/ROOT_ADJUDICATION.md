# CLOSE1649 — adjudicación de la raíz

## CLOSE1649 — estado vigente 2026-09-16T01:50:49.671657+00:00

Parcial: 8 aprobados, 1 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 587/742 | 155 | 0 | >=461 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 459 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); CLOSE1649 añade 2. No se cuentan revalidaciones.

Siguiente acción: CLOSE1649: 6 ejecutados, 8 aprobados, -2 fallidos, 2 créditos (índices [0, 2]); Abrir aplicaciones 48/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/CLOSE1649/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 199.94 s acumulados; pico GPU 3497.56 MiB; pico RAM 1884.22 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0112 | passed | Cierre de un cliente que no está abierto: window.resolve terminó window_not_found, ninguna app.close y el final dijo que no está abierto; crédito con dos variantes aprobadas del mismo cliente. | Turno ordinario: exactamente una window.resolve del nombre pedido terminada window_not_found (el cliente no está en ejecución), ninguna app.close; nada abierto ni cerrado; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0546 | failed | Falló: la lectura de ventana no terminó en ausencia, se propuso un cierre o el final no fue fiel. | Turno ordinario: cero violaciones; pins intactos; la lectura de ventanas terminó en un fallo de inventario (un proceso ajeno terminó durante la enumeración) y no en la observación de ausencia; nada cerrado. |
| 2 | H0693 | passed | Cierre de un cliente que no está abierto: window.resolve terminó window_not_found, ninguna app.close y el final dijo que no está abierto; crédito con dos variantes aprobadas del mismo cliente. | Turno ordinario: exactamente una window.resolve del nombre pedido terminada window_not_found (el cliente no está en ejecución), ninguna app.close; nada abierto ni cerrado; cero confirmaciones y violaciones; pins intactos. |
| 3 | close1649-dev-01 | passed | Cierre de un cliente que no está abierto: window.resolve terminó window_not_found, ninguna app.close y el final dijo que no está abierto. | Turno ordinario: exactamente una window.resolve del nombre pedido terminada window_not_found (el cliente no está en ejecución), ninguna app.close; nada abierto ni cerrado; cero confirmaciones y violaciones; pins intactos. |
| 4 | close1649-dev-02 | passed | Cierre de un cliente que no está abierto: window.resolve terminó window_not_found, ninguna app.close y el final dijo que no está abierto. | Turno ordinario: exactamente una window.resolve del nombre pedido terminada window_not_found (el cliente no está en ejecución), ninguna app.close; nada abierto ni cerrado; cero confirmaciones y violaciones; pins intactos. |
| 5 | close1649-dev-03 | passed | Cierre de un cliente que no está abierto: window.resolve terminó window_not_found, ninguna app.close y el final dijo que no está abierto. | Turno ordinario: exactamente una window.resolve del nombre pedido terminada window_not_found (el cliente no está en ejecución), ninguna app.close; nada abierto ni cerrado; cero confirmaciones y violaciones; pins intactos. |
| 6 | close1649-dev-04 | passed | Cierre de un cliente que no está abierto: window.resolve terminó window_not_found, ninguna app.close y el final dijo que no está abierto. | Turno ordinario: exactamente una window.resolve del nombre pedido terminada window_not_found (el cliente no está en ejecución), ninguna app.close; nada abierto ni cerrado; cero confirmaciones y violaciones; pins intactos. |
| 7 | close1649-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | close1649-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 199.94 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1884.22 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
