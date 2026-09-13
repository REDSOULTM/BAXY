# WEB1265 — adjudicación de la raíz

## WEB1265 — estado vigente 2026-09-13T22:21:00.207085+00:00

Parcial: 5 aprobados, 1 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 346/742 | 396 | 0 | >=220 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 218 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEB1265 añade 2. No se cuentan revalidaciones.

Siguiente acción: WEB1265: 6 ejecutados, 5 aprobados, 1 fallidos, 2 créditos (índices [0, 1]). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/WEB1265/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 101.67 s acumulados; pico GPU 3497.56 MiB; pico RAM 1595.92 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0051 | passed | Abrió la app YouTube instalada y lo dijo; crédito con dos variantes aprobadas. | Turno ordinario: app.open de la entrada «YouTube» del catálogo de Inicio (PWA de Chrome) completada y verificada; cero confirmaciones y violaciones; pins intactos; la raíz cerró después las ventanas de Chrome nuevas. |
| 1 | H0741 | passed | Abrió la app YouTube instalada y lo dijo; crédito con dos variantes aprobadas. | Turno ordinario: app.open de la entrada «YouTube» del catálogo de Inicio (PWA de Chrome) completada y verificada; cero confirmaciones y violaciones; pins intactos; la raíz cerró después las ventanas de Chrome nuevas. |
| 2 | web1265-dev-01 | passed | Abrió la app YouTube instalada y lo dijo. | Turno ordinario: app.open de la entrada «YouTube» del catálogo de Inicio (PWA de Chrome) completada y verificada; cero confirmaciones y violaciones; pins intactos; la raíz cerró después las ventanas de Chrome nuevas. |
| 3 | web1265-dev-02 | passed | Abrió la app YouTube instalada y lo dijo. | Turno ordinario: app.open de la entrada «YouTube» del catálogo de Inicio (PWA de Chrome) completada y verificada; cero confirmaciones y violaciones; pins intactos; la raíz cerró después las ventanas de Chrome nuevas. |
| 4 | web1265-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | web1265-boundary-02 | failed | Límite fallido: no navegó pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 101.67 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1595.92 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
