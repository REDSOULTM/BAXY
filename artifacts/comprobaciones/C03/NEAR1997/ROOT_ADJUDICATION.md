# NEAR1997 — adjudicación de la raíz

## NEAR1997 — estado vigente 2026-09-21T04:12:18.740376+00:00

Parcial: 4 aprobados, 4 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 652/742 | 90 | 0 | >=628 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 628 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); NEAR1997 añade 0. No se cuentan revalidaciones.

Siguiente acción: NEAR1997: 8 ejecutados, 4 aprobados, 4 fallidos, 0 créditos (índices []). Siguiente: las tandas de las demás lecturas de REOPEN1993 (alarma de la sesión, otra ventana, mirar la pantalla, ponle texto) y cien.

Evidencia: `artifacts/comprobaciones/C03/NEAR1997/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 320.14 s acumulados; pico GPU 3492.93 MiB; pico RAM 2420.75 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0227 | failed | Falló: no abrió Steam, preguntó, o el final no lo dijo con verdad. | Turno ordinario: una app.open de Steam completada y verificada sin preguntar; el final dijo que la app ya estaba abierta sin nombrarla; pins intactos. |
| 1 | H0398 | failed | Falló: no abrió Steam, preguntó, o el final no lo dijo con verdad. | Turno ordinario: una app.open de Steam completada y verificada sin preguntar; el final dijo que la app ya estaba abierta sin nombrarla; pins intactos. |
| 2 | H0521 | failed | Falló: no abrió Steam, preguntó, o el final no lo dijo con verdad. | Turno ordinario: una app.open de Steam completada y verificada sin preguntar; el final dijo que la app ya estaba abierta sin nombrarla; pins intactos. |
| 3 | near1997-dev-01 | passed | una app.open de Steam verificada sin preguntar; el final nombra Steam y dice que lo abrió o que ya estaba abierto. | Turno ordinario: exactamente una app.open de Steam completada y verificada (el Steam del dueño reutilizado, ninguna pregunta); el final dice que abrió Steam o que ya estaba abierto; cero confirmaciones y violaciones; pins intactos. |
| 4 | near1997-dev-02 | passed | una app.open de Steam verificada sin preguntar; el final nombra Steam y dice que lo abrió o que ya estaba abierto. | Turno ordinario: exactamente una app.open de Steam completada y verificada (el Steam del dueño reutilizado, ninguna pregunta); el final dice que abrió Steam o que ya estaba abierto; cero confirmaciones y violaciones; pins intactos. |
| 5 | near1997-dev-03 | failed | Falló: no abrió Steam, preguntó, o el final no lo dijo con verdad. | Turno ordinario: una app.open de Steam completada y verificada sin preguntar; el final dijo que la app ya estaba abierta sin nombrarla; pins intactos. |
| 6 | near1997-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | near1997-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 320.14 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2420.75 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
