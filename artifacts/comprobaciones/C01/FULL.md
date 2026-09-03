# Full C01 — `.\scripts\test_source_quality.ps1 -Mode Full`

Log íntegro: `full.log` (también `{scratch}/full.log`).
`source_quality_gate_passed: mode=Full`

## Recuentos oficiales

| Etapa | Resultado |
|---|---|
| powershell-source, python-ruff, python-compileall, eslint, tsc app/node, dotnet-format, dotnet-build-release | passed |
| Baxy.Contracts.Tests | 60 pass / 0 fail / 0 skip |
| Baxy.Integration.Tests | 2861 pass / 0 fail / **1 skip** |
| Baxy.Kernel.Tests | 137 pass / 0 fail / 0 skip |
| Baxy.Providers.Windows.Tests | 451 pass / 0 fail / 0 skip |
| Baxy.Setup.Tests | 477 pass / 0 fail / 0 skip |
| python-tests | **8792 pass / 0 fail / 3 skip**, 3 warnings, 446 subtests |

.NET: 3986 pass / 0 fail / 1 skip oficial (Integration). El log imprime además pruebas Explicit/Ignore históricas (`CompareLegacy…`, `OptInRealRuntime…`, `HistoricalApplicationCommand…`, etc.); no las añadió C01.
Python: 3 skip preexistentes (mismo número que la auditoría). C01 no añadió skip/xfail.

Delta vs auditoría b2505da (3978 .NET pass, 8788 Python pass / 4 fail): +8 Integration (FieldProduct) y +4 Python (2 sellos STT + 2 wakeword). El STT intermitente de la auditoría pasó en este Full.

## Owner tests C01

`dotnet test tests/Baxy.Integration.Tests -c Release --filter FullyQualifiedName~FieldProduct`: 8 pass / 0 fail / 0 skip.
`pytest tests/test_wakeword_runtime_resources.py tests/test_stt_quality_evaluators.py`: 14 pass / 1 skip ambiental.
