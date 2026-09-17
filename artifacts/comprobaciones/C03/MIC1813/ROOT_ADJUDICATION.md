# MIC1813 — adjudicación de la raíz

## MIC1813 — estado vigente 2026-09-17T05:48:14.465345+00:00

Parcial: 3 aprobados, 2 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 644/742 | 98 | 0 | >=528 | 14/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 528 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MIC1813 añade 0. No se cuentan revalidaciones.

Siguiente acción: MIC1813: 5 ejecutados, 3 aprobados, 2 fallidos, 0 créditos (índices []); Interacción dentro de aplicaciones 18/22. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/MIC1813/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 102.09 s acumulados; pico GPU 3497.56 MiB; pico RAM 2053.56 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0420 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: audio.microphone.mute completada y verificada; la raíz midió el micrófono silenciado después y restauró el estado previo; ningún final llegó a la persona: los borradores verdaderos fueron vetados por un patrón del compositor que casa dentro de la palabra micrófono. |
| 1 | mic1813-dev-01 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: audio.microphone.mute completada y verificada; la raíz midió el micrófono silenciado después y restauró el estado previo; ningún final llegó a la persona: los borradores verdaderos fueron vetados por un patrón del compositor que casa dentro de la palabra micrófono. |
| 2 | mic1813-dev-02 | passed | audio.microphone.mute completada y verificada por la postlectura del endpoint de captura; la raíz midió el micrófono silenciado después; el final dijo lo hecho. | Turno ordinario: audio.microphone.mute con state true completada y verificada por la postlectura del endpoint de captura; la raíz midió el micrófono silenciado después y restauró el estado previo; cero confirmaciones y violaciones; pins intactos. |
| 3 | mic1813-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | mic1813-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 102.09 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2053.56 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
