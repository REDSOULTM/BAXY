# SYSTEM1181 — adjudicación de la raíz

## SYSTEM1181 — estado vigente 2026-09-13T11:15:05+00:00

Parcial: 3 aprobados, 2 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 245/742 | 497 | 0 | >=119 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 119 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; SYSTEM1181 no añade. No se cuentan revalidaciones.

Siguiente acción: SYSTEM1181 completa: 5 ejecutados, 3 aprobados, 2 fallidos, 0 créditos. La reparación de la elipsis nominal se demuestra: «Y espacio?», «y disco?», «¿Y el disco?» y «And the disk?» leen el disco en vez de pedir confirmación (en SYSTEM1175 los dos literales confirmaban). Lo que impide acreditar es la etiqueta «disponibles en total» sobre total_usable en español (2 de 3 lecturas en español), el mismo defecto medido en memoria (SYSTEM1173/1177): sólo se resuelve renombrando las claves de la proyección de medidas (contrato con tests no ejecutables por orden del dueño). Estado de hardware queda 28/40; no remedir disco ni memoria sin ese cambio.

Evidencia: `artifacts/comprobaciones/C03/SYSTEM1181/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 89.27 s acumulados; pico GPU 3497.56 MiB; pico RAM 1639.56 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0219 | passed | Leyó el disco y dio el espacio libre observado; sin crédito por faltar un segundo par aprobado. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0607 | failed | Leyó el disco pero llamó «disponibles» al total. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | system1181-dev-01 | failed | Llamó «disponibles» al total del disco. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | system1181-dev-02 | passed | Variante original aprobada: disco leído con etiquetas correctas. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 4 | system1181-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 89.27 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1639.56 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
