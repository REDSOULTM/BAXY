# MEME2057 — adjudicación de la raíz

## MEME2057 — estado vigente 2026-09-22T10:07:44.746311+00:00

Parcial: 2 aprobados, 4 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 675/742 | 67 | 0 | >=651 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 651 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MEME2057 añade 0. No se cuentan revalidaciones.

Siguiente acción: MEME2057: 6 ejecutados, 2 aprobados, 4 fallidos, 0 créditos (índices []). Siguiente: la presentación (H0188) y las tipadas revisadas (winget, Steam).

Evidencia: `artifacts/comprobaciones/C03/MEME2057/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 123.81 s acumulados; pico GPU 3579.20 MiB; pico RAM 2542.83 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0069 | failed | Falló: no descargó ni abrió una imagen, preguntó, o el final no la nombró. | Turno ordinario: la imagen se descargó y se abrió con el visor (verificado); el final que la nombra fue rechazado por la App (nombre observado leído como código en la ruta de conversación); pins intactos. Reparación en el commit siguiente. |
| 1 | meme2057-dev-01 | failed | Falló: no descargó ni abrió una imagen, preguntó, o el final no la nombró. | Turno ordinario: la imagen se descargó y se abrió con el visor (verificado); el final fue rechazado por la App; pins intactos. |
| 2 | meme2057-dev-02 | failed | Falló: no descargó ni abrió una imagen, preguntó, o el final no la nombró. | Turno ordinario: la imagen se descargó y se abrió con el visor (verificado); el final fue rechazado por la App; pins intactos. |
| 3 | meme2057-dev-03 | failed | Falló: no descargó ni abrió una imagen, preguntó, o el final no la nombró. | Turno ordinario: la imagen se descargó y se abrió con el visor (verificado); el final fue rechazado por la App; pins intactos. |
| 4 | meme2057-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | meme2057-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 123.81 s de segmentos; pico GPU 3579.20 MiB; pico RAM 2542.83 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
