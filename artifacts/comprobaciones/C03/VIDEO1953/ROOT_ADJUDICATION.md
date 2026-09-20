# VIDEO1953 — adjudicación de la raíz

## VIDEO1953 — estado vigente 2026-09-20T14:25:37.633722+00:00

Parcial: 5 aprobados, 1 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 738/742 | 4 | 0 | >=622 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 621 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); VIDEO1953 añade 1. No se cuentan revalidaciones.

Siguiente acción: VIDEO1953: 6 ejecutados, 5 aprobados, 1 fallidos, 1 créditos (índices [0]). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/VIDEO1953/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 170.84 s acumulados; pico GPU 3492.93 MiB; pico RAM 3943.36 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0712 | passed | exactamente una reproducción en Disney+ aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde; crédito con dos variantes aprobadas del mismo grupo. | Turno revisado: exactamente una streaming.play.named con service=disney_plus aprobada por la raíz, completada y verificada contra el avance observado del vídeo en la ficha elegida; una confirmación, cero violaciones; pins intactos. |
| 1 | video1953-dev-01 | passed | exactamente una reproducción en Disney+ aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde. | Turno revisado: exactamente una streaming.play.named con service=disney_plus aprobada por la raíz, completada y verificada contra el avance observado del vídeo en la ficha elegida; una confirmación, cero violaciones; pins intactos. |
| 2 | video1953-dev-02 | passed | exactamente una reproducción en Disney+ aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde. | Turno revisado: exactamente una streaming.play.named con service=disney_plus aprobada por la raíz, completada y verificada contra el avance observado del vídeo en la ficha elegida; una confirmación, cero violaciones; pins intactos. |
| 3 | video1953-dev-03 | failed | Falló: la reproducción no se propuso, no se completó o no se verificó, o el final no fue fiel. | Turno revisado: cero violaciones; pins intactos; la reproducción se verificó, pero el final afirmó un fallo que no ocurrió antes de nombrar lo que se reproduce. |
| 4 | video1953-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | video1953-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 170.84 s de segmentos; pico GPU 3492.93 MiB; pico RAM 3943.36 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
