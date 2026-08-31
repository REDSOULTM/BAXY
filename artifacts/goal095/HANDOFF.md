# Handoff — 09.5.3 code_tests campaign — 2026-08-31

## Objetivo
Vaciar la campana `code_tests` (477 checkpoints) con una sola meta. Criterio: pending=0.

## Estado
Hecho: campana terminal. 477/477 complete, claimed=0, pending=0.
En curso: nada de code_tests.
Sin empezar: campana `docs` (docs-002+) y `evidence_assets`.

## Decisiones tomadas
- Una campana (`artifacts/goal095/campaigns/code_tests.json`), no un goal por batch_id.
- `next_prompt` de unidades = `campaign:code_tests`; nunca `09.5.3_AUDITAR_CODIGO_LOTE.md`.
- 001 y 002 se conservaron; 002 se reanudo (claim viva).
- El empaquetado v1 de `traces.jsonl.N` (mismo SHA en decenas de lotes) se cubre una vez y el resto `duplicado_por_hash`.
- Schema Agent (477) no esta en el worktree HEAD de BAXY; se leyo por `git cat-file` de blobs 09.5.1 (Tools-Reduce).
- Decisiones provisionales hasta 09.5.9. No se copio codigo de producto.

## Archivos tocados
- `scripts/goal095_code_ledger.py` — resume de claim, next_prompt de campana
- `scripts/goal095_code_campaign.py` — cursor
- `scripts/goal095_close_code_unit.py` — cierre generico
- `scripts/goal095_inspect_code_batch.py` — inspect por batch_id
- `scripts/emit_goal095_code_002.py` — 002 a mano (Carter v2 audit)
- `artifacts/goal095/ledger/code_tests-*.json` — 477 ledgers
- `documentacion/herencia/09_5_COBERTURA.md`

## Archivos relevantes aun sin tocar
- `documentacion/sprints/09.5.2_LEER_DOCUMENTACION_LOTE.md` — siguiente prompt humano
- `documentacion/sprints/09.5.4_AUDITAR_EVIDENCIA_LOTE.md` — despues de vaciar docs

## Hipotesis
Confirmadas: compound-smoke 5/10 trivial-con-tools; hardcode_guard 0 findings por allowlist; gates GREEN contradichos en el mismo lote; 327 lotes = hash duplicado.
Descartadas: «falta pegar 09.5.3 otra vez». «Schema Agent es una carpeta hermana» — son blobs git de BAXY.

## Comandos ejecutados y resultado
- `py -3.12 scripts/_goal095_validate_code_campaign.py` → pending=0 claimed=0 complete=477 invalid_ledgers=0 relaunch_09_5_3=0 next_human=09.5.2
- `py -3.12 -m pytest tests/test_goal095_code_ledger.py tests/test_goal_launch_contracts.py tests/test_goal095_docs_ledger.py tests/test_goal095_queues.py -q` → 29 passed in 13.19s
- Claims `code_tests-*.json` selladas a `status=complete` (cola ya tenia claimed=0)

## Problemas pendientes
Ninguno de code_tests. `docs` sigue pendiente (docs-002).

## Siguiente accion recomendada
Pegar `documentacion/sprints/09.5.2_LEER_DOCUMENTACION_LOTE.md` (sesion nueva, /goal). No relanzar 09.5.3.
