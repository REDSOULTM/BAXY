# AUDIO1801 — adjudicación de la raíz

## AUDIO1801 — estado vigente 2026-09-17T04:01:32.693298+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 640/742 | 102 | 0 | >=524 | 12/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 523 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); AUDIO1801 añade 1. No se cuentan revalidaciones.

Siguiente acción: AUDIO1801: 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos (índices [0]); Música 38/39. Siguiente: UI1775 (Epic) sobre la misma compilación y el volumen de Spotify.

Evidencia: `artifacts/comprobaciones/C03/AUDIO1801/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 111.94 s acumulados; pico GPU 3497.56 MiB; pico RAM 1680.86 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0652 | passed | Preguntó cuánto y ajustó el volumen propio de Spotify en la cantidad contestada, verificado por postlectura; crédito con dos variantes aprobadas. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz (una cantidad), audio.app.volume.adjust completada y verificada por la postlectura de las sesiones de audio del cliente de Spotify (abierto y reproduciendo por la raíz antes del caso, pausado y cerrado después; volumen maestro preajustado y restaurado); un envío tras el primero; cero violaciones; pins intactos. |
| 1 | audio1801-dev-01 | passed | Preguntó cuánto y ajustó el volumen propio de Spotify en la cantidad contestada, verificado por postlectura; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz (una cantidad), audio.app.volume.adjust completada y verificada por la postlectura de las sesiones de audio del cliente de Spotify (abierto y reproduciendo por la raíz antes del caso, pausado y cerrado después; volumen maestro preajustado y restaurado); un envío tras el primero; cero violaciones; pins intactos. |
| 2 | audio1801-dev-02 | passed | Preguntó cuánto y ajustó el volumen propio de Spotify en la cantidad contestada, verificado por postlectura; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz (una cantidad), audio.app.volume.adjust completada y verificada por la postlectura de las sesiones de audio del cliente de Spotify (abierto y reproduciendo por la raíz antes del caso, pausado y cerrado después; volumen maestro preajustado y restaurado); un envío tras el primero; cero violaciones; pins intactos. |
| 3 | audio1801-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | audio1801-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 111.94 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1680.86 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
