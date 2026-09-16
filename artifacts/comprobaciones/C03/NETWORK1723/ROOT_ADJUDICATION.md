# NETWORK1723 — adjudicación de la raíz

## NETWORK1723 — estado vigente 2026-09-16T15:38:36.225215+00:00

Parcial: 7 aprobados, 0 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 617/742 | 125 | 0 | >=501 | 10/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 498 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); NETWORK1723 añade 3. No se cuentan revalidaciones.

Siguiente acción: NETWORK1723: 7 ejecutados, 7 aprobados, 0 fallidos, 3 créditos (índices [0, 1, 2]); Red y Bluetooth 19/21. Siguiente: UI1725 (aritmética en la Calculadora) y LIMITS1727 (H0077).

Evidencia: `artifacts/comprobaciones/C03/NETWORK1723/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 127.41 s acumulados; pico GPU 3497.56 MiB; pico RAM 1698.46 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 7; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0170 | passed | La conexión al wifi nombrado se revisó y aprobó, ningún perfil guardado lleva ese nombre, el intento terminó con el código sellado wifi_profile_not_found y el final lo dijo con verdad sin tocar la conectividad; crédito con dos variantes aprobadas del grupo (fallo honesto sellado). | Turno revisado: wifi.connect.named propuesta con el nombre pedido, aprobada por la raíz tras comprobar que ningún perfil guardado coincide, terminada con el código sellado wifi_profile_not_found (fallo honesto); estado WLAN del dueño intacto; una confirmación; cero violaciones; pins intactos; final veraz. |
| 1 | H0376 | passed | La conexión al wifi nombrado se revisó y aprobó, ningún perfil guardado lleva ese nombre, el intento terminó con el código sellado wifi_profile_not_found y el final lo dijo con verdad sin tocar la conectividad; crédito con dos variantes aprobadas del grupo (fallo honesto sellado). | Turno revisado: wifi.connect.named propuesta con el nombre pedido, aprobada por la raíz tras comprobar que ningún perfil guardado coincide, terminada con el código sellado wifi_profile_not_found (fallo honesto); estado WLAN del dueño intacto; una confirmación; cero violaciones; pins intactos; final veraz. |
| 2 | H0739 | passed | La conexión al wifi nombrado se revisó y aprobó, ningún perfil guardado lleva ese nombre, el intento terminó con el código sellado wifi_profile_not_found y el final lo dijo con verdad sin tocar la conectividad; crédito con dos variantes aprobadas del grupo (fallo honesto sellado). | Turno revisado: wifi.connect.named propuesta con el nombre pedido, aprobada por la raíz tras comprobar que ningún perfil guardado coincide, terminada con el código sellado wifi_profile_not_found (fallo honesto); estado WLAN del dueño intacto; una confirmación; cero violaciones; pins intactos; final veraz. |
| 3 | network1723-dev-01 | passed | La conexión al wifi nombrado se revisó y aprobó, ningún perfil guardado lleva ese nombre, el intento terminó con el código sellado wifi_profile_not_found y el final lo dijo con verdad sin tocar la conectividad. | Turno revisado: wifi.connect.named propuesta con el nombre pedido, aprobada por la raíz tras comprobar que ningún perfil guardado coincide, terminada con el código sellado wifi_profile_not_found (fallo honesto); estado WLAN del dueño intacto; una confirmación; cero violaciones; pins intactos; final veraz. |
| 4 | network1723-dev-02 | passed | La conexión al wifi nombrado se revisó y aprobó, ningún perfil guardado lleva ese nombre, el intento terminó con el código sellado wifi_profile_not_found y el final lo dijo con verdad sin tocar la conectividad. | Turno revisado: wifi.connect.named propuesta con el nombre pedido, aprobada por la raíz tras comprobar que ningún perfil guardado coincide, terminada con el código sellado wifi_profile_not_found (fallo honesto); estado WLAN del dueño intacto; una confirmación; cero violaciones; pins intactos; final veraz. |
| 5 | network1723-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | network1723-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 127.41 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1698.46 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
