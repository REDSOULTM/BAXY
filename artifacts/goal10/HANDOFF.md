# Handoff — Goal 10.1 corpus y cola — 2026-08-31

## Objetivo
Congelar N10/M10 reproducibles (≥1.947/808, suelo 1.947/626 y 808/281 exactos), C10 (≥74) y la cola 10.7–10.16 sin solapes.

## Estado
Hecho: freeze `scripts/freeze_goal10_corpus.py`; N10=1947/626, M10=808/281, C10=74; delta 09.5 de turnos=0; residual_evidence no reparseado; dos reconstrucciones byte-idénticas; tests dueño 10/10 dos veces.
En curso: nada.
Sin empezar: `10.2_PRESENCIA_Y_RECURSOS.md`.

## Decisiones tomadas
- Selección = `origin=observed_user` y no `codex/`; en esta autoridad coincide con el suelo `a6cd673` (prefijos `probando_gemma4/`, `gemma4_local/`) sin copiar ese filtro como regla.
- Partición por operaciones, cadenas y semántica de turno cero-op (hechos locales / web / conversación), no por etiqueta `language`.
- C10 = `possible_chain` o >1 operación; son subset de M10, owner único `10.16`.
- Familias 10.3–10.6 por frecuencia observada y partición distinta: `conversation`, `media.play`, `audio.volume`, `system.status`, `system.settings`.
- Delta 09.5 de turnos de usuario = 0 (fuentes 09.5 listadas; `residual_evidence` no se reparsea).

## Archivos tocados
- `scripts/freeze_goal10_corpus.py` — builder N10/M10/C10 y cola
- `tests/test_freeze_goal10_corpus.py` — identidad, suelos, unión, C10, env, familias, privacidad
- `tests/data/goal10_corpus_freeze.v1.json` — conteos/hashes/schema
- `tests/data/goal10_partition_index.v1.jsonl` — message_id → owner, sin texto
- `tests/data/GOAL10_CORPUS_NOTICE.md`, `.gitignore` — JSONL privado ignorado
- `documentacion/sprints/00_ORDEN_DESDE_09_5.md` — 10.1 cerrado; siguiente 10.2

## Archivos relevantes aún sin tocar
- `documentacion/sprints/10.2_PRESENCIA_Y_RECURSOS.md` — siguiente prompt
- `tests/data/historical_messages.jsonl` — autoridad (no editar)

## Hipótesis
Confirmadas: autoridades SHA256 `9d8b2d09…` / `b5e9c75c…` = ledger; suelo 1947/626 y 808/281 intacto; observed_user no-codex no añade filas.
Descartadas: reparsear 09.5.4; restaurar el filtro de prefijos de `a6cd673` como regla; particionar por etiqueta `other`.

## Comandos ejecutados y resultado
- `py -3.12 -m pytest tests/test_freeze_goal10_corpus.py -q` → `10 passed in 4.96s`; segunda `10 passed in 4.52s`. 0 fail, 0 skip.
- `py -3.12 -X utf8 scripts/freeze_goal10_corpus.py` ×2 dirs vacíos → N10 SHA256 `ec44e32e0d3ec5653e52c337d86fefd836078f8c97505784809cfedcb45fec2e`; M10 `76a8f2f651a343d23864dc1a64abceceb499434d65c8fb3ec8dda59f4866f5fa`; C10=74; hashes = publicación versionada.
- Occupancy 10.7–10.16: 1083, 94, 31, 81, 166, 178, 80, 127, 33, 74 (suma 1947).
- No ejecutado: Full — no es gate de 10.1.

## Problemas pendientes
Ninguno de 10.1. Filas in-scope con app/cuenta/contenido ausente siguen en cola con `required_environment`; 10.2 no las ejecuta.

## Siguiente acción recomendada
`documentacion/sprints/10.2_PRESENCIA_Y_RECURSOS.md` (sesión nueva, un pegado).
