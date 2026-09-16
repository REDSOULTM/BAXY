# NETWORK1729 — adjudicación de la raíz

## NETWORK1729 — estado vigente 2026-09-16T16:22:43.556030+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 621/742 | 121 | 0 | >=505 | 10/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 504 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); NETWORK1729 añade 1. No se cuentan revalidaciones.

Siguiente acción: NETWORK1729: 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos (índices [0]); Red y Bluetooth 20/21. Siguiente: la respuesta del dueño sobre Steam/Epic (H0559/H0432) y las filas diferidas.

Evidencia: `artifacts/comprobaciones/C03/NETWORK1729/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 91.03 s acumulados; pico GPU 3497.56 MiB; pico RAM 1690.12 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0302 | passed | La lectura de redes wifi corrió y terminó con el código sellado wifi_interface_off porque la radio WLAN de este PC está apagada, y el final lo dijo con verdad sin inventar redes ni cambiar nada; crédito con dos variantes aprobadas del grupo (estado honesto sellado). | Turno ordinario: wifi.scan de sólo lectura terminada con el código sellado wifi_interface_off porque la radio WLAN de este PC está apagada (la raíz registró el estado de la interfaz antes y después: sin cambios); cero confirmaciones y violaciones; pins intactos. |
| 1 | network1729-dev-01 | passed | La lectura de redes wifi corrió y terminó con el código sellado wifi_interface_off porque la radio WLAN de este PC está apagada, y el final lo dijo con verdad sin inventar redes ni cambiar nada. | Turno ordinario: wifi.scan de sólo lectura terminada con el código sellado wifi_interface_off porque la radio WLAN de este PC está apagada (la raíz registró el estado de la interfaz antes y después: sin cambios); cero confirmaciones y violaciones; pins intactos. |
| 2 | network1729-dev-02 | passed | La lectura de redes wifi corrió y terminó con el código sellado wifi_interface_off porque la radio WLAN de este PC está apagada, y el final lo dijo con verdad sin inventar redes ni cambiar nada. | Turno ordinario: wifi.scan de sólo lectura terminada con el código sellado wifi_interface_off porque la radio WLAN de este PC está apagada (la raíz registró el estado de la interfaz antes y después: sin cambios); cero confirmaciones y violaciones; pins intactos. |
| 3 | network1729-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | network1729-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 91.03 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1690.12 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
