# Handoff — Goal 09 — 2026-08-24 — 273a321+

## Objetivo
BAXY oye «BAXY», transcribe y habla, local e interrumpible.

## Estado
Hecho: TTS neural Piper es_MX-claude-high; habla siempre; barge-in; listen-command; STT Parakeet; holdout 12/12; EOU p50 0,38 s; launch 2/2; FAR **2,02 h / 6 disparos**.
`wake_on_start` false: Poisson 5,85/h > 0,1/h. No se retoca el umbral 0,5.

## Decisiones tomadas
- Umbral wake 0,5 del goal 01, no retocado.
- Población de cobertura: palabra aislada, es-MX + en-US. Helena es-ES y rates ±6 fuera.
- TTS: ONNX Piper + eSpeak; sherpa OfflineTts rechazó el export.
- Motores en sidecar Python, no en .NET. Sustituir = fichero + hash.

## Siguiente acción recomendada
Leer `{SCRATCH}/wake_far.json`. Si hours ≥ 2, copiar a `artifacts/goal09/wake_far.json`. Si FAR superior ≤ 0,1/h, escribir `baxy-wake-corpus-gate-v3.json` y registrar wake_on_start.
