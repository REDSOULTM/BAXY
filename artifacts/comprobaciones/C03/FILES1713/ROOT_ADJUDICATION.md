# FILES1713 — adjudicación de la raíz

## FILES1713 — estado vigente 2026-09-16T11:02:19.622773+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 612/742 | 130 | 0 | >=496 | 10/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 495 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); FILES1713 añade 1. No se cuentan revalidaciones.

Siguiente acción: FILES1713: 6 ejecutados, 5 aprobados, 1 fallidos, 1 créditos (índices [0]); Abrir aplicaciones 47/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/FILES1713/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 112.06 s acumulados; pico GPU 3497.56 MiB; pico RAM 1660.09 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0334 | passed | system.process.list y filesystem.write.text completadas y verificadas; el archivo del sandbox lista los procesos leídos; el final nombró el archivo y los procesos sin inventar; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una system.process.list y una filesystem.write.text completadas y verificadas; el archivo del sandbox lista los procesos leídos (relectura de la raíz); cero confirmaciones y violaciones; pins intactos. |
| 1 | files1713-dev-01 | passed | system.process.list y filesystem.write.text completadas y verificadas; el archivo del sandbox lista los procesos leídos; el final nombró el archivo y los procesos sin inventar. | Turno ordinario: exactamente una system.process.list y una filesystem.write.text completadas y verificadas; el archivo del sandbox lista los procesos leídos (relectura de la raíz); cero confirmaciones y violaciones; pins intactos. |
| 2 | files1713-dev-02 | passed | system.process.list y filesystem.write.text completadas y verificadas; el archivo del sandbox lista los procesos leídos; el final nombró el archivo y los procesos sin inventar. | Turno ordinario: exactamente una system.process.list y una filesystem.write.text completadas y verificadas; el archivo del sandbox lista los procesos leídos (relectura de la raíz); cero confirmaciones y violaciones; pins intactos. |
| 3 | files1713-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | files1713-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 112.06 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1660.09 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
