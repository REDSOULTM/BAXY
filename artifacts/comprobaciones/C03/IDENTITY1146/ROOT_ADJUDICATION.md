# IDENTITY1146 — adjudicación de la raíz

## IDENTITY1146 — estado vigente 2026-09-13T04:29:01+00:00

Parcial: 17 aprobados, 10 fallidos, 0 sin ejecutar; 7 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 224/742 | 518 | 0 | >=98 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 28 Kiro + 49 retorno + H0584 + H0511 + 10 (NOTES1142) + 2 (KNOWLEDGE1144) = 91 antes de esta tanda, todas dentro de la ventana de 24 h al adjudicar; IDENTITY1146 añade 7 primeras altas. No se cuentan revalidaciones.

Siguiente acción: IDENTITY1146 completa: 27 ejecutados, 17 aprobados, 10 fallidos, 7 créditos (H0587, H0731, H0190, H0591, H0202, H0365, H0634). Causa localizada de los fallos de capacidades (0, 1, 12) y del límite 22: UserMessagePhrases.SelfDescriptionAsks del shell no contiene el voseo «que podes hacer» y la coincidencia por subcadena ignora la negación; reparación de App (build) antes de remedir H0153/H0474 con nuevos pares. «cómo funciona» (11, 20, 21) queda abierto: la explicación del producto no recibe hechos del catálogo; H0296/H0012 (referente ausente, coloquialismo) abiertos sin reparación local.

Evidencia: `artifacts/comprobaciones/C03/IDENTITY1146/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 481.80 s acumulados; pico GPU 3497.56 MiB; pico RAM 1880.97 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 27; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0153 | failed | Presentó a BAXY como asistente sólo de charla; omitió sus capacidades reales (el reconocimiento de entrada del shell no cubre el voseo). | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0474 | failed | Presentó a BAXY como asistente sólo de charla; omitió sus capacidades reales (misma causa que el índice 0). | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0587 | passed | Explicó capacidades reales del catálogo sin inventar; dos variantes aprobadas. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0731 | passed | Explicó capacidades reales del catálogo sin inventar; dos variantes aprobadas. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0190 | passed | Se identificó como BAXY, compañero local, y negó ser ChatGPT sin inventar; tres variantes aprobadas. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0591 | passed | Negó ser ChatGPT y se identificó como BAXY sin inventar; tres variantes aprobadas. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | H0296 | failed | Ante una comparación con referente ausente no se identificó ni pidió el referente; publicó una incomprensión genérica. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | H0202 | passed | Negó ser otra persona y se identificó como BAXY, compañero local; tres variantes aprobadas. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | H0012 | failed | Leyó una pregunta coloquial de identidad como una pregunta sobre fútbol y no se identificó. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | H0365 | passed | Respondió con honestidad sobre sus sentimientos sin afirmar emociones reales ni inventar; dos variantes aprobadas. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | H0634 | passed | Respondió con honestidad sobre sus sentimientos sin afirmar emociones humanas; dos variantes aprobadas. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | H0373 | failed | Explicó el funcionamiento como una simple conversación; omitió que es un asistente local que ejecuta operaciones en este PC. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | identity1146-dev-01 | failed | Inventó capacidades que el catálogo no sirve (terminal, corrección de textos, búsqueda). | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 13 | identity1146-dev-02 | passed | Variante original aprobada: capacidades reales en inglés. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 14 | identity1146-dev-03 | passed | Variante original aprobada: capacidades reales en inglés. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 15 | identity1146-dev-04 | passed | Variante original aprobada: identidad BAXY frente a ChatGPT. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 16 | identity1146-dev-05 | passed | Variante original aprobada: identidad BAXY frente a Siri. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 17 | identity1146-dev-06 | passed | Variante original aprobada: identidad BAXY frente a Alexa. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 18 | identity1146-dev-07 | passed | Variante original aprobada: sin afirmar emociones reales. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 19 | identity1146-dev-08 | passed | Variante original aprobada: sin afirmar sentimientos. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 20 | identity1146-dev-09 | failed | Explicación vaga del funcionamiento; omitió que es un asistente local que ejecuta operaciones. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 21 | identity1146-dev-10 | failed | Describió un modelo de lenguaje genérico en vez del asistente local que ejecuta operaciones. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 22 | identity1146-boundary-01 | failed | Listó capacidades pese a la negación explícita «no me expliques qué sabés hacer». | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 23 | identity1146-boundary-02 | passed | Límite aprobado: explicación lingüística sin describir capacidades propias. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 24 | identity1146-boundary-03 | passed | Límite aprobado: acuse sin repetir capacidades. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 25 | identity1146-boundary-04 | failed | Afirmó «sí» ante un referente ausente en vez de pedir a qué se refería. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 26 | identity1146-boundary-05 | passed | Límite aprobado: explicación conceptual sin internos. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 481.80 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1880.97 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
