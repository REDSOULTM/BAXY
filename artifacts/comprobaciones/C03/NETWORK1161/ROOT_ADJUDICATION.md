# NETWORK1161 — adjudicación de la raíz

## NETWORK1161 — estado vigente 2026-09-13T06:29:03+00:00

Parcial: 11 aprobados, 12 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 239/742 | 503 | 0 | >=113 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 111 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; NETWORK1161 añade 2. No se cuentan revalidaciones.

Siguiente acción: NETWORK1161 completa: 23 ejecutados, 11 aprobados, 12 fallidos, 2 créditos (H0647 wifi encendido, H0732 internet). Causas medidas: (a) dominio de wifi.status no reconocido para «decime si el wifi está prendido»/«qué onda con el wifi» y sin regla de dominio para network.ip.list (IP) → veto → confirmación (a veces con vocabulario del contrato) o negación de alcance; (b) el compositor añade «no está en línea» a una lectura wifi connected=false (hecho no observado y falso), lo que impidió acreditar H0127/H0433; (c) «redes guardadas» resuelve a wifi.status y el texto afirma que no hay guardadas sin listarlas; (d) confirmación compuesta para network.ip.list (lectura) detiene el caso. Red queda 3/21. Siguiente: reglas de dominio para wifi.status (decime si…/qué onda) y network.ip.list (ip/dirección ip) en effect_intent, verificables sin GPU; después remedir con pares nuevos.

Evidencia: `artifacts/comprobaciones/C03/NETWORK1161/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 376.92 s acumulados; pico GPU 3497.56 MiB; pico RAM 1664.48 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 23; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0127 | passed | Informó fielmente que no hay conexión wifi; sin crédito porque las variantes añadieron un hecho no observado. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0433 | passed | Informó fielmente que no hay conexión wifi; sin crédito porque las variantes añadieron un hecho no observado. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0647 | passed | Leyó el estado wifi y respondió según lo observado; dos variantes aprobadas. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0230 | failed | Pidió confirmación en vez de leer el estado wifi. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0221 | failed | Pidió confirmación en vez de leer el estado wifi. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0302 | failed | Respondió con el estado de conexión sin aclarar que no puede listar redes disponibles. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 6 | H0455 | failed | Pidió confirmación con vocabulario interno en vez de leer la IP. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | H0568 | failed | Pidió confirmación en vez de leer la IP. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | H0481 | failed | Negó una capacidad que tiene (leer la IP). | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | H0732 | passed | Leyó el estado de red y respondió según lo observado; dos variantes aprobadas. | Final revisado con una admisión; una lectura de red verificada; cero confirmaciones y violaciones; pins intactos. |
| 10 | network1161-dev-01 | failed | Añadió un hecho no observado («no está en línea») a una lectura correcta. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 11 | network1161-dev-02 | failed | Añadió un hecho no observado («not online») a una lectura correcta. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 12 | network1161-dev-03 | passed | Variante original aprobada: estado wifi leído. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 13 | network1161-dev-04 | passed | Variante original aprobada: estado wifi leído. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 14 | network1161-dev-05 | failed | Afirmó que no hay redes guardadas sin haberlas listado. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 15 | network1161-dev-06 | failed | Afirmó que no hay redes guardadas sin haberlas listado. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 16 | network1161-dev-07 | failed | Pidió confirmar una lectura de sólo lectura; el runner detuvo el caso. | Final revisado con una admisión; ninguna operación; una violación de composición de confirmación registrada; pins intactos. |
| 17 | network1161-dev-08 | failed | Pidió confirmar una lectura de sólo lectura; el runner detuvo el caso. | Final revisado con una admisión; ninguna operación; una violación de composición de confirmación registrada; pins intactos. |
| 18 | network1161-dev-09 | passed | Variante original aprobada: estado de red leído. | Final revisado con una admisión; una lectura de red verificada; cero confirmaciones y violaciones; pins intactos. |
| 19 | network1161-dev-10 | passed | Variante original aprobada: estado de red leído. | Final revisado con una admisión; una lectura de red verificada; cero confirmaciones y violaciones; pins intactos. |
| 20 | network1161-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 21 | network1161-boundary-02 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 22 | network1161-boundary-03 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 376.92 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1664.48 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
