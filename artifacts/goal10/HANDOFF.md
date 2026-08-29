# Handoff — Goal 10 — 2026-08-29 — restart limpio

## Objetivo
BAXY cumple la identidad (es/en/spanglish) y cada mensaje real in-scope pasa
con veredicto individual. In-scope fail = 0. Ambientales omitidas, no convertidas.

## Estado
Hecho: inventario heredar/descartar; r123 incompleta anulada (no overlay);
mente restaurada a HEAD anti-acumulación; `_daily_use_family_intent` en un dueño;
fail-closed de `system.power`; LastBoot `2026-08-27 21:25:24`.
Familias: 63 passed twice. Power test 2/2.
En curso: 4 tests HEAD-preexistentes (trivia web.search vs conversación).
Sin empezar: campaña 1.947 (no se lanza hasta esa costura), 808/2036/holdouts,
matriz viva, latencia ABBA, Full.

## Decisiones tomadas
- No `reset --hard 8c57747` ni force-push: origin ya tiene 163 commits del Goal 10.
- No overlay de shards incompletos o voided.
- La mente es el LLM; un reconocedor de familia, no un regex por fail.
- `system.power` nunca se invoca en vivo en este PC.

## Archivos tocados
- `artifacts/goal10/inherit-discard.v1.md` — inventario
- `src/baxy_mind/effect_intent.py` — `_daily_use_family_intent`
- `src/Baxy.Providers.Windows/External/WindowsPowerTransitionAdapter.cs` — deny host
- `tests/Baxy.Integration.Tests/ObservedUserCorpusReplayTests.cs` — env deny=1

## Hipótesis
Confirmadas: r123 muerta (`^C`, 29 filas). Last boot sin cambio.
Descartadas: «hay que resetear origin al Goal 9» → rompe la regla de publicación.

## Siguiente acción recomendada
Cuando `test_effect_intent.py` + `test_turn_policy.py` + el test de power pasen
dos veces: una campaña testhost 20 shards con `BAXY_DENY_HOST_POWER_TRANSITION=1`.
