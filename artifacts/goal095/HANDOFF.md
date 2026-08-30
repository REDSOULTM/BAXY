# Handoff — 09.5.1 — 2026-08-30

## Objetivo
Manifiesto unico, colas disjuntas y lotes <=350k para auditar solo lo no cubierto.

## Estado
Hecho: manifiesto 28373; cola 19512; duplicados 8348; cobertura previa 513;
exclusiones 261935; sparse_exclusions sin hashes inventados; 634 lotes;
dos reconstrucciones identicas; tests 9 passed.
En curso: nada de 09.5.1.
Sin empezar: 09.5.2 sobre `docs-001-carter`.

## Decisiones tomadas
- Cubierto solo con hash identico a `biblioteca/01_INVENTARIO.md` o tarjeta unica
  de `00_MAPA.md` / `D_ADAPTADORES_POR_APP.md`. Coincidencia de nombre no cubre.
- Exclusiones: reglas (`dot_directory`, `node_modules`, `vendor_snapshot`, ...),
  no juicio. Cuentan contra el recuento 09.5.0; no van al manifiesto hasheado.
- Estimador `bytes/2`. Binarios 256. Evidence/JSONL/logs: tope 8192 (parseo).
- Schema Agent: 12 blobs de refs Git de BAXY, `source_id=baxy_schema_agent`.

## Archivos tocados
- `scripts/build_goal095_queues.py` — builder
- `tests/test_goal095_queues.py` — union, privacidad, 09.5.0, reconstrucciones
- `artifacts/goal095/queue/*` — cola, ledger, manifiesto, sello
- `artifacts/goal095/sources/*.keep.sha256.jsonl` — keep hasheado
- `documentacion/herencia/09_5_COBERTURA.md` — resumen
- `artifacts/goal095/HANDOFF.md` — este handoff

## Archivos relevantes aun sin tocar
- `documentacion/sprints/09.5.2_LEER_DOCUMENTACION_LOTE.md`
- `artifacts/goal095/queue/batches.json` lote `docs-001-carter`

## Hipotesis
Confirmadas: recuentos A=B=09.5.0; manifiestos FG/PG4 estables; union 100%.
Descartadas: «cubrir por nombre de biblioteca» → 513 solo por hash/tarjeta.

## Comandos ejecutados y resultado
- `py -m pytest tests/test_goal095_queues.py -q` → 9 passed
- `scripts/build_goal095_queues.py --repeat 2` → sellos identicos,
  `first_docs_batch_id=docs-001-carter`, missing 0, overlaps 0
- Full: no. No hay cambio de producto.

## Problemas pendientes
Ninguno de 09.5.1. 09.5.2 lee 72 archivos / 299986 tokens de `docs-001-carter`.

## Siguiente accion recomendada
Pegar `documentacion/sprints/09.5.2_LEER_DOCUMENTACION_LOTE.md` y reclamar
`docs-001-carter`.
