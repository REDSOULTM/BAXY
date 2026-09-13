# CONVERSATION1152 — adjudicación de la raíz

## CONVERSATION1152 — estado vigente 2026-09-13T05:30:02+00:00

Parcial: 8 aprobados, 5 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 233/742 | 509 | 0 | >=107 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 28 Kiro + 49 retorno + H0584 + H0511 + 10 (NOTES1142) + 2 (KNOWLEDGE1144) + 7 (IDENTITY1146) + 2 (IDENTITY1148) + 2 (KNOWLEDGE1149) + 4 (CONVERSATION1150) = 106 antes de esta tanda, todas dentro de la ventana de 24 h al adjudicar; CONVERSATION1152 añade 1. No se cuentan revalidaciones.

Siguiente acción: CONVERSATION1152 completa: 13 ejecutados, 8 aprobados, 5 fallidos, 1 crédito (H0702). Reparación BUILD1151 demostrada: los tres finales que antes eran «No pude entender bien» por descarte de la pregunta de recuperación (H0059, H0354, límite hora) ahora publican la pregunta del mind; H0354 aprobado pero sin crédito por un solo par aprobado en la tanda (dev-06 terminó en fallo sin pregunta válida). Abiertos: H0059 (acuse convertido en pregunta), H0122 (nombre ajeno), H0354 (falta segundo par en una tanda). Siguiente: tanda breve de ayuda abierta (H0354 + dos pares) junto con el residual de conocimiento (H0703) o reloj; no repetir H0059/H0122 sin causa nueva.

Evidencia: `artifacts/comprobaciones/C03/CONVERSATION1152/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 238.39 s acumulados; pico GPU 3497.56 MiB; pico RAM 2231.70 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 13; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0122 | failed | Saludó sin aclarar que es BAXY cuando se le llamó por otro nombre. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0702 | passed | Confirmó presencia con naturalidad; dos variantes aprobadas. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0059 | failed | Preguntó en vez de acusar recibo; ya no publica una incomprensión falsa. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0354 | passed | Preguntó con qué necesita ayuda (reparación demostrada); sin crédito por faltar un segundo par aprobado en la tanda. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | conversation1152-dev-01 | passed | Variante original aprobada: presencia confirmada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | conversation1152-dev-02 | passed | Variante original aprobada: presencia confirmada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | conversation1152-dev-03 | failed | Preguntó en vez de acusar recibo. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | conversation1152-dev-04 | passed | Variante original aprobada: acuse natural. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | conversation1152-dev-05 | passed | Variante original aprobada: preguntó con qué. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | conversation1152-dev-06 | failed | Publicó una incomprensión; la recuperación no aportó una pregunta válida. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | conversation1152-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | conversation1152-boundary-02 | failed | No leyó la hora tras el acuse; preguntó en vez de fallar. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | conversation1152-boundary-03 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 238.39 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2231.70 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
