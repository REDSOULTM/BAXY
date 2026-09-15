# MUSIC1575 — adjudicación de la raíz

## MUSIC1575 — estado vigente 2026-09-15T16:44:52.371305+00:00

Parcial: 6 aprobados, 1 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 534/742 | 208 | 0 | >=408 | 5/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 407 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MUSIC1575 añade 1. No se cuentan revalidaciones.

Siguiente acción: MUSIC1575: 7 ejecutados, 6 aprobados, 1 fallidos, 1 créditos (índices [0]); Música 20/39. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/MUSIC1575/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 207.50 s acumulados; pico GPU 3513.33 MiB; pico RAM 2409.55 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 7; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0405 | passed | Preguntó qué música poner, reprodujo con revisión lo contestado desde YouTube en el reproductor local y lo nombró por su título observado; crédito con dos variantes aprobadas. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 1 | H0009 | failed | Falló: no preguntó, o la reproducción de lo contestado no se verificó, o el final citó un título no observado, no lo nombró, preguntó o no hubo final. | Diálogo de dos turnos: la pregunta fue fiel y la reproducción revisada se propuso y aprobó, pero el primer resultado (vídeo de casi cuatro horas, sólo mp4 muxado) no arrancó en la ventana de verificación en dos intentos; el final informó el fallo con verdad; cero violaciones; pins intactos. |
| 2 | music1575-dev-01 | passed | Preguntó qué música poner y reprodujo con revisión lo contestado, nombrándolo por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 3 | music1575-dev-02 | passed | Preguntó qué música poner y reprodujo con revisión lo contestado, nombrándolo por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 4 | music1575-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | music1575-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | music1575-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 207.50 s de segmentos; pico GPU 3513.33 MiB; pico RAM 2409.55 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
