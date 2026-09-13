# UI1275 — adjudicación de la raíz

## UI1275 — estado vigente 2026-09-13T23:06:42.382748+00:00

Parcial: 8 aprobados, 2 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 351/742 | 391 | 0 | >=225 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 222 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1275 añade 3. No se cuentan revalidaciones.

Siguiente acción: UI1275: 10 ejecutados, 8 aprobados, 2 fallidos, 3 créditos (índices [0, 1, 2]). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UI1275/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 201.85 s acumulados; pico GPU 3497.56 MiB; pico RAM 2059.61 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0293 | passed | Apretó el botón pedido en la calculadora y lo dijo; crédito con dos variantes aprobadas. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: pregunta de confirmación y final; input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 1 | H0378 | passed | Apretó el botón pedido en la calculadora y lo dijo; crédito con dos variantes aprobadas. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: pregunta de confirmación y final; input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 2 | H0328 | passed | Apretó el botón pedido en la calculadora y lo dijo; crédito con dos variantes aprobadas. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: pregunta de confirmación y final; input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 3 | H0555 | failed | Falló: el clic no se verificó o el final no fue fiel. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: pregunta de confirmación y final; input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 4 | ui1275-dev-01 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: pregunta de confirmación y final; input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 5 | ui1275-dev-02 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: pregunta de confirmación y final; input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 6 | ui1275-dev-03 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: pregunta de confirmación y final; input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 7 | ui1275-dev-04 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: pregunta de confirmación y final; input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 8 | ui1275-boundary-01 | failed | Límite fallido: no navegó pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | ui1275-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 201.85 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2059.61 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
