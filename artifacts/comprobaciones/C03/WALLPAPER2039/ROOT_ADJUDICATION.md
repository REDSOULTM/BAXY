# WALLPAPER2039 — adjudicación de la raíz

## WALLPAPER2039 — estado vigente 2026-09-22T04:39:31.355759+00:00

Parcial: 5 aprobados, 1 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 672/742 | 70 | 0 | >=648 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 647 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WALLPAPER2039 añade 1. No se cuentan revalidaciones.

Siguiente acción: WALLPAPER2039: 6 ejecutados, 5 aprobados, 1 fallidos, 1 créditos (índices [0]). Siguiente: las tipadas de archivos (zip, ruta pegada, conteo del Explorador) y las de red.

Evidencia: `artifacts/comprobaciones/C03/WALLPAPER2039/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 101.84 s acumulados; pico GPU 3485.56 MiB; pico RAM 2109.78 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0459 | passed | desktop.wallpaper.set verificada sin preguntar; el final dice el color aplicado; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una desktop.wallpaper.set completada y verificada (color liso aplicado por SPI y releído del registro); el final dice el color aplicado; cero confirmaciones y violaciones; pins intactos. |
| 1 | wallpaper2039-dev-01 | failed | Falló: no cambió el fondo, preguntó, o el final no dijo el color aplicado. | Turno ordinario: el fondo cambió y se releyó; el final no se pudo componer (heurística de lectura del narrador; reparación en el commit siguiente). |
| 2 | wallpaper2039-dev-02 | passed | desktop.wallpaper.set verificada sin preguntar; el final dice el color aplicado. | Turno ordinario: exactamente una desktop.wallpaper.set completada y verificada (color liso aplicado por SPI y releído del registro); el final dice el color aplicado; cero confirmaciones y violaciones; pins intactos. |
| 3 | wallpaper2039-dev-03 | passed | desktop.wallpaper.set verificada sin preguntar; el final dice el color aplicado. | Turno ordinario: exactamente una desktop.wallpaper.set completada y verificada (color liso aplicado por SPI y releído del registro); el final dice el color aplicado; cero confirmaciones y violaciones; pins intactos. |
| 4 | wallpaper2039-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | wallpaper2039-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 101.84 s de segmentos; pico GPU 3485.56 MiB; pico RAM 2109.78 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
