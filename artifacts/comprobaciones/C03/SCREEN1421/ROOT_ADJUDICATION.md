# SCREEN1421 — adjudicación de la raíz

## SCREEN1421 — estado vigente 2026-09-14T14:55:09.743569+00:00

Parcial: 12 aprobados, 2 fallidos, 0 sin ejecutar; 5 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 435/742 | 307 | 0 | >=309 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 304 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SCREEN1421 añade 5. No se cuentan revalidaciones.

Siguiente acción: SCREEN1421: 14 ejecutados, 12 aprobados, 2 fallidos, 5 créditos (índices [0, 3, 4, 5, 6]); Pantalla, captura e interpretación visual 12/19. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/SCREEN1421/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 282.62 s acumulados; pico GPU 3497.56 MiB; pico RAM 2412.88 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 14; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0187 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad; crédito con dos variantes aprobadas. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 1 | H0458 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; sin final publicado (la cita fiel de una línea de la pantalla que termina en «: false» fue vetada como código interno); cero violaciones; pins intactos; la captura y el texto leído quedan privados. |
| 2 | H0593 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; sin final publicado (la cita fiel de una línea de la pantalla que termina en «: false» fue vetada como código interno); cero violaciones; pins intactos; la captura y el texto leído quedan privados. |
| 3 | H0462 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad; crédito con dos variantes aprobadas. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 4 | H0742 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad; crédito con dos variantes aprobadas. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 5 | H0240 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad; crédito con dos variantes aprobadas. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 6 | H0277 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad; crédito con dos variantes aprobadas. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 7 | screen1421-dev-01 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 8 | screen1421-dev-02 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 9 | screen1421-dev-03 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 10 | screen1421-dev-04 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 11 | screen1421-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | screen1421-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 13 | screen1421-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 282.62 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2412.88 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
