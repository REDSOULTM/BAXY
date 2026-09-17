# WEB1805 — adjudicación de la raíz

## WEB1805 — estado vigente 2026-09-17T04:29:47.021293+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 641/742 | 101 | 0 | >=525 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 524 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEB1805 añade 1. No se cuentan revalidaciones.

Siguiente acción: WEB1805: 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos (índices [0]); Navegación y búsqueda web 43/46. Siguiente: filas de Spotify (media.play.query) y Discord (navegación por buscador).

Evidencia: `artifacts/comprobaciones/C03/WEB1805/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 132.80 s acumulados; pico GPU 3528.40 MiB; pico RAM 3409.62 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0094 | passed | Abrió el sitio pedido en el navegador nombrado con revisión de la raíz y lo dijo; crédito con dos variantes aprobadas. | Turno revisado: browser.navigate.named propuesta con el navegador nombrado y la URL del sitio, aprobada por la raíz, completada y verificada (identidad del ejecutable y URL final) en el perfil CDP privado del producto; la raíz cerró después esa instancia (sólo el perfil del producto; los navegadores del dueño no se tocan); una confirmación; cero violaciones; pins intactos. |
| 1 | web1805-dev-01 | passed | Abrió el sitio pedido en el navegador nombrado con revisión de la raíz y lo dijo; variante o literal sin dos pares aprobados. | Turno revisado: browser.navigate.named propuesta con el navegador nombrado y la URL del sitio, aprobada por la raíz, completada y verificada (identidad del ejecutable y URL final) en el perfil CDP privado del producto; la raíz cerró después esa instancia (sólo el perfil del producto; los navegadores del dueño no se tocan); una confirmación; cero violaciones; pins intactos. |
| 2 | web1805-dev-02 | passed | Abrió el sitio pedido en el navegador nombrado con revisión de la raíz y lo dijo; variante o literal sin dos pares aprobados. | Turno revisado: browser.navigate.named propuesta con el navegador nombrado y la URL del sitio, aprobada por la raíz, completada y verificada (identidad del ejecutable y URL final) en el perfil CDP privado del producto; la raíz cerró después esa instancia (sólo el perfil del producto; los navegadores del dueño no se tocan); una confirmación; cero violaciones; pins intactos. |
| 3 | web1805-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | web1805-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 132.80 s de segmentos; pico GPU 3528.40 MiB; pico RAM 3409.62 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
