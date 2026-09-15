# MUSIC1565 — adjudicación de la raíz

## MUSIC1565 — estado vigente 2026-09-15T14:19:07.744263+00:00

Parcial: 4 aprobados, 6 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 523/742 | 219 | 0 | >=397 | 5/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 397 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MUSIC1565 añade 0. No se cuentan revalidaciones.

Siguiente acción: MUSIC1565: 10 ejecutados, 4 aprobados, 6 fallidos, 0 créditos (índices []); Música 9/39. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/MUSIC1565/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 615.19 s acumulados; pico GPU 3517.65 MiB; pico RAM 3654.62 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0068 | failed | Falló: la reproducción no se verificó o el final citó un título no observado, no lo nombró, preguntó o no hubo final. | Turno revisado: media.play.youtube propuesta y aprobada; la reproducción no se verificó en dos arranques; una confirmación; cero violaciones; pins intactos; sin final publicado. |
| 1 | H0213 | failed | Falló: la reproducción no se verificó o el final citó un título no observado, no lo nombró, preguntó o no hubo final. | Turno revisado: media.play.youtube propuesta y aprobada; la reproducción no se verificó en dos arranques; una confirmación; cero violaciones; pins intactos; final honesto de fallo. |
| 2 | H0250 | failed | Falló: la reproducción no se verificó o el final citó un título no observado, no lo nombró, preguntó o no hubo final. | Turno revisado: media.play.youtube propuesta y aprobada; la reproducción no se verificó; una confirmación; cero violaciones; pins intactos; el final negó la capacidad. |
| 3 | H0388 | failed | Falló: la reproducción no se verificó o el final citó un título no observado, no lo nombró, preguntó o no hubo final. | Turno revisado: media.play.youtube propuesta y aprobada; la reproducción no se verificó; una confirmación; cero violaciones; pins intactos; final honesto de fallo. |
| 4 | H0598 | failed | Falló: la reproducción no se verificó o el final citó un título no observado, no lo nombró, preguntó o no hubo final. | Turno revisado: media.play.youtube propuesta y aprobada; la reproducción no se verificó; una confirmación; cero violaciones; pins intactos; final honesto de fallo. |
| 5 | music1565-dev-01 | failed | Falló: la reproducción no se verificó o el final citó un título no observado, no lo nombró, preguntó o no hubo final. | Turno revisado: media.play.youtube propuesta y aprobada; la reproducción no se verificó; una confirmación; cero violaciones; pins intactos; sin final publicado. |
| 6 | music1565-dev-02 | passed | Reprodujo con revisión el primer resultado de YouTube en el reproductor local y lo nombró por su título observado; variante o literal sin dos pares aprobados. | Turno revisado: media.play.youtube propuesta con la consulta de la persona, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz al terminar; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 7 | music1565-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | music1565-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | music1565-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 615.19 s de segmentos; pico GPU 3517.65 MiB; pico RAM 3654.62 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
