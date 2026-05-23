# SPIKE — sherpa-onnx + Parakeet-TDT-0.6B-v3 int8 (medido en la máquina, 2026-05-23)

> Eje VIABILIDAD. NO es producción. Verifica la ruta que la investigación de
> RED recomendó como GANADORA. Medido contra clips reales+sintéticos existentes.

## Lo que SÍ se confirmó (a favor)

- **pip-installable, CPU, sin compilar**: `pip install sherpa-onnx>=1.13.1` (1.13.2)
  wheel precompilado Windows/Py3.10. ✅ Carga en ~2s.
- **API de biasing real existe**: `OfflineRecognizer.from_transducer(...,
  hotwords_file, hotwords_score, decoding_method="modified_beam_search",
  bpe_vocab, modeling_unit)`. (Corrección a la investigación: NO existe
  `from_nemo_transducer`; es `from_transducer(model_type="nemo_transducer")`.)
- **LATENCIA EXCELENTE en comando corto** (audio ~1.7s, 4 threads, CPU):
  - greedy: **p50 108ms / p95 163ms**
  - modified_beam_search: **p50 120ms / p95 162ms**
  - => **~10x más rápido que whisper-small** en CPU (que daba >1s). La
    investigación se equivocó al decir "comparable"; en comandos cortos
    Parakeet es MUCHO más rápido. (RTF ~0.06-0.07.)
- **RAM**: greedy 773MB, hotwords (MBS) 1472MB. Cabe en CPU; no toca VRAM del LLM.

## Lo que NO funcionó (en contra — el motivo de migrar falla)

- **La calidad BASE de Parakeet-v3 sobre este audio Spanglish es MALA**, igual o
  peor que Whisper:
  - "abre Steam" → "A Hema Hablestan."
  - "Hey Gemma, ..." → "A Hema / Ey Jamma / Eigenma" (rompe el wake word también)
  - "Stranger Things en Netflix" → "Ponstrom Gertis in Netfix"
  - "Counter-Strike" → "Trikenstein"
- **Los hotwords NO arreglan los nombres — DESESTABILIZAN la salida.** Con
  `hotwords_score=3.0` y los nombres correctamente tokenizados a BPE
  (▁Ste+am, ▁Net+fl+ix, etc. — verificado que el vocab SÍ los representa):
  - "abre Steam" → "8 mal." (PEOR, gibberish)
  - "Daredevil...Max" → "off the dragon enough, Max" (sigue mal)
  - varios casos el biasing empeoró vs greedy.
  Coincide con Gotcha #1 de la investigación (inestabilidad MBS+TDT) PERO además
  el problema de fondo es que **el biasing no puede rescatar una transcripción
  base ya rota**: si "Steam" se oyó "Hablestan", subir el score de los tokens de
  "Steam" no alcanza para vencer la evidencia acústica mal modelada.

GOTCHA de packaging: el modelo NO trae `bpe.vocab` (la investigación lo asumía).
`text2token` requiere `bpe.model` (sentencepiece) que tampoco viene. Tuve que
construir un tokenizador BPE greedy desde tokens.txt para encodear hotwords =
fricción real, no "enchufar y listo".

## CAVEAT honesto sobre el audio del spike

Estos clips son **sintéticos (Piper)** — Parakeet-v3 fue entrenado con datos
EUROPEOS (Granary), sesgo a castellano de España; las voces Piper + acento
pueden penalizarlo injustamente. NO medí sobre voz real con anglicismos (no
existe dataset libre, held-out de RED pendiente). Es posible que sobre voz
humana real Parakeet rinda mejor. PERO: (a) Whisper-small sobre los MISMOS clips
sintéticos daba mejor base, (b) el hecho de que los hotwords DESESTABILICEN (no
solo "no ayuden") es una señal de riesgo independiente del tipo de voz.

## VEREDICTO DEL SPIKE

La ruta sherpa-onnx+Parakeet **cumple las 6 restricciones formales** (CPU, pip,
open-vocab, biasing real, autosuficiente, español) y **gana en latencia** — pero
**en la prueba medida NO mejora el reconocimiento de nombres propios; los
hotwords lo empeoran**, y la calidad base es peor que Whisper en este audio.

=> NO migrar a ciegas. El único motivo para migrar (mejor biasing de nombres) NO
se sostuvo en la medición. Antes de descartar o adoptar, falta UNA cosa decisiva
que sólo RED puede dar: **voz real con anglicismos** (su held-out). Si sobre SU
voz Parakeet+hotwords sí mejora los nombres, se reconsidera (la latencia 10x
sería un bonus enorme). Si no, Whisper-small + corrector dinámico (Ruta C) sigue
siendo el mejor compromiso.

**Recomendación:** mantener Whisper-small como motor. Reconsiderar Parakeet SOLO
con un A/B sobre voz real de RED (no sintética). El spike deja todo listo
(`scripts/spike_sherpa_parakeet.py`) para re-correr con esos clips.
