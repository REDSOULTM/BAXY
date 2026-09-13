# IDENTITY1145 — adjudicación de la raíz

## IDENTITY1145 — estado vigente 2026-09-13T03:20:00+00:00

Parcial: 1 aprobados, 2 fallidos, 24 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 217/742 | 525 | 0 | >=91 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 28 Kiro + 49 retorno + H0584 + H0511 + 10 (NOTES1142) + 2 (KNOWLEDGE1144), todas dentro de la ventana de 24 h al adjudicar; IDENTITY1145 no añade. No se cuentan revalidaciones.

Siguiente acción: IDENTITY1145 detenida tras 3 casos por RAM libre < 4000 MiB (guarda heredada, no rebajada): la App ChatGPT/Codex del dueño se relanza y ocupa ~1.3 GB; el arnés no autoriza cerrarla por la fuerza de nuevo. 2 fallidos (capacidades sólo de charla por «podés» no reconocido en el lector de capacidades), 1 aprobado, 24 sin ejecutar, 0 créditos. Siguiente: reparar el voseo en request_reading (podes/sabes/sos/vos), verificar sin GPU sobre los 742, y medir IDENTITY1146 completa en cuanto la RAM libre supere 4000 MiB.

Evidencia: `artifacts/comprobaciones/C03/IDENTITY1145/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 68.95 s acumulados; pico GPU 3497.56 MiB; pico RAM 1588.11 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 3; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0153 | failed | Presentó a BAXY como asistente sólo de charla; omitió sus capacidades reales. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0474 | failed | Presentó a BAXY como asistente sólo de charla; omitió sus capacidades reales. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0587 | passed | Explicó capacidades reales sin inventar; sin crédito por falta de pares ejecutados. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 68.95 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1588.11 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
