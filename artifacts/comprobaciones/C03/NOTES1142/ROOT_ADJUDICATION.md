# NOTES1142 — adjudicación de la raíz

## NOTES1142 — estado vigente 2026-09-13T02:41:00+00:00

Parcial: 20 aprobados, 5 fallidos, 0 sin ejecutar; 10 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 215/742 | 527 | 0 | >=89 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 28 Kiro + 49 retorno + H0584 (MESSAGING1140) + H0511 (NOTES1141), todas dentro de la ventana de 24 h al adjudicar; NOTES1142 añade diez. No se cuentan revalidaciones ni verification_updated_at.

Siguiente acción: NOTES1142 sobre la gramática reparada: 25 ejecutados, 20 aprobados, 5 fallidos; +10 (ocho creaciones y dos listados). Fallos restantes: dos vetos falsos de la App sobre borradores correctos tras efecto verificado (14: «martes» contiene «marte» en LooksLikeOutOfWorldRequest → out_of_catalog; 19: internal_code sin subcausa capturada) que terminan publicando un código de diagnóstico al agotar reintentos; un compromiso inventado en prosa (13); dos límites de conversación (21 hecho gramatical falso, 22 respuesta inconexa). Siguiente: reparar en App la comparación por palabra completa de LooksLikeOutOfWorldRequest (C#, requiere build) y capturar la subcausa de internal_code; categoría Notas queda con 1 abierto (H0319, límite sin marca).

Evidencia: `artifacts/comprobaciones/C03/NOTES1142/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 398.28 s acumulados; pico GPU 3497.56 MiB; pico RAM 2050.58 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 25; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0092 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel; dos pares pertinentes aprobados. | Final revisado con una admisión; una invocación note.create verificada en el perfil aislado; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0229 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel; dos pares pertinentes aprobados. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0286 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel; dos pares pertinentes aprobados. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0416 | passed | Nota guardada y verificada; confirmación fiel con una cola conversacional innecesaria; dos pares pertinentes aprobados. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0321 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel; dos pares pertinentes aprobados. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0284 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel; dos pares pertinentes aprobados. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. |
| 6 | H0437 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel; dos pares pertinentes aprobados. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. |
| 7 | H0673 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel; dos pares pertinentes aprobados. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. |
| 8 | H0485 | passed | Consulta verificada de notas con respuesta veraz a la lista vacía; dos pares pertinentes aprobados. | Final revisado con una admisión; una invocación note.list verificada; cero confirmaciones y violaciones; pins intactos. Persona gramatical menos precisa, hecho correcto. |
| 9 | H0734 | passed | Consulta verificada de notas con respuesta veraz a la lista vacía; dos pares pertinentes aprobados. | Final revisado con una admisión; una invocación note.list verificada; cero confirmaciones y violaciones; pins intactos. |
| 10 | notes1141-dev-01 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. |
| 11 | notes1141-dev-02 | passed | Nota guardada y verificada; confirmación fiel con una cola conversacional innecesaria. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. |
| 12 | notes1141-dev-03 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. |
| 13 | notes1141-dev-04 | failed | Nota guardada y verificada, pero el final afirma un compromiso inventado e incorrecto. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. Cola con hecho inventado. |
| 14 | notes1141-dev-05 | failed | Efecto verificado, pero la composición del resultado fue vetada falsamente hasta agotar reintentos y se publicó un código de diagnóstico. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. Veto falso de App (subcadena «marte» en «martes»). |
| 15 | notes1141-dev-06 | passed | Nota guardada y verificada con el contenido pedido; confirmación fiel. | Final revisado con una admisión; una invocación note.create verificada; cero confirmaciones y violaciones; pins intactos. |
| 16 | notes1141-dev-07 | passed | Consulta verificada de notas con respuesta veraz a la lista vacía. | Final revisado con una admisión; una invocación note.list verificada; cero confirmaciones y violaciones; pins intactos. |
| 17 | notes1141-dev-08 | passed | Consulta verificada de notas con respuesta veraz a la lista vacía. | Final revisado con una admisión; una invocación note.list verificada; cero confirmaciones y violaciones; pins intactos. |
| 18 | notes1141-dev-09 | passed | Consulta verificada de notas con respuesta veraz a la lista vacía. | Final revisado con una admisión; una invocación note.list verificada; cero confirmaciones y violaciones; pins intactos. |
| 19 | notes1141-dev-10 | failed | Lectura verificada, pero la composición fue vetada falsamente hasta agotar reintentos y se publicó un código de diagnóstico. | Final revisado con una admisión; una invocación note.list verificada; cero confirmaciones y violaciones; pins intactos. Veto falso de App (internal_code sobre un borrador natural). |
| 20 | notes1141-boundary-01 | passed | Reconoce la prohibición sin efecto ni política persistida. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. |
| 21 | notes1141-boundary-02 | failed | Trató la cita como dato sin efecto, pero explicó la persona gramatical incorrectamente. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. |
| 22 | notes1141-boundary-03 | failed | Sin efecto, pero respuesta inconexa ante un relato con prohibición. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. |
| 23 | notes1141-boundary-04 | passed | Pide el contenido ausente sin crear nada. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. |
| 24 | notes1141-boundary-05 | passed | Explicación conceptual útil sin efectos. | Final revisado con una admisión; ninguna operación de nota; cero confirmaciones y violaciones; pins intactos. |

Recursos: 398.28 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2050.58 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
