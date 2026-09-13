# SYSTEM1183 — adjudicación de la raíz

## SYSTEM1183 — estado vigente 2026-09-13T11:29:43+00:00

Parcial: 7 aprobados, 3 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 246/742 | 496 | 0 | >=120 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 119 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; SYSTEM1183 añade 1 (H0607). No se cuentan revalidaciones.

Siguiente acción: SYSTEM1183 completa: 10 ejecutados, 7 aprobados, 3 fallidos, 1 crédito (H0607). El renombrado de claves (total/free/used) se demuestra: ninguna de las seis lecturas llama «disponible» al total (antes 2 de 3). Fallos restantes: H0508 llama «instalados» al total (la instalada es 17,18 GB): confusión total/instalada del modelo, distinta de la anterior; los dos pares de memoria con pedido doble (total + libre) terminan en aclaración porque la recuperación léxica de candidatos no propone system.status (candidate_operations vacío → explicit_conversation → unsupported → recuperación): reparar la recuperación de candidatos para «cuánta RAM… y cuánta queda libre» antes de remedir H0532. Estado de hardware queda 29/40.

Evidencia: `artifacts/comprobaciones/C03/SYSTEM1183/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 166.17 s acumulados; pico GPU 3497.56 MiB; pico RAM 1606.94 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0508 | failed | Versión correcta; llamó «instalados» al total de RAM (la instalada es otra cifra). | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0532 | passed | Leyó la memoria y dio el total sin etiqueta falsa; sin crédito por faltar los pares. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0607 | passed | Leyó el disco con etiquetas correctas; dos pares aprobados. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | system1183-dev-01 | passed | Variante original aprobada. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 4 | system1183-dev-02 | passed | Variante original aprobada. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 5 | system1183-dev-03 | failed | Pidió confirmación en vez de leer la memoria. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | system1183-dev-04 | failed | Pidió aclaración en vez de leer la memoria. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | system1183-dev-05 | passed | Variante original aprobada. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 8 | system1183-dev-06 | passed | Variante original aprobada. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 9 | system1183-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 166.17 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1606.94 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
