# BRIGHT1319 — adjudicación de la raíz

## BRIGHT1319 — estado vigente 2026-09-14T03:05:01.706194+00:00

Parcial: 8 aprobados, 2 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 388/742 | 354 | 0 | >=262 | 2/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 261 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); BRIGHT1319 añade 1. No se cuentan revalidaciones.

Siguiente acción: BRIGHT1319: 10 ejecutados, 8 aprobados, 2 fallidos, 1 créditos (índices [1]); Brillo y pantalla 14/17 (H0459 fondo de pantalla sin mecanismo). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/BRIGHT1319/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 179.58 s acumulados; pico GPU 3497.56 MiB; pico RAM 2300.82 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0430 | failed | Falló: el final no fue fiel al nivel observado, no leyó, tocó el brillo o no reconoció la restricción. | Turno revisado: system.settings.set (brightness, 80) propuesta, aprobada por la raíz por valor exacto, completada y verificada por WMI; una confirmación; cero violaciones; ningún final publicado (borradores agotados); pins intactos. |
| 1 | H0496 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos (brillo verificado igual antes y después por la raíz). |
| 2 | H0674 | failed | Falló: el final no fue fiel al nivel observado, no leyó, tocó el brillo o no reconoció la restricción. | Turno ordinario: system.settings.status (brightness) de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos; el final contradijo el valor observado. |
| 3 | bright1319-dev-01 | passed | Respuesta fiel y útil. | Turno revisado: system.settings.set (brightness, valor pedido) propuesta, aprobada por la raíz por valor exacto, completada y verificada por WMI; una confirmación; cero violaciones; pins intactos. |
| 4 | bright1319-dev-02 | passed | Respuesta fiel y útil. | Turno revisado: system.settings.set (brightness, valor pedido) propuesta, aprobada por la raíz por valor exacto, completada y verificada por WMI; una confirmación; cero violaciones; pins intactos. |
| 5 | bright1319-dev-03 | passed | Respuesta fiel y útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos (brillo verificado igual antes y después por la raíz). |
| 6 | bright1319-dev-04 | passed | Respuesta fiel y útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos (brillo verificado igual antes y después por la raíz). |
| 7 | bright1319-dev-05 | passed | Respuesta fiel y útil. | Turno ordinario: system.settings.status (brightness) de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 8 | bright1319-dev-06 | passed | Respuesta fiel y útil. | Turno ordinario: system.settings.status (brightness) de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 9 | bright1319-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos (brillo verificado igual antes y después por la raíz). |

Recursos: 179.58 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2300.82 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
