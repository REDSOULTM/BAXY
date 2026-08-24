# Goal 09 — qué se heredó, qué se midió, qué se dejó

Fecha: 2026-08-23. Máquina de este goal.

## Heredado y vigente

| Pieza | De dónde | Por qué se queda |
|---|---|---|
| Wake `baxy.onnx` (openWakeWord / LiveKit, mel + embedding + cabeza) | `BAXY/legacy/models/artifacts/wake_livekit/` | Goal 01 lo ejecutó: positivo 0,916 / negativo 0,225, 0 disparos. Hoy se habilita con manifiesto y hash. |
| STT Parakeet TDT 0.6b v3 int8 (sherpa-onnx, CPU) | `~/.gemma4/models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` | Ya era el STT requerido. RTF CPU. El nombre propio se corrige después del KWS, no se usa para despertar. |
| Captura, VAD Silero, AEC/ducking, barge-in, protocolo `voice.*` | `src/baxy_mind/voice.py` | Ya estaba escrito. No se rehízo el bucle. |
| Confirmaciones `sí`/`no` por el mismo `MissionInput` | `ConfirmationReplyParser` | Una transcripción de confirmación entra por el mismo camino que el texto. |
| Interruptor visible de escucha | Field UI mic + `VoiceModeLabel` | Ya existía. Este goal lo hace accionable por voz. |

## Medido hoy y elegido

| Pieza | Elegido | Por qué |
|---|---|---|
| Wake | `baxy.onnx` umbral **0,5** (punto de operación del goal 01, no retocado al abrir el holdout) | SAPI Sabina (es-MX) y Zira (en-US) disparan por encima de 0,5; ruido y películas se miden aparte. |
| STT | Parakeet int8 CPU | Sigue siendo el bundle declarado. Qwen3-ASR-0.6B GGUF está en disco (~1 GB) y **no se adoptó**: pediría otro runtime y competiría por RAM; el fallo del nombre propio no es el wake. |
| TTS | Piper `es_MX-claude-high` ONNX + eSpeak `es-419`, vía onnxruntime (no `piper.exe` GPL) | Voz con carácter, español latino. SAPI queda como degradación si falta el ONNX. Sherpa OfflineTts rechazó este export (sin `sample_rate` en metadatos); no se descargó un bundle duplicado. |

## Descartado porque el estado del arte o la evidencia lo dejó atrás

- **SAPI como voz de producto.** ADR-0007 la eligió para no importar Piper GPL. El goal 09 manda voz con carácter. Se aisló la licencia: onnxruntime Apache + pesos MIT + eSpeak ya instalado; SAPI no es la voz.
- **Piper.exe GPL in-process.** Rechazo vigente de la auditoría de licencias. No se importa.
- **HyperSpotter / cascada CTC / clasificadores acústicos propios.** Rechazados en este repositorio. El KWS de producto es la cabeza LiveKit de una palabra, `BAXY`.
- **Holdout de 13 idiomas.** Identidad: acentos latinos e inglés.
- **STT en GPU / Qwen3-ASR como motor de producto.** CPU. El GGUF se deja en disco.

## Frontera de proceso

Wake, STT y TTS corren en el sidecar Python (`baxy.local.v1`), no en el proceso .NET. Sustituir uno es cambiar el fichero + el SHA-256 del manifiesto, sin recompilar la App. No se abrieron tres procesos extra tipo `llama-server`: el sidecar ya es esa frontera, y el coste de IPC no se justificó frente a la sustituibilidad que ya da el manifiesto.

## Accesibilidad

Toda respuesta se dice en voz alta aunque la entrada sea texto. «deja de escucharme» / «escucha siempre» accionan el interruptor de BAXY, no el mute de Windows. Las confirmaciones `sí`/`no` ya iban por `MissionInput`.
