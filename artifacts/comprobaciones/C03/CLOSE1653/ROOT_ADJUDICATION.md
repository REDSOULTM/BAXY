# CLOSE1653 — adjudicación de la raíz

## CLOSE1653 — estado vigente 2026-09-16T02:43:42.282739+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 588/742 | 154 | 0 | >=462 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 461 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); CLOSE1653 añade 1. No se cuentan revalidaciones.

Siguiente acción: CLOSE1653: 6 ejecutados, 5 aprobados, 1 fallidos, 1 créditos (índices [0]); Abrir aplicaciones 47/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/CLOSE1653/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 103.17 s acumulados; pico GPU 3497.56 MiB; pico RAM 1795.67 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0546 | passed | Cierre de un cliente que no está abierto: window.resolve terminó window_not_found, ninguna app.close y el final dijo que no está abierto; crédito con dos variantes aprobadas del mismo cliente. | Turno ordinario: exactamente una window.resolve del nombre pedido terminada window_not_found (el cliente no está en ejecución), ninguna app.close; nada abierto ni cerrado; cero confirmaciones y violaciones; pins intactos. |
| 1 | close1653-dev-01 | passed | Cierre de un cliente que no está abierto: window.resolve terminó window_not_found, ninguna app.close y el final dijo que no está abierto. | Turno ordinario: exactamente una window.resolve del nombre pedido terminada window_not_found (el cliente no está en ejecución), ninguna app.close; nada abierto ni cerrado; cero confirmaciones y violaciones; pins intactos. |
| 2 | close1653-dev-02 | passed | Cierre de un cliente que no está abierto: window.resolve terminó window_not_found, ninguna app.close y el final dijo que no está abierto. | Turno ordinario: exactamente una window.resolve del nombre pedido terminada window_not_found (el cliente no está en ejecución), ninguna app.close; nada abierto ni cerrado; cero confirmaciones y violaciones; pins intactos. |
| 3 | close1653-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | close1653-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 103.17 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1795.67 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
