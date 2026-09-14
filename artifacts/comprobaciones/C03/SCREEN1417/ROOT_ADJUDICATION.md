# SCREEN1417 — adjudicación de la raíz

## SCREEN1417 — estado vigente 2026-09-14T14:27:02.996339+00:00

Parcial: 5 aprobados, 5 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 427/742 | 315 | 0 | >=301 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 301 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SCREEN1417 añade 0. No se cuentan revalidaciones.

Siguiente acción: SCREEN1417: 10 ejecutados, 5 aprobados, 5 fallidos, 0 créditos (índices []); Pantalla, captura e interpretación visual 4/19. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/SCREEN1417/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 264.17 s acumulados; pico GPU 3497.56 MiB; pico RAM 2489.75 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0164 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; sin final publicado (la advertencia honesta sobre las imágenes fue vetada como fallo afirmado); cero violaciones; pins intactos; la captura y el texto leído quedan privados. |
| 1 | H0564 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; sin final publicado (la advertencia honesta sobre las imágenes fue vetada como fallo afirmado); cero violaciones; pins intactos; la captura y el texto leído quedan privados. |
| 2 | H0716 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 3 | screen1417-dev-01 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; sin final publicado (la advertencia honesta sobre las imágenes fue vetada como fallo afirmado); cero violaciones; pins intactos; la captura y el texto leído quedan privados. |
| 4 | screen1417-dev-02 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; sin final publicado (la advertencia honesta sobre las imágenes fue vetada como fallo afirmado); cero violaciones; pins intactos; la captura y el texto leído quedan privados. |
| 5 | screen1417-dev-03 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; sin final publicado (la advertencia honesta sobre las imágenes fue vetada como fallo afirmado); cero violaciones; pins intactos; la captura y el texto leído quedan privados. |
| 6 | screen1417-dev-04 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 7 | screen1417-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | screen1417-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | screen1417-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 264.17 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2489.75 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
