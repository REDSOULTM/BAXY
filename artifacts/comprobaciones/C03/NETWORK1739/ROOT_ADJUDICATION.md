# NETWORK1739 — adjudicación de la raíz

## NETWORK1739 — estado vigente 2026-09-16T19:06:52.200589+00:00

Parcial: 0 aprobados, 5 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 625/742 | 117 | 0 | >=509 | 12/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 509 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); NETWORK1739 añade 0. No se cuentan revalidaciones.

Siguiente acción: NETWORK1739: 5 ejecutados, 0 aprobados, 5 fallidos, 0 créditos (índices []); Red y Bluetooth 21/21. Siguiente: WEB1741 (Chrome por nombre) en la misma compilación.

Evidencia: `artifacts/comprobaciones/C03/NETWORK1739/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 18.56 s acumulados; pico GPU 0.00 MiB; pico RAM 209.13 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0302 | failed | Falló: no avisó ni ofreció, o tras el sí no encendió la radio ni escaneó con verificación, o el final citó redes no observadas o afirmó de más, o no hubo final. | La App se detuvo al arrancar (núcleo con excepción de inicialización por valores de catálogo sin ordenar); ningún turno, ninguna operación; cero violaciones; pins intactos. |
| 1 | network1739-dev-01 | failed | Falló: no avisó ni ofreció, o tras el sí no encendió la radio ni escaneó con verificación, o el final citó redes no observadas o afirmó de más, o no hubo final. | La App se detuvo al arrancar (núcleo con excepción de inicialización por valores de catálogo sin ordenar); ningún turno, ninguna operación; cero violaciones; pins intactos. |
| 2 | network1739-dev-02 | failed | Falló: no avisó ni ofreció, o tras el sí no encendió la radio ni escaneó con verificación, o el final citó redes no observadas o afirmó de más, o no hubo final. | La App se detuvo al arrancar (núcleo con excepción de inicialización por valores de catálogo sin ordenar); ningún turno, ninguna operación; cero violaciones; pins intactos. |
| 3 | network1739-boundary-01 | failed | Límite fallido: cero operaciones de radio, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | network1739-boundary-02 | failed | Límite fallido: cero operaciones de radio, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 18.56 s de segmentos; pico GPU 0.00 MiB; pico RAM 209.13 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
