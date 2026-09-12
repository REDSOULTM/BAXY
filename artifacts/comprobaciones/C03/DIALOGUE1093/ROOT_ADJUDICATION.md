# DIALOGUE1093 — adjudicación de la raíz

## DIALOGUE1093 — estado vigente 2026-09-12T20:55:24.6551435Z

Parcial: 12 aprobados, 5 fallidos, 8 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 197/742 | 545 | 0 | >=71 | 0/35 |

Procedencia de primeras altas: Al menos 28 primeras altas de Kiro y 41 del retorno acreditadas el 12 de septiembre, más las nuevas de esta tanda. No se cuentan revalidaciones.

Siguiente acción: Ejecutar AGENDA1097, ocho literales preparados de primera aclaración sin efectos. Ocho literales de DIALOGUE1093 quedan sin ejecutar por pares incompletos; requieren reparar las familias fallidas antes de otra tanda. Propuesta 1098 revisada, aún sin integrar ni medir. No se declara cierre de categoría ni de C03.

Evidencia: `artifacts/comprobaciones/C03/DIALOGUE1093/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 463.72 s acumulados; pico GPU 3497.56 MiB; pico RAM 2312.77 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 10 | dialogue1093-dev-01 | failed | Inventó una causa para un fragmento del relato del usuario. | La respuesta confundió el contenido expresado con un fallo de interpretación del producto. Sin operaciones adicionales. |
| 11 | dialogue1093-dev-02 | passed | Aclaración pertinente al fragmento. | Pidió el contexto que faltaba sin inventar hechos ni realizar operaciones. |
| 12 | dialogue1093-dev-03 | passed | Pidió aclarar a qué se refería el término aislado. | Presentó las interpretaciones como pregunta, sin afirmar un propósito ni ejecutar operaciones. |
| 13 | dialogue1093-dev-04 | passed | Pidió el referente ausente. | Aclaración contextual breve sin inventar el contenido ni realizar operaciones. |
| 2 | H0313 | passed | Aclaró el referente y el propósito del fragmento. | Literal útil con dos variantes pertinentes aprobadas, sin hechos inventados ni operaciones. |
| 5 | H0349 | passed | Aclaró el término aislado sin asumir su significado. | Literal útil y fiel con dos variantes pertinentes aprobadas. |
| 14 | dialogue1093-dev-05 | failed | Respuesta inconexa a una negativa breve. | No reconoció de forma útil la preferencia expresada. No realizó operaciones. |
| 15 | dialogue1093-dev-06 | passed | Reconoció la negativa sin inventar una cancelación. | Respuesta natural y sin efectos. |
| 16 | dialogue1093-dev-07 | failed | La entrada numérica acabó en una avería de interpretación. | No produjo el reconocimiento o la aclaración útil requerida. Sin efectos. |
| 17 | dialogue1093-dev-08 | failed | Convirtió una entrada numérica en una petición fuera de capacidad. | No dio el reconocimiento o la aclaración contextual requerida. Sin efectos. |
| 18 | dialogue1093-dev-09 | passed | Pidió qué necesitaba la persona sin reconstruir el dato oculto. | La pregunta solicita el propósito ausente y no realiza operaciones. |
| 19 | dialogue1093-dev-10 | failed | El marcador sin contexto acabó en una avería de interpretación. | No produjo una aclaración útil; no reconstruyó datos ni realizó operaciones. |
| 20 | dialogue1004-boundary-01 | passed | Respetó la petición de esperar sin actuar ni preguntar. | Reconocimiento breve y ausencia de operaciones. |
| 21 | dialogue1004-boundary-04 | passed | Explicó correctamente el concepto solicitado. | Respuesta directa, útil y sin operaciones. |
| 22 | clarify1043-boundary-01 | passed | Respetó la abstención y la intención de explicarse después. | No abrió nada ni inventó un encargo pendiente. |
| 23 | clarify1043-boundary-04 | passed | Resolvió correctamente el cálculo sencillo. | Respuesta directa sin operaciones. |
| 24 | clarify1043-boundary-05 | passed | Reconoció honestamente el límite de una acción física. | No fingió realizar la acción ni tener capacidad para hacerla. |

Recursos: 463.72 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2312.77 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
