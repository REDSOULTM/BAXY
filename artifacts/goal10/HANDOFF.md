# Handoff — Goal 10 — 2026-08-29 — r126 overlay scored

## Objetivo
BAXY cumple la identidad (es/en/spanglish) y cada mensaje real in-scope pasa
con veredicto individual. In-scope fail = 0. Ambientales omitidas, no convertidas.

## Estado
Hecho: r128 20/20 + overlay 14 (verified_effect). In-scope **1576/144**.
`open the file explorer` pasa. LastBoot `2026-08-27 21:25:24`.
Sin empezar: 808/2036/holdouts, matriz viva, ABBA, Full. No r129 encima.

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
Confirmadas: r126 ejecutó brillo al máximo; overlay 11 ids; env 217 omitidas; 7 other-lang omitidas.
Descartadas: overlay wholesale de shards; r127 encima de una tanda incompleta.

## Comandos ejecutados y resultado
- r126 waiter → **DONE**. 20/20 empty=0 + `campaign done`. LastBoot `2026-08-27 21:25:24`
- overlay r126: unique 1947, overlaid 11, blocked_lost_journal 177
- in-scope `artifacts/goal10/goal10-in-scope-r126.json` → **1564/159**, criterion_zero_fail false
- mind-runtime pytest → **2598 passed** twice (pre-r126 grounding)

## Siguiente acción recomendada
Familia dueño sobre `(none)` 61 / `app.open` 11 / `media.play.query` 6.
Tests verdes dos veces antes de otra remake.
