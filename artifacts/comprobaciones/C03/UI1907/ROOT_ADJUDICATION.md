# UI1907 — adjudicación de la raíz

## UI1907 — estado vigente 2026-09-19T18:18:45.225413+00:00

Parcial: 6 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 702/742 | 40 | 0 | >=586 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 585 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1907 añade 1. No se cuentan revalidaciones.

Siguiente acción: UI1907: 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos (índices [0]). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UI1907/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 222.62 s acumulados; pico GPU 3492.93 MiB; pico RAM 2689.72 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0096 | passed | mira la pantalla antes de pulsar y, al no haber nada con ese nombre, lo dice sin afirmar que pulsó; crédito con dos variantes aprobadas del mismo grupo. | Turno revisado sobre la ventana que la raíz abrió: una lectura de los controles visibles completada y verificada, y un solo clic aprobado por la raíz que termina sin encontrar la etiqueta; cero violaciones; pins intactos. |
| 1 | ui1907-dev-01 | passed | mira la pantalla antes de pulsar y, al no haber nada con ese nombre, lo dice sin afirmar que pulsó. | Turno revisado sobre la ventana que la raíz abrió: una lectura de los controles visibles completada y verificada, y un solo clic aprobado por la raíz que termina sin encontrar la etiqueta; cero violaciones; pins intactos. |
| 2 | ui1907-dev-02 | passed | mira la pantalla antes de pulsar y, al no haber nada con ese nombre, lo dice sin afirmar que pulsó. | Turno revisado sobre la ventana que la raíz abrió: una lectura de los controles visibles completada y verificada, y un solo clic aprobado por la raíz que termina sin encontrar la etiqueta; cero violaciones; pins intactos. |
| 3 | ui1907-dev-03 | passed | mira la pantalla antes de pulsar y, al no haber nada con ese nombre, lo dice sin afirmar que pulsó. | Turno revisado sobre la ventana que la raíz abrió: una lectura de los controles visibles completada y verificada, y un solo clic aprobado por la raíz que termina sin encontrar la etiqueta; cero violaciones; pins intactos. |
| 4 | ui1907-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | ui1907-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 222.62 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2689.72 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
