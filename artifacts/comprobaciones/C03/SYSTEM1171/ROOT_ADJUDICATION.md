# SYSTEM1171 — adjudicación de la raíz

## SYSTEM1171 — estado vigente 2026-09-13T07:08:46+00:00

Parcial: 5 aprobados, 2 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 243/742 | 499 | 0 | >=117 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 117 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; SYSTEM1171 no añade. No se cuentan revalidaciones.

Siguiente acción: SYSTEM1171 completa: 7 ejecutados, 5 aprobados, 2 fallidos, 0 créditos. La reparación del scope GPU se demuestra en español («¿Cuánto uso tiene la GPU ahora?» → 5.01 GB dedicados) pero no cubre «in use» en inglés; el validador mislabeled_memory produjo agotamiento de reintentos y un código interno en H0508: retirado (queda la etiqueta falsa como causa abierta: el modelo traduce total_usable como «disponible»; candidato: renombrar claves de la proyección de memoria). H0114 sigue aprobado sin crédito. Estado de hardware 26/40.

Evidencia: `artifacts/comprobaciones/C03/SYSTEM1171/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 129.17 s acumulados; pico GPU 3497.56 MiB; pico RAM 2334.60 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 7; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0114 | passed | Leyó la GPU y dio el uso observado; sin crédito por faltar un segundo par aprobado. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0508 | failed | El validador nuevo rechazó todos los borradores y el shell publicó un código interno; validador retirado. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | system1171-dev-01 | passed | Variante original aprobada: uso de GPU leído. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | system1171-dev-02 | failed | Leyó el resumen sin GPU y negó una capacidad que tiene. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 4 | system1171-dev-03 | passed | Variante original aprobada: versión y RAM total leídas. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 5 | system1171-dev-04 | passed | Variante original aprobada: versión y RAM total leídas. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 6 | system1171-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 129.17 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2334.60 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
