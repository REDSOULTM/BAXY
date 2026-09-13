# CLOCK1157 — adjudicación de la raíz

## CLOCK1157 — estado vigente 2026-09-13T06:03:47+00:00

Parcial: 1 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 235/742 | 507 | 0 | >=109 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 109 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; CLOCK1157 no añade. No se cuentan revalidaciones.

Siguiente acción: CLOCK1157 completa: 4 ejecutados, 1 aprobado (límite), 3 fallidos, 0 créditos. La reparación del mind (fecha proyectada para «día») es necesaria pero el shell debe leer «día/day» igual: UserMessagePolicy.dateRequested sólo cubre fecha|date y exige la hora en el borrador; los borradores correctos se rechazan y el producto publica el código interno (defecto R07 de agotamiento). Siguiente: alinear el shell (dateRequested con día/day), BUILD, y remedir H0243 con los mismos pares.

Evidencia: `artifacts/comprobaciones/C03/CLOCK1157/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 79.61 s acumulados; pico GPU 3497.56 MiB; pico RAM 1682.72 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 4; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0243 | failed | Leyó el reloj y redactó la fecha correcta, pero el shell rechazó el borrador por falta de hora y publicó un código interno. | Final revisado con una admisión; una lectura del reloj verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | clock1157-dev-01 | failed | Borrador correcto rechazado por el shell; código interno publicado. | Final revisado con una admisión; una lectura del reloj verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | clock1157-dev-02 | failed | Borrador correcto rechazado por el shell; código interno publicado. | Final revisado con una admisión; una lectura del reloj verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | clock1157-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 79.61 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1682.72 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
