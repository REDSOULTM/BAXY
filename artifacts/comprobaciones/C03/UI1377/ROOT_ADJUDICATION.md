# UI1377 — adjudicación de la raíz

## UI1377 — estado vigente 2026-09-14T07:55:25.192099+00:00

Parcial: 8 aprobados, 2 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 417/742 | 325 | 0 | >=291 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 291 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1377 añade 0. No se cuentan revalidaciones.

Siguiente acción: UI1377: 10 ejecutados, 8 aprobados, 2 fallidos, 0 créditos (índices []); Interacción dentro de aplicaciones 3/22. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UI1377/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 230.87 s acumulados; pico GPU 3497.56 MiB; pico RAM 2464.49 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0555 | failed | Falló: el clic no se verificó o el final no fue fiel. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 1 | ui1377-dev-01 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 2 | ui1377-dev-02 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 3 | ui1377-dev-03 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 4 | ui1377-dev-04 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 5 | ui1377-dev-05 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 6 | ui1377-dev-06 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 7 | ui1377-boundary-01 | failed | Límite fallido: cero clics, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | ui1377-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | ui1377-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 230.87 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2464.49 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
