# APPS1231 — adjudicación de la raíz

## APPS1231 — estado vigente 2026-09-13T18:19:05.079095+00:00

Parcial: 9 aprobados, 12 fallidos, 0 sin ejecutar; 5 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 310/742 | 432 | 0 | >=184 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 179 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; APPS1231 añade 5. No se cuentan revalidaciones.

Siguiente acción: APPS1231 completa: 21 ejecutados, 9 aprobados, 12 fallidos, 5 créditos (H0497 «abre a calculadora», H0730 «me abrís la calculadora», H0348 «abrime la calculadora dale», H0165 «avrí la calculadora», H0724 «son las tres abrí la calculadora») con sus dos pares. Abrir aplicaciones queda 34/54. Fallos con causa medida para la próxima tanda: Explorador ×4 (verificación de app.open en el proceso del shell: proveedor), destinos ausentes ×5 (sin lectura app.installed para un nombre de software ausente: lector), compuesto ×3 (final omite la apertura: composición). Fuera y documentado: H0461 (límite sin marca), Steam ×3 y erratas de Steam ×4, Mortal Kombat ×2, H0249, idiomas ×3.

Evidencia: `artifacts/comprobaciones/C03/APPS1231/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 367.77 s acumulados; pico GPU 3497.56 MiB; pico RAM 2330.26 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 21; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0497 | passed | Abrió la Calculadora con verificación; dos pares aprobados. | Final publicado; app.open completada y verificada (proceso nuevo, alreadyRunning false); cero confirmaciones y violaciones; raíz cerró después sólo la ventana lanzada; pins intactos. |
| 1 | H0730 | passed | Abrió la Calculadora con verificación; dos pares aprobados. | Final publicado; app.open completada y verificada (proceso nuevo, alreadyRunning false); cero confirmaciones y violaciones; raíz cerró después sólo la ventana lanzada; pins intactos. |
| 2 | H0348 | passed | Abrió la Calculadora con verificación; dos pares aprobados. | Final publicado; app.open completada y verificada (proceso nuevo, alreadyRunning false); cero confirmaciones y violaciones; raíz cerró después sólo la ventana lanzada; pins intactos. |
| 3 | H0165 | passed | Abrió la Calculadora con verificación; dos pares aprobados. | Final publicado; app.open completada y verificada (proceso nuevo, alreadyRunning false); cero confirmaciones y violaciones; raíz cerró después sólo la ventana lanzada; pins intactos. |
| 4 | H0724 | passed | Abrió la Calculadora con verificación; dos pares aprobados. | Final publicado; app.open completada y verificada (proceso nuevo, alreadyRunning false); cero confirmaciones y violaciones; raíz cerró después sólo la ventana lanzada; pins intactos. |
| 5 | H0151 | failed | Falló: la apertura del Explorador no se verificó (ventana en el proceso del shell). | Final publicado; app.open failed/verification_failed aunque la ventana nueva del Explorador apareció (raíz la cerró después); cero violaciones; pins intactos. |
| 6 | H0147 | failed | Failed: the Explorer opening was not verified (window in the shell process). | Final publicado; app.open failed/verification_failed aunque la ventana nueva del Explorador apareció (raíz la cerró después); cero violaciones; pins intactos. |
| 7 | H0289 | failed | Falló: negó una capacidad que sí tiene en vez de comprobar el catálogo. | Final publicado; ninguna operación (sin lectura app.installed); cero violaciones; pins intactos. |
| 8 | H0558 | failed | Falló: negativa vacía sin comprobar el catálogo. | Final publicado; ninguna operación (sin lectura app.installed); cero violaciones; pins intactos. |
| 9 | H0691 | failed | Falló: preguntó en vez de comprobar que Firefox no está instalado. | Final publicado; ninguna operación (sin lectura app.installed); cero violaciones; pins intactos. |
| 10 | H0183 | failed | Falló: abrió y leyó la hora, pero el final omitió la apertura. | Final publicado; app.open y system.time completadas y verificadas; el final sólo informa la hora; cero violaciones; pins intactos. |
| 11 | apps1231-dev-01 | passed | Variante original aprobada: abrió la Calculadora con verificación. | Final publicado; app.open completada y verificada (proceso nuevo, alreadyRunning false); cero confirmaciones y violaciones; raíz cerró después sólo la ventana lanzada; pins intactos. |
| 12 | apps1231-dev-02 | passed | Variante original aprobada: abrió la Calculadora con verificación. | Final publicado; app.open completada y verificada (proceso nuevo, alreadyRunning false); cero confirmaciones y violaciones; raíz cerró después sólo la ventana lanzada; pins intactos. |
| 13 | apps1231-dev-03 | failed | Falló: apertura no verificada y sin respuesta. | Final publicado; app.open failed/verification_failed aunque la ventana nueva del Explorador apareció (raíz la cerró después); cero violaciones; pins intactos. |
| 14 | apps1231-dev-04 | failed | Failed: unverified opening and no response. | Final publicado; app.open failed/verification_failed aunque la ventana nueva del Explorador apareció (raíz la cerró después); cero violaciones; pins intactos. |
| 15 | apps1231-dev-05 | failed | Falló: negó la capacidad en vez de comprobar el catálogo. | Final publicado; ninguna operación (sin lectura app.installed); cero violaciones; pins intactos. |
| 16 | apps1231-dev-06 | failed | Failed: asked for the exact name instead of checking the catalog. | Final publicado; ninguna operación (sin lectura app.installed); cero violaciones; pins intactos. |
| 17 | apps1231-dev-07 | failed | Falló: final incompleto (omite la apertura). | Final publicado; app.open y system.time completadas y verificadas; el final sólo informa la hora; cero violaciones; pins intactos. |
| 18 | apps1231-dev-08 | failed | Failed: incomplete final (omits the opening). | Final publicado; app.open y system.time completadas y verificadas; el final sólo informa la hora; cero violaciones; pins intactos. |
| 19 | apps1231-boundary-01 | passed | Límite aprobado: respuesta informativa sin efecto. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 20 | apps1231-boundary-02 | passed | Límite aprobado: reconoció la prohibición sin efecto. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 367.77 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2330.26 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
