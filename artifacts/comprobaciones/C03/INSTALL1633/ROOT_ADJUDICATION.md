# INSTALL1633 — adjudicación de la raíz

## INSTALL1633 — estado vigente 2026-09-16T00:31:56.393190+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 580/742 | 162 | 0 | >=454 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 453 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); INSTALL1633 añade 1. No se cuentan revalidaciones.

Siguiente acción: INSTALL1633: 6 ejecutados, 5 aprobados, 1 fallidos, 1 créditos (índices [0]); Abrir aplicaciones 47/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/INSTALL1633/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 87.70 s acumulados; pico GPU 3497.56 MiB; pico RAM 1730.17 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0608 | passed | Lectura completada y verificada (biblioteca de Steam o catálogo de inicio); el final dijo lo observado sin instalar ni quitar nada; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: una lectura (game.entitlement.named del título o app.installed del nombre) completada y verificada; nada instalado, descargado ni quitado; cero confirmaciones y violaciones; pins intactos. |
| 1 | install1633-dev-01 | passed | Lectura completada y verificada (biblioteca de Steam o catálogo de inicio); el final dijo lo observado sin instalar ni quitar nada. | Turno ordinario: una lectura (game.entitlement.named del título o app.installed del nombre) completada y verificada; nada instalado, descargado ni quitado; cero confirmaciones y violaciones; pins intactos. |
| 2 | install1633-dev-02 | passed | Lectura completada y verificada (biblioteca de Steam o catálogo de inicio); el final dijo lo observado sin instalar ni quitar nada. | Turno ordinario: una lectura (game.entitlement.named del título o app.installed del nombre) completada y verificada; nada instalado, descargado ni quitado; cero confirmaciones y violaciones; pins intactos. |
| 3 | install1633-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | install1633-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 87.70 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1730.17 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
