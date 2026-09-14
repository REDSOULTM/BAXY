# SCREEN1409 — adjudicación de la raíz

## SCREEN1409 — estado vigente 2026-09-14T13:34:59.527210+00:00

Parcial: 3 aprobados, 7 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 424/742 | 318 | 0 | >=298 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 298 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SCREEN1409 añade 0. No se cuentan revalidaciones.

Siguiente acción: SCREEN1409: 10 ejecutados, 3 aprobados, 7 fallidos, 0 créditos (índices []); Pantalla, captura e interpretación visual 1/19. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/SCREEN1409/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 286.31 s acumulados; pico GPU 3497.56 MiB; pico RAM 2422.49 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0038 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; sin final publicado (la composición agotó su presupuesto de 5 s intentando transcribir el texto completo); cero violaciones; pins intactos; la captura y el texto leído quedan privados. |
| 1 | H0709 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; sin final publicado (la composición agotó su presupuesto de 5 s intentando transcribir el texto completo); cero violaciones; pins intactos; la captura y el texto leído quedan privados. |
| 2 | H0616 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; sin final publicado (la composición agotó su presupuesto de 5 s intentando transcribir el texto completo); cero violaciones; pins intactos; la captura y el texto leído quedan privados. |
| 3 | screen1409-dev-01 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; final publicado infiel: resumen con afirmaciones que el texto reconocido no contiene; cero violaciones; pins intactos; la captura y el texto leído quedan privados. |
| 4 | screen1409-dev-02 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; final publicado infiel: resumen con afirmaciones que el texto reconocido no contiene; cero violaciones; pins intactos; la captura y el texto leído quedan privados. |
| 5 | screen1409-dev-03 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; sin final publicado (la composición agotó su presupuesto de 5 s intentando transcribir el texto completo); cero violaciones; pins intactos; la captura y el texto leído quedan privados. |
| 6 | screen1409-dev-04 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; final publicado infiel: resumen con afirmaciones que el texto reconocido no contiene; cero violaciones; pins intactos; la captura y el texto leído quedan privados. |
| 7 | screen1409-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | screen1409-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | screen1409-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 286.31 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2422.49 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
