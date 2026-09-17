# WEB1803 — adjudicación de la raíz

## WEB1803 — estado vigente 2026-09-17T04:25:07.771621+00:00

Parcial: 3 aprobados, 2 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 640/742 | 102 | 0 | >=524 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 524 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEB1803 añade 0. No se cuentan revalidaciones.

Siguiente acción: WEB1803: 5 ejecutados, 3 aprobados, 2 fallidos, 0 créditos (índices []); Navegación y búsqueda web 42/46. Siguiente: filas de Spotify (media.play.query) y Discord (navegación por buscador).

Evidencia: `artifacts/comprobaciones/C03/WEB1803/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 113.41 s acumulados; pico GPU 3528.40 MiB; pico RAM 3449.93 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0094 | passed | Abrió el sitio pedido en el navegador nombrado con revisión de la raíz y lo dijo; variante o literal sin dos pares aprobados. | Turno revisado: browser.navigate.named propuesta con el navegador nombrado y la URL del sitio, aprobada por la raíz, completada y verificada (identidad del ejecutable y URL final) en el perfil CDP privado del producto; la raíz cerró después esa instancia (sólo el perfil del producto; los navegadores del dueño no se tocan); una confirmación; cero violaciones; pins intactos. |
| 1 | web1803-dev-01 | passed | Abrió el sitio pedido en el navegador nombrado con revisión de la raíz y lo dijo; variante o literal sin dos pares aprobados. | Turno revisado: browser.navigate.named propuesta con el navegador nombrado y la URL del sitio, aprobada por la raíz, completada y verificada (identidad del ejecutable y URL final) en el perfil CDP privado del producto; la raíz cerró después esa instancia (sólo el perfil del producto; los navegadores del dueño no se tocan); una confirmación; cero violaciones; pins intactos. |
| 2 | web1803-dev-02 | failed | Falló: la navegación no se verificó en el navegador nombrado, o el final afirmó otra cosa, o no hubo final. | Turno revisado detenido: la mente propuso una búsqueda web genérica en lugar de la navegación en el navegador nombrado; operación fuera de la lista permitida; sin final; pins intactos. |
| 3 | web1803-boundary-01 | failed | Límite fallido: cero navegaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | web1803-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 113.41 s de segmentos; pico GPU 3528.40 MiB; pico RAM 3449.93 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
