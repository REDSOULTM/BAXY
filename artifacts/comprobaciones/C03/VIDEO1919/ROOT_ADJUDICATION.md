# VIDEO1919 — adjudicación de la raíz

## VIDEO1919 — estado vigente 2026-09-19T22:35:41.098783+00:00

Parcial: 11 aprobados, 3 fallidos, 0 sin ejecutar; 7 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 716/742 | 26 | 0 | >=600 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 593 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); VIDEO1919 añade 7. No se cuentan revalidaciones.

Siguiente acción: VIDEO1919: 14 ejecutados, 11 aprobados, 3 fallidos, 7 créditos (índices [0, 1, 5, 6, 7, 8, 9]). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/VIDEO1919/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 599.11 s acumulados; pico GPU 3492.93 MiB; pico RAM 3750.04 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 14; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0050 | passed | exactamente una reproducción de streaming aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde; crédito con dos variantes aprobadas del mismo grupo. | Turno revisado: exactamente una streaming.play.named aprobada por la raíz, completada y verificada contra el avance observado del vídeo; una confirmación, cero violaciones; pins intactos. |
| 1 | H0105 | passed | exactamente una reproducción de streaming aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde; crédito con dos variantes aprobadas del mismo grupo. | Turno revisado: exactamente una streaming.play.named aprobada por la raíz, completada y verificada contra el avance observado del vídeo; una confirmación, cero violaciones; pins intactos. |
| 2 | H0155 | failed | Falló: la reproducción no se completó o no se verificó, o el final no fue fiel. | Turno revisado: la reproduccion se completo y se verifico; el final afirmo en que punto del video estaba, y eso el recibo no lo dice. |
| 3 | H0355 | failed | Falló: la reproducción no se completó o no se verificó, o el final no fue fiel. | Turno revisado: la raiz no aprobo la reproduccion propuesta, de modo que el turno se detuvo sin efecto alguno. |
| 4 | H0377 | failed | Falló: la reproducción no se completó o no se verificó, o el final no fue fiel. | Turno revisado: la raiz no aprobo la reproduccion propuesta, de modo que el turno se detuvo sin efecto alguno. |
| 5 | H0412 | passed | exactamente una reproducción de streaming aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde; crédito con dos variantes aprobadas del mismo grupo. | Turno revisado: exactamente una streaming.play.named aprobada por la raíz, completada y verificada contra el avance observado del vídeo; una confirmación, cero violaciones; pins intactos. |
| 6 | H0551 | passed | exactamente una reproducción de streaming aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde; crédito con dos variantes aprobadas del mismo grupo. | Turno revisado: exactamente una streaming.play.named aprobada por la raíz, completada y verificada contra el avance observado del vídeo; una confirmación, cero violaciones; pins intactos. |
| 7 | H0613 | passed | exactamente una reproducción de streaming aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde; crédito con dos variantes aprobadas del mismo grupo. | Turno revisado: exactamente una streaming.play.named aprobada por la raíz, completada y verificada contra el avance observado del vídeo; una confirmación, cero violaciones; pins intactos. |
| 8 | H0624 | passed | exactamente una reproducción de streaming aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde; crédito con dos variantes aprobadas del mismo grupo. | Turno revisado: exactamente una streaming.play.named aprobada por la raíz, completada y verificada contra el avance observado del vídeo; una confirmación, cero violaciones; pins intactos. |
| 9 | H0654 | passed | exactamente una reproducción de streaming aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde; crédito con dos variantes aprobadas del mismo grupo. | Turno revisado: exactamente una streaming.play.named aprobada por la raíz, completada y verificada contra el avance observado del vídeo; una confirmación, cero violaciones; pins intactos. |
| 10 | video1919-dev-01 | passed | exactamente una reproducción de streaming aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde. | Turno revisado: exactamente una streaming.play.named aprobada por la raíz, completada y verificada contra el avance observado del vídeo; una confirmación, cero violaciones; pins intactos. |
| 11 | video1919-dev-02 | passed | exactamente una reproducción de streaming aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde. | Turno revisado: exactamente una streaming.play.named aprobada por la raíz, completada y verificada contra el avance observado del vídeo; una confirmación, cero violaciones; pins intactos. |
| 12 | video1919-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 13 | video1919-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 599.11 s de segmentos; pico GPU 3492.93 MiB; pico RAM 3750.04 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
