# VIDEO1921 — adjudicación de la raíz

## VIDEO1921 — estado vigente 2026-09-20T01:21:43.667384+00:00

Parcial: 5 aprobados, 1 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 716/742 | 26 | 0 | >=600 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 600 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); VIDEO1921 añade 0. No se cuentan revalidaciones.

Siguiente acción: VIDEO1921: 6 ejecutados, 5 aprobados, 1 fallidos, 0 créditos (índices []). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/VIDEO1921/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 149.75 s acumulados; pico GPU 3492.93 MiB; pico RAM 3689.87 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0155 | passed | exactamente una reproducción de streaming aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde. | Turno revisado: exactamente una streaming.play.named aprobada por la raíz, completada y verificada contra el avance observado del vídeo; una confirmación, cero violaciones; pins intactos. |
| 1 | H0411 | passed | exactamente una reproducción de streaming aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde. | Turno revisado: exactamente una streaming.play.named aprobada por la raíz, completada y verificada contra el avance observado del vídeo; una confirmación, cero violaciones; pins intactos. |
| 2 | video1921-dev-01 | failed | Falló: la reproducción no se propuso, no se completó o no se verificó, o el final no fue fiel. | Turno revisado sin propuesta: la raiz no recibio nada que aprobar; el final pregunto por el servicio y el titulo que el pedido ya nombraba. |
| 3 | video1921-dev-02 | passed | exactamente una reproducción de streaming aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde. | Turno revisado: exactamente una streaming.play.named aprobada por la raíz, completada y verificada contra el avance observado del vídeo; una confirmación, cero violaciones; pins intactos. |
| 4 | video1921-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | video1921-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 149.75 s de segmentos; pico GPU 3492.93 MiB; pico RAM 3689.87 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
