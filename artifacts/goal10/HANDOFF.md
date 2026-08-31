# Handoff — Goal 10.0 base verde — 2026-08-31

## Objetivo
Confirmar —y sólo si todavía hace falta, reparar— que Full es coherente con el
contrato estructurado de prosa heredado, sin cambiar conducta de producto ni
reintroducir respuestas visibles fijas.

## Estado
Hecho: Full vivo verde; los 85 históricos ausentes (reparados en 09.5.11C);
`OptInRealRuntimeTraversesShellMindAndCoreUsingReadOnlyOperations` clasificado
opt-in / fuera de Full, nunca contado como pass.
En curso: nada.
Sin empezar: `10.1_CORPUS_Y_COLA.md`.

## Decisiones tomadas
- Preflight verde: no se edita producto ni tests. El cluster frase-vs-JSON ya
  lo cerró `c28cd62` (09.5.11C) con `OperationOutcomeNarration.Facts`.
- El caso `[Explicit]` `PhysicalMindShellGate` no es aceptación in-scope de
  Full ni de esta meta. Owner: `scripts/run_mind_shell_e2e_gate.ps1` (nivel 4).
  No es `FALLO_DE_AMBIENTE`.
- VSTest Integration `Omitido: 1` es
  `EveryExactRuntimeMessageIsAuditedByTheRealGuiInputPipeline` (`Assert.Ignore`
  por jsonl en `.gitignore`), documentado en `00_COMPUERTA.md` §8–9. Tampoco
  es pass.

## Archivos tocados
- `artifacts/goal10/HANDOFF.md` — este fichero
- `artifacts/goal10/full-verdict.md` — contadores Full
- `artifacts/goal10/integration-fail-inventory.md` — 85 por causa
- `artifacts/goal10/skip-classification.md` — frontera Explicit / Full
- `documentacion/sprints/00_ORDEN_DESDE_09_5.md` — 10.0 cerrado; siguiente 10.1

## Archivos relevantes aún sin tocar
- `documentacion/sprints/10.1_CORPUS_Y_COLA.md` — siguiente prompt
- `src/Baxy.Kernel/Operations/OperationVisibleFacts.cs` — contrato JSON vivo
- `scripts/run_mind_shell_e2e_gate.ps1` — dueño del opt-in físico

## Hipótesis
Confirmadas: 09.5.11C/09.5.12 Full verde sigue siendo el baseline;
`2377b69` no se usó. Live Full = inherited Full (2828/1 Integration,
8760/10 Python, EXIT=0).
Descartadas: «hay que reescribir los 85 otra vez»; «el skip Explicit de
shell/mind es aceptación in-scope de Full».

## Comandos ejecutados y resultado
- `.\scripts\test_source_quality.ps1 -Mode Full` →
  `source_quality_gate_passed: mode=Full`; EXIT=0;
  Contracts 60; Integration 2828 pass / 1 skip; Kernel 137;
  Providers 451; Setup 477; python 8760 passed, 10 skipped, 446 subtests.
  Log SHA256 `d2b9e7936089771bde5bc6f2a701df90b5790ff2be279cabc89b03f1ec05a7ad`.
- Dueño Integration (segunda corrida Release `--no-build`):
  `Correctas! Superado: 2828, Omitido: 1, Total: 2829`; EXIT=0.
  Coincide con Full. Ningún fail→skip.

## Problemas pendientes
Ninguno de 10.0. No ejecutar 10.1 en esta meta.

## Siguiente acción recomendada
`documentacion/sprints/10.1_CORPUS_Y_COLA.md` (sesión nueva, un pegado).
