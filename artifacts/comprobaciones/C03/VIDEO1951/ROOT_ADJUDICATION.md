# VIDEO1951 — adjudicación de la raíz

## VIDEO1951 — estado vigente 2026-09-20T14:14:18.621899+00:00

Parcial: 9 aprobados, 1 fallidos, 0 sin ejecutar; 5 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 737/742 | 5 | 0 | >=621 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 616 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); VIDEO1951 añade 5. No se cuentan revalidaciones.

Siguiente acción: VIDEO1951: 10 ejecutados, 9 aprobados, 1 fallidos, 5 créditos (índices [0, 1, 2, 3, 4]). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/VIDEO1951/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 342.56 s acumulados; pico GPU 3492.93 MiB; pico RAM 4088.71 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0235 | passed | exactamente una reproducción en Disney+ aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde; crédito con dos variantes aprobadas del mismo grupo. | Turno revisado: exactamente una streaming.play.named con service=disney_plus aprobada por la raíz, completada y verificada contra el avance observado del vídeo en la ficha elegida; una confirmación, cero violaciones; pins intactos. |
| 1 | H0305 | passed | exactamente una reproducción en Disney+ aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde; crédito con dos variantes aprobadas del mismo grupo. | Turno revisado: exactamente una streaming.play.named con service=disney_plus aprobada por la raíz, completada y verificada contra el avance observado del vídeo en la ficha elegida; una confirmación, cero violaciones; pins intactos. |
| 2 | H0341 | passed | exactamente una reproducción en Disney+ aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde; crédito con dos variantes aprobadas del mismo grupo. | Turno revisado: exactamente una streaming.play.named con service=disney_plus aprobada por la raíz, completada y verificada contra el avance observado del vídeo en la ficha elegida; una confirmación, cero violaciones; pins intactos. |
| 3 | H0362 | passed | exactamente una reproducción en Disney+ aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde; crédito con dos variantes aprobadas del mismo grupo. | Turno revisado: exactamente una streaming.play.named con service=disney_plus aprobada por la raíz, completada y verificada contra el avance observado del vídeo en la ficha elegida; una confirmación, cero violaciones; pins intactos. |
| 4 | H0535 | passed | exactamente una reproducción en Disney+ aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde; crédito con dos variantes aprobadas del mismo grupo. | Turno revisado: exactamente una streaming.play.named con service=disney_plus aprobada por la raíz, completada y verificada contra el avance observado del vídeo en la ficha elegida; una confirmación, cero violaciones; pins intactos. |
| 5 | H0712 | failed | Falló: la reproducción no se propuso, no se completó o no se verificó, o el final no fue fiel. | Turno revisado: cero violaciones; pins intactos; la operación falló porque la ficha elegida no terminó de cargar; el final no fingió la reproducción. |
| 6 | video1951-dev-01 | passed | exactamente una reproducción en Disney+ aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde. | Turno revisado: exactamente una streaming.play.named con service=disney_plus aprobada por la raíz, completada y verificada contra el avance observado del vídeo en la ficha elegida; una confirmación, cero violaciones; pins intactos. |
| 7 | video1951-dev-02 | passed | exactamente una reproducción en Disney+ aprobada por la raíz, completada y verificada contra el avance observado del vídeo; el final nombra lo que se reproduce y dónde. | Turno revisado: exactamente una streaming.play.named con service=disney_plus aprobada por la raíz, completada y verificada contra el avance observado del vídeo en la ficha elegida; una confirmación, cero violaciones; pins intactos. |
| 8 | video1951-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | video1951-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 342.56 s de segmentos; pico GPU 3492.93 MiB; pico RAM 4088.71 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
