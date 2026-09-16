# PDF1691 — adjudicación de la raíz

## PDF1691 — estado vigente 2026-09-16T08:32:43.358878+00:00

Parcial: 4 aprobados, 1 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 607/742 | 135 | 0 | >=491 | 9/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 491 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); PDF1691 añade 0. No se cuentan revalidaciones.

Siguiente acción: PDF1691: 6 ejecutados, 4 aprobados, 2 fallidos, 0 créditos (índices []); Abrir aplicaciones 46/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/PDF1691/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 148.53 s acumulados; pico GPU 3497.56 MiB; pico RAM 2396.47 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0666 | passed | document.pdf.read completada y verificada sobre el PDF de prueba de la raíz; el final nombró el documento, sus títulos y su comienzo tal cual, sin inventar; fixture retirado por la raíz. | Turno ordinario: exactamente una document.pdf.read completada y verificada sobre el PDF de prueba de la raíz (informe.pdf, escritorio, texto extraíble, sin OCR); el final nombró el documento, sus títulos y su comienzo tal cual; la raíz retiró el fixture; cero confirmaciones y violaciones; pins intactos. |
| 1 | pdf1691-dev-01 | passed | document.pdf.read completada y verificada sobre el PDF de prueba de la raíz; el final nombró el documento, sus títulos y su comienzo tal cual, sin inventar; fixture retirado por la raíz. | Turno ordinario: exactamente una document.pdf.read completada y verificada sobre el PDF de prueba de la raíz (informe.pdf, escritorio, texto extraíble, sin OCR); el final nombró el documento, sus títulos y su comienzo tal cual; la raíz retiró el fixture; cero confirmaciones y violaciones; pins intactos. |
| 2 | pdf1691-dev-02 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: la operación se completó y verificó, cero violaciones, pins intactos; ningún final fue publicado (los borradores ingleses tomaron forma de campos y el veto los rechazó). |
| 3 | pdf1691-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | pdf1691-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 148.53 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2396.47 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
