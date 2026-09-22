# TEXTREAD2061 — adjudicación de la raíz

## TEXTREAD2061 — estado vigente 2026-09-22T11:01:18.930296+00:00

Parcial: 4 aprobados, 2 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 676/742 | 66 | 0 | >=652 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 652 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); TEXTREAD2061 añade 0. No se cuentan revalidaciones.

Siguiente acción: TEXTREAD2061: 6 ejecutados, 4 aprobados, 2 fallidos, 0 créditos (índices []). Siguiente: el conteo del Explorador (H0701) y las tipadas de red.

Evidencia: `artifacts/comprobaciones/C03/TEXTREAD2061/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 94.98 s acumulados; pico GPU 3485.56 MiB; pico RAM 1712.68 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0299 | failed | Falló: no leyó la ruta, preguntó qué hacer con ella, o el final no dijo de qué trata el archivo. | Turno ordinario: la lectura falló con verdad porque el panel midió la ruta real del registro, ausente en este PC (el fixture vive bajo raiz_textos); final honesto; pins intactos. Re-medición con la ruta del fixture. |
| 1 | textread2061-dev-01 | passed | document.text.read verificada sobre la ruta pegada; el final nombra el archivo, sus líneas y de qué trata. | Turno ordinario: exactamente una document.text.read completada y verificada (carpeta conocida, subcarpeta y nombre de la ruta pegada); el final nombra el archivo, dice cuántas líneas tiene y de qué trata citando sus títulos o su comienzo tal cual; cero confirmaciones y violaciones; pins intactos. |
| 2 | textread2061-dev-02 | passed | document.text.read verificada sobre la ruta pegada; el final nombra el archivo, sus líneas y de qué trata. | Turno ordinario: exactamente una document.text.read completada y verificada (carpeta conocida, subcarpeta y nombre de la ruta pegada); el final nombra el archivo, dice cuántas líneas tiene y de qué trata citando sus títulos o su comienzo tal cual; cero confirmaciones y violaciones; pins intactos. |
| 3 | textread2061-dev-03 | failed | Falló: no leyó la ruta, preguntó qué hacer con ella, o el final no dijo de qué trata el archivo. | Turno ordinario: la lectura falló con verdad porque la ruta del panel (raiz) no es la del fixture (raiz_textos); final honesto; pins intactos. |
| 4 | textread2061-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | textread2061-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 94.98 s de segmentos; pico GPU 3485.56 MiB; pico RAM 1712.68 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
