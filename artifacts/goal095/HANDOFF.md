# Handoff — 09.5.2 docs campaign — 2026-08-31

## Objetivo
Vaciar la campana `docs` (25 checkpoints) con una sola meta. Criterio: pending=0.

## Estado
Hecho: campana terminal. 25/25 complete, claimed=0, pending=0.
En curso: nada de docs.
Sin empezar: campana `evidence_assets` (09.5.4).

## Decisiones tomadas
- Una campana (`artifacts/goal095/campaigns/docs.json`), no un goal por batch_id.
- Cola v1 envuelta in situ; `docs-001-carter` se conservo por hash.
- `next_prompt` de unidades = `campaign:docs`; nunca `09.5.2_LEER_DOCUMENTACION_LOTE.md`.
- UTF-16 LE (`ff fe`) en logs `legacy/data/logs/gemma4-audit/` se lee, no se excluye.
- Agrupacion de tarjetas por directorio padre. Afirmacion documental != resultado reproducido.
- Decisiones de herencia quedan para 09.5.9. No se copio codigo de producto.

## Archivos tocados
- `scripts/goal095_docs_ledger.py` — resume de claim, next_prompt de campana
- `scripts/goal095_docs_campaign.py` — cursor
- `scripts/goal095_inspect_docs_batch.py` — titulos/fragmentos/medidas
- `scripts/goal095_close_docs_unit.py` — cierre generico
- `artifacts/goal095/ledger/docs-*.json` — 25 ledgers
- `documentacion/herencia/09_5_COBERTURA.md`

## Archivos relevantes aun sin tocar
- `documentacion/sprints/09.5.4_AUDITAR_EVIDENCIA_LOTE.md` — siguiente prompt humano

## Hipotesis
Confirmadas: 943/943 con terminal valido; hashes disco=cola en los 24 lotes nuevos; faltantes/solapes 0/0.
Descartadas: «los .txt con NUL son binarios» — son UTF-16 LE. «Falta pegar 09.5.2 otra vez».

## Comandos ejecutados y resultado
- `py -3.12 scripts/_goal095_validate_docs_campaign.py` → pending=0 claimed=0 complete=25 invalid_ledgers=0 relaunch_09_5_2=0 next_human=09.5.4
- `py -3.12 -m pytest tests/test_goal095_docs_ledger.py tests/test_goal095_code_ledger.py tests/test_goal095_queues.py -q` → ver corrida de cierre
- Claims `docs-*.json` selladas a `status=complete`

## Problemas pendientes
Ninguno de docs. `evidence_assets` sigue pendiente (09.5.4).

## Siguiente accion recomendada
Pegar `documentacion/sprints/09.5.4_AUDITAR_EVIDENCIA_LOTE.md` (sesion nueva, /goal). No relanzar 09.5.2 ni 09.5.3.
