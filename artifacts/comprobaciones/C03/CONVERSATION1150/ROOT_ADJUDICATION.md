# CONVERSATION1150 — adjudicación de la raíz

## CONVERSATION1150 — estado vigente 2026-09-13T05:15:32+00:00

Parcial: 14 aprobados, 12 fallidos, 0 sin ejecutar; 4 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 232/742 | 510 | 0 | >=106 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 28 Kiro + 49 retorno + H0584 + H0511 + 10 (NOTES1142) + 2 (KNOWLEDGE1144) + 7 (IDENTITY1146) + 2 (IDENTITY1148) + 2 (KNOWLEDGE1149) = 102 antes de esta tanda, todas dentro de la ventana de 24 h al adjudicar; CONVERSATION1150 añade 4. No se cuentan revalidaciones.

Siguiente acción: CONVERSATION1150 completa: 26 ejecutados, 14 aprobados, 12 fallidos, 4 créditos (H0247, H0358, H0615, H0661: acuses). Conversación queda 23/31. Causas medidas sin reparación adoptada: (a) generación sólo-pregunta vetada → clarify → error de comprensión (H0059; misma familia que H0703 en KNOWLEDGE1149); (b) «necesito ayuda con algo» clasificado unsupported por el mind → error; (c) el modelo promete memes (H0069 y ambas variantes) y finge comprensión ante ruido (H0410 y ambas variantes): sin ruta para texto ininteligible ni hecho de catálogo «sin imágenes»; (d) nombre ajeno en el saludo sin aclaración (H0122, variante). Siguiente: sonda sin GPU de la ruta veto→clarify→error (afecta a tres literales de dos categorías) antes de otra tanda conversacional; luego reloj (10 abiertos).

Evidencia: `artifacts/comprobaciones/C03/CONVERSATION1150/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 455.82 s acumulados; pico GPU 3497.56 MiB; pico RAM 2083.98 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 26; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0122 | failed | Saludó sin aclarar que es BAXY cuando se le llamó por otro nombre. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0702 | passed | Confirmó presencia con naturalidad; sin crédito por faltar un segundo par aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0059 | failed | Acuse contradictorio con una incomprensión tras vetar dos respuestas que sólo preguntaban. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0247 | passed | Acuse natural sin inventar antecedentes; dos variantes aprobadas. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0358 | passed | Acuse natural sin inventar antecedentes; dos variantes aprobadas. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0615 | passed | Aceptó la negativa con naturalidad; dos variantes aprobadas. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | H0661 | passed | Acuse natural sin inventar antecedentes; dos variantes aprobadas. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | H0354 | failed | Publicó una incomprensión en vez de preguntar con qué necesita ayuda. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | H0069 | failed | Prometió un meme que no puede mostrar. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | H0410 | failed | Fingió entender un texto sin sentido. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | conversation1150-dev-01 | failed | Devolvió el nombre ajeno como si fuera el de la persona; no aclaró que es BAXY. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | conversation1150-dev-02 | passed | Variante original aprobada: presencia confirmada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | conversation1150-dev-03 | failed | Presupuso una actividad propia inexistente. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 13 | conversation1150-dev-04 | passed | Variante original aprobada: acuse natural. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 14 | conversation1150-dev-05 | passed | Variante original aprobada: acuse natural. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 15 | conversation1150-dev-06 | passed | Variante original aprobada: preguntó qué necesita. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 16 | conversation1150-dev-07 | passed | Variante original aprobada: preguntó con qué. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 17 | conversation1150-dev-08 | failed | Prometió un meme que no puede mostrar. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 18 | conversation1150-dev-09 | failed | Presentó un chiste de texto como meme sin decir que no tiene imágenes. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 19 | conversation1150-dev-10 | failed | Inventó una interpretación de un texto sin sentido. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 20 | conversation1150-dev-11 | failed | Fingió entender un texto sin sentido. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 21 | conversation1150-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 22 | conversation1150-boundary-02 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 23 | conversation1150-boundary-03 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 24 | conversation1150-boundary-04 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 25 | conversation1150-boundary-05 | failed | No leyó la hora cuando la pregunta venía tras un acuse. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 455.82 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2083.98 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
