# Handoff — 09.5.2 docs-001-carter — 2026-08-30

## Objetivo
Cerrar un lote `docs` de la cola 09.5.1 en tarjetas trazables, sin implementar producto.

## Estado
Hecho: `docs-001-carter` (72 archivos, 299986 tokens, 18 tarjetas, todos `leido`).
En curso: nada de este lote.
Sin empezar: `docs-002-carter` (86 archivos, 299425 tokens).

## Decisiones tomadas
- Cubrir el snapshot Carter OS AI (`9cf62d23…`), no la copia de biblioteca: 15 hashes identicos, 57 delta.
- Un hallazgo por mecanismo, no una tarjeta por fichero. Repeticion de agentes no suma evidencia.
- Benches/transcripts = `documental`. Reproducido aqui: HEAD, SHA-256 72/72, presupuesto.
- `hermes3:8b` fair-winner y E4B-Q6_K 57/60 no se presentan como default vigente (Goal 01 midio E2B).

## Archivos tocados
- `scripts/goal095_docs_ledger.py` — claim + esquema v1
- `scripts/emit_goal095_docs_001.py` — emisor de este lote
- `tests/test_goal095_docs_ledger.py` — esquema, recinto, invariantes publicadas
- `artifacts/goal095/ledger/docs-001-carter.json` — tarjetas
- `artifacts/goal095/queue/ledger.json` y `batches.json` — status complete
- `documentacion/herencia/09_5_COBERTURA.md` — proximo `docs-002-carter`

## Archivos relevantes aun sin tocar
- `documentacion/sprints/09.5.2_LEER_DOCUMENTACION_LOTE.md` — se relanza para `docs-002-carter`
- `artifacts/goal095/queue/batches.json` lote `docs-002-carter`

## Hipotesis
Confirmadas: dry-run/scripted/soak no equivalen a live LLM; harness de un solo protocolo de tools sesga el torneo; mute sin read-back es fake success.
Descartadas: «biblioteca ya cubre estos docs por titulo» → 09.5.1 exige hash; 57/72 diferian.

## Comandos ejecutados y resultado
- Carter OS AI `git rev-parse HEAD` → `9cf62d236cdef08012897d3c8c680b8afef0d62e`
- hashes 72/72 coinciden con el lote; tokens 299986 ≤ 350000
- `py scripts/goal095_docs_ledger.py validate --ledger artifacts/goal095/ledger/docs-001-carter.json` → `ok`
- `py -3.12 -m pytest tests/test_goal095_docs_ledger.py tests/test_goal095_queues.py -q` → 15 passed in 10.58s
- Full: no. No hay cambio de producto.

## Problemas pendientes
Ninguno de `docs-001-carter`. `REPORTE_EXTENDIDO.md` (57/60) no estaba en el lote; la tarjeta `gemma4-migrar-condicional-no-en-lote` solo conserva el puntero.

## Siguiente accion recomendada
Pegar `documentacion/sprints/09.5.2_LEER_DOCUMENTACION_LOTE.md` y reclamar `docs-002-carter`.
