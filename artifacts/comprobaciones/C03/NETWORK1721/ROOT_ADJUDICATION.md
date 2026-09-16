# NETWORK1721 — adjudicación de la raíz

## NETWORK1721 — estado vigente 2026-09-16T15:08:08.603197+00:00

Parcial: 2 aprobados, 5 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 614/742 | 128 | 0 | >=498 | 10/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 498 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); NETWORK1721 añade 0. No se cuentan revalidaciones.

Siguiente acción: NETWORK1721: 7 ejecutados, 2 aprobados, 5 fallidos, 0 créditos (índices []); Red y Bluetooth 16/21. Siguiente: reparar la rama de confirmación de la App (el hecho de fallo de la operación sustituido por confirmed_no_effect) y repetir el panel.

Evidencia: `artifacts/comprobaciones/C03/NETWORK1721/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 138.56 s acumulados; pico GPU 3497.56 MiB; pico RAM 1658.91 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 7; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0170 | failed | Falló: la conexión no terminó con el fallo honesto sellado, o el final no fue fiel. | Turno revisado: la raíz aprobó wifi.connect.named con el nombre pedido tras comprobar que ningún perfil guardado coincide; el proveedor terminó wifi_profile_not_found y la WLAN siguió igual; cero violaciones; pins intactos; el final no dio la causa («no hubo efecto» en lugar de «no hay ninguna red guardada con ese nombre»). |
| 1 | H0376 | failed | Falló: la conexión no terminó con el fallo honesto sellado, o el final no fue fiel. | Turno revisado: la raíz aprobó wifi.connect.named con el nombre pedido tras comprobar que ningún perfil guardado coincide; el proveedor terminó wifi_profile_not_found y la WLAN siguió igual; cero violaciones; pins intactos; el final no dio la causa («no hubo efecto» en lugar de «no hay ninguna red guardada con ese nombre»). |
| 2 | H0739 | failed | Falló: la conexión no terminó con el fallo honesto sellado, o el final no fue fiel. | Turno revisado: la raíz aprobó wifi.connect.named con el nombre pedido tras comprobar que ningún perfil guardado coincide; el proveedor terminó wifi_profile_not_found y la WLAN siguió igual; cero violaciones; pins intactos; el final no dio la causa («no hubo efecto» en lugar de «no hay ninguna red guardada con ese nombre»). |
| 3 | network1721-dev-01 | failed | Falló: la conexión no terminó con el fallo honesto sellado, o el final no fue fiel. | Turno revisado: la raíz aprobó wifi.connect.named con el nombre pedido tras comprobar que ningún perfil guardado coincide; el proveedor terminó wifi_profile_not_found y la WLAN siguió igual; cero violaciones; pins intactos; el final no dio la causa («no hubo efecto» en lugar de «no hay ninguna red guardada con ese nombre»). |
| 4 | network1721-dev-02 | failed | Falló: la conexión no terminó con el fallo honesto sellado, o el final no fue fiel. | Turno revisado: la raíz aprobó wifi.connect.named con el nombre pedido tras comprobar que ningún perfil guardado coincide; el proveedor terminó wifi_profile_not_found y la WLAN siguió igual; cero violaciones; pins intactos; el final no dio la causa («no hubo efecto» en lugar de «no hay ninguna red guardada con ese nombre»). |
| 5 | network1721-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | network1721-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 138.56 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1658.91 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
