# KNOWLEDGE1149 — adjudicación de la raíz

## KNOWLEDGE1149 — estado vigente 2026-09-13T04:58:18+00:00

Parcial: 15 aprobados, 7 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 228/742 | 514 | 0 | >=102 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 28 Kiro + 49 retorno + H0584 + H0511 + 10 (NOTES1142) + 2 (KNOWLEDGE1144) + 7 (IDENTITY1146) + 2 (IDENTITY1148) = 100 antes de esta tanda, todas dentro de la ventana de 24 h al adjudicar; KNOWLEDGE1149 añade 2. No se cuentan revalidaciones.

Siguiente acción: KNOWLEDGE1149 completa: 22 ejecutados, 15 aprobados, 7 fallidos, 2 créditos (H0236, H0239). Las dos causas de prompt de 1144 (idioma, «SIEMPRE») no reaparecen. Nuevas causas medidas: respuestas sólo-pregunta vetadas que acaban en error de comprensión (H0703; dev-10 con el borrador útil descartado por la forma error), pedido deíctico de conversión clasificado unsupported (límite), y hechos inventados del modelo (BvS, moneda-satélite). Conocimiento queda 22/37. Siguiente: conversación social (12) y reloj (10); las causas de veto→error merecen sonda sin GPU antes de otra tanda de conocimiento.

Evidencia: `artifacts/comprobaciones/C03/KNOWLEDGE1149/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 419.39 s acumulados; pico GPU 3497.56 MiB; pico RAM 2353.72 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 22; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0211 | failed | Ofreció elegir el tipo de chiste en vez de contarlo. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0236 | passed | Explicó el juego con hechos correctos y sin inventar; dos variantes aprobadas. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0239 | passed | Comparó con criterio y sin hechos inventados; dos variantes aprobadas. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0582 | failed | Cerró la comparación con un dato de película inventado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0703 | failed | Publicó una incomprensión tras vetar dos respuestas que sólo preguntaban. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0297 | passed | Respondió con una paráfrasis útil y sin fuga del prompt; sin crédito por faltar un segundo par aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | H0030 | failed | Deflexión sin contenido ante una pregunta ambigua. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | knowledge1149-dev-01 | passed | Variante original aprobada: chiste directo. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | knowledge1149-dev-02 | passed | Variante original aprobada: chiste directo en inglés. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | knowledge1149-dev-03 | passed | Variante original aprobada: hechos correctos del juego. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | knowledge1149-dev-04 | passed | Variante original aprobada: hechos correctos del juego. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | knowledge1149-dev-05 | passed | Variante original aprobada: comparación con criterio. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | knowledge1149-dev-06 | passed | Variante original aprobada: comparación factual correcta. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 13 | knowledge1149-dev-07 | passed | Variante original aprobada: comparación razonada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 14 | knowledge1149-dev-08 | failed | Dato curioso inventado y físicamente falso. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 15 | knowledge1149-dev-09 | passed | Variante original aprobada: dato correcto. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 16 | knowledge1149-dev-10 | failed | Publicó una incomprensión; el borrador con la propuesta se descartó por la forma de error. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 17 | knowledge1149-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 18 | knowledge1149-boundary-02 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 19 | knowledge1149-boundary-03 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 20 | knowledge1149-boundary-04 | failed | Negó la conversión en vez de pedir el valor ausente. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 21 | knowledge1149-boundary-05 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 419.39 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2353.72 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
