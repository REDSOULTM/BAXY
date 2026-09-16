# APPS1673 — adjudicación de la raíz

## APPS1673 — estado vigente 2026-09-16T04:38:29.740747+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 601/742 | 141 | 0 | >=475 | 8/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 474 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); APPS1673 añade 1. No se cuentan revalidaciones.

Siguiente acción: APPS1673: 6 ejecutados, 5 aprobados, 1 fallidos, 1 créditos (índices [0]); Abrir aplicaciones 47/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/APPS1673/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 88.14 s acumulados; pico GPU 3497.56 MiB; pico RAM 1630.92 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0322 | passed | Lectura app.installed completada y verificada (ausente); el final dijo que el programa no está instalado sin abrir nada; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una app.installed de sólo lectura completada y verificada (ausente), ninguna apertura; el final dice que no está instalado; cero confirmaciones y violaciones; pins intactos. |
| 1 | apps1673-dev-01 | passed | Lectura app.installed completada y verificada (ausente); el final dijo que el programa no está instalado sin abrir nada. | Turno ordinario: exactamente una app.installed de sólo lectura completada y verificada (ausente), ninguna apertura; el final dice que no está instalado; cero confirmaciones y violaciones; pins intactos. |
| 2 | apps1673-dev-02 | passed | Lectura app.installed completada y verificada (ausente); el final dijo que el programa no está instalado sin abrir nada. | Turno ordinario: exactamente una app.installed de sólo lectura completada y verificada (ausente), ninguna apertura; el final dice que no está instalado; cero confirmaciones y violaciones; pins intactos. |
| 3 | apps1673-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | apps1673-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 88.14 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1630.92 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
