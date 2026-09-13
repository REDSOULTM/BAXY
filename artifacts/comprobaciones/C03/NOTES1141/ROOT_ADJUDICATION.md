# NOTES1141 — adjudicación de la raíz

## NOTES1141 — estado vigente 2026-09-13T02:15:30+00:00

Parcial: 14 aprobados, 12 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 205/742 | 537 | 0 | >=79 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 28 Kiro + 49 retorno + H0584 (MESSAGING1140), todas dentro de la ventana de 24 h al adjudicar; NOTES1141 añade H0511. No se cuentan revalidaciones ni verification_updated_at.

Siguiente acción: NOTES1141: 26 ejecutados, 15 aprobados, 11 fallidos; +1 H0511. Siete literales de creación aprobados sin crédito por falta de dos variantes de creación aprobadas (sólo índice 13). Causa común de los fallos demostrada sin GPU: huecos de la gramática cerrada de notas (dos puntos sin espacio, «que diga:», «creá» sin plegar en argumentos, cabezas guardame/tomá/take, formas nominales y de listado sin verbo); el reconocedor determinista pasó 100 % de sus casos y la ruta del modelo aclaró/confirmó/negó. Siguiente: adoptar la reparación léxica (effect_intent.py + __main__.py) verificada offline contra los 742 literales (3 cambios, todos deseados) y medir NOTES1142 con los fallidos y sus pares.

Evidencia: `artifacts/comprobaciones/C03/NOTES1141/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 432.72 s acumulados; pico GPU 3497.56 MiB; pico RAM 2388.08 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 26; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0092 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel. | Final revisado con una admisión; una invocación note.create verificada en el perfil aislado; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0229 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0286 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0416 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel con una cola conversacional innecesaria. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. Cola «vamos a hacerlo» sin afirmación de efecto. |
| 4 | H0321 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0284 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. |
| 6 | H0437 | failed | Preguntó título y contenido ya presentes; no creó la nota. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. Causa léxica localizada (dos puntos sin espacio en inglés). |
| 7 | H0673 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. |
| 8 | H0511 | passed | Consulta verificada de notas con respuesta veraz a la lista vacía; dos pares pertinentes aprobados. | Final revisado con una admisión; una invocación note.list verificada; cero confirmaciones y violaciones; pins intactos. |
| 9 | H0485 | failed | Pidió confirmación para una lectura inequívoca en lugar de listar. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. |
| 10 | H0734 | failed | Pidió confirmación para una lectura inequívoca en lugar de listar. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. |
| 11 | notes1141-dev-01 | failed | Preguntó el título con el contenido presente; no creó la nota. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. |
| 12 | notes1141-dev-02 | failed | Agotamiento de reintentos sin respuesta útil; no creó la nota. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. Composición del error rechazada (invented/missing_failure) hasta agotar. |
| 13 | notes1141-dev-03 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. |
| 14 | notes1141-dev-04 | failed | Negó una capacidad existente; no creó la nota. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. |
| 15 | notes1141-dev-05 | failed | Error de interpretación genérico; no creó la nota. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. |
| 16 | notes1141-dev-06 | failed | Preguntó el título con el contenido presente; no creó la nota. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. |
| 17 | notes1141-dev-07 | passed | Consulta verificada de notas con respuesta veraz a la lista vacía. | Final revisado con una admisión; una invocación note.list verificada; cero confirmaciones y violaciones; pins intactos. |
| 18 | notes1141-dev-08 | failed | Pidió confirmación para una lectura inequívoca en lugar de listar. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. |
| 19 | notes1141-dev-09 | passed | Consulta verificada de notas con respuesta veraz a la lista vacía. | Final revisado con una admisión; una invocación note.list verificada; cero confirmaciones y violaciones; pins intactos. |
| 20 | notes1141-dev-10 | failed | Pidió confirmación para una lectura inequívoca en lugar de listar. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. |
| 21 | notes1141-boundary-01 | passed | Reconoce la prohibición sin efecto ni política persistida. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. |
| 22 | notes1141-boundary-02 | failed | Trató la cita como dato sin efecto, pero explicó la persona gramatical incorrectamente. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. Hecho gramatical incorrecto y marcas markdown. |
| 23 | notes1141-boundary-03 | failed | Sin efecto, pero respuesta inconexa ante un relato con prohibición. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. |
| 24 | notes1141-boundary-04 | passed | Pide el contenido ausente sin crear nada. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. |
| 25 | notes1141-boundary-05 | passed | Explicación conceptual útil sin efectos. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. |

Recursos: 432.72 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2388.08 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
