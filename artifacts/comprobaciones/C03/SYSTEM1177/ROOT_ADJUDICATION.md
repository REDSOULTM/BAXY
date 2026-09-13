# SYSTEM1177 — adjudicación de la raíz

## SYSTEM1177 — estado vigente 2026-09-13T07:30:51+00:00

Parcial: 2 aprobados, 2 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 245/742 | 497 | 0 | >=119 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 119 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; SYSTEM1177 no añade. No se cuentan revalidaciones.

Siguiente acción: SYSTEM1177 completa: 4 ejecutados, 2 aprobados, 2 fallidos, 0 créditos. «tirame» demostrado (lectura en vez de confirmación); la etiqueta «disponible» para total_usable persiste en 2 de 3 lecturas de memoria (también H0508 en 1173): sólo se resuelve cambiando la proyección de claves (measurement_prose_projection, contrato con tests): decisión del dueño. Estado de hardware 28/40; no remedir memoria sin ese cambio.

Evidencia: `artifacts/comprobaciones/C03/SYSTEM1177/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 65.87 s acumulados; pico GPU 3497.56 MiB; pico RAM 1591.37 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 4; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0532 | failed | Leyó la memoria pero llamó «disponible» al total. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | system1177-dev-01 | failed | Llamó «disponibles» a la RAM total. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | system1177-dev-02 | passed | Variante original aprobada: RAM instalada leída. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | system1177-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 65.87 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1591.37 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
