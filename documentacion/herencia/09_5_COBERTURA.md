# Goal 9.5.1 — Cobertura y cola de auditoria

Generado por `scripts/build_goal095_queues.py`. Estimador: `bytes_div_2`.
Tokenizer compatible para el arbol: ninguno (no se vuelca contenido).
No decide herencia. No lee cuerpos.

## Manifiesto

- Archivos en manifiesto (con hash): **28373**
- En cola: **19512**
- Duplicados por hash: **8348**
- Cobertura previa demostrable: **513**
- Excluidos por regla (fuera del manifiesto hasheado): **261935**
- Faltantes del manifiesto: **0**
- Solapes: **0**

Union cola + duplicados + cobertura previa = manifiesto. Las exclusiones
cierran el recuento 09.5.0 por fuente. `sparse_exclusions` no suma faltantes.

## Hashes 09.5.0 reutilizados

- FunctionGemma manifiesto `ff150df27808ca19c7a80fe40127011ef050be170b83bcd28bacf8d56f619eaa`
- Probando Gemma 4 manifiesto `72f9e5fc6597be5169c99e282d33749d6f7537813fb824809beb85e1b13c7e71`

## Exclusiones (reglas, no juicio)

| Regla | Archivos | Bytes | Razon |
|---|---:|---:|---|
| `dot_directory` | 91435 | 14402646075 | directorio cuyo nombre empieza por punto (.git, .venv, caches, IDE) |
| `python_cache` | 6203 | 90940849 | bytecode o caches de pytest/ruff/mypy |
| `python_venv` | 0 | 0 | entorno virtual, no es fuente del linaje |
| `node_modules` | 77410 | 1737801616 | dependencias instaladas, no fuente propia |
| `dotnet_obj` | 1262 | 201066963 | salida de compilacion MSBuild |
| `egg_info` | 22 | 34751 | metadatos de instalacion pip |
| `vendor_snapshot` | 85603 | 1681589771 | arbol de terceros clonado (competidores, OpenClaw, Hermes, llama.cpp) |
| `non_regular` | 0 | 0 | symlink o no-regular; no se hashea el blob |

## Snapshot disperso (no inspeccionado, no faltante)

Ver `artifacts/goal095/queue/sparse_exclusions.json`.
Categorias: `gguf_models`, `training_datasets`, `training_checkpoints`.

## Lotes

Objetivo 300000 / limite 350000 tokens de entrada.
Binarios: solo metadatos. JSONL/logs/corpus: parseo por herramienta.
Cola completa: `artifacts/goal095/queue/batches.json` y `artifacts/goal095/queue/ledger.json`.

| kind | lotes | archivos | tokens max | owner |
|---|---:|---:|---:|---|
| `docs` | 25 | 943 | 299986 | `documentacion/sprints/09.5.2_LEER_DOCUMENTACION_LOTE.md` |
| `code_tests` | 477 | 5769 | 300000 | `documentacion/sprints/09.5.3_AUDITAR_CODIGO_LOTE.md` |
| `evidence_assets` | 132 | 13138 | 299999 | `documentacion/sprints/09.5.4_AUDITAR_EVIDENCIA_LOTE.md` |

Primer lote docs (subsistema, no alfabeto global):

- `batch_id`: `docs-001-carter` — **completo** (09.5.2, 2026-08-30)
- archivos: 72, todos `leido`
- tokens estimados: 299986 (limite 350000)
- tarjetas: 18 en `artifacts/goal095/ledger/docs-001-carter.json`
- biblioteca: 15 hashes identicos, 57 delta (se leyo el snapshot Carter OS AI)
- faltantes/solapes globales: 0 / 0 (sin cambio)

Proximo lote docs pendiente:

- `batch_id`: `docs-002-carter`
- archivos: 86
- tokens estimados: 299425
- salida: `artifacts/goal095/ledger/docs-002-carter.json`

Primer lote code_tests:

- `batch_id`: `code_tests-001-carter` — **completo** (09.5.3, 2026-08-30)
- archivos: 32 (22 `leido`, 6 `parseado_completo`, 1 `binario_inventariado`, 3 `excluido_razonado`)
- tokens estimados: 293211 (limite 350000)
- tarjetas: 12 en `artifacts/goal095/ledger/code_tests-001-carter.json`
- hashes disco=cola 32/32; 0 identicos a biblioteca
- subsistemas: `carter_docs` + `carter_legacy_Carter_v2`
- faltantes/solapes globales: 0 / 0 (sin cambio)

Proximo lote code_tests pendiente:

- `batch_id`: `code_tests-002-carter-carter_legacy_Carter_v2`
- archivos: 43
- tokens estimados: 291016
- salida: `artifacts/goal095/ledger/code_tests-002-carter-carter_legacy_Carter_v2.json`

## Siguiente

Primer lote code_tests pendiente: `code_tests-002-carter-carter_legacy_Carter_v2` — prompt `documentacion/sprints/09.5.3_AUDITAR_CODIGO_LOTE.md`.
Docs sigue pendiente en `docs-002-carter` (prompt 09.5.2).
