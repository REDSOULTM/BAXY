# Handoff — Goal 10 — 2026-08-29 — owner-fix (none)/app.open → r129

## Objetivo
BAXY cumple la identidad (es/en/spanglish) y cada mensaje real in-scope pasa
con veredicto individual. In-scope fail = 0. Ambientales omitidas, no convertidas.

## Estado
Hecho: r128 overlay 14; in-scope **1576/144**. Owner-fix (none)/app.open:
hechos implícitos → `DoNotPersist` (mente conversa, no `AskToSave`); `Tiempo`
→ `system.time`; `abrí la aplicación X` + prefijo único 3 chars; alarma hora >23
sin aclarar; terminal `System32\cmd.exe`. Tests verdes dos veces.
r129 lanzada vía Win32 Create (`launch_r129.ps1`, python 54788/55316).
LastBoot `2026-08-27 21:25:24`.
En curso: campaña r129 1947 (esperar 20/20 + `campaign done`).
Sin empezar: overlay r129, 808/2036/holdouts, matriz viva, ABBA, Full.

## Decisiones tomadas
- Hecho implícito no se guarda ni se pregunta: `MustNotPersist` + `NoRoute`.
  El oráculo `ask_to_save` contradecía invariante 5 (respuesta fija
  `context_not_saved`). Safety sigue: `must_not_persist_before_consent`.
- Prefijo de catálogo único a 3 letras (`Steel`→Steam) si hay un solo hit.
  No literales de corpus en runtime.
- `AskToSave` queda sin llamadas; no se borra en este paso.

## Archivos tocados
- `src/baxy_mind/effect_intent.py` — time, named open, prefix 3, alarma >23
- `src/Baxy.App/NaturalMemoryRequestParser.cs` — ImplicitMemory → DoNotPersist
- `src/Baxy.Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs`
  — cmd.exe por `SystemDirectory`
- `tests/data/memory_corpus_oracle.json` — implicit consent = `no_memory_route`
- `artifacts/goal10/goal10-in-scope-r128.json` — score vigente hasta overlay r129

## Hipótesis
Confirmadas: parser `AskToSave` rompía 2 hard-negatives al cambiar a DoNotPersist
sin tocar el oráculo. Explorer 51/51. pytest 2605.
Descartadas: relanzar 1947 con el test de memoria en rojo.

## Comandos ejecutados y resultado
- `pytest tests/test_effect_intent.py tests/test_turn_policy.py -q` → **2605 passed** ×2
- `dotnet test …NaturalMemoryRequestParserTests` → **1746 passed** ×2
- `dotnet test …WindowsApplicationOpenProviderTests` → **51 passed**
- LastBoot `2026-08-27 21:25:24`

## Siguiente acción recomendada
Esperar r129 `DONE` (20/20 + campaign done). Overlay `overlay_r129.py`, no shards
incompletos. Score in-scope. Familias r128 restantes:
`artifacts/goal10/r128-remaining-families.md`. Si fail>0, una familia en dueño.
