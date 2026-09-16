# CLOSE1651 — adjudicación de la raíz

## CLOSE1651 — estado vigente 2026-09-16T02:15:02.613582+00:00

Parcial: 2 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 587/742 | 155 | 0 | >=461 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 461 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); CLOSE1651 añade 0. No se cuentan revalidaciones.

Siguiente acción: CLOSE1651: 6 ejecutados, 2 aprobados, 4 fallidos, 0 créditos (índices []); Abrir aplicaciones 46/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/CLOSE1651/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 99.97 s acumulados; pico GPU 3497.56 MiB; pico RAM 1836.82 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0546 | failed | Falló: la lectura de ventana no terminó en ausencia, se propuso un cierre o el final no fue fiel. | Turno ordinario: cero violaciones; pins intactos; la lectura de ventanas terminó otra vez en un fallo de inventario y no en la observación de ausencia; nada cerrado. |
| 1 | close1651-dev-01 | failed | Falló: la lectura de ventana no terminó en ausencia, se propuso un cierre o el final no fue fiel. | Turno ordinario: cero violaciones; pins intactos; la lectura terminó en ausencia, pero el final afirmó el cierre antes de negarlo. |
| 2 | close1651-dev-02 | passed | Cierre de un cliente que no está abierto: window.resolve terminó window_not_found, ninguna app.close y el final dijo que no está abierto. | Turno ordinario: exactamente una window.resolve del nombre pedido terminada window_not_found (el cliente no está en ejecución), ninguna app.close; nada abierto ni cerrado; cero confirmaciones y violaciones; pins intactos. |
| 3 | close1651-boundary-01 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | close1651-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 99.97 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1836.82 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
