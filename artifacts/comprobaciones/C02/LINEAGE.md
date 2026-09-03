# C02 — linaje de sellos y rojos de base

## STT program tree

| Sello | Qué es | Qué hace C02 |
|---|---|---|
| `08300d7cec3ef1d770fb1a10c9a6de7e9d8fdf64e69c7a3be9c4bf4221a5fc7b` | Expectativa en b2505da / auditoría 2026-09-03, anterior a `scripts/goal095_09512_integrate.py` | Histórico. Conservado en `artifacts/audit/goals_01_10_20260903/program-tree-diagnostic.json`. No se reescribe. |
| `1d3a69df31ac1ce1a75517f3f988b25a0d701b29667c89dd015d55956889bdac` | Árbol actual de `evaluate_reserved_stt.py` y `audit_fresh_postweight_stt_sources.py` (C01 re-selló; C02 verifica igualdad con `_program_tree`) | Expectativa viva. |
| `7e148e76…` | `preregister_minds14_stt_holdout.py` (campaña nunca abierta) | Contrato histórico. Distinto del sello vivo a propósito. |

Prueba: `tests/test_stt_quality_evaluators.py`.

## FieldUi

Decisión escrita: `src/Baxy.FieldUi/ORIGIN.md` reapertura 10.2.5.
Sello conjunto `0F6DCDA5DCF7DFA8A89C64763EF4E75067967977C5673121197825F8EB0E1C71`, 38 ficheros.
La constante de `MainWindowShellContractTests` no se subió a lo que hubiera en disco.

## SessionOptions / wakeword

`tests/test_wakeword_runtime_resources.py` (C01 lo versionó): cada `InferenceSession` queda con 1 hilo, `ORT_SEQUENTIAL`, spinning off. No es una prueba de consumo de CPU. C02 la incluye en el linaje; no se borra.

## STT intermitente

`test_goal09_voice_engines.py::test_voice_engine_pcm_source_wakes_on_injected_wav` (`open up pad please` vs notepad). C01 no lo tocó. C02 no baja umbral; se observa en Full.

## Runtime hash fail-closed

`MindRuntimeDiscoveryTests.RegisteredRuntimeRejectsAnyDeclaredAssetWhoseHashChanged` (GGUF) y `RegisteredRuntimeRejectsASwappedLlamaServerHash`. `manifestIsVersioned` en R281.
`IsForeignBaxyWorktree`: segmento de ruta `\BAXY\` (no `BAXY Definitivo`, no `BAXYRuntime`).
