# MEMORY1247 — adjudicación de la raíz

## MEMORY1247 — estado vigente 2026-09-13T20:08:37.716426+00:00

Parcial: 1 aprobados, 9 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 334/742 | 408 | 0 | >=208 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 208 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MEMORY1247 no añade ninguna. No se cuentan revalidaciones.

Siguiente acción: MEMORY1247 completa: 10 ejecutados, 1 aprobado (límite), 9 fallidos, 0 créditos. El instrumento de dos fases funciona: siete casos activaron la memoria y guardaron el dato con verificación. Causa medida del fallo: la composición del final de un guardado (hechos memory_updated sin el dato guardado, banderas internas verbalizadas, idioma tomado del segundo turno). Siguiente: MEMORY1249 con la proyección de hechos del guardado enriquecida (qué se guardó, sin banderas internas) y el idioma del pedido original, y remedición de H0157, H0149, H0452, H0506.

Evidencia: `artifacts/comprobaciones/C03/MEMORY1247/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 189.25 s acumulados; pico GPU 3497.56 MiB; pico RAM 2245.25 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0157 | failed | Falló: guardó de verdad, pero el final inventa un archivo y jerga interna y no dice qué recordó. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 1 | H0149 | failed | Falló: guardó de verdad, pero el final inventa un archivo y jerga interna y no dice qué recordó. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 2 | H0452 | failed | Falló: sin respuesta publicable. | Sin final; memory.save fallida (memory_disabled) y ninguna confirmación; pins intactos. |
| 3 | H0506 | failed | Falló: guardó de verdad, pero el final inventa un archivo y jerga interna y no dice qué recordó. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 4 | memory1247-dev-01 | failed | Falló: guardó de verdad, pero el final inventa un archivo y jerga interna y no dice qué recordó. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 5 | memory1247-dev-02 | failed | Falló: guardó de verdad, pero el final inventa un archivo y jerga interna y no dice qué recordó. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 6 | memory1247-dev-03 | failed | Falló: guardó de verdad, pero el final inventa un archivo y jerga interna y no dice qué recordó. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 7 | memory1247-dev-04 | failed | Falló: guardó de verdad, pero el final inventa un archivo y jerga interna y no dice qué recordó. | Dos fases: pregunta de activación y final; memory.save (memory_disabled), memory.enable completada y verificada, memory.save completada y verificada; una confirmación del conductor; cero violaciones; pins intactos. |
| 8 | memory1247-boundary-01 | passed | Límite aprobado: usó el nombre sin guardarlo. | Final publicado; ninguna operación de memoria; cero confirmaciones y violaciones; pins intactos. |
| 9 | memory1247-boundary-02 | failed | Límite fallido: describió mal qué guarda. | Final publicado; ninguna operación de memoria; cero confirmaciones y violaciones; pins intactos. |

Recursos: 189.25 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2245.25 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
