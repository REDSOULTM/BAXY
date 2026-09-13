# CLOCK1156 — adjudicación de la raíz

## CLOCK1156 — estado vigente 2026-09-13T05:56:04+00:00

Parcial: 8 aprobados, 9 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 235/742 | 507 | 0 | >=109 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 107 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; CLOCK1156 añade 2. No se cuentan revalidaciones.

Siguiente acción: CLOCK1156 completa: 17 ejecutados, 8 aprobados, 9 fallidos, 2 créditos (H0630, H0301). La reparación del reconocedor se demuestra: «qe ora es», «¿Qué hora es ya?», «What's today's date?» y «qué día es hoy» ahora leen el reloj. Causa nueva medida en H0243: la proyección de composición de system.time sólo aporta la hora (clock) cuando el pedido dice «día» y el modelo inventa la fecha («10 de abril de 2025»): reparar la proyección (fecha cuando se pregunta por el día) y remedir H0243 con pares. Abiertos sin reparación: «tiempo» a secas (polisemia por diseño; además la confirmación filtra vocabulario del contrato), cuentas atrás y duraciones fuera de catálogo.

Evidencia: `artifacts/comprobaciones/C03/CLOCK1156/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 283.97 s acumulados; pico GPU 3497.56 MiB; pico RAM 2078.36 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 17; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0630 | passed | Leyó y dijo la hora correcta; dos variantes aprobadas. | Final revisado con una admisión; una lectura del reloj verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0243 | failed | Leyó el reloj pero publicó una fecha inventada (la proyección no incluía la fecha). | Final revisado con una admisión; una lectura del reloj verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0301 | passed | Leyó y dijo la fecha correcta; dos variantes aprobadas. | Final revisado con una admisión; una lectura del reloj verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0399 | failed | Declaró fuera de alcance una cuenta atrás que se resuelve leyendo el reloj. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0054 | failed | Pidió confirmación con vocabulario interno en vez de dar la hora. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0312 | failed | Pidió confirmación con vocabulario interno en vez de dar la hora. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | clock1156-dev-01 | passed | Variante original aprobada: hora real leída. | Final revisado con una admisión; una lectura del reloj verificada; cero confirmaciones y violaciones; pins intactos. |
| 7 | clock1156-dev-02 | passed | Variante original aprobada: hora real leída. | Final revisado con una admisión; una lectura del reloj verificada; cero confirmaciones y violaciones; pins intactos. |
| 8 | clock1156-dev-03 | passed | Variante original aprobada: fecha real leída. | Final revisado con una admisión; una lectura del reloj verificada; cero confirmaciones y violaciones; pins intactos. |
| 9 | clock1156-dev-04 | passed | Variante original aprobada: fecha real leída. | Final revisado con una admisión; una lectura del reloj verificada; cero confirmaciones y violaciones; pins intactos. |
| 10 | clock1156-dev-05 | failed | Declaró fuera de alcance una cuenta atrás. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | clock1156-dev-06 | failed | Publicó una incomprensión ante una cuenta atrás. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | clock1156-dev-07 | failed | Pidió confirmación con vocabulario interno en vez de dar la hora. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 13 | clock1156-dev-08 | failed | Pidió confirmación con vocabulario interno en vez de dar la hora. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 14 | clock1156-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 15 | clock1156-boundary-02 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 16 | clock1156-boundary-03 | failed | Negó una pregunta de conocimiento como fuera de alcance. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 283.97 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2078.36 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
