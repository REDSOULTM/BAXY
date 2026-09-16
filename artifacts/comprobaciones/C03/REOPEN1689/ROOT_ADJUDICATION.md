# REOPEN1689 — adjudicación de la raíz

## REOPEN1689 — estado vigente 2026-09-16T08:21:56.269489+00:00

Parcial: 7 aprobados, 1 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 607/742 | 135 | 0 | >=491 | 9/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 490 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); REOPEN1689 añade 1. No se cuentan revalidaciones.

Siguiente acción: REOPEN1689: 6 ejecutados, 7 aprobados, -1 fallidos, 1 créditos (índices [1]); Abrir aplicaciones 47/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/REOPEN1689/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 178.58 s acumulados; pico GPU 3497.56 MiB; pico RAM 2397.11 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0666 | passed | document.pdf.read completada y verificada sobre el PDF de prueba de la raíz; el final nombró el documento, sus títulos y su comienzo tal cual, sin inventar; fixture retirado por la raíz. | Turno ordinario: exactamente una document.pdf.read completada y verificada sobre el PDF de prueba de la raíz (informe.pdf, escritorio, texto extraíble, sin OCR); el final nombró el documento, sus títulos y su comienzo tal cual; la raíz retiró el fixture; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0658 | passed | window.minimize.all completada y verificada sobre las ventanas del escritorio, ninguna cerrada; el final dijo que minimizó todas las ventanas; ventanas restauradas por la raíz; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una window.minimize.all completada y verificada (todas las ventanas visibles del escritorio minimizadas y releídas), ninguna cerrada; la raíz restauró las ventanas del dueño; cero confirmaciones y violaciones; pins intactos. |
| 2 | reopen1689-dev-01 | passed | document.pdf.read completada y verificada sobre el PDF de prueba de la raíz; el final nombró el documento, sus títulos y su comienzo tal cual, sin inventar; fixture retirado por la raíz. | Turno ordinario: exactamente una document.pdf.read completada y verificada sobre el PDF de prueba de la raíz (informe.pdf, escritorio, texto extraíble, sin OCR); el final nombró el documento, sus títulos y su comienzo tal cual; la raíz retiró el fixture; cero confirmaciones y violaciones; pins intactos. |
| 3 | reopen1689-dev-02 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: la operación se completó y verificó, cero violaciones, pins intactos; el final fue fiel al documento pero en español ante un pedido en inglés. |
| 4 | reopen1689-dev-03 | passed | window.minimize.all completada y verificada sobre las ventanas del escritorio, ninguna cerrada; el final dijo que minimizó todas las ventanas; ventanas restauradas por la raíz. | Turno ordinario: exactamente una window.minimize.all completada y verificada (todas las ventanas visibles del escritorio minimizadas y releídas), ninguna cerrada; la raíz restauró las ventanas del dueño; cero confirmaciones y violaciones; pins intactos. |
| 5 | reopen1689-dev-04 | passed | window.minimize.all completada y verificada sobre las ventanas del escritorio, ninguna cerrada; el final dijo que minimizó todas las ventanas; ventanas restauradas por la raíz. | Turno ordinario: exactamente una window.minimize.all completada y verificada (todas las ventanas visibles del escritorio minimizadas y releídas), ninguna cerrada; la raíz restauró las ventanas del dueño; cero confirmaciones y violaciones; pins intactos. |
| 6 | reopen1689-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | reopen1689-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 178.58 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2397.11 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
