# AGENDA1104 — adjudicación de la raíz

## AGENDA1104 — estado vigente 2026-09-12T22:35:57.2332064Z

Parcial: 4 aprobados, 6 fallidos, 5 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 198/742 | 544 | 0 | >=72 | 0/35 |

Procedencia de primeras altas: Cota inferior previa: 28 primeras altas en Kiro y 43 tras el retorno, dentro del 12 de septiembre; se suma sólo el crédito nuevo de esta tanda, no revalidaciones o actualizaciones de fecha.

Siguiente acción: Integrar la sustitución de etiqueta AGENDA1107 y medir AGENDA1108: cuatro literales de alarma y sus dos variantes, con límites intactos y sin repetir fallos sin hipótesis pertinente. H0572 covered con pares8/9; H0137 open por inversión del destinatario. DIALOGUE1106 queda preparado para cinco fragmentos después de integrar1098, todavía pendiente.

Evidencia: `artifacts/comprobaciones/C03/AGENDA1104/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 224.17 s acumulados; pico GPU 3497.56 MiB; pico RAM 1659.45 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 1 | H0137 | failed | Cambia el destinatario del recordatorio. | Pregunta la hora conservando contenido y día, pero se atribuye el recordatorio a sí mismo. |
| 5 | H0572 | passed | Recordatorio aclarado con fidelidad y variantes. | Conserva destinatario, contenido y mañana; pide sólo la hora. Crédito explícito con pares8/9. |
| 6 | agenda1097-dev-01 | failed | Confunde periodo horario con recurrencia. | Pregunta por repetición diaria o semanal que no fue solicitada. |
| 8 | agenda1097-dev-07 | passed | Aclaración temporal pertinente. | Conserva lo que debe recordarse y mañana; pide la hora. |
| 9 | agenda1097-dev-08 | passed | Aclaración temporal pertinente en inglés. | Conserva contenido y próximo martes; sólo pide la hora. |
| 10 | agenda1097-boundary-01 | failed | Respuesta inconexa ante la prohibición. | No programó nada; la respuesta no atendió al mensaje. |
| 11 | agenda1097-boundary-02 | failed | Agrega una precisión temporal no dada. | Interpreta la cita como de mañana sin fundamento. |
| 12 | agenda1097-boundary-03 | failed | Negativa improcedente ante una hipótesis. | No programó, pero no respondió a la situación hipotética. |
| 13 | agenda1097-boundary-04 | failed | Trata el relato como una petición imposible. | No hizo cambios, pero no atendió a la narración pasada. |
| 14 | agenda1097-boundary-05 | passed | Explicación conceptual pertinente. | Distingue duración del evento e instante del aviso sin efectos. |

Recursos: 224.17 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1659.45 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
