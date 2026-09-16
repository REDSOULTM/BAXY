# NETWORK1743 — adjudicación de la raíz

## NETWORK1743 — estado vigente 2026-09-16T20:00:17.364375+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 625/742 | 117 | 0 | >=509 | 12/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 509 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); NETWORK1743 añade 0. No se cuentan revalidaciones.

Siguiente acción: NETWORK1743: 5 ejecutados, 5 aprobados, 0 fallidos, 0 créditos (índices []); Red y Bluetooth 21/21. Siguiente: WEB1745 (Chrome por nombre) en la misma compilación.

Evidencia: `artifacts/comprobaciones/C03/NETWORK1743/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 107.66 s acumulados; pico GPU 3497.56 MiB; pico RAM 2113.36 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0302 | passed | Avisó que la radio wifi está apagada y ofreció encenderla; tras el sí, encendió la radio con revisión de la raíz, escaneó y nombró las redes observadas; re-demostración de H0302 (ya acreditado en NETWORK1729), sin crédito. | Caso de diálogo: primer turno con wifi.scan terminada wifi_interface_off y final que avisa que la radio está apagada y ofrece encenderla; respuesta afirmativa guionizada por la raíz; wifi.radio.set state = true propuesta, aprobada por la raíz, completada y verificada por la API de radios de Windows; wifi.scan completada y verificada; la raíz registró el estado de la radio antes y después y la apagó de nuevo; los nombres de red quedan en recibos privados; cero violaciones; pins intactos. |
| 1 | network1743-dev-01 | passed | Avisó que la radio wifi está apagada y ofreció encenderla; tras el sí, encendió la radio con revisión de la raíz, escaneó y nombró las redes observadas; variante del literal. | Caso de diálogo: primer turno con wifi.scan terminada wifi_interface_off y final que avisa que la radio está apagada y ofrece encenderla; respuesta afirmativa guionizada por la raíz; wifi.radio.set state = true propuesta, aprobada por la raíz, completada y verificada por la API de radios de Windows; wifi.scan completada y verificada; la raíz registró el estado de la radio antes y después y la apagó de nuevo; los nombres de red quedan en recibos privados; cero violaciones; pins intactos. |
| 2 | network1743-dev-02 | passed | Avisó que la radio wifi está apagada y ofreció encenderla; tras el sí, encendió la radio con revisión de la raíz, escaneó y nombró las redes observadas; variante del literal. | Caso de diálogo: primer turno con wifi.scan terminada wifi_interface_off y final que avisa que la radio está apagada y ofrece encenderla; respuesta afirmativa guionizada por la raíz; wifi.radio.set state = true propuesta, aprobada por la raíz, completada y verificada por la API de radios de Windows; wifi.scan completada y verificada; la raíz registró el estado de la radio antes y después y la apagó de nuevo; los nombres de red quedan en recibos privados; cero violaciones; pins intactos. |
| 3 | network1743-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | network1743-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 107.66 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2113.36 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
