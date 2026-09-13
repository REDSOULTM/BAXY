# CLOSE1215 — adjudicación de la raíz

## CLOSE1215 — estado vigente 2026-09-13T15:31:45+00:00

Parcial: 0 aprobados, 1 fallidos, 13 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 291/742 | 451 | 0 | >=165 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 165 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; CLOSE1215 no añade ninguna. No se cuentan revalidaciones.

Siguiente acción: CLOSE1215 parcial: 1 ejecutado, 0 aprobados, 1 fallido, 13 sin ejecutar, 0 créditos. La cadena reconocimiento → window.resolve por nombre → desafío de app.close funciona sobre la ventana propia; el punto roto es la captura de la confirmación para el turno revisado (guarda no identificada). Siguiente: CLOSE1217 con traza de la captura (BUILD1217) y los mismos 14 objetos.

Evidencia: `artifacts/comprobaciones/C03/CLOSE1215/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 20.33 s acumulados; pico GPU 3497.56 MiB; pico RAM 1446.19 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 1; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0095 | failed | Identificó la ventana correcta y pidió confirmación, pero el turno revisado no expuso la propuesta al revisor. | Fase de petición publicada; una lectura verificada; sin propuesta de revisión ni cierre; la ventana de prueba de raíz siguió abierta; pins intactos. |

Recursos: 20.33 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1446.19 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
