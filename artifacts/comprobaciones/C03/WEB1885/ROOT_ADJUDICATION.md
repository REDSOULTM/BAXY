# WEB1885 — adjudicación de la raíz

## WEB1885 — estado vigente 2026-09-19T05:10:09.946792+00:00

Parcial: 3 aprobados, 2 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 683/742 | 59 | 0 | >=567 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 567 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEB1885 añade 0. No se cuentan revalidaciones.

Siguiente acción: WEB1885: 5 ejecutados, 3 aprobados, 2 fallidos, 0 créditos (índices []); Navegación y búsqueda web 44/46. Siguiente: filas de Spotify (media.play.query) y Discord (navegación por buscador).

Evidencia: `artifacts/comprobaciones/C03/WEB1885/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 116.72 s acumulados; pico GPU 3508.37 MiB; pico RAM 3666.18 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0081 | failed | Falló: la navegación no se verificó en el navegador nombrado, o el final afirmó otra cosa, o no hubo final. | Turno revisado: cero operaciones; cero violaciones; pins intactos; el final preguntó si abrir en vez de abrir. |
| 1 | web1885-dev-01 | passed | Abrió el sitio pedido en el navegador nombrado con revisión de la raíz y lo dijo; variante o literal sin dos pares aprobados. | Turno revisado: browser.navigate.named propuesta con el navegador nombrado y la URL del sitio, aprobada por la raíz, completada y verificada (identidad del ejecutable y URL final) en el perfil CDP privado del producto; la raíz cerró después esa instancia (sólo el perfil del producto; los navegadores del dueño no se tocan); una confirmación; cero violaciones; pins intactos. |
| 2 | web1885-dev-02 | passed | Abrió el sitio pedido en el navegador nombrado con revisión de la raíz y lo dijo; variante o literal sin dos pares aprobados. | Turno revisado: browser.navigate.named propuesta con el navegador nombrado y la URL del sitio, aprobada por la raíz, completada y verificada (identidad del ejecutable y URL final) en el perfil CDP privado del producto; la raíz cerró después esa instancia (sólo el perfil del producto; los navegadores del dueño no se tocan); una confirmación; cero violaciones; pins intactos. |
| 3 | web1885-boundary-01 | failed | Límite fallido: cero navegaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | web1885-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 116.72 s de segmentos; pico GPU 3508.37 MiB; pico RAM 3666.18 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
