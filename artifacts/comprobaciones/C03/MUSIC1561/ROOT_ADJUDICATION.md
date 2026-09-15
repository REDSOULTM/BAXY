# MUSIC1561 — adjudicación de la raíz

## MUSIC1561 — estado vigente 2026-09-15T13:23:09.322547+00:00

Parcial: 7 aprobados, 2 fallidos, 1 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 523/742 | 219 | 0 | >=397 | 5/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 397 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MUSIC1561 añade 0. No se cuentan revalidaciones.

Siguiente acción: MUSIC1561: 9 ejecutados (el límite 9 no se ejecutó: el proceso raíz se interrumpió tras escribir su recibo de fixture), 7 aprobados, 2 fallidos, 0 créditos (índices []); Música 9/39. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/MUSIC1561/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 222.51 s acumulados; pico GPU 3515.54 MiB; pico RAM 2675.93 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0068 | passed | Reprodujo con revisión el primer resultado de YouTube en el reproductor local y lo nombró por su título observado; variante o literal sin dos pares aprobados. | Turno revisado: media.play.youtube propuesta con la consulta de la persona, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz al terminar; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 1 | H0213 | passed | Reprodujo con revisión el primer resultado de YouTube en el reproductor local y lo nombró por su título observado; variante o literal sin dos pares aprobados. | Turno revisado: media.play.youtube propuesta con la consulta de la persona, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz al terminar; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 2 | H0250 | passed | Reprodujo con revisión el primer resultado de YouTube en el reproductor local y lo nombró por su título observado; variante o literal sin dos pares aprobados. | Turno revisado: media.play.youtube propuesta con la consulta de la persona, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz al terminar; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 3 | H0388 | passed | Reprodujo con revisión el primer resultado de YouTube en el reproductor local y lo nombró por su título observado; variante o literal sin dos pares aprobados. | Turno revisado: media.play.youtube propuesta con la consulta de la persona, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz al terminar; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 4 | H0598 | failed | Falló: la reproducción no se verificó o el final citó un título no observado, no lo nombró, preguntó o no hubo final. | Turno revisado: media.play.youtube propuesta, aprobada, completada y verificada; una confirmación; cero violaciones; pins intactos; sin final publicado («escuchando» no contó como estado de reproducción). |
| 5 | music1561-dev-01 | passed | Reprodujo con revisión el primer resultado de YouTube en el reproductor local y lo nombró por su título observado; variante o literal sin dos pares aprobados. | Turno revisado: media.play.youtube propuesta con la consulta de la persona, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz al terminar; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 6 | music1561-dev-02 | failed | Falló: la reproducción no se verificó o el final citó un título no observado, no lo nombró, preguntó o no hubo final. | Turno revisado: media.play.youtube propuesta, aprobada, completada y verificada; una confirmación; cero violaciones; pins intactos; sin final publicado («escuchando» no contó como estado de reproducción). |
| 7 | music1561-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | music1561-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 222.51 s de segmentos; pico GPU 3515.54 MiB; pico RAM 2675.93 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
