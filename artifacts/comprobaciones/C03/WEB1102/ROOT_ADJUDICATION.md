# WEB1102 — adjudicación de la raíz

## WEB1102 — estado vigente 2026-09-12T22:21:25.4583586Z

Parcial: 3 aprobados, 4 fallidos, 5 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 197/742 | 545 | 0 | >=71 | 0/35 |

Procedencia de primeras altas: Cota inferior de primeras altas: 28 en Kiro y 43 tras el retorno, todas dentro del 12 de septiembre. Se cuentan adjudicaciones iniciales, no actualizaciones de verification_updated_at ni revalidaciones.

Siguiente acción: Ejecutar AGENDA1104 con fuente1103 ya integrada: pares6/7 antes de cuatro literales de alarma y8/9 antes de dos recordatorios. WEB1102 conserva siete ejecutados, tres aprobados, cuatro fallidos y cero créditos; no repetir búsqueda incierta del índice2. WEB1105 descarta una regla que sólo mejora variantes; propuesta de completitud semántica pendiente de decisión.

Evidencia: `artifacts/comprobaciones/C03/WEB1102/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 186.53 s acumulados; pico GPU 3497.56 MiB; pico RAM 1815.68 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 7; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | web1102-dev-search-01 | failed | Búsqueda fallida por resultados irrelevantes. | Hubo búsqueda real, pero no resultados verificados útiles; ningún crédito. |
| 2 | web1102-dev-destination-01 | failed | Búsqueda inesperada en lugar de aclarar el destino. | Tramo detenido sin respuesta final; operación y estado incierto conservados. |
| 7 | web1102-boundary-01 | failed | Respuesta inconexa ante la prohibición. | No hubo búsqueda, pero la respuesta no fue útil. |
| 8 | web1102-boundary-02 | passed | Explicación fiel del verbo citado. | Respondió en inglés y no realizó búsquedas. |
| 9 | web1102-boundary-03 | passed | Respeta la condición futura. | Respuesta pertinente; no hubo búsqueda ni navegación. |
| 10 | web1102-boundary-04 | failed | Explicación imprecisa sobre transmisión y publicación. | No accedió a datos privados, pero la distinción solicitada no fue fiel. |
| 11 | web1102-boundary-05 | passed | Acuse pertinente de un relato pasado. | No buscó ni abrió páginas; preguntó por la experiencia relatada. |

Recursos: 186.53 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1815.68 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
