# Handoff — Goal 10 — 2026-08-29 — r125 overlay scored

## Objetivo
BAXY cumple la identidad (es/en/spanglish) y cada mensaje real in-scope pasa
con veredicto individual. In-scope fail = 0. Ambientales omitidas, no convertidas.

## Estado
Hecho: r125 20/20 + campaign done. Overlay quirúrgico **28** ids (gained_prose
incluido). In-scope **1561 pass / 162 fail / 1723**. LastBoot
`2026-08-27 21:25:24`. `system.settings.set` al máximo ahora grounds value=100
sin pedir dígito (el testhost eligió action pero no ejecutó).
En curso: owner-fix grounding + una remake r126. No overlay de incompletos.
Sin empezar: 808/2036/holdouts, matriz viva, ABBA, Full.

## Decisiones tomadas
- No regex-por-fail ni literales de corpus (`zzqwx123`, `Abre stea`, `a`→Hello).
- `poné una canción` sigue pidiendo query (`test_bare_song_request_clarifies…`).
- `subí el brillo al máximo` es `system.settings.set` value=100, no amount.
- Hechos verificados que el 4B no formula se narran en `TurnVisibleFacts`.
- `system.power` nunca se invoca en vivo. Last boot no se toca.

## Archivos tocados
- `artifacts/goal10/goal10-in-scope-r124.json` — score in-scope r124
- `src/baxy_mind/effect_intent.py` — explorer/terminal/settings aliases, brillo max/status
- `src/baxy_mind/__main__.py` — args de media, brillo, window status
- `src/Baxy.App/TurnVisibleFacts.cs` — process.list, window status, brillo
- `src/Baxy.Providers.Windows/Applications/` — `windows.explorer` + explorer.exe

## Hipótesis
Confirmadas: r124 overlay 77; env 221 omitidas; 7 other-lang omitidas.
Descartadas: overlay wholesale de shards r124 (99/191 originales divergían).

## Comandos ejecutados y resultado
- mind-runtime pytest `tests/test_effect_intent.py tests/test_turn_policy.py -q` → **2597 passed** twice (78s, 68s)
- `dotnet test …WindowsApplicationOpenProviderTests --filter ExplorerIdentity` → 1 pass
- `dotnet test …PlannerAppBoundaryTests --filter LastResortFailureProse…` → 1 pass
- LastBoot → `2026-08-27 21:25:24`

## Siguiente acción recomendada
Tras el push: una campaña testhost r125, 20 shards,
`BAXY_DENY_HOST_POWER_TRANSITION=1`. No overlay hasta 20/20 + «campaign done».
Score in-scope igual que r124; si fail>0, otra familia en el dueño, no veinte remakes.
