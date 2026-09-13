# MEMORY1255 — adjudicación de la raíz

## MEMORY1255 — estado vigente 2026-09-13T20:56:47.905208+00:00

Parcial: 7 aprobados, 1 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 338/742 | 404 | 0 | >=212 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 210 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MEMORY1255 añade 2 (H0452, H0506), 212 después. No se cuentan revalidaciones.

Siguiente acción: MEMORY1255: 8 ejecutados, 7 aprobados, 1 fallidos, 2 créditos (H0452, H0506 con dev-01/dev-02). La comprobación por palabras de contenido admite el cambio de persona y sigue rechazando la traducción. Quedan en Memoria personal los recuerdos (H0604, H0173: requieren un guardado previo en el mismo perfil) y H0174 (modelo). Siguiente: otra categoría por masa abierta.

Evidencia: `artifacts/comprobaciones/C03/MEMORY1255/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 135.48 s acumulados; pico GPU 3497.56 MiB; pico RAM 1745.59 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0452 | passed | Guardó y lo dijo citando el dato en el idioma del pedido; crédito con dos variantes aprobadas. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 1 | H0506 | passed | Guardó y lo dijo citando el dato en el idioma del pedido; crédito con dos variantes aprobadas. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 2 | memory1255-dev-01 | passed | Guardó y lo dijo citando el dato; variante que sostiene el crédito de los literales. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 3 | memory1255-dev-02 | passed | Guardó y lo dijo citando el dato; variante que sostiene el crédito de los literales. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 4 | memory1255-dev-03 | passed | Guardó y lo dijo citando el dato; variante que sostiene el crédito de los literales. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 5 | memory1255-dev-04 | passed | Guardó y lo dijo citando el dato; variante que sostiene el crédito de los literales. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 6 | memory1255-boundary-01 | passed | Límite aprobado: usó el nombre sin guardarlo. | Final publicado; ninguna operación de memoria; cero confirmaciones y violaciones; pins intactos. |
| 7 | memory1255-boundary-02 | failed | Límite fallido: describió mal qué guarda. | Final publicado; ninguna operación de memoria; cero confirmaciones y violaciones; pins intactos. |

Recursos: 135.48 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1745.59 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
