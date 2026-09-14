# UI1397 — adjudicación de la raíz

## UI1397 — estado vigente 2026-09-14T12:21:01.694672+00:00

Parcial: 10 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 423/742 | 319 | 0 | >=297 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 296 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1397 añade 1. No se cuentan revalidaciones.

Siguiente acción: UI1397: 10 ejecutados, 10 aprobados, 0 fallidos, 1 créditos (índices [0]); Interacción dentro de aplicaciones 5/22. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UI1397/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 195.74 s acumulados; pico GPU 3497.56 MiB; pico RAM 1877.51 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0472 | passed | Abrió la calculadora, apretó el botón pedido y lo dijo; crédito con dos variantes aprobadas. | Turno revisado: app.open de la Calculadora completada y verificada (paso ordinario) y luego input.visible.click completado y verificado (control invocado, superficie cambiada) sobre la Calculadora lanzada por el producto; una confirmación aprobada por la raíz para la etiqueta esperada sólo con esa ventana lanzada en primer plano; cero violaciones; pins intactos; Calculadora lanzada cerrada por la raíz después. |
| 1 | ui1397-dev-01 | passed | Abrió la calculadora, apretó el botón pedido y lo dijo. | Turno revisado: app.open de la Calculadora completada y verificada (paso ordinario) y luego input.visible.click completado y verificado (control invocado, superficie cambiada) sobre la Calculadora lanzada por el producto; una confirmación aprobada por la raíz para la etiqueta esperada sólo con esa ventana lanzada en primer plano; cero violaciones; pins intactos; Calculadora lanzada cerrada por la raíz después. |
| 2 | ui1397-dev-02 | passed | Abrió la calculadora, apretó el botón pedido y lo dijo. | Turno revisado: app.open de la Calculadora completada y verificada (paso ordinario) y luego input.visible.click completado y verificado (control invocado, superficie cambiada) sobre la Calculadora lanzada por el producto; una confirmación aprobada por la raíz para la etiqueta esperada sólo con esa ventana lanzada en primer plano; cero violaciones; pins intactos; Calculadora lanzada cerrada por la raíz después. |
| 3 | ui1397-dev-03 | passed | Abrió la calculadora, apretó el botón pedido y lo dijo. | Turno revisado: app.open de la Calculadora completada y verificada (paso ordinario) y luego input.visible.click completado y verificado (control invocado, superficie cambiada) sobre la Calculadora lanzada por el producto; una confirmación aprobada por la raíz para la etiqueta esperada sólo con esa ventana lanzada en primer plano; cero violaciones; pins intactos; Calculadora lanzada cerrada por la raíz después. |
| 4 | ui1397-dev-04 | passed | Abrió la calculadora, apretó el botón pedido y lo dijo. | Turno revisado: app.open de la Calculadora completada y verificada (paso ordinario) y luego input.visible.click completado y verificado (control invocado, superficie cambiada) sobre la Calculadora lanzada por el producto; una confirmación aprobada por la raíz para la etiqueta esperada sólo con esa ventana lanzada en primer plano; cero violaciones; pins intactos; Calculadora lanzada cerrada por la raíz después. |
| 5 | ui1397-dev-05 | passed | Abrió la calculadora, apretó el botón pedido y lo dijo. | Turno revisado: app.open de la Calculadora completada y verificada (paso ordinario) y luego input.visible.click completado y verificado (control invocado, superficie cambiada) sobre la Calculadora lanzada por el producto; una confirmación aprobada por la raíz para la etiqueta esperada sólo con esa ventana lanzada en primer plano; cero violaciones; pins intactos; Calculadora lanzada cerrada por la raíz después. |
| 6 | ui1397-dev-06 | passed | Abrió la calculadora, apretó el botón pedido y lo dijo. | Turno revisado: app.open de la Calculadora completada y verificada (paso ordinario) y luego input.visible.click completado y verificado (control invocado, superficie cambiada) sobre la Calculadora lanzada por el producto; una confirmación aprobada por la raíz para la etiqueta esperada sólo con esa ventana lanzada en primer plano; cero violaciones; pins intactos; Calculadora lanzada cerrada por la raíz después. |
| 7 | ui1397-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | ui1397-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | ui1397-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 195.74 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1877.51 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
