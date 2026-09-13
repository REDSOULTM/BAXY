# CLOSE1217 — adjudicación de la raíz

## CLOSE1217 — estado vigente 2026-09-13T15:49:43+00:00

Parcial: 0 aprobados, 1 fallidos, 13 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 291/742 | 451 | 0 | >=165 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 165 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; CLOSE1217 no añade ninguna. No se cuentan revalidaciones.

Siguiente acción: CLOSE1217 parcial: 1 ejecutado, 0 aprobados, 1 fallido, 13 sin ejecutar, 0 créditos. Causa identificada por la traza: la proyección de observaciones del plan descarta complete/offset/observedCount/hasMore/foreground, campos que la forma del cierre revisado exige. Siguiente: CLOSE1219 con BUILD1219 (campos seguros por operación) y los mismos 14 objetos.

Evidencia: `artifacts/comprobaciones/C03/CLOSE1217/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 18.56 s acumulados; pico GPU 3497.56 MiB; pico RAM 1442.86 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 1; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0095 | failed | Identificó la ventana correcta y pidió confirmación; la revisión no vio la propuesta porque la observación proyectada omitía los campos de página que la forma revisada exige. | Fase de petición publicada; una lectura verificada; sin propuesta de revisión ni cierre; la ventana de prueba de raíz siguió abierta; pins intactos. |

Recursos: 18.56 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1442.86 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
