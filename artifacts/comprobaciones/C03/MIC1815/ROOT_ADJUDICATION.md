# MIC1815 — adjudicación de la raíz

## MIC1815 — estado vigente 2026-09-17T05:52:16.211952+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 645/742 | 97 | 0 | >=529 | 14/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 528 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MIC1815 añade 1. No se cuentan revalidaciones.

Siguiente acción: MIC1815: 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos (índices [0]); Interacción dentro de aplicaciones 19/22. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/MIC1815/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 86.45 s acumulados; pico GPU 3497.56 MiB; pico RAM 1766.25 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0420 | passed | audio.microphone.mute completada y verificada por la postlectura del endpoint de captura; la raíz midió el micrófono silenciado después; el final dijo lo hecho; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: audio.microphone.mute con state true completada y verificada por la postlectura del endpoint de captura; la raíz midió el micrófono silenciado después y restauró el estado previo; cero confirmaciones y violaciones; pins intactos. |
| 1 | mic1815-dev-01 | passed | audio.microphone.mute completada y verificada por la postlectura del endpoint de captura; la raíz midió el micrófono silenciado después; el final dijo lo hecho. | Turno ordinario: audio.microphone.mute con state true completada y verificada por la postlectura del endpoint de captura; la raíz midió el micrófono silenciado después y restauró el estado previo; cero confirmaciones y violaciones; pins intactos. |
| 2 | mic1815-dev-02 | passed | audio.microphone.mute completada y verificada por la postlectura del endpoint de captura; la raíz midió el micrófono silenciado después; el final dijo lo hecho. | Turno ordinario: audio.microphone.mute con state true completada y verificada por la postlectura del endpoint de captura; la raíz midió el micrófono silenciado después y restauró el estado previo; cero confirmaciones y violaciones; pins intactos. |
| 3 | mic1815-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | mic1815-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 86.45 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1766.25 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
