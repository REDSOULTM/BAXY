# SYSTEM1547 — adjudicación de la raíz

## SYSTEM1547 — estado vigente 2026-09-15T05:24:02.397221+00:00

Parcial: 5 aprobados, 1 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 520/742 | 222 | 0 | >=394 | 5/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 393 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SYSTEM1547 añade 1. No se cuentan revalidaciones.

Siguiente acción: SYSTEM1547: 6 ejecutados, 5 aprobados, 1 fallidos, 1 créditos (índices [0]); Estado de hardware y sistema 39/40. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/SYSTEM1547/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 106.95 s acumulados; pico GPU 3497.56 MiB; pico RAM 2075.01 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0076 | passed | Leyó el sistema y contestó la versión de Windows y la memoria observadas sin reclamar Python ni un script; crédito con dos variantes aprobadas del grupo. | Turno ordinario: una system.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 1 | system1547-dev-01 | passed | Leyó el sistema y contestó la versión de Windows y la memoria observadas sin reclamar Python ni un script; variante o literal sin dos pares aprobados. | Turno ordinario: una system.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 2 | system1547-dev-02 | passed | Leyó el sistema y contestó la versión de Windows y la memoria observadas sin reclamar Python ni un script; variante o literal sin dos pares aprobados. | Turno ordinario: una system.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 3 | system1547-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | system1547-boundary-02 | failed | Límite fallido: cero operaciones, pero el acuse de la prohibición no llegó a publicarse (borrador con pregunta y reintento vacío). | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | system1547-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 106.95 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2075.01 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
