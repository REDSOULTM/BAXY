# MUSIC1583 — adjudicación de la raíz

## MUSIC1583 — estado vigente 2026-09-15T17:47:53.208221+00:00

Parcial: 6 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 537/742 | 205 | 0 | >=411 | 5/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 410 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MUSIC1583 añade 1. No se cuentan revalidaciones.

Siguiente acción: MUSIC1583: 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos (índices [0]); Música 21/39. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/MUSIC1583/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 131.67 s acumulados; pico GPU 3513.33 MiB; pico RAM 3476.59 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0129 | passed | Preguntó qué música poner, reprodujo con revisión lo contestado desde YouTube en el reproductor local y lo nombró por su título observado; crédito con dos variantes aprobadas. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 1 | music1583-dev-01 | passed | Preguntó qué música poner y reprodujo con revisión lo contestado, nombrándolo por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 2 | music1583-dev-02 | passed | Preguntó qué música poner y reprodujo con revisión lo contestado, nombrándolo por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 3 | music1583-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | music1583-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | music1583-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 131.67 s de segmentos; pico GPU 3513.33 MiB; pico RAM 3476.59 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
