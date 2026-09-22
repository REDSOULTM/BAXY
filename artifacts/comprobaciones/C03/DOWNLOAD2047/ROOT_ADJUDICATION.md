# DOWNLOAD2047 — adjudicación de la raíz

## DOWNLOAD2047 — estado vigente 2026-09-22T06:33:29.789241+00:00

Parcial: 2 aprobados, 4 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 674/742 | 68 | 0 | >=650 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 650 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); DOWNLOAD2047 añade 0. No se cuentan revalidaciones.

Siguiente acción: DOWNLOAD2047: 6 ejecutados, 2 aprobados, 4 fallidos, 0 créditos (índices []). Siguiente: el meme (H0069) y la presentación (H0188).

Evidencia: `artifacts/comprobaciones/C03/DOWNLOAD2047/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 122.72 s acumulados; pico GPU 3485.56 MiB; pico RAM 2415.39 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0077 | failed | Falló: no descargó, navegó o preguntó, o el final no nombró el archivo escrito. | Turno ordinario: la imagen se descargó y se verificó; el final no se pudo componer (el nombre observado del archivo se leyó como jerga; reparación en el commit siguiente). |
| 1 | download2047-dev-01 | passed | web.download verificada en la carpeta nombrada; el final nombra el archivo escrito y su tamaño. | Turno ordinario: exactamente una web.download completada y verificada (de una página, la imagen og:image que anuncia; de un archivo, el archivo) escrita en la carpeta nombrada; el final nombra el archivo escrito y su tamaño; cero confirmaciones y violaciones; pins intactos. |
| 2 | download2047-dev-02 | failed | Falló: no descargó, navegó o preguntó, o el final no nombró el archivo escrito. | Turno ordinario: la página no anuncia imagen de portada; el fallo tipado no se pudo narrar (reparación en el commit siguiente). |
| 3 | download2047-dev-03 | failed | Falló: no descargó, navegó o preguntó, o el final no nombró el archivo escrito. | Turno ordinario: la dirección no respondió (404); el fallo tipado no se pudo narrar (reparación en el commit siguiente). |
| 4 | download2047-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | download2047-boundary-02 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 122.72 s de segmentos; pico GPU 3485.56 MiB; pico RAM 2415.39 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
