# SCREEN1807 — adjudicación de la raíz

## SCREEN1807 — estado vigente 2026-09-17T05:02:12.368102+00:00

Parcial: 3 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 641/742 | 101 | 0 | >=525 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 525 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SCREEN1807 añade 0. No se cuentan revalidaciones.

Siguiente acción: SCREEN1807: 6 ejecutados, 3 aprobados, 3 fallidos, 0 créditos (índices []); Pantalla, captura e interpretación visual 16/19. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/SCREEN1807/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 105.19 s acumulados; pico GPU 3497.56 MiB; pico RAM 1674.31 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0285 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 1 | H0492 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; el final citó líneas reconocidas tal cual pero copió una instrucción interna como frase propia y no dijo que sólo lee el texto. |
| 2 | H0704 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; el final citó líneas reconocidas tal cual pero copió una instrucción interna como frase propia y no respondió sobre el botón pedido. |
| 3 | screen1807-dev-01 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 4 | screen1807-dev-02 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; el final citó líneas reconocidas tal cual pero afirmó una cuenta de líneas falsa y envolvió toda la respuesta entre comillas. |
| 5 | screen1807-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 105.19 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1674.31 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
