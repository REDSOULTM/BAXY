# Computer use, caso a caso (goal CU rápido, 2026-10-20)

Producto de partida d7a76adf1 (hub/baxy-renew 51cd74225, modelo c2-e1.0, ayudas encendidas). Cada caso se corrió una
vez en vivo por el conductor, en el escritorio real de su máquina, y su variante para no arreglar una sola frase. Los
pedidos reales del dueño viven fuera del repositorio (`F:\BAXYeval\cu_v1\casos_cu.md`); aquí, cada caso en genérico.

Veredictos: **funciona**, **arreglado** (no funcionaba y ahora sí, con su variante), **a medias** (el pedido real sí,
la variante no), **pendiente** (causa sabida, arreglo fuera del tope).

| Caso | Patrón (genérico) | Máq. | Antes | Después | Causa (archivo:línea) | Arreglo | Commit |
|---|---|---|---|---|---|---|---|
| C04 | Abrir en un lanzador la página de un juego concreto, por su nombre | PC | no funciona: abre Steam y hace 8-15 clics en TIENDA/BIBLIOTECA/«Buscar en la tienda» hasta fallar | pedido real **arreglado** (3 pasos, 8,6 s: `app.open` place `game` con el título, mirada, respuesta cierta); variante **a medias** | el place `game` sólo admitía el número de catálogo (`ApplicationPlaces.cs:79`, `{game}` = dígitos) y el modelo sólo tiene el título; el resultado de `app.open` sin place no decía qué places tiene la app; un valor que el place no admite se rechazaba como «place de otra app» (`AppOpenHandler.cs:57`) | `game` acepta el título: Steam lo resuelve con sus juegos instalados y la búsqueda pública de la tienda (`SteamLocalAdapter.PageTitleAsync`, `GameTitles.cs`) y el resultado nombra el juego hallado (`placeGame`); ayuda nueva `app_places` (el resultado de `app.open` sin place lista los places de esa app y lo que toma cada uno); rechazo `place_value_not_taken` con lo que toma cada place; una frase en la descripción de `app.open` | ver git log «CU C04» |
| C10 | Dar formato en un procesador de texto a lo seleccionado | NB | no funciona: la mirada caía a «sin árbol» y los clics iban a índices inventados | pedido real **arreglado**; variante pendiente (ver nota) | `DesktopUiaWorker.ps1:2678` (`@($found).Count` sobre `List[object]` lanza en PS 5.1 con >150 controles y alguno deshabilitado: toda ventana grande sin árbol) | `$found.Count` | 6d7bb0516 |

Notas:
- **C04, variante («la página de <otro juego>»)**: el modelo resuelve antes el título con `game.entitlement.named` (lo
  obtiene: appId), y después busca el juego con clics en la biblioteca; no usa el place `game`. Arreglarlo con
  un hecho en el resultado de `game.entitlement.named` empujaría a abrir páginas en las preguntas «¿lo tengo?»: queda
  pendiente.
- **C10, variante (otro formato)**: el modelo no mira y elige `input.key.press` con un atajo inexistente. Frase añadida
  a `input.key.press` en `tool_descriptions.en.v1.json` («applying a format … look at the window and click its
  button»); su efecto lo comprueba el notebook.
