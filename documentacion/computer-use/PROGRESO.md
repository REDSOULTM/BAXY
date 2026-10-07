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
| Procedimientos: no se aprende con pasos fallidos; se reproduce sólo sobre la ventana de la app | hecho | 9afbef63 |
| Contrato de paquete ordenado (Setup 477/477); MEDICIONES.md (cobertura, latencia, procedimientos) | hecho | 1425cf71 |
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

## Cierre

- Misiones: **9/9 logradas y verificadas** en vivo (más Win32 extra: Panel de control → «Sistema y seguridad», y
  humo tras mover el lector a `semantic/missions.py`: Calculadora «84»).
- Compuerta Full verde (e46afeaf): Contracts 70, Integration 2431 (+1 skip ambiental: pruebas opt-in de runtime
  real), Kernel 212, Providers.Windows 963, Setup 477, pytest 18 735.
- Mediciones: `MEDICIONES.md` (cobertura por tipo de app, latencia por paso, ahorro de procedimientos).
- Estado del PC devuelto: volumen 60 y brillo 40 como al empezar; modo avión revertido; Steam, Discord, Opera,
  Reloj, Calculadora y Panel de control abiertos por las pruebas, cerrados; sesión de Opera del dueño restaurada
  byte a byte desde la copia previa.

## v2 (2026-10-07): universal, encadenado, rápido

Pedido del dueño (00:10): que BAXY use el PC como una persona, en cualquier app, con misiones encadenadas, rápido y
con calidad; plazo 13:00. Rama `fable/cu-universal-v2`. Análisis (fase A): el tiempo era sobrecoste de BAXY (UWP 30 s,
PowerShell por tecla, esperas fijas, finales y progreso por LLM, paso del modelo con 148 tokens), y la universalidad
fallaba por un solo acto por pedido, sin búsqueda dentro de la app ni objetivos libres.

| Cambio | Commit |
|---|---|
| Paso del modelo con gramática de acto primero (4 s → 0,2–0,7 s medido en llama-server) | bf38d6b4 |
| Mente: BUSCAR universal, encadenado `steps[]`, objetivos libres, guardas, nombres bilingües | 9ff5b4fc |
| Último recurso: una orden sobre el PC sin operación la intenta el motor | df446de1 |
| Vista para el modelo: 30 controles por el objetivo + «N de M» | 2a6b2c3e |
| Provider (agente A): UWP por su marco, teclas en proceso, clic rápido, worker precalentado, scroll por control | merge 8177a776 |
| App/Kernel (agente B): sub-objetivos, esperas de 150 ms, OCR a demanda, guardas, política ampliada | merge cbbf199c |
| Arreglos medidos en vivo: escritorio no es ventana de app; espera de arranque; ventana elevada; page: contra la vista previa al clic; clic físico si no se invoca; límite no anula misión | ea14333b, b396dfe8, fa009cf1 |

### Banco en vivo (turno completo, `latency_ms`; verificación independiente)

| # | Pedido | Resultado | Turno | Antes |
|---|---|---|---|---|
| 1 | en la calculadora calculá 37*12 (cerrada) | **logrado** — pantalla «444» | 4,4 s | 38–41 s |
| 3 | en Configuración andá a Bluetooth y dispositivos | **logrado** — ítem seleccionado | 3,3 s | — |
| 4 | en el Explorador de archivos andá a Descargas | **logrado** (tras arreglo del escritorio) | misión 3,5 s | — |
| 5 | en el Panel de control abrí Programas | **logrado** | 4,7 s | 7,5 s |
| 6 | en el Administrador de tareas andá a Rendimiento | límite de Windows (app elevada), dicho con esa causa | 33,6 s | — |
| 7 | abrí Paint y elegí la herramienta Texto | **logrado** — «Texto» activo | 6,5 s | — |
