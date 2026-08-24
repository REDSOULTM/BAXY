# Handoff — Goal 09 — 2026-08-24 — (uncommitted)

## Objetivo
BAXY oye «BAXY», transcribe y habla, local e interrumpible.

## Estado
Hecho: TTS neural Piper es_MX-claude-high (onnxruntime+eSpeak, no piper.exe); habla siempre; barge-in cancel; listen-command por voz; STT Parakeet con transcripción dudosa → pregunta; holdout wake 12/12 Sabina+Zira umbral 0,5; manifiesto TTS+STT con SHA; pruebas `test_goal09_voice_engines.py` y `VoiceListenCommandTests`.
En curso: FAR de horas sobre series (checkpoint en scratch `wake_far.json`); wake_on_start sigue false hasta Poisson ≤0,1/h.
Sin: calibración aprobada (FAR de TV comedia ya disparó 1 vez en ~0,1 h).

## Decisiones tomadas
- Umbral wake 0,5 del goal 01, no retocado.
- Población de cobertura: palabra aislada, es-MX + en-US. Helena es-ES y rates ±6 fuera.
- TTS: ONNX Piper + eSpeak; sherpa OfflineTts rechazó el export.
- Motores en sidecar Python, no en .NET. Sustituir = fichero + hash.

## Siguiente acción recomendada
Leer `{SCRATCH}/wake_far.json`. Si hours ≥ 2, copiar a `artifacts/goal09/wake_far.json`. Si FAR superior ≤ 0,1/h, escribir `baxy-wake-corpus-gate-v3.json` y registrar wake_on_start.
