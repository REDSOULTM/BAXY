# MEMORY1253 — adjudicación de la raíz

## MEMORY1253 — estado vigente 2026-09-13T20:47:46.276515+00:00

Parcial: 7 aprobados, 3 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 336/742 | 406 | 0 | >=210 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 208 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MEMORY1253 añade 2 (H0157, H0149), 210 después. No se cuentan revalidaciones.

Siguiente acción: MEMORY1253: 10 ejecutados, 7 aprobados, 3 fallidos, 2 créditos (H0157, H0149 con las variantes dev-01/dev-02). Las tres causas de MEMORY1251 (idioma, cita traducida, mensaje de fallo memory_disabled) quedaron resueltas; la comprobación literal nueva del dato recordado fue demasiado estricta con el cambio de persona y dejó sin final a H0506 y dev-04. Siguiente: MEMORY1255 con la comprobación por palabras de contenido (mente) para H0452, H0506 y sus variantes.

Evidencia: `artifacts/comprobaciones/C03/MEMORY1253/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 197.10 s acumulados; pico GPU 3497.56 MiB; pico RAM 2397.53 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0157 | passed | Guardó y lo dijo citando el dato en el idioma del pedido; crédito con dos variantes aprobadas. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 1 | H0149 | passed | Guardó y lo dijo citando el dato en el idioma del pedido; crédito con dos variantes aprobadas. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 2 | H0452 | passed | Guardó y lo dijo citando el dato; sin crédito por faltar el segundo par aprobado. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 3 | H0506 | failed | Falló: guardó de verdad, pero la verificación literal del dato rechazó una confirmación fiel y el turno terminó sin respuesta. | Dos fases: pregunta de activación y luego sin final publicable (no_response;recovery:no_response;retry_exhausted); memory.save (memory_disabled), memory.enable y memory.save completadas y verificadas; una confirmación; cero violaciones; pins intactos. |
| 4 | memory1253-dev-01 | passed | Guardó y lo dijo citando el nombre; variante que sostiene el crédito de los literales. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 5 | memory1253-dev-02 | passed | Guardó y lo dijo citando el nombre; variante que sostiene el crédito de los literales. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 6 | memory1253-dev-03 | passed | Guardó y lo dijo citando el dato; sin crédito por faltar el segundo par aprobado. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 7 | memory1253-dev-04 | failed | Falló: guardó de verdad, pero la verificación literal del dato rechazó una confirmación fiel y el turno terminó sin respuesta. | Dos fases: pregunta de activación y luego sin final publicable (no_response;recovery:no_response;retry_exhausted); memory.save (memory_disabled), memory.enable y memory.save completadas y verificadas; una confirmación; cero violaciones; pins intactos. |
| 8 | memory1253-boundary-01 | passed | Límite aprobado: usó el nombre sin guardarlo. | Final publicado; ninguna operación de memoria; cero confirmaciones y violaciones; pins intactos. |
| 9 | memory1253-boundary-02 | failed | Límite fallido: describió mal qué guarda. | Final publicado; ninguna operación de memoria; cero confirmaciones y violaciones; pins intactos. |

Recursos: 197.10 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2397.53 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
