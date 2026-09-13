# NETWORK1203 — adjudicación de la raíz

## NETWORK1203 — estado vigente 2026-09-13T13:31:07+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 268/742 | 474 | 0 | >=142 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 140 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; NETWORK1203 añade 2. No se cuentan revalidaciones.

Siguiente acción: NETWORK1203 completa: 5 ejecutados, 5 aprobados, 2 créditos (H0568, H0481). Las dos reparaciones de composición se demuestran: la clave de procedencia ya no dispara el validador de palabras recortadas y las cuatro lecturas enumeran las tres direcciones. Red queda 9/21; restan wifi («decime si el wifi está prendido», redes disponibles/guardadas), bluetooth y efectos de red.

Evidencia: `artifacts/comprobaciones/C03/NETWORK1203/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 85.47 s acumulados; pico GPU 3497.56 MiB; pico RAM 1564.84 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0568 | passed | Leyó y enumeró todas las direcciones observadas; dos pares aprobados. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0481 | passed | Leyó y enumeró todas las direcciones observadas en inglés; dos pares aprobados. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | network1203-dev-01 | passed | Variante original aprobada. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | network1203-dev-02 | passed | Variante original aprobada. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 4 | network1203-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 85.47 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1564.84 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
