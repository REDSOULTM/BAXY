# Handoff — Goal 09 — 2026-08-24

## Objetivo
BAXY oye «BAXY», transcribe y habla, local e interrumpible.

## Estado
Hecho. Motores en el sidecar Python; nombre+SHA en el manifiesto vivo y en R281.

- Wake: `baxy.onnx` SHA `9b1ae5db…`, manifiesto SHA `fefb9517…`, umbral 0,5. Holdout 12/12. FAR **2,00 h terminada** (`partial: false`) / 5 disparos (2,50/h, Poisson 5,26/h). Umbral no promocionado; `calibration.approved` false.
- Escucha permanente: `wake_on_start` true vía `BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED`. Idle 60 s wake on: RSS **1088 MB**, llama-server no corre, GPU 510/16380 MiB. `VoiceListenCommand` es el apagado visible.
- Catálogo por voz: MissionInput texto=transcripción (misma intención/riesgo/confirmación); `sí`/`no` autorizan o cancelan; narración de cada operación. C# 65 passed (VoiceListenCommand + pipeline + confirmación + narración).
- STT: Parakeet TDT 0.6b v3 int8 SHA `5a70e086…`. Holdout 3/3 es/en/codeswitch (`stt_holdout.json`).
- EOU live: ingest habla + silencio → `recognized` p50 0,21 s, máx 0,31 s (`eou_first_signal.json`).
- TTS: Piper `es_MX-claude-high` SHA `3ef40a71…`; barge-in corta a media frase.
- Launch: 2/2 `wake_detected` + «Open notepad please» + speak + cancel (`voice_launch.json`).
- Pytest: 81 passed en 36,56 s (`{SCRATCH}/voice_unit.log`). C#: Discovery 24; catálogo-voz/confirmación/narración 65.

## Decisiones tomadas
- Umbral wake 0,5 del goal 01, no retocado pese al FAR.
- Escucha al arrancar por identidad, no por promoción del listón 0,1/h.
- TTS: ONNX Piper + eSpeak; sherpa OfflineTts rechazó el export.
- Motores en sidecar Python, no tres procesos llama-server. Sustituir = fichero + hash.

## Siguiente acción recomendada
Nada en este goal. FAR 0,1/h sigue abierto en APLAZADOS para cuando haya un candidato de cabeza.
