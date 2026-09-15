# MEMORY1599 — adjudicación de la raíz

## MEMORY1599 — estado vigente 2026-09-15T19:26:16.133149+00:00

Parcial: 5 aprobados, 4 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 545/742 | 197 | 0 | >=419 | 5/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 419 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MEMORY1599 añade 0. No se cuentan revalidaciones.

Siguiente acción: MEMORY1599: 9 ejecutados, 5 aprobados, 4 fallidos, 0 créditos (índices []); Memoria personal 8/10. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/MEMORY1599/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 165.28 s acumulados; pico GPU 3497.56 MiB; pico RAM 1773.23 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0604 | failed | Falló: el guardado no se completó, el recuerdo no se hizo o no se verificó, o el final no dijo el dato guardado tal cual. | Guardado guionizado y recuerdo verificados; el final dijo el dato en primera persona, como si fuera de BAXY; cero violaciones; pins intactos. |
| 1 | H0173 | failed | Falló: el guardado no se completó, el recuerdo no se hizo o no se verificó, o el final no dijo el dato guardado tal cual. | Guardado guionizado y recuerdo verificados; el final dijo el dato en primera persona, como si fuera de BAXY; cero violaciones; pins intactos. |
| 2 | memory1599-dev-01 | passed | Preguntó qué música poner y reprodujo con revisión lo contestado, nombrándolo por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 3 | memory1599-dev-02 | passed | Preguntó qué música poner y reprodujo con revisión lo contestado, nombrándolo por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 4 | memory1599-dev-03 | failed | Falló: el guardado no se completó, el recuerdo no se hizo o no se verificó, o el final no dijo el dato guardado tal cual. | Guardado guionizado y recuerdo verificados; el final dijo el dato en primera persona; cero violaciones; pins intactos. |
| 5 | memory1599-dev-04 | failed | Falló: el guardado no se completó, el recuerdo no se hizo o no se verificó, o el final no dijo el dato guardado tal cual. | Guardado guionizado y recuerdo verificados; el final dijo el dato en primera persona; cero violaciones; pins intactos. |
| 6 | memory1599-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | memory1599-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | memory1599-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 165.28 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1773.23 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
