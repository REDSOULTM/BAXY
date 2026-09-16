# NETWORK1741 — adjudicación de la raíz

## NETWORK1741 — estado vigente 2026-09-16T19:38:45.567688+00:00

Parcial: 2 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 625/742 | 117 | 0 | >=509 | 12/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 509 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); NETWORK1741 añade 0. No se cuentan revalidaciones.

Siguiente acción: NETWORK1741: 5 ejecutados, 2 aprobados, 3 fallidos, 0 créditos (índices []); Red y Bluetooth 21/21. Siguiente: WEB1741 (Chrome por nombre) en la misma compilación.

Evidencia: `artifacts/comprobaciones/C03/NETWORK1741/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 100.66 s acumulados; pico GPU 3497.56 MiB; pico RAM 2072.93 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0302 | failed | Falló: no avisó ni ofreció, o tras el sí no encendió la radio ni escaneó con verificación, o el final citó redes no observadas o afirmó de más, o no hubo final. | Caso de diálogo: primer turno con wifi.scan terminada wifi_interface_off y final que avisa que la radio está apagada y ofrece encenderla; tras la respuesta afirmativa guionizada por la raíz, el producto propuso la misión y pidió confirmación, pero la captura revisada rechazó la forma del plan de dos pasos y no llegó ninguna proposición a la raíz; radio Off antes y después; cero violaciones; pins intactos. |
| 1 | network1741-dev-01 | failed | Falló: no avisó ni ofreció, o tras el sí no encendió la radio ni escaneó con verificación, o el final citó redes no observadas o afirmó de más, o no hubo final. | Caso de diálogo: primer turno con wifi.scan terminada wifi_interface_off y final que avisa que la radio está apagada y ofrece encenderla; tras la respuesta afirmativa guionizada por la raíz, el producto propuso la misión y pidió confirmación, pero la captura revisada rechazó la forma del plan de dos pasos y no llegó ninguna proposición a la raíz; radio Off antes y después; cero violaciones; pins intactos. |
| 2 | network1741-dev-02 | failed | Falló: no avisó ni ofreció, o tras el sí no encendió la radio ni escaneó con verificación, o el final citó redes no observadas o afirmó de más, o no hubo final. | Caso de diálogo: primer turno con wifi.scan terminada wifi_interface_off y final que avisa que la radio está apagada y ofrece encenderla; tras la respuesta afirmativa guionizada por la raíz, el producto propuso la misión y pidió confirmación, pero la captura revisada rechazó la forma del plan de dos pasos y no llegó ninguna proposición a la raíz; radio Off antes y después; cero violaciones; pins intactos. |
| 3 | network1741-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | network1741-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 100.66 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2072.93 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
