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

## En curso

- Enrutado: «ve a la pestaña de X» → misión en el navegador de la persona (`application: navegador`); verbos de
  cláusula generales (voseo, usted, infinitivo, inglés).
- `browser.control close_all` en el navegador predeterminado con confirmación ligada al argumento; se conserva la
  última pestaña.

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
| 1 | ve a Cotele en Discord | pendiente | | | |
| 2 | cerrá todas las pestañas del navegador | pendiente | | | |
| 3 | abre Steam y ve a la biblioteca | pendiente | | | |
| 4 | en Discord apretá enter | pendiente | | | |
| 5 | abrí Configuración y activá el modo avión | pendiente | | | |
| 6 | en la calculadora calculá 12×7 | pendiente | | | |
| 7 | ve a la pestaña de YouTube | pendiente | | | |
| 8 | pon La Casa del Dragón en HBO Max | pendiente | | | |
| 9 | app desconocida (por elegir) | pendiente | | | |

## Falta

- Misiones en vivo (≥ 8/9), compuerta Full, cobertura por tipo de app, latencia por paso, ahorro de procedimientos,
  merge `--no-ff` a `codex/kiro-goal-c03`, push, informe.
