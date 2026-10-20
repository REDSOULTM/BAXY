# Computer use, caso a caso (goal CU rápido, 2026-10-20)

Producto de partida d7a76adf1 (hub/baxy-renew 51cd74225, modelo c2-e1.0, ayudas encendidas). Cada caso se corrió una
vez en vivo por el conductor, en el escritorio real de su máquina, y su variante para no arreglar una sola frase. Los
pedidos reales del dueño viven fuera del repositorio (`F:\BAXYeval\cu_v1\casos_cu.md`); aquí, cada caso en genérico.

Veredictos: **funciona**, **arreglado** (no funcionaba y ahora sí, con su variante), **a medias** (el pedido real sí,
la variante no), **pendiente** (causa sabida, arreglo fuera del tope).

| Caso | Patrón (genérico) | Máq. | Antes | Después | Causa (archivo:línea) | Arreglo | Commit |
|---|---|---|---|---|---|---|---|
| C04 | Abrir en un lanzador la página de un juego concreto, por su nombre | PC | no funciona: abre Steam y hace 8-15 clics en TIENDA/BIBLIOTECA/«Buscar en la tienda» hasta fallar | pedido real **arreglado** (3 pasos, 8,6 s: `app.open` place `game` con el título, mirada, respuesta cierta); variante **a medias** | el place `game` sólo admitía el número de catálogo (`ApplicationPlaces.cs:79`, `{game}` = dígitos) y el modelo sólo tiene el título; el resultado de `app.open` sin place no decía qué places tiene la app; un valor que el place no admite se rechazaba como «place de otra app» (`AppOpenHandler.cs:57`) | `game` acepta el título: Steam lo resuelve con sus juegos instalados y la búsqueda pública de la tienda (`SteamLocalAdapter.PageTitleAsync`, `GameTitles.cs`) y el resultado nombra el juego hallado (`placeGame`); ayuda nueva `app_places` (el resultado de `app.open` sin place lista los places de esa app y lo que toma cada uno); rechazo `place_value_not_taken` con lo que toma cada place; una frase en la descripción de `app.open` | ver git log «CU C04» |
| C05 | Buscar dentro de la tienda de un lanzador (no en lo instalado) | PC | no funciona: lista los juegos instalados que contienen el término y contesta «lo tienes instalado» | variante **arreglada** (`app.open` place `results` con el término, mirada, respuesta cierta, 10 s); pedido real **a medias**: ya no responde en falso, pero busca a clics en la tienda y acaba en un fallo honesto | `game.catalog.list` no decía que es sólo lo instalado frente a la búsqueda de la tienda (`tool_descriptions.en.v1.json`, game.catalog.list); `placeValue` no decía que un tema basta, y el modelo pedía un título exacto | dos frases: game.catalog.list («searching games to find or buy (the store's search: app_open Steam with place results)») y placeValue de app.open («the person's own words, a topic or a kind of game is enough») | ver git log «CU C05» |
| C10 | Dar formato en un procesador de texto a lo seleccionado | NB | no funciona: la mirada caía a «sin árbol» y los clics iban a índices inventados | pedido real **arreglado**; variante pendiente (ver nota) | `DesktopUiaWorker.ps1:2678` (`@($found).Count` sobre `List[object]` lanza en PS 5.1 con >150 controles y alguno deshabilitado: toda ventana grande sin árbol) | `$found.Count` | 6d7bb0516 |
| C11 | Seleccionar una fila o columna de una hoja de cálculo y darle formato | NB | no funciona | **pendiente** | (1) la vista de la hoja lista 60 de ~375 controles y los encabezados de fila/columna quedan tras el tope; el modelo no usa `wanted` (una frase en la línea del tope no cambió nada en vivo y se revirtió); (2) el clic UIA sobre «Seleccionar todo» no selecciona (postread_unchanged); (3) el recibo de Negrita no dice a qué celdas se aplicó y el modelo afirmó la fila 1 (falsedad) | ninguno dentro del tope | — |

Notas:
- **C04, variante («la página de <otro juego>»)**: el modelo resuelve antes el título con `game.entitlement.named` (lo
  obtiene: appId), y después busca el juego con clics en la biblioteca; no usa el place `game`. Arreglarlo con
  un hecho en el resultado de `game.entitlement.named` empujaría a abrir páginas en las preguntas «¿lo tengo?»: queda
  pendiente.
- **C10, variante (otro formato)**: el modelo no mira y elige `input.key.press` con un atajo inexistente. Frase añadida
  a `input.key.press` en `tool_descriptions.en.v1.json` («applying a format … look at the window and click its
  button»); su efecto lo comprueba el notebook.
