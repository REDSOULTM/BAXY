# Computer use universal — progreso (Fase 4, goal 2026-10-06)

Goal: `documentacion/GOAL_COMPUTER_USE_2026-10-06.md`. Rama `fable/computer-use-universal` (worktree
`%LOCALAPPDATA%\BAXY\cu-universal-wt`), base `codex/kiro-goal-c03`. Evidencia de misiones en vivo fuera del repo:
`%LOCALAPPDATA%\BAXY\cu-universal-evidencia\<misión>`; perfil de prueba `%LOCALAPPDATA%\BAXY\cu-universal-perfil`.

## Hecho

| Paso | Estado | Commit |
|---|---|---|
| Fusión de `fable/computer-use-engine` (13 conflictos de contenido) | hecho; Kernel 207/207, Providers 950/950 | 6cb48f77 |
| Clic: worker UIA del motor + atadura M132 a la ventana recién abierta; `DesktopClickVisible.ps1` retirado | hecho | 6cb48f77 |
| Mente: ganchos del motor portados a `semantic/patterns.py`, `semantic/arguments.py`, `__main__.py` | hecho; `tests/test_computer_use.py` 16/16 | 6cb48f77 |
| Enrutado: pestañas → misión en «navegador»; verbos en cualquier persona; `close_all` confirmado | hecho; Kernel 212, Providers 963, Integración 2430 (1 skip) | 444ebd47 |
| CEF/Steam: tapada al abrir, menú, llegada `page:`, OCR multipalabra, paso robusto | hecho | 88ab1432, d33f709e |
| Prioridad: lo tipado gana salvo primitivas de la misión; verbo suelto → decisor; finales en 1.ª persona | hecho; pytest 9272 (84 ficheros) | c727f1cf |

## Decisiones (criterio por defecto)

- Misión 2 («cerrá todas las pestañas del navegador») va por `browser.control close_all` —el catálogo ya la tenía,
  declinada sólo porque `RiskPolicy` no ligaba la confirmación a un argumento; el motor trajo `RiskPolicy` por
  argumentos—. Cierre pestaña a pestaña con el camino medido en Opera GX (clic central) y relectura del marco.
- Misión 7 («ve a la pestaña de YouTube») va al motor: aplicación = categoría «navegador», que el provider resuelve a
  la ventana delantera del navegador predeterminado (`UserBrowser*`). Sin código por navegador.
- Las misiones en vivo corren con el conductor de la App (`Baxy.exe --conductor`, mismo turno que la UI); la
  confirmación es el turno siguiente («sí»).

## Misiones en vivo

| # | Pedido | Resultado | Pasos | Latencia | Nota |
|---|---|---|---|---|---|
| 1 | ve a Cotele en Discord → «no» | **lograda** — «He encontrado el canal de voz "Cotele!!!??" en el servidor Choche… pero no me he unido. ¿Quieres que lo haga?» → «no» → no se unió | ruta tipada `client.channel.locate` (catálogo) | 17 s | intento 1 por el motor: el 4B pulsó 6 veces sin hallar el canal → la ruta tipada del catálogo ya no la engloba la misión |
| 2 | cerrá todas las pestañas del navegador → «sí» | **lograda** (intento 2) — pide confirmación; «Cerré cuatro pestañas; queda una abierta.»; Opera con 1 pestaña (UIA) | `browser.control close_all` (4 cierres releídos) | 13 s tras el «sí» | intento 1: «GX Corner» no se cierra como activa y el final calló las 3 cerradas → respaldo por otra pestaña + final con la cifra (e9139d30) |
| 3 | abre Steam y ve a la biblioteca | **lograda** (intento 8) — captura: BIBLIOTECA resaltada, «Tus colecciones» | 2 (clic «biblioteca» → menú; clic en su entrada) | misión 9,3 s (modelo 4,6 s) | 7 intentos fallidos enseñaron 6 arreglos generales (ventana tapada al abrir, contención sólo en ítems con título, OCR de varias palabras, menú abierto por el clic, llegada `page:`, paso ilegible). Falsos éxitos/negativos medidos y corregidos |
| 4 | en Discord apretá enter | **lograda** — Enter pulsado en el MD de prueba Ron92, nada enviado (captura) | 1 (tecla dictada) | misión 2,9 s, turno 4,6 s | final «…y vi que la acción se completó» → compositor: con una tecla sólo «Pulsé Enter» |
| 5 | abrí Configuración y activá el modo avión | **lograda** — «Activé el modo avión y se apagó el Bluetooth.»; radio Bluetooth leída `Off`; revertido con «desactivá el modo avión» → `On` | ruta tipada `system.settings.set` (D21: Windows lo verifica mejor que la pantalla) | 1,6 s | Configuración ya estaba abierta (del dueño), no se tocó |
| 6 | en la calculadora calculá 12×7 | **lograda** — la Calculadora muestra «84», expresión «12 × 7=» (UIA independiente) | 2 (escribir `12*7`, Enter; dictados sin modelo) | 41 s el turno (misión 35,9 s) | final en 3.ª persona → arreglado (c727f1cf); procedimiento aprendido |
| 7 | ve a la pestaña de YouTube | **lograda** — Opera GX: `TabItem «(126) YouTube» [selected]` (UIA independiente) | 2 (traer el navegador, clic en la pestaña) | misión 4,9 s | aplicación «navegador» → ventana delantera del predeterminado |
| 8 | pon La Casa del Dragón en HBO Max | **lograda** — Opera GX reproduce un episodio (`play.hbomax.com/video/watch/…`, pestaña con sonido, subtítulos de la serie) | ruta tipada `streaming.play.named` | 23 s | sesión de Opera del dueño respaldada antes y restaurada byte a byte después |
| 9 | abrí el Reloj y andá a Cronómetro (UWP que BAXY no conoce) | **lograda** — `ListItem Cronómetro [selected]` (UIA independiente) | — | 35 s el turno | final fiel: «Fui al Cronómetro y vi que estaba pausado a las 96 horas…» (el cronómetro del dueño lo mostraba) |

## Falta

- Misiones en vivo (≥ 8/9), compuerta Full, cobertura por tipo de app, latencia por paso, ahorro de procedimientos,
  merge `--no-ff` a `codex/kiro-goal-c03`, push, informe.
