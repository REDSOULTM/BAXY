# INSTALL1627 — adjudicación de la raíz

## INSTALL1627 — estado vigente 2026-09-16T00:02:24.573337+00:00

Parcial: 7 aprobados, 0 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 574/742 | 168 | 0 | >=448 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 445 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); INSTALL1627 añade 3. No se cuentan revalidaciones.

Siguiente acción: INSTALL1627: 6 ejecutados, 7 aprobados, -1 fallidos, 3 créditos (índices [0, 1, 2]); Abrir aplicaciones 49/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/INSTALL1627/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 114.74 s acumulados; pico GPU 3497.56 MiB; pico RAM 1593.51 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 7; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0083 | passed | Lectura completada y verificada (biblioteca de Steam o catálogo de inicio); el final dijo lo observado sin instalar ni quitar nada; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: una lectura (game.entitlement.named del título o app.installed del nombre) completada y verificada; nada instalado, descargado ni quitado; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0396 | passed | Lectura completada y verificada (biblioteca de Steam o catálogo de inicio); el final dijo lo observado sin instalar ni quitar nada; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: una lectura (game.entitlement.named del título o app.installed del nombre) completada y verificada; nada instalado, descargado ni quitado; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0456 | passed | Lectura completada y verificada (biblioteca de Steam o catálogo de inicio); el final dijo lo observado sin instalar ni quitar nada; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: una lectura (game.entitlement.named del título o app.installed del nombre) completada y verificada; nada instalado, descargado ni quitado; cero confirmaciones y violaciones; pins intactos. |
| 3 | install1627-dev-01 | passed | Lectura completada y verificada (biblioteca de Steam o catálogo de inicio); el final dijo lo observado sin instalar ni quitar nada. | Turno ordinario: una lectura (game.entitlement.named del título o app.installed del nombre) completada y verificada; nada instalado, descargado ni quitado; cero confirmaciones y violaciones; pins intactos. |
| 4 | install1627-dev-02 | passed | Lectura completada y verificada (biblioteca de Steam o catálogo de inicio); el final dijo lo observado sin instalar ni quitar nada. | Turno ordinario: una lectura (game.entitlement.named del título o app.installed del nombre) completada y verificada; nada instalado, descargado ni quitado; cero confirmaciones y violaciones; pins intactos. |
| 5 | install1627-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | install1627-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 114.74 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1593.51 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
