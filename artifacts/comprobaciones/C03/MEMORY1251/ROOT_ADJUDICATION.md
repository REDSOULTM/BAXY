# MEMORY1251 — adjudicación de la raíz

## MEMORY1251 — estado vigente 2026-09-13T20:32:21.631957+00:00

Parcial: 5 aprobados, 5 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 334/742 | 408 | 0 | >=208 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 208 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MEMORY1251 no añade ninguna. No se cuentan revalidaciones.

Siguiente acción: MEMORY1251 completa: 10 ejecutados, 5 aprobados, 5 fallidos, 0 créditos (los grupos nombre y dato pierden un par cada uno: idioma español ante pedidos en inglés y cita traducida; «acordate que mi color favorito…» sin respuesta por el mensaje de fallo que afirma recordar). Siguiente: MEMORY1253 con el texto del pedido original en la continuación de memoria (App), cita literal del dato recordado y mensaje de fallo memory_disabled sin afirmar recordar (mente).

Evidencia: `artifacts/comprobaciones/C03/MEMORY1251/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 183.30 s acumulados; pico GPU 3497.56 MiB; pico RAM 2240.12 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0157 | passed | Guardó y lo dijo citando el dato; sin crédito por faltar el segundo par aprobado. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 1 | H0149 | failed | Falló: tradujo el nombre guardado. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 2 | H0452 | failed | Falló: el mensaje de fallo afirmaba recordar y no pudo publicarse. | Sin final; memory.save fallida (memory_disabled); ninguna confirmación; pins intactos. |
| 3 | H0506 | passed | Guardó y lo dijo citando el dato; sin crédito por faltar el segundo par aprobado. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 4 | memory1251-dev-01 | passed | Guardó y lo dijo citando el dato; sin crédito por faltar el segundo par aprobado. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 5 | memory1251-dev-02 | failed | Failed: replied in Spanish to an English request. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 6 | memory1251-dev-03 | passed | Guardó y lo dijo citando el dato; sin crédito por faltar el segundo par aprobado. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 7 | memory1251-dev-04 | failed | Failed: Spanish reply and a translated quotation. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 8 | memory1251-boundary-01 | passed | Límite aprobado: usó el nombre sin guardarlo. | Final publicado; ninguna operación de memoria; cero confirmaciones y violaciones; pins intactos. |
| 9 | memory1251-boundary-02 | failed | Límite fallido: describió mal qué guarda. | Final publicado; ninguna operación de memoria; cero confirmaciones y violaciones; pins intactos. |

Recursos: 183.30 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2240.12 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
