# Fase 3.5 — progreso (fuente de verdad ante un corte)

Sesión Opus 5.5, rama `codex/kiro-goal-c03`, punto de partida tag `opus55-inicio` = b5c9fe72 (creado por esta
sesión: el tag no existía; ver DECISIONES_OPUS_2026-09-22.md). Al retomar: leer esto, `git status --short`,
`git log --oneline opus55-inicio..HEAD`. Un comando largo a medias se vuelve a correr entero.

## Entregables de «Hecho»

| # | Entregable | Estado |
|---|---|---|
| 1 | `scripts/semantic_replay.py` + `semantic_replay_state.ps1` (conversaciones por el conductor; 742 sólo-decisión) | hecho |
| 2 | held-out `contexto/heldout-2026-09-22.turns.jsonl` escrito, medido en baseline y commiteado antes de tocar src | hecho (15/30) |
| 3 | `SEMANTICA_BASELINE_2026-09-22.md` (turnos malos del 21 clasificados + held-out por clase) | en curso: faltan bancos y 742 |
| 4 | Clase 1 — hueco de diálogo compartido mente/shell | pendiente |
| 5 | Clase 2 — guarda «sin pedido» no se come charla ni respuestas | pendiente |
| 6 | Clase 3 — lista corta / elección del modelo | pendiente |
| 7 | Clase 4 — familia existente (mutea…) | pendiente |
| 8 | Clase 5 — veto de efecto inventado | pendiente |
| 9 | Full verde + cien 100/100 (cien-99…) | pendiente |
| 10 | `SEMANTICA_2026-09-22.md` (antes/después, tests, cien, reverts) | pendiente |
| 11 | `DECISIONES_OPUS_2026-09-22.md` | en curso (2 decisiones) |
| 12 | `documentacion/SEMANTICA.md` | pendiente |
| 13 | todo commiteado y pusheado | pendiente |

## Última cifra medida

- Baseline b5c9fe72: dueño 33/60, held-out 15/30 (SEMANTICA_BASELINE). Corriendo: 742 sólo-decisión → lit-base.jsonl, luego bancos → base-banks.

## Comandos del harness (scratchpad de esta sesión = `S`)

- Conversaciones: `python -X utf8 scripts/semantic_replay.py conv --out S/base --label sem-base <turns...>`
- 742: `python -X utf8 scripts/semantic_replay.py literals --out S/lit-base.jsonl`; comparar con `diff`.
- python = `%LOCALAPPDATA%\BAXYRuntime\python\mind-runtime-v1\Scripts\python.exe`. Build previo: `main.compile_if_needed`.

## Cambios sin commitear

- `scripts/semantic_replay.py`, `scripts/semantic_replay_state.ps1` (harness).
- `contexto/heldout-2026-09-22.turns.jsonl` (nuevo), campo `clase` en `contexto/dueno-2026-09-21.turns.jsonl`.
- `DECISIONES_OPUS_2026-09-22.md`, este fichero.

## Próximo paso

Baseline: dueño + held-out (corriendo), luego los 35 bancos y los 742 sólo-decisión; commit del harness + held-out +
baseline antes de tocar src.
