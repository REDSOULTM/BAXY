# SYSTEM1545 — adjudicación de la raíz

## SYSTEM1545 — estado vigente 2026-09-15T05:15:27.393790+00:00

Parcial: 3 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 519/742 | 223 | 0 | >=393 | 5/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 393 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SYSTEM1545 añade 0. No se cuentan revalidaciones.

Siguiente acción: SYSTEM1545: 6 ejecutados, 3 aprobados, 3 fallidos, 0 créditos (índices []); Estado de hardware y sistema 38/40. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/SYSTEM1545/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 127.56 s acumulados; pico GPU 3497.56 MiB; pico RAM 2324.18 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0076 | failed | Falló: la lectura se verificó pero no hubo final: el compositor rechazó los borradores que llamaban instalada a la memoria total observada. | Turno ordinario: una system.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos; sin final publicado (borradores rechazados por etiquetar el total como instalado). |
| 1 | system1545-dev-01 | failed | Falló: la lectura se verificó pero no hubo final: el compositor rechazó los borradores que llamaban instalada a la memoria total observada. | Turno ordinario: una system.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos; sin final publicado (borradores rechazados por etiquetar el total como instalado). |
| 2 | system1545-dev-02 | passed | Leyó el sistema y contestó la versión de Windows y la memoria observadas sin reclamar Python ni un script; variante o literal sin dos pares aprobados. | Turno ordinario: una system.status de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos. |
| 3 | system1545-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | system1545-boundary-02 | failed | Límite fallido: cero operaciones, pero la prohibición recibió un saludo en vez de un acuse. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | system1545-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 127.56 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2324.18 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
