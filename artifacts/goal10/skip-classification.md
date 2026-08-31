# Skip classification — Goal 10.0

Named case: `OptInRealRuntimeTraversesShellMindAndCoreUsingReadOnlyOperations`

## Verdict

Deliberately **opt-in**, **outside Full**. Not in-scope acceptance for this
meta. **Not counted as pass.** Owner: `scripts/run_mind_shell_e2e_gate.ps1`.
Nivel 4 (hardware/voz/proceso real) is not implicit in Full
(`documentacion/01_ARQUITECTURA/GUIA_AGENTES_IA/05_VALIDACION_SEGURIDAD_Y_HANDOFF.md`).

Not `FALLO_DE_AMBIENTE`. Missing GGUF/Python/attestation would block the
physical gate, not this Full.

## Proof in the test

`tests/Baxy.Integration.Tests/MindShellEndToEndTests.cs`:

```
[Test]
[Explicit("Real-runtime read-only shell/Core proof; execute through run_mind_shell_e2e_gate.ps1.")]
[Category("PhysicalMindShellGate")]
public async Task OptInRealRuntimeTraversesShellMindAndCoreUsingReadOnlyOperations()
```

NUnit `[Explicit]`: not run unless selected by name/filter.

## Proof in Full's gate

`scripts/test_source_quality.ps1` Full `dotnet-tests`:

```
test Baxy.slnx -c Release --no-build -m:1 --nologo
```

No `--filter` includes this identity or `Category=PhysicalMindShellGate`. The
script never calls `run_mind_shell_e2e_gate.ps1`.

That physical script first discovers the class (expects Explicit `NotExecuted`
or omitted), then runs only
`FullyQualifiedName=Baxy.Integration.Tests.MindShellEndToEndTests.OptInRealRuntimeTraversesShellMindAndCoreUsingReadOnlyOperations`.

Live Full Integration:

```
Omitidas OptInRealRuntimeTraversesShellMindAndCoreUsingReadOnlyOperations [< 1 ms]
Correctas! - Con error:     0, Superado:  2828, Omitido:     1, Total:  2829
```

The named case is printed `Omitidas` and is **not** in Superado. It is **not**
the VSTest `Omitido: 1` row. That row is
`EveryExactRuntimeMessageIsAuditedByTheRealGuiInputPipeline` (`Assert.Ignore`
when gitignored jsonl is absent; `documentacion/base/00_COMPUERTA.md` §8–9).
09.5.12's "1 skip opt-in" is that Ignore, not a converted 85-fail.

Owner Integration re-run (Release `--no-build`): same `Omitidas` line, same
`Superado: 2828, Omitido: 1, Total: 2829`, EXIT=0.

## Other Explicit omissions (same Full boundary)

Printed `Omitidas`, outside Total/Skipped (NUnit Explicit):

- Integration: JSON/Core microbenchmarks, physical Start-menu app open
- Kernel: fingerprint microbenchmark
- Providers: NativeAOT audio round-trip, WLAN, GPU/PDH, IP list
- Setup: install-root rename while executable runs

Documented since Goal 02 (`00_COMPUERTA.md`, `REGISTRO_DE_MANTENIBILIDAD.md`).

## Python

`8760 passed, 10 skipped`. Same ambient count as 09.5.12. Not counted as pass.
Full green; not re-litigated.
