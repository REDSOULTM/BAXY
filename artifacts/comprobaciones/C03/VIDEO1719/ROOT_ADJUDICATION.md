# VIDEO1719 — adjudicación de la raíz

## VIDEO1719 — estado vigente 2026-09-16T11:53:47.134989+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 614/742 | 128 | 0 | >=498 | 10/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 497 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); VIDEO1719 añade 1. No se cuentan revalidaciones.

Siguiente acción: VIDEO1719: 12 ejecutados, 5 aprobados, 7 fallidos, 1 créditos (índices [0]); Música 15/39. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/VIDEO1719/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 129.86 s acumulados; pico GPU 3513.33 MiB; pico RAM 2382.93 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0141 | passed | Preguntó qué música poner, reprodujo con revisión lo contestado desde YouTube en el reproductor local y lo nombró por su título observado; crédito con dos variantes aprobadas. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 1 | video1719-dev-01 | passed | Preguntó qué música poner y reprodujo con revisión lo contestado, nombrándolo por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 2 | video1719-dev-02 | passed | Preguntó qué música poner y reprodujo con revisión lo contestado, nombrándolo por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 3 | video1719-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | video1719-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 129.86 s de segmentos; pico GPU 3513.33 MiB; pico RAM 2382.93 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
