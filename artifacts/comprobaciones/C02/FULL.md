# Full C02 — `.\scripts\test_source_quality.ps1 -Mode Full`

Commit medido: `605e486dbba6e1d7eb4bad820ed9238e5d25f8f5`.
Árbol congelado: `git status --short` vacío en las dos corridas (logs untracked copiados después).
`source_quality_gate_passed: mode=Full` las tres veces. 0 fail. 0 warnings Release.

| Corrida | Log | .NET | Python |
|---|---|---|---|
| Congelado 1 | `full-frozen-1.log` | 3996 pass / 0 fail / 1 skip | 8793 pass / 0 fail / 3 skip |
| Congelado 2 | `full-frozen-2.log` | idéntico | idéntico |
| Clon limpio | `full-clone.log` | 3996 pass / 0 fail / 1 skip | 8785 pass / 0 fail / 11 skip |

.NET desglose (las tres): Contracts 60; Integration 2870 pass / 1 skip; Kernel 138; Providers 451; Setup 477. Compilación 0 advertencias.

Delta vs C01 (3986 / 8792): +10 Integration (sesiones + hash llama + worktree extranjero + 3 casos de segmento), +1 Kernel (constructor), +1 Python (resolución llama-server).

## Skips — no cuentan como pass

**Oficial .NET (1):** Integration, el mismo opt-in/histórico que C01. Las líneas `Omitidas CompareLegacy…` / `OptInRealRuntime…` / `HistoricalApplicationCommand…` son Explicit/Ignore impresas; no las añadió C02.

**Python árbol de desarrollo (3):** preexistentes. Una es `tests/test_stt_quality_evaluators.py` blind campaign inputs absent (`environment:`). Las otras dos, el mismo trío C01.

**Python clon (+8 → 11):** mismas 3 más 8 de entorno (Goal 02 §12: `.venv` del spike y artefactos gitignored). Mensaje `environment`. No son regresiones. Subtests 433 vs 446: los extra skips cubren algunos subtests.

Ningún rojo se cerró con skip/xfail/umbral/fallback. STT intermitente (`open up pad please`) pasó en las tres corridas; no se bajó umbral.
