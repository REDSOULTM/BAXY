# CLOCK1155 — adjudicación de la raíz

## CLOCK1155 — estado vigente 2026-09-13T05:45:11+00:00

Parcial: 5 aprobados, 12 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 233/742 | 509 | 0 | >=107 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 107 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; CLOCK1155 no añade. No se cuentan revalidaciones.

Siguiente acción: CLOCK1155 completa: 17 ejecutados, 5 aprobados, 12 fallidos, 0 créditos. Causa dominante medida sin GPU: effect_intent._direct_current_time_request (dominio de system.time) no reconoce «qué día es hoy» (día/day), la cola «ya», la contracción «what's» ni la errata «qe ora es»; el veto de dominio retira system.time y domain_confirmation publica una confirmación (a veces con vocabulario del contrato: UTC, desfase local). «tiempo» a secas es polisémico por diseño (veto documentado). Cuentas atrás (H0399 y pares) y «cuánto tiempo tarda» se declaran fuera de catálogo. Siguiente: reparación léxica del reconocedor de reloj (Python, verificable sin GPU sobre los 742) y CLOCK1156 con el mismo material.

Evidencia: `artifacts/comprobaciones/C03/CLOCK1155/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 293.05 s acumulados; pico GPU 3497.56 MiB; pico RAM 2043.75 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 17; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0630 | failed | Pidió confirmación (con vocabulario interno) en vez de leer la hora. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0243 | failed | Pidió aclaración en vez de leer la fecha. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0301 | passed | Leyó y dijo la fecha correcta; sin crédito por faltar un segundo par aprobado. | Final revisado con una admisión; una lectura del reloj verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0399 | failed | Declaró fuera de alcance una cuenta atrás que se resuelve leyendo el reloj. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0054 | failed | Pidió confirmación con vocabulario interno en vez de dar la hora. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0312 | failed | Pidió confirmación con vocabulario interno en vez de dar la hora. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | clock1155-dev-01 | failed | Pidió confirmación en vez de leer la hora. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | clock1155-dev-02 | passed | Variante original aprobada: hora real leída. | Final revisado con una admisión; una lectura del reloj verificada; cero confirmaciones y violaciones; pins intactos. |
| 8 | clock1155-dev-03 | passed | Variante original aprobada: fecha real leída. | Final revisado con una admisión; una lectura del reloj verificada; cero confirmaciones y violaciones; pins intactos. |
| 9 | clock1155-dev-04 | failed | Pidió confirmación en vez de leer la fecha. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | clock1155-dev-05 | failed | Declaró fuera de alcance una cuenta atrás; redacción con el actor invertido. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | clock1155-dev-06 | failed | Publicó una incomprensión ante una cuenta atrás. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | clock1155-dev-07 | failed | Pidió confirmación con vocabulario interno en vez de dar la hora. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 13 | clock1155-dev-08 | failed | Pidió confirmación con vocabulario interno en vez de dar la hora. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 14 | clock1155-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 15 | clock1155-boundary-02 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 16 | clock1155-boundary-03 | failed | Negó una pregunta de conocimiento como fuera de alcance. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 293.05 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2043.75 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
