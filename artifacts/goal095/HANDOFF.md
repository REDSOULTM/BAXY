# Handoff — 09.5.3 code_tests-001-carter — 2026-08-30

## Objetivo
Cerrar un lote `code_tests` de la cola 09.5.1 en tarjetas de componente, sin copiar codigo.

## Estado
Hecho: `code_tests-001-carter` (32 archivos, 293211 tokens, 12 tarjetas).
En curso: nada de este lote.
Sin empezar: `code_tests-002-carter-carter_legacy_Carter_v2` (43 archivos, 291016 tokens).

## Decisiones tomadas
- Auditar el snapshot en disco (hash 09.5.1), no git HEAD: 21 ficheros de `docs/investigaciones` estan untracked; 3 memory.db coinciden con la cola y no con HEAD.
- Un hallazgo por mecanismo. Harness de stubs y matrix 540 son dos bancos, no uno.
- `.db` cuyo nombre empieza por punto no es `binary` en 09.5.1 (`suffix_of` vacio). Sidecars `.db-shm` = `sqlite_runtime_shm`. WAL sin padre en el lote = `binario_inventariado`.
- Ningun `reuse_exact`. CORE_PROMPT, registro OpenAI, e5 retrieval, audio nativo Gemma y `.env` openai/auto-approve = `reject_candidate`. Flags llama-server y estados inconclusive del verifier = `adapt_candidate` sin apilar capas.
- No se ejecutó codigo historico. SQLite se abrio sobre copias temporales; no se volcaron valores de `facts`.

## Archivos tocados
- `scripts/goal095_code_ledger.py` — claim + esquema v1
- `scripts/emit_goal095_code_001.py` — emisor de este lote
- `scripts/_goal095_code001_inspect.py` — hash + outline + parse SQLite
- `tests/test_goal095_code_ledger.py`
- `artifacts/goal095/ledger/code_tests-001-carter.json`
- `artifacts/goal095/queue/ledger.json` — status complete
- `documentacion/herencia/09_5_COBERTURA.md`

## Archivos relevantes aun sin tocar
- `documentacion/sprints/09.5.3_AUDITAR_CODIGO_LOTE.md` — se relanza para `code_tests-002-carter-carter_legacy_Carter_v2`
- Carter v4 vivo (lotes `carter_legacy_Carter_v4`): estas copias `04_agent.py` etc. son snapshots de investigacion

## Hipotesis
Confirmadas: el 55/60 del torneo Gemma nace de stubs, no de providers; K3/N2 del judge estan acoplados al titulo stub "YouTube - Google Chrome"; el agent v4 acumula flags OFF en vez de retirar capas; LocalMemoryStore ya sustituyo SQLite.
Descartadas: «biblioteca cubre este codigo por titulo» — 0 hashes identicos. «los .db son binarios en la cola» — el clasificador no los vio.

## Comandos ejecutados y resultado
- Carter OS AI HEAD `9cf62d236cdef08012897d3c8c680b8afef0d62e` (worktree sucio; no se toco)
- hashes 32/32 coinciden con el lote; tokens 293211 ≤ 350000
- `py scripts/goal095_code_ledger.py validate --ledger artifacts/goal095/ledger/code_tests-001-carter.json` → `ok`
- `py -3.12 -m pytest tests/test_goal095_code_ledger.py tests/test_goal095_docs_ledger.py tests/test_goal095_queues.py -q` → 22 passed in 30.68s
- Full: no. No hay cambio de producto.

## Problemas pendientes
Ninguno de `code_tests-001-carter`. `skills.db` padre de postopt/ultra_final no esta en este lote (sidecar partido por presupuesto).

## Siguiente accion recomendada
Pegar `documentacion/sprints/09.5.3_AUDITAR_CODIGO_LOTE.md` y reclamar `code_tests-002-carter-carter_legacy_Carter_v2`.
