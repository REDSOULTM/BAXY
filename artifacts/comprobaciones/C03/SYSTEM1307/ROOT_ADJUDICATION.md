# SYSTEM1307 — adjudicación de la raíz

## SYSTEM1307 — estado vigente 2026-09-14T02:13:16.963260+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 382/742 | 360 | 0 | >=256 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 255 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SYSTEM1307 añade 1. No se cuentan revalidaciones.

Siguiente acción: SYSTEM1307: 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos (índices [0]). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/SYSTEM1307/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 82.22 s acumulados; pico GPU 3497.56 MiB; pico RAM 1584.24 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0508 | passed | Lectura verificada y respuesta fiel; crédito con dos variantes aprobadas. | Turno ordinario: system.status de sólo lectura completada y verificada (dos lecturas coherentes); cero confirmaciones y violaciones; pins intactos. |
| 1 | system1307-dev-01 | passed | Lectura verificada y respuesta fiel. | Turno ordinario: system.status de sólo lectura completada y verificada (dos lecturas coherentes); cero confirmaciones y violaciones; pins intactos. |
| 2 | system1307-dev-02 | passed | Lectura verificada y respuesta fiel. | Turno ordinario: system.status de sólo lectura completada y verificada (dos lecturas coherentes); cero confirmaciones y violaciones; pins intactos. |
| 3 | system1307-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | system1307-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 82.22 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1584.24 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
