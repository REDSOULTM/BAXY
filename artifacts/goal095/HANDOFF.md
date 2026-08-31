# Handoff — 09.5.4 evidence_assets campaign — 2026-08-31

## Objetivo
Vaciar la campana `evidence_assets` (132 checkpoints) con una sola meta. Criterio: pending=0.

## Estado
Hecho: campana terminal. 132/132 complete, claimed=0, pending=0.
En curso: nada de evidence_assets.
Sin empezar: campana/sintesis `09.5.5_MODELOS_ROUTER_IDIOMAS.md`.

## Decisiones tomadas
- Una campana (`artifacts/goal095/campaigns/evidence_assets.json`), cola v1 envuelta in situ.
- Cuatro terminales: `parseado_completo`, `binario_inventariado`, `duplicado_por_hash`, `excluido_razonado`. `leido` rechazado.
- Lease 6h: claims vivas se reanudan sin resetear `claimed_utc`; vencidas vuelven a `pending`.
- Existir un GGUF/safetensors/wav/dll no es `works`. Smoke omitido; resultados recuperados.
- Leftovers rust/dotnet (`rlib`/`rmeta`/`*.d`/`bin/`) no son modelos: `excluido_razonado`.
- Omisiones dispersas de Probando Gemma 4 no inventan hash: `_09510_requirements.json`.
- `next_prompt` de unidades = `campaign:evidence_assets`; el ultimo apunta a 09.5.5. Nunca 09.5.4.

## Archivos tocados
- `scripts/goal095_evidence_{campaign,ledger,parse}.py`, `goal095_close_evidence_unit.py`
- `scripts/_goal095_validate_evidence_campaign.py`, `_goal095_scan_evidence_terminals.py`
- `tests/test_goal095_evidence_ledger.py`
- `artifacts/goal095/ledger/evidence_assets-*.json` — 132
- `artifacts/goal095/extract/evidence_assets-*.parse.json` — 132
- `documentacion/herencia/09_5_COBERTURA.md`

## Archivos relevantes aun sin tocar
- `documentacion/sprints/09.5.5_MODELOS_ROUTER_IDIOMAS.md` — siguiente prompt humano

## Hipotesis
Confirmadas: 13138/13138 con terminal valido; pending=0 claimed=0 invalid=0 relaunch_09_5_4=0; sha256 disco=parser en log y jsonl reales.
Descartadas: «los .db del snapshot son sqlite usable» — algunos no son base (error en extract, no aborta). «Falta pegar 09.5.4 otra vez».

## Comandos ejecutados y resultado
- `py -3.12 scripts/_goal095_validate_evidence_campaign.py` → pending=0 claimed=0 complete=132 invalid_ledgers=0 relaunch_09_5_4=0 next_human=09.5.5 required_human_launches=1
- `py -3.12 scripts/_goal095_scan_evidence_terminals.py` → parseado_completo=7212 binario_inventariado=3884 excluido_razonado=2042 ranking=0 works_true=0
- `py -3.12 -m pytest tests/test_goal095_docs_ledger.py tests/test_goal095_code_ledger.py tests/test_goal095_queues.py tests/test_goal095_evidence_ledger.py -q` → ver corrida de cierre

## Problemas pendientes
Ninguno de evidence_assets. Siguiente humano: 09.5.5.

## Siguiente accion recomendada
Pegar `documentacion/sprints/09.5.5_MODELOS_ROUTER_IDIOMAS.md` (sesion nueva, /goal). No relanzar 09.5.4.
