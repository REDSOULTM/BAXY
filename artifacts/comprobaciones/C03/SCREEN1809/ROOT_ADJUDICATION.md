# SCREEN1809 — adjudicación de la raíz

## SCREEN1809 — estado vigente 2026-09-17T05:11:21.507178+00:00

Parcial: 4 aprobados, 2 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 641/742 | 101 | 0 | >=525 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 525 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SCREEN1809 añade 0. No se cuentan revalidaciones.

Siguiente acción: SCREEN1809: 6 ejecutados, 4 aprobados, 2 fallidos, 0 créditos (índices []); Pantalla, captura e interpretación visual 16/19. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/SCREEN1809/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 125.83 s acumulados; pico GPU 3497.56 MiB; pico RAM 2392.09 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0285 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 1 | H0492 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 2 | H0704 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; ningún final llegó a la persona: los borradores fieles fueron vetados por la lente de fallo del compositor (la frase de alcance sobre botones no estaba exenta). |
| 3 | screen1809-dev-01 | passed | Capturó la pantalla con revisión, leyó el texto reconocido y lo transcribió con fidelidad. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada; ocr.read sobre esa captura completada y verificada; una confirmación; cero violaciones; pins intactos; la captura y el texto reconocido quedan en recibos privados y no se publican. |
| 4 | screen1809-dev-02 | failed | Falló: la captura o la lectura no se verificaron o el final no fue fiel. | Turno revisado: captura aprobada por la raíz, completada y verificada; ocr.read completada y verificada; el final citó líneas reconocidas tal cual pero afirmó una cuenta de líneas falsa. |
| 5 | screen1809-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 125.83 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2392.09 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
