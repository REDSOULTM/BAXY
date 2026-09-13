# SYSTEM1175 — adjudicación de la raíz

## SYSTEM1175 — estado vigente 2026-09-13T07:25:42+00:00

Parcial: 6 aprobados, 3 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 245/742 | 497 | 0 | >=119 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 118 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; SYSTEM1175 añade 1. No se cuentan revalidaciones.

Siguiente acción: SYSTEM1175 completa: 9 ejecutados, 6 aprobados, 3 fallidos, 1 crédito (H0146). La reparación del scope de disco se demuestra en las formas directas; las formas elípticas/coloquiales (H0219 «Y espacio?», H0607 «y disco?», H0532 «tirame…») siguen en pregunta de confirmación de dominio del planificador aunque tengan scope: causa común con «decime si el wifi…» (ruta de confirmación para propuestas del modelo con cabeza no determinista). Estado de hardware queda 28/40. Siguiente: localizar en __main__ por qué una propuesta del modelo con dominio y scope válidos pasa a domain_confirmation en estos textos.

Evidencia: `artifacts/comprobaciones/C03/SYSTEM1175/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 142.28 s acumulados; pico GPU 3497.56 MiB; pico RAM 1637.69 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0146 | passed | Leyó el disco y dio el espacio libre observado; dos variantes aprobadas. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0219 | failed | Pidió confirmación en vez de leer el disco. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0607 | failed | Pidió confirmación en vez de leer el disco. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0532 | failed | Pidió confirmación en vez de leer la memoria. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | system1175-dev-01 | passed | Variante original aprobada: espacio libre leído. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 5 | system1175-dev-02 | passed | Variante original aprobada: espacio libre leído. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 6 | system1175-dev-03 | passed | Variante original aprobada: RAM total leída. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 7 | system1175-dev-04 | passed | Variante original aprobada: RAM leída. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 8 | system1175-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 142.28 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1637.69 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
