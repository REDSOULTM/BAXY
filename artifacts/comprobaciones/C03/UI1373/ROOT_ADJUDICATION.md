# UI1373 — adjudicación de la raíz

## UI1373 — estado vigente 2026-09-14T07:46:58.492689+00:00

Parcial: 6 aprobados, 4 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 417/742 | 325 | 0 | >=291 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 291 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1373 añade 0. No se cuentan revalidaciones.

Siguiente acción: UI1373: 10 ejecutados, 6 aprobados, 4 fallidos, 0 créditos (índices []); Interacción dentro de aplicaciones 3/22. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UI1373/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 221.58 s acumulados; pico GPU 3497.56 MiB; pico RAM 2479.08 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0555 | failed | Falló: el clic no se verificó o el final no fue fiel. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 1 | ui1373-dev-01 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 2 | ui1373-dev-02 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 3 | ui1373-dev-03 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 4 | ui1373-dev-04 | passed | Apretó el botón pedido en la calculadora y lo dijo. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 5 | ui1373-dev-05 | failed | Falló: el clic no se verificó o el final no fue fiel. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 6 | ui1373-dev-06 | failed | Falló: el clic no se verificó o el final no fue fiel. | Turno revisado sobre la Calculadora propia de la raíz en primer plano: input.visible.click completado y verificado (control invocado, superficie cambiada); una confirmación aprobada por la raíz para la etiqueta esperada; cero violaciones; pins intactos; ventana propia cerrada después por la raíz. |
| 7 | ui1373-boundary-01 | failed | Límite fallido: cero clics, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | ui1373-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | ui1373-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 221.58 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2479.08 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
