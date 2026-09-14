# UI1389 — adjudicación de la raíz

## UI1389 — estado vigente 2026-09-14T09:32:27.007786+00:00

Parcial: 9 aprobados, 1 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 421/742 | 321 | 0 | >=295 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 294 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1389 añade 1. No se cuentan revalidaciones.

Siguiente acción: UI1389: 10 ejecutados, 9 aprobados, 1 fallidos, 1 créditos (índices [0]); Interacción dentro de aplicaciones 4/22. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UI1389/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 227.66 s acumulados; pico GPU 3497.56 MiB; pico RAM 2377.17 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0555 | passed | Apretó el botón pedido en la calculadora y lo dijo; crédito con dos variantes aprobadas. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 1 | ui1389-dev-01 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 2 | ui1389-dev-02 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 3 | ui1389-dev-03 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 4 | ui1389-dev-04 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 5 | ui1389-dev-05 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 6 | ui1389-dev-06 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 7 | ui1389-boundary-01 | failed | Límite fallido: cero clics, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | ui1389-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | ui1389-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 227.66 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2377.17 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
