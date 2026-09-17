# SCREEN1811 — adjudicación de la raíz

## SCREEN1811 — estado vigente 2026-09-17T05:29:12.084520+00:00

Parcial: 6 aprobados, 0 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 644/742 | 98 | 0 | >=528 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 525 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SCREEN1811 añade 3. No se cuentan revalidaciones.

Siguiente acción: SCREEN1811: 6 ejecutados, 6 aprobados, 0 fallidos, 3 créditos (índices [0, 1, 2]); Pantalla, captura e interpretación visual 19/19. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/SCREEN1811/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 111.70 s acumulados; pico GPU 3497.56 MiB; pico RAM 1707.72 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0285 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad; crédito con dos variantes aprobadas. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 1 | H0492 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad; crédito con dos variantes aprobadas. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 2 | H0704 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad; crédito con dos variantes aprobadas. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 3 | screen1811-dev-01 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 4 | screen1811-dev-02 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 5 | screen1811-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 111.70 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1707.72 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
