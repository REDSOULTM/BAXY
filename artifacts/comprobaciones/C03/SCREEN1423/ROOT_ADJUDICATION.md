# SCREEN1423 — adjudicación de la raíz

## SCREEN1423 — estado vigente 2026-09-14T15:06:14.438635+00:00

Parcial: 9 aprobados, 0 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 437/742 | 305 | 0 | >=311 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 309 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SCREEN1423 añade 2. No se cuentan revalidaciones.

Siguiente acción: SCREEN1423: 9 ejecutados, 9 aprobados, 0 fallidos, 2 créditos (índices [0, 1]); Pantalla, captura e interpretación visual 14/19. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/SCREEN1423/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 149.88 s acumulados; pico GPU 3497.56 MiB; pico RAM 1698.09 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0458 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad; crédito con dos variantes aprobadas. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 1 | H0593 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad; crédito con dos variantes aprobadas. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 2 | screen1423-dev-01 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 3 | screen1423-dev-02 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 4 | screen1423-dev-03 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 5 | screen1423-dev-04 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 6 | screen1423-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | screen1423-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | screen1423-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 149.88 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1698.09 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
