# FILES1587 — adjudicación de la raíz

## FILES1587 — estado vigente 2026-09-15T18:01:38.642433+00:00

Parcial: 2 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 538/742 | 204 | 0 | >=412 | 5/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 412 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); FILES1587 añade 0. No se cuentan revalidaciones.

Siguiente acción: FILES1587: 5 ejecutados, 2 aprobados, 3 fallidos, 0 créditos (índices []); Archivos y carpetas 25/32. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/FILES1587/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 86.59 s acumulados; pico GPU 3497.56 MiB; pico RAM 1637.08 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0299 | failed | Falló: operó, repitió la ruta completa, adivinó el contenido o no preguntó qué hacer con el archivo. | Turno ordinario: cero operaciones; la aclaración compuesta fue rechazada por la propia mente (nombre de archivo tomado por identificador) y el final fue una recuperación genérica; cero violaciones; pins intactos. |
| 1 | files1587-dev-01 | failed | Falló: operó, repitió la ruta completa, adivinó el contenido o no preguntó qué hacer con el archivo. | Turno ordinario: cero operaciones; la aclaración compuesta fue rechazada por la propia mente y el final fue una recuperación genérica; cero violaciones; pins intactos. |
| 2 | files1587-dev-02 | failed | Falló: operó, repitió la ruta completa, adivinó el contenido o no preguntó qué hacer con el archivo. | Turno ordinario: cero operaciones; la aclaración compuesta fue rechazada por la propia mente y la recuperación preguntó algo adivinado; cero violaciones; pins intactos. |
| 3 | files1587-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | files1587-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 86.59 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1637.08 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
