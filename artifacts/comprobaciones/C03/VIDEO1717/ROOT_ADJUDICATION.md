# VIDEO1717 — adjudicación de la raíz

## VIDEO1717 — estado vigente 2026-09-16T11:48:59.463904+00:00

Parcial: 4 aprobados, 1 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 613/742 | 129 | 0 | >=497 | 10/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 497 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); VIDEO1717 añade 0. No se cuentan revalidaciones.

Siguiente acción: VIDEO1717: 12 ejecutados, 4 aprobados, 8 fallidos, 0 créditos (índices []); Música 14/39. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/VIDEO1717/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 134.91 s acumulados; pico GPU 3513.33 MiB; pico RAM 2599.40 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0141 | failed | Falló: no preguntó, o la reproducción de lo contestado no se verificó, o el final citó un título no observado, no lo nombró, preguntó o no hubo final. | Caso de diálogo: la pregunta se hizo sin operar, la reproducción se aprobó y verificó, pero ningún final fue publicado (borradores vetados). |
| 1 | video1717-dev-01 | passed | Preguntó qué música poner y reprodujo con revisión lo contestado, nombrándolo por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 2 | video1717-dev-02 | passed | Preguntó qué música poner y reprodujo con revisión lo contestado, nombrándolo por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 3 | video1717-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | video1717-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 134.91 s de segmentos; pico GPU 3513.33 MiB; pico RAM 2599.40 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
