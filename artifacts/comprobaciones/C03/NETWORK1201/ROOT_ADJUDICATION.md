# NETWORK1201 — adjudicación de la raíz

## NETWORK1201 — estado vigente 2026-09-13T13:26:39+00:00

Parcial: 4 aprobados, 2 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 266/742 | 476 | 0 | >=140 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 139 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; NETWORK1201 añade 1. No se cuentan revalidaciones.

Siguiente acción: NETWORK1201 completa: 6 ejecutados, 4 aprobados, 2 fallidos, 1 crédito (H0455). La lectura de IP sin confirmación (BUILD1201) y el lector/dominio se demuestran en las cinco lecturas. Fallos de composición: H0568 dio una sola dirección; H0481 agotó la composición por el falso positivo de _truncated_fact_word con la clave de procedencia «authority» («address» frente a «…_addresses_…»). Siguiente: excluir «authority» de los hechos comparables (como observationScope, unit y operation), línea de alcance para enumerar todas las direcciones observadas, y remedir H0568/H0481 con pares (NETWORK1203).

Evidencia: `artifacts/comprobaciones/C03/NETWORK1201/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 114.36 s acumulados; pico GPU 3497.56 MiB; pico RAM 2362.39 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0455 | passed | Leyó las direcciones IP sin confirmación y las enumeró todas; dos pares aprobados. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0568 | failed | Dio una sola de las tres direcciones observadas. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0481 | failed | Leyó las direcciones pero publicó un código interno en vez de la respuesta. | Final revisado con una admisión; una lectura verificada; el texto final fue un código de diagnóstico; pins intactos. |
| 3 | network1201-dev-01 | passed | Variante original aprobada. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 4 | network1201-dev-02 | passed | Variante original aprobada. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 5 | network1201-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 114.36 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2362.39 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
