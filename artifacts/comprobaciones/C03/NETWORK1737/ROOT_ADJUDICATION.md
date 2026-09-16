# NETWORK1737 — adjudicación de la raíz

## NETWORK1737 — estado vigente 2026-09-16T18:29:15.314155+00:00

Parcial: 5 aprobados, 3 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 625/742 | 117 | 0 | >=509 | 11/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 508 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); NETWORK1737 añade 1. No se cuentan revalidaciones.

Siguiente acción: NETWORK1737: 8 ejecutados, 5 aprobados, 3 fallidos, 1 créditos (índices [1]); Red y Bluetooth 21/21. Siguiente: filas de Chrome y Spotify.

Evidencia: `artifacts/comprobaciones/C03/NETWORK1737/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 150.83 s acumulados; pico GPU 3497.56 MiB; pico RAM 1782.09 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0302 | failed | Falló: no avisó ni ofreció, o la radio no cambió verificada, o el escaneo no se completó, o el final citó redes no observadas o afirmó de más, o no hubo final. | Caso de diálogo: primer turno con wifi.scan terminada wifi_interface_off y final que avisa que la radio está apagada y ofrece encenderla; tras la respuesta afirmativa guionizada por la raíz, el producto no propuso ninguna operación y preguntó otra vez el estado de la radio; la raíz registró la radio Off antes y después; cero violaciones; pins intactos. |
| 1 | H0324 | passed | Apagó la radio wifi con revisión de la raíz y lo dijo; crédito con dos variantes aprobadas del grupo. | Turno revisado: la raíz encendió la radio antes del caso; wifi.radio.set state = false propuesta, aprobada por la raíz, completada y verificada por la API de radios de Windows; cero violaciones; pins intactos. |
| 2 | network1737-dev-01 | failed | Falló: no avisó ni ofreció, o la radio no cambió verificada, o el escaneo no se completó, o el final citó redes no observadas o afirmó de más, o no hubo final. | Caso de diálogo: primer turno con wifi.scan terminada wifi_interface_off y final que avisa que la radio está apagada y ofrece encenderla; tras la respuesta afirmativa guionizada por la raíz, el producto no propuso ninguna operación y preguntó otra vez el estado de la radio; la raíz registró la radio Off antes y después; cero violaciones; pins intactos. |
| 3 | network1737-dev-02 | failed | Falló: no avisó ni ofreció, o la radio no cambió verificada, o el escaneo no se completó, o el final citó redes no observadas o afirmó de más, o no hubo final. | Caso de diálogo: primer turno con wifi.scan terminada wifi_interface_off y final que avisa que la radio está apagada y ofrece encenderla; tras la respuesta afirmativa guionizada por la raíz, el producto no propuso ninguna operación y preguntó otra vez el estado de la radio; la raíz registró la radio Off antes y después; cero violaciones; pins intactos. |
| 4 | network1737-dev-03 | passed | Apagó la radio wifi con revisión de la raíz y lo dijo; variante o literal sin dos pares aprobados. | Turno revisado: la raíz encendió la radio antes del caso; wifi.radio.set state = false propuesta, aprobada por la raíz, completada y verificada por la API de radios de Windows; cero violaciones; pins intactos. |
| 5 | network1737-dev-04 | passed | Apagó la radio wifi con revisión de la raíz y lo dijo; variante o literal sin dos pares aprobados. | Turno revisado: la raíz encendió la radio antes del caso; wifi.radio.set state = false propuesta, aprobada por la raíz, completada y verificada por la API de radios de Windows; cero violaciones; pins intactos. |
| 6 | network1737-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | network1737-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 150.83 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1782.09 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
