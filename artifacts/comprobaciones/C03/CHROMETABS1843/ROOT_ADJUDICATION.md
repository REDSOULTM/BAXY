# CHROMETABS1843 — adjudicación de la raíz

## CHROMETABS1843 — estado vigente 2026-09-17T17:17:27.887528+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 653/742 | 89 | 0 | >=537 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 536 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); CHROMETABS1843 añade 1. No se cuentan revalidaciones.

Siguiente acción: CHROMETABS1843: 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos (índices [0]); Organizar ventanas y pestañas 13/13. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/CHROMETABS1843/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 84.03 s acumulados; pico GPU 3497.56 MiB; pico RAM 1610.59 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0444 | passed | browser.control con close_all completada y verificada (todas las pestanas del navegador propio cerradas, ninguna queda); el final dijo que cerro todas las pestanas del navegador; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una browser.control con accion close_all completada y verificada (todas las pestanas del navegador CDP propio cerradas, ninguna queda); el final dijo en pasado que cerro todas las pestanas del navegador; cero confirmaciones y violaciones; pins intactos. |
| 1 | chrometabs1843-dev-01 | passed | browser.control con close_all completada y verificada (todas las pestanas del navegador propio cerradas, ninguna queda); el final dijo que cerro todas las pestanas del navegador. | Turno ordinario: exactamente una browser.control con accion close_all completada y verificada (todas las pestanas del navegador CDP propio cerradas, ninguna queda); el final dijo en pasado que cerro todas las pestanas del navegador; cero confirmaciones y violaciones; pins intactos. |
| 2 | chrometabs1843-dev-02 | passed | browser.control con close_all completada y verificada (todas las pestanas del navegador propio cerradas, ninguna queda); el final dijo que cerro todas las pestanas del navegador. | Turno ordinario: exactamente una browser.control con accion close_all completada y verificada (todas las pestanas del navegador CDP propio cerradas, ninguna queda); el final dijo en pasado que cerro todas las pestanas del navegador; cero confirmaciones y violaciones; pins intactos. |
| 3 | chrometabs1843-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | chrometabs1843-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 84.03 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1610.59 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
