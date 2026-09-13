# NETWORK1163 — adjudicación de la raíz

## NETWORK1163 — estado vigente 2026-09-13T06:38:23+00:00

Parcial: 7 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 239/742 | 503 | 0 | >=113 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 113 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; NETWORK1163 no añade. No se cuentan revalidaciones.

Siguiente acción: NETWORK1163 completa: 10 ejecutados, 7 aprobados, 3 fallidos, 0 créditos. La reparación del dominio de wifi.status se demuestra en H0221 («qué onda» → lectura verificada), pero «decime si el wifi está prendido/activo» sigue en confirmación por una ruta de aclaración temprana (decisión clarify sin fase final de turn-audit) aún no localizada, y los pares de red conectada siguen inventando «offline» en una de cada dos variantes. Cuatro literales aprobados (H0127, H0433, H0221 y, en 1161, H0302 parcial) esperan pares: siguiente tanda con pares que eviten la pregunta por internet (p. ej. «¿qué red wifi tenés conectada?») y sonda de la ruta «decime si…».

Evidencia: `artifacts/comprobaciones/C03/NETWORK1163/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 171.31 s acumulados; pico GPU 3497.56 MiB; pico RAM 1748.37 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0127 | passed | Informó fielmente que no hay conexión wifi; sin crédito por faltar un segundo par aprobado. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0433 | passed | Informó fielmente que no hay conexión wifi; sin crédito por faltar un segundo par aprobado. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0230 | failed | Pidió confirmación en vez de leer el estado wifi (ruta distinta del veto de dominio). | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0221 | passed | Leyó el estado wifi y respondió según lo observado; sin crédito por faltar un segundo par aprobado. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 4 | network1163-dev-01 | passed | Variante original aprobada: estado wifi leído sin inventar. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 5 | network1163-dev-02 | failed | Añadió «offline», hecho no observado, a una lectura correcta. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 6 | network1163-dev-03 | failed | Pidió confirmación en vez de leer el estado wifi. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | network1163-dev-04 | passed | Variante original aprobada: estado wifi leído. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 8 | network1163-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | network1163-boundary-02 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 171.31 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1748.37 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
