# CLOCK1159 — adjudicación de la raíz

## CLOCK1159 — estado vigente 2026-09-13T06:08:50+00:00

Parcial: 4 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 236/742 | 506 | 0 | >=110 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 109 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; CLOCK1159 añade 1. No se cuentan revalidaciones.

Siguiente acción: CLOCK1159 completa: 4 ejecutados, 4 aprobados, 1 crédito (H0243). Las dos reparaciones (proyección de fecha en el mind + lectura de «día/day» en el shell) se demuestran juntas. Reloj queda 16/23 (abiertos H0399 cuenta atrás, H0054/H0312 «tiempo», y 4 límites sin marca). Siguiente: H0354 (ayuda abierta, dos pares) y H0703 («estoy aburrido»), luego categorías por masa según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/CLOCK1159/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 63.53 s acumulados; pico GPU 3497.56 MiB; pico RAM 1550.54 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 4; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0243 | passed | Leyó y dijo la fecha correcta; dos variantes aprobadas. | Final revisado con una admisión; una lectura del reloj verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | clock1159-dev-01 | passed | Variante original aprobada: fecha real leída. | Final revisado con una admisión; una lectura del reloj verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | clock1159-dev-02 | passed | Variante original aprobada: fecha real leída. | Final revisado con una admisión; una lectura del reloj verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | clock1159-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 63.53 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1550.54 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
