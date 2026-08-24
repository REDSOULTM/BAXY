# Handoff — Goal 09 — 2026-08-24

## Objetivo
BAXY oye «BAXY», transcribe y habla, local e interrumpible.

## Estado
Hecho. Motores en el sidecar Python; nombre+SHA en el manifiesto vivo y en R281.

- Wake: `baxy.onnx` SHA `9b1ae5db…`, manifiesto SHA `fefb9517…`, umbral 0,5. Holdout 12/12. FAR 2,06 h / 6 disparos (2,91/h, Poisson 5,74/h). Umbral no promocionado; `calibration.approved` false.
- Escucha permanente: `wake_on_start` true vía `BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED`. El hash se publica aunque el interruptor apague. `VoiceListenCommand` es el apagado visible.
- STT: Parakeet TDT 0.6b v3 int8 SHA `5a70e086…`. Holdout 3/3 es/en/codeswitch (`stt_holdout.json`).
- EOU live: ingest habla + silencio → `recognized` p50 0,21 s, máx 0,31 s (`eou_first_signal.json`).
- TTS: Piper `es_MX-claude-high` SHA `3ef40a71…`; barge-in corta a media frase.
- Launch: 2/2 `wake_detected` + «Open notepad please» + speak + cancel (`voice_launch.json`).
- Pytest: 81 passed en 36,56 s (`{SCRATCH}/voice_unit.log`). C#: MindRuntimeDiscovery + VoiceListenCommand 24 passed.

## Decisiones tomadas
- Umbral wake 0,5 del goal 01, no retocado pese al FAR.
- Escucha al arrancar por identidad, no por promoción del listón 0,1/h.
- TTS: ONNX Piper + eSpeak; sherpa OfflineTts rechazó el export.
- Motores en sidecar Python, no tres procesos llama-server. Sustituir = fichero + hash.

## Siguiente acción recomendada
Nada en este goal. FAR 0,1/h sigue abierto en APLAZADOS para cuando haya un candidato de cabeza.
