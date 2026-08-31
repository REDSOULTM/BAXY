# Goal 09.5.6 — Síntesis: wake word, STT, TTS, audio y presencia

Cerrado 2026-08-31. Fuente de verdad machine-readable:
[`artifacts/goal095/synthesis/09.5.6_voz_audio_presencia.v1.json`](../../artifacts/goal095/synthesis/09.5.6_voz_audio_presencia.v1.json).
Inventario desde tarjetas 09.5.2–09.5.4, Goal 09
(`documentacion/herencia/09_VOZ.md`, `documentacion/03_COSTURAS.md`,
`artifacts/goal09/`) y `_09510_requirements.json`. No se leyeron cuerpos de
`biblioteca/` ni se recorrieron árboles fuente.

Siguiente prompt humano:
[`../sprints/09.5.7_TOOLS_SKILLS_MISIONES.md`](../sprints/09.5.7_TOOLS_SKILLS_MISIONES.md).

Goal 09 **no se reabre**. Pesos/manifiestos vivos de wake/STT/TTS **no se
tocaron**. `transplants: []`.

## Idiomas

ES, EN y spanglish cubiertos. Un nombre de app en inglés dentro de una frase
española («abre notepad please», «Spotify») es spanglish. pt/fr/de/it y el
eval de wake en 13 lenguas no crean trabajo.

## Qwen-ASR y Gemma native audio (no se silencian)

| Pieza | Métrica | Veredicto |
|---|---|---|
| **Qwen3-ASR-0.6B int8** CPU sherpa-onnx | Arena n=12 WER 0,081 recall anclas 0,889 p95 5,61 s; minds14 n=84 preservación 0,988 p95 9,09 s RSS 2,71 GiB; 0 rescates únicos vs Nemotron | `candidatePromoted=false`. Goal 09: otro runtime y RAM. |
| **Gemma 4 native audio** | llama-server no rutea `input_audio` (#21868); recarga por clip; ES rioplatense 2/5; 5 WAV sintéticos Sabina | Rechazo. Parakeet es el oído. |

## Subáreas (16/16)

Cada fila: mejor pieza histórica, estado Goal 09, hueco comprobado. Kind =
diseño / código / asset / benchmark / prueba_fisica.

| Subárea | Mejor histórica | Goal 09 | Hueco |
|---|---|---|---|
| Wake | LiveKit/openWakeWord `baxy.onnx` (Goal 01 0,916/0,225) | SHA `9b1ae5db…` umbral 0,5 holdout **12/12 FRR 0** | FAR no promociona; no retocar 0,5 |
| Falsos disparos | FAR Poisson TV umbral locked | **2,00 h, 5 disparos, 2,50/h, upper 5,26/h** `calibration.approved` false | Listón 0,1/h abierto en APLAZADOS |
| Ruido | `stt_noise_robustness` + FAR series | Launch 2/2 `noise_did_not_wake` | SNR STT no reejecutado; no swap |
| VAD | Silero ONNX CPU, EOU 700 ms | EOU p50 **0,21 s** máx 0,31 s | Cumple; no segundo VAD |
| STT | Parakeet int8: WER 0,044 vs Whisper 0,075; p50 71 vs 1570 ms | SHA `5a70e086…` holdout **3/3** p50 0,20 s | Entidad, no el motor |
| Nombres propios | Corrector ES 64%→81% entity-recall (ya en producto) | BAXY/Spotify fallan; dudo no ejecuta | Hotwords 5/18 rechazadas |
| Bilingüe/spanglish | ServiceNow n=59 WER 0,094 ES 0,007 EN 0,130; holdout notepad | 3/3 es/en/«abre notepad please» | App names frágiles; 13 lenguas no |
| TTS | Piper `es_MX-claude-high` ONNX + eSpeak | SHA `3ef40a71…` first 0,02 s; cancel mid | SAPI/GPL/`piper.exe`/Sherpa OfflineTts fuera |
| Primera señal | EOU oído p50 0,21 s | Launch 0,13–0,20 s; TTS 0,02 s caliente | No es el p50 2,18 s del LLM |
| Barge-in | `cancel()` media frase | Launch 2/2 cancelled | Diseño PG4 500 ms no es 2º controlador |
| Ducking | Restore-exact + AEC NLMS WASAPI | Heredado en `voice_aec.py`; AEC=false si no hay loopback | Falta dB físico, no otro ducker |
| Dispositivos | WASAPI honesto | Sidecar Python; launch 2/2 en esta máquina | Carter NOT_EXECUTED no es works |
| Modelos/assets | Manifiesto SHA wake/STT/TTS | Mismos hashes; sustituir = fichero+SHA | pg4 blobs: hashes not invented |
| Latencia | Parakeet 71 ms / RTF 0,065–0,087 | STT 0,20 s EOU 0,21 s wake 0,12 s | Qwen-ASR p95 5,6 s |
| Recursos | Idle 60 s **RSS 1088 MB**, GPU 510/16380, llama-server off | STT/TTS CPU; VRAM del decisor intacta | Qwen-ASR +2,71 GiB RSS |
| Presencia | Always-on por identidad | `BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED`; `VoiceListenCommand` apaga | No promocionar FAR para «cerrar» presencia |

## Rechazos con métrica (no folklore)

- HyperSpotter Conformer 14/96, 5/96, 19/96 FA; Whisper 25/96, 18/96, 32/96 FA (R90).
- Hotword oracle MSNER 5/18 + 18 entidades dañadas + 69 distractores.
- Qwen-ASR no promovido (recall 0,889, p95>2 s, 0 rescate único).
- Gemma native audio: API no lista.
- Whisper como fallback: eliminado (test Parakeet-only).
- `piper.exe` GPL; SAPI no es voz de producto.
- FunctionGemma `mmproj-Q8_0.gguf`: existir no es oído.

## Trasplantes

Ninguno. El corrector, hotwords, Silero, AEC/ducking y barge-in ya están en
`src/baxy_mind/voice.py`. Un recambio de cabeza wake o de STT es 09.5.9/10,
con instrumento ciego y sin retocar umbrales al abrir.

Pesos vivos, encoder y manifiestos: **no se tocaron**.
