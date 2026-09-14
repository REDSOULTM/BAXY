# SCREEN1407 — adjudicación de la raíz

## SCREEN1407 — estado vigente 2026-09-14T13:13:56.970069+00:00

Parcial: 3 aprobados, 7 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 424/742 | 318 | 0 | >=298 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 298 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SCREEN1407 añade 0. No se cuentan revalidaciones.

Siguiente acción: SCREEN1407: 10 ejecutados, 3 aprobados, 7 fallidos, 0 créditos (índices []); Pantalla, captura e interpretación visual 1/19. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/SCREEN1407/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 190.73 s acumulados; pico GPU 3497.56 MiB; pico RAM 1796.85 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0038 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada sin segunda confirmación; sin final publicado (la composición falló antes del modelo); cero violaciones; pins intactos; la captura y el texto reconocido quedan privados. |
| 1 | H0709 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada sin segunda confirmación; sin final publicado (la composición falló antes del modelo); cero violaciones; pins intactos; la captura y el texto reconocido quedan privados. |
| 2 | H0616 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada sin segunda confirmación; sin final publicado (la composición falló antes del modelo); cero violaciones; pins intactos; la captura y el texto reconocido quedan privados. |
| 3 | screen1407-dev-01 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada sin segunda confirmación; sin final publicado (la composición falló antes del modelo); cero violaciones; pins intactos; la captura y el texto reconocido quedan privados. |
| 4 | screen1407-dev-02 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada sin segunda confirmación; sin final publicado (la composición falló antes del modelo); cero violaciones; pins intactos; la captura y el texto reconocido quedan privados. |
| 5 | screen1407-dev-03 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada sin segunda confirmación; sin final publicado (la composición falló antes del modelo); cero violaciones; pins intactos; la captura y el texto reconocido quedan privados. |
| 6 | screen1407-dev-04 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada sin segunda confirmación; sin final publicado (la composición falló antes del modelo); cero violaciones; pins intactos; la captura y el texto reconocido quedan privados. |
| 7 | screen1407-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | screen1407-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | screen1407-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 190.73 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1796.85 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
