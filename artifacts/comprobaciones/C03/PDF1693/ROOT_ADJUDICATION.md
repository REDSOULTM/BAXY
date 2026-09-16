# PDF1693 — adjudicación de la raíz

## PDF1693 — estado vigente 2026-09-16T08:37:42.931218+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 608/742 | 134 | 0 | >=492 | 9/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 491 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); PDF1693 añade 1. No se cuentan revalidaciones.

Siguiente acción: PDF1693: 6 ejecutados, 5 aprobados, 1 fallidos, 1 créditos (índices [0]); Abrir aplicaciones 47/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/PDF1693/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 131.09 s acumulados; pico GPU 3497.56 MiB; pico RAM 2468.06 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0666 | passed | document.pdf.read completada y verificada sobre el PDF de prueba de la raíz; el final nombró el documento, sus títulos y su comienzo tal cual, sin inventar; fixture retirado por la raíz; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una document.pdf.read completada y verificada sobre el PDF de prueba de la raíz (informe.pdf, escritorio, texto extraíble, sin OCR); el final nombró el documento, sus títulos y su comienzo tal cual; la raíz retiró el fixture; cero confirmaciones y violaciones; pins intactos. |
| 1 | pdf1693-dev-01 | passed | document.pdf.read completada y verificada sobre el PDF de prueba de la raíz; el final nombró el documento, sus títulos y su comienzo tal cual, sin inventar; fixture retirado por la raíz. | Turno ordinario: exactamente una document.pdf.read completada y verificada sobre el PDF de prueba de la raíz (informe.pdf, escritorio, texto extraíble, sin OCR); el final nombró el documento, sus títulos y su comienzo tal cual; la raíz retiró el fixture; cero confirmaciones y violaciones; pins intactos. |
| 2 | pdf1693-dev-02 | passed | document.pdf.read completada y verificada sobre el PDF de prueba de la raíz; el final nombró el documento, sus títulos y su comienzo tal cual, sin inventar; fixture retirado por la raíz. | Turno ordinario: exactamente una document.pdf.read completada y verificada sobre el PDF de prueba de la raíz (informe.pdf, escritorio, texto extraíble, sin OCR); el final nombró el documento, sus títulos y su comienzo tal cual; la raíz retiró el fixture; cero confirmaciones y violaciones; pins intactos. |
| 3 | pdf1693-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | pdf1693-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 131.09 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2468.06 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
