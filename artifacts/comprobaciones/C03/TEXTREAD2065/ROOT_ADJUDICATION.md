# TEXTREAD2065 — adjudicación de la raíz

## TEXTREAD2065 — estado vigente 2026-09-22T11:50:21.902198+00:00

Parcial: 6 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 677/742 | 65 | 0 | >=653 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 652 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); TEXTREAD2065 añade 1. No se cuentan revalidaciones.

Siguiente acción: TEXTREAD2065: 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos (índices [0]). Siguiente: el conteo del Explorador (H0701) y las tipadas de red.

Evidencia: `artifacts/comprobaciones/C03/TEXTREAD2065/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 93.00 s acumulados; pico GPU 3485.56 MiB; pico RAM 1602.19 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0299 | passed | document.text.read verificada sobre la ruta pegada; el final nombra el archivo, sus líneas y de qué trata; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una document.text.read completada y verificada (carpeta conocida, subcarpeta y nombre de la ruta pegada); el final nombra el archivo, dice cuántas líneas tiene y de qué trata citando sus títulos o su comienzo tal cual; cero confirmaciones y violaciones; pins intactos. |
| 1 | textread2065-dev-01 | passed | document.text.read verificada sobre la ruta pegada; el final nombra el archivo, sus líneas y de qué trata. | Turno ordinario: exactamente una document.text.read completada y verificada (carpeta conocida, subcarpeta y nombre de la ruta pegada); el final nombra el archivo, dice cuántas líneas tiene y de qué trata citando sus títulos o su comienzo tal cual; cero confirmaciones y violaciones; pins intactos. |
| 2 | textread2065-dev-02 | passed | document.text.read verificada sobre la ruta pegada; el final nombra el archivo, sus líneas y de qué trata. | Turno ordinario: exactamente una document.text.read completada y verificada (carpeta conocida, subcarpeta y nombre de la ruta pegada); el final nombra el archivo, dice cuántas líneas tiene y de qué trata citando sus títulos o su comienzo tal cual; cero confirmaciones y violaciones; pins intactos. |
| 3 | textread2065-dev-03 | passed | document.text.read verificada sobre la ruta pegada; el final nombra el archivo, sus líneas y de qué trata. | Turno ordinario: exactamente una document.text.read completada y verificada (carpeta conocida, subcarpeta y nombre de la ruta pegada); el final nombra el archivo, dice cuántas líneas tiene y de qué trata citando sus títulos o su comienzo tal cual; cero confirmaciones y violaciones; pins intactos. |
| 4 | textread2065-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | textread2065-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 93.00 s de segmentos; pico GPU 3485.56 MiB; pico RAM 1602.19 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
