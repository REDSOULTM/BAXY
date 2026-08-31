# Goal 10.0 — live Full verdict

Command: `.\scripts\test_source_quality.ps1 -Mode Full`

Scratch log: `C:\Users\usuario\AppData\Local\Temp\grok-goal-a53e71c2ff66\implementer\full-1.log`
SHA256: `d2b9e7936089771bde5bc6f2a701df90b5790ff2be279cabc89b03f1ec05a7ad` (16650 bytes)

```
source_quality_gate_passed: mode=Full
EXIT=0
```

Stages: powershell-source, python-ruff, python-compileall, field-ui-eslint,
field-ui-tsc-app, field-ui-tsc-node, dotnet-format, dotnet-build-release
(0 warnings, 0 errors), dotnet-tests, python-tests — all passed.

## .NET (Release)

| Project | Superado | Omitido | Error | Total |
|---|---:|---:|---:|---:|
| Contracts | 60 | 0 | 0 | 60 |
| Integration | 2828 | 1 | 0 | 2829 |
| Kernel | 137 | 0 | 0 | 137 |
| Providers.Windows | 451 | 0 | 0 | 451 |
| Setup | 477 | 0 | 0 | 477 |

Build: 0 Advertencia(s), 0 Errores.

Agrees with inherited 09.5.12: Integration 2828 pass, 1 skip opt-in; python
8760 passed, 10 skipped (ambient).

## Python

`8760 passed, 10 skipped, 446 subtests passed in 463.21s (0:07:43)`

The 10 skips are the same ambient count 09.5.12 already recorded. Not counted
as pass. Full stayed green; not re-litigated.

Owner Integration re-run (`dotnet test tests\Baxy.Integration.Tests -c Release --no-build`):
`Correctas! Superado: 2828, Omitido: 1, Total: 2829`; EXIT=0. Same counters.

## Integration skip vs Explicit

VSTest Integration `Omitido: 1` = `EveryExactRuntimeMessageIsAuditedByTheRealGuiInputPipeline`
(`Assert.Ignore` when gitignored `artifacts/historical_exhaustive/*.jsonl` is
absent). See `documentacion/base/00_COMPUERTA.md` §8–9.

`OptInRealRuntimeTraversesShellMindAndCoreUsingReadOnlyOperations` is
`[Explicit]` / `PhysicalMindShellGate`. Printed `Omitidas`, **not** in
Superado 2828, **not** the Omitido:1 row. Owner:
`scripts/run_mind_shell_e2e_gate.ps1`. Full's `dotnet test` has no filter that
selects it. Nivel 4, not implicit in Full.
