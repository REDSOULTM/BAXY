# NETWORK1165 — adjudicación de la raíz

## NETWORK1165 — estado vigente 2026-09-13T06:44:18+00:00

Parcial: 7 aprobados, 1 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 240/742 | 502 | 0 | >=114 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 113 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; NETWORK1165 añade 1. No se cuentan revalidaciones.

Siguiente acción: NETWORK1165 completa: 8 ejecutados, 7 aprobados, 1 fallido, 1 crédito (H0221). H0127/H0433 aprobados por tercera vez sin crédito: el par inglés de red conectada añade siempre «offline» (hecho no observado; el equipo está online por cable). Causa a reparar antes de otra remedición: compositor/validador de wifi.status (no permitir afirmaciones sobre internet cuando sólo se observó la conexión wifi). Red queda 4/21.

Evidencia: `artifacts/comprobaciones/C03/NETWORK1165/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 132.47 s acumulados; pico GPU 3497.56 MiB; pico RAM 1651.54 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0127 | passed | Informó fielmente que no hay conexión wifi; sin crédito por faltar un segundo par aprobado. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0433 | passed | Informó fielmente que no hay conexión wifi; sin crédito por faltar un segundo par aprobado. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0221 | passed | Leyó el estado wifi y respondió según lo observado; dos variantes aprobadas. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | network1165-dev-01 | passed | Variante original aprobada: estado wifi leído. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 4 | network1165-dev-02 | failed | Añadió «offline», hecho no observado, a una lectura correcta. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 5 | network1165-dev-03 | passed | Variante original aprobada: estado wifi leído. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 6 | network1165-dev-04 | passed | Variante original aprobada: estado wifi leído. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 7 | network1165-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 132.47 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1651.54 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
