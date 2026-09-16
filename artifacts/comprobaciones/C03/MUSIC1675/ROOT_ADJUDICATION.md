# MUSIC1675 — adjudicación de la raíz

## MUSIC1675 — estado vigente 2026-09-16T04:58:46.205386+00:00

Parcial: 4 aprobados, 1 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 602/742 | 140 | 0 | >=476 | 9/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 475 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MUSIC1675 añade 1. No se cuentan revalidaciones.

Siguiente acción: MUSIC1675: 6 ejecutados, 4 aprobados, 2 fallidos, 1 créditos (índices [0]); Abrir aplicaciones 47/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/MUSIC1675/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 115.94 s acumulados; pico GPU 3497.56 MiB; pico RAM 1796.24 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0421 | passed | Pausa condicionada a Spotify abierto: window.resolve terminó window_not_found, ninguna media.control y el final dijo que no está abierto; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una window.resolve sobre Spotify terminada window_not_found (sin ventana), ninguna media.control; nada pausado; cero confirmaciones y violaciones; pins intactos. |
| 1 | music1675-dev-01 | passed | Pausa condicionada a Spotify abierto: window.resolve terminó window_not_found, ninguna media.control y el final dijo que no está abierto. | Turno ordinario: exactamente una window.resolve sobre Spotify terminada window_not_found (sin ventana), ninguna media.control; nada pausado; cero confirmaciones y violaciones; pins intactos. |
| 2 | music1675-dev-02 | passed | Pausa condicionada a Spotify abierto: window.resolve terminó window_not_found, ninguna media.control y el final dijo que no está abierto. | Turno ordinario: exactamente una window.resolve sobre Spotify terminada window_not_found (sin ventana), ninguna media.control; nada pausado; cero confirmaciones y violaciones; pins intactos. |
| 3 | music1675-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | music1675-boundary-02 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 115.94 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1796.24 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
