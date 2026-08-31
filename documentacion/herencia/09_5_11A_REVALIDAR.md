# Goal 09.5.11A — Revalidar Goals 01–03C

Cerrado 2026-08-31. Fuente de verdad machine-readable:
[`../artifacts/goal095/synthesis/09.5.11A_revalidar_01_03C.v1.json`](../../artifacts/goal095/synthesis/09.5.11A_revalidar_01_03C.v1.json).
Ledger: [`../artifacts/goal095/ledger/revalidate-09.5.11A.json`](../../artifacts/goal095/ledger/revalidate-09.5.11A.json).

Siguiente prompt humano:
[`../sprints/09.5.11B_REVALIDAR_04_06.md`](../sprints/09.5.11B_REVALIDAR_04_06.md).
No remite a 09.5.11A, 09.5.10, 09.5.11C ni 10.0.

## Cola transplant

**Vacía.** `pending=0` `claimed=0`. 09.5.2–09.5.4 siguen
docs 25/25, code 477/477,
evidence 132/132, `pending=0` `claimed=0`.
Hashes sparse **not invented**. Rechazos protegidos fuera.

## Holdouts

### Comprensión, abstención, alcance

Corpus `artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl`
SHA-256 `761c1bc3b3facbf14a3aaafa09f24c0e5e0baaf8cebdd0edc7c2e648cb87413d` (es/en/es_en). Scorer:
`experiments/mind_router_spike/run_goal03_comprehension.py` `score` / `_final_operations`.

| Corrida | Servidos | `acted` | p50 |
|---|---:|---:|---:|
| `goal09511a_r1` | **113/124** | **1/36** | 3.807 s |
| `goal09511a_r2` | **113/124** | **1/36** | 3.778 s |
| `goal09511a_r3` | **113/124** | **1/36** | 3.832 s |

Mediana **113/124**. Máximo `acted` **1/36**.
Idiomas ['en', 'es', 'es_en']. p50 [3.807, 3.778, 3.832]. Las nueve ooc estables del 03B no publican hoja.

### Catálogo

**169/158/31**,
sello `2231d681fb396c128b6d99d5b415c17c880be59dd5758ead523f80c2ee436831`.
Sello 03C `dc0a789316b769cb37739e86b7bc60c29dab2682ca4c8230da05c92e38b0771d` se conserva como identidad histórica.
Operaciones perdidas: ninguna.
Contratos cambiados: ['input.visible.click'].

### Procedencia y reproducibilidad

Procedencia: sparse_not_invented=True.
Reproducibilidad: `.\scripts\test_source_quality.ps1` → source_quality_gate_passed: mode=Fast; EXIT=0.

### Trazados, no reejecutados

Banco compuesto `artifacts/development/goal03b_compound_goal03c_cmp2.json`: 6/15 misiones,
15/32 pasos.
VRAM `artifacts/development/goal03_vram_rec5e2e8.json` y overhead `artifacts/development/goal03_overhead_rec5e2e8.json`: runtime no trasplantado.

## Mapa Goal 01

Actualización del sello FieldUi: el hallazgo de 35 ficheros se conserva;
Goal 02 recuperó los tres `dist/` y el sello `0F6C38D1…` cuadra. Ver
`documentacion/herencia/00_MAPA.md`.

Cero aplazos al Goal 10.
