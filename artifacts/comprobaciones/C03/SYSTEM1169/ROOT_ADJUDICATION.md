# SYSTEM1169 — adjudicación de la raíz

## SYSTEM1169 — estado vigente 2026-09-13T06:59:51+00:00

Parcial: 9 aprobados, 2 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 243/742 | 499 | 0 | >=117 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 116 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; SYSTEM1169 añade 1. No se cuentan revalidaciones.

Siguiente acción: SYSTEM1169 completa: 11 ejecutados, 9 aprobados, 2 fallidos, 1 crédito (H0037). Causas medidas: H0508 etiqueta la RAM total como «disponible» (compositor; validador de RAM sólo exige conservar el número); «¿Cuánto uso tiene la GPU ahora?» eligió el scope summary sin GPU. H0114 aprobado sin crédito (un solo par de GPU). Estado de hardware queda 26/40. Siguiente: validador de etiqueta de memoria (total/disponible) en llm._payload_fact_defect y selección de scope GPU para «uso… GPU»; después remedir H0508/H0114 con pares.

Evidencia: `artifacts/comprobaciones/C03/SYSTEM1169/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 179.72 s acumulados; pico GPU 3497.56 MiB; pico RAM 1641.50 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 11; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0037 | passed | Leyó la batería y dijo que no está cargando, según lo observado; dos variantes aprobadas. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0114 | passed | Leyó la GPU y dio el uso de VRAM observado; sin crédito por faltar un segundo par aprobado. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0508 | failed | Versión correcta, pero presentó la RAM total como «disponible». | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | system1169-dev-01 | passed | Variante original aprobada: batería leída. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 4 | system1169-dev-02 | passed | Variante original aprobada: batería leída. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 5 | system1169-dev-03 | failed | Leyó el resumen del equipo sin la GPU y no pudo dar su uso. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 6 | system1169-dev-04 | passed | Variante original aprobada: GPU leída con sus números. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 7 | system1169-dev-05 | passed | Variante original aprobada: versión y RAM leídas y bien etiquetadas. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 8 | system1169-dev-06 | passed | Variante original aprobada: versión y RAM leídas. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 9 | system1169-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | system1169-boundary-02 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 179.72 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1641.50 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
