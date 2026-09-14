# BRIGHT1321 — adjudicación de la raíz

## BRIGHT1321 — estado vigente 2026-09-14T03:15:03.296889+00:00

Parcial: 10 aprobados, 0 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 390/742 | 352 | 0 | >=264 | 2/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 262 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); BRIGHT1321 añade 2. No se cuentan revalidaciones.

Siguiente acción: BRIGHT1321: 10 ejecutados, 10 aprobados, 0 fallidos, 2 créditos (índices [0, 1]); Brillo y pantalla 16/17 (H0459 fondo de pantalla sin mecanismo). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/BRIGHT1321/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 180.03 s acumulados; pico GPU 3497.56 MiB; pico RAM 1657.95 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0430 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno revisado: system.settings.set (brightness, valor pedido) propuesta, aprobada por la raíz por valor exacto, completada y verificada por WMI; una confirmación; cero violaciones; pins intactos. |
| 1 | H0674 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno ordinario: system.settings.status (brightness) de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | bright1321-dev-01 | passed | Respuesta fiel y útil. | Turno revisado: system.settings.set (brightness, valor pedido) propuesta, aprobada por la raíz por valor exacto, completada y verificada por WMI; una confirmación; cero violaciones; pins intactos. |
| 3 | bright1321-dev-02 | passed | Respuesta fiel y útil. | Turno revisado: system.settings.set (brightness, valor pedido) propuesta, aprobada por la raíz por valor exacto, completada y verificada por WMI; una confirmación; cero violaciones; pins intactos. |
| 4 | bright1321-dev-03 | passed | Respuesta fiel y útil. | Turno ordinario: system.settings.status (brightness) de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 5 | bright1321-dev-04 | passed | Respuesta fiel y útil. | Turno ordinario: system.settings.status (brightness) de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 6 | bright1321-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos (brillo verificado igual antes y después por la raíz). |
| 7 | bright1321-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos (brillo verificado igual antes y después por la raíz). |
| 8 | bright1321-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos (brillo verificado igual antes y después por la raíz). |
| 9 | bright1321-boundary-04 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos (brillo verificado igual antes y después por la raíz). |

Recursos: 180.03 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1657.95 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
