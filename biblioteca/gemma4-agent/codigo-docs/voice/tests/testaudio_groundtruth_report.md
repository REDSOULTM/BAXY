# testaudio ground-truth report

- Source: `Grabación (2).m4a`
- Model: `faster-whisper large-v3`
- Language: `es` (prob=0.9424)
- Duration: 292.84s (4.88 min)
- Segments (continuous): 118
- Generated: 2026-05-18T16:42:28

## Continuous transcription (first 20 segments)

| Start | End | Text | no_speech | logprob |
|---|---|---|---|---|
| 0.00s | 20.24s | Hey Gemma, abre Chrome. Gemma, abre Steam. Hey Gemma, abre Chrome. Gemma, abre Steam. Hey Gemma, cierra WhatsApp. Gemma, cierra WhatsApp. Hey Gemma, minimiza la ventana. Gemma, minimiza la ventana. | 0.4319 | -0.1255 |
| 20.24s | 47.24s | Hey Gemma, pausa. Gemma, pausa. Gemma, sigue. Hey Gemma, sigue. Hey Gemma, stop. Gemma, stop. Hey Gemma, stop. Gemma, siguiente canción. Hey Gemma, siguiente canción. Gemma, siguiente canción. Hey Gemma, pon música. Gemma, pon música. Hey Gemma, pon música clásica. | 0.0071 | -0.0896 |
| 47.24s | 49.72s | Hey Gemma, pon música clásica. | 0.0071 | -0.0896 |
| 50.24s | 64.24s | Hey Gemma, ponme música tranquila. Hey Gemma, ponme música tranquila. Hey Gemma, ponme música tranquila. Hey Gemma, reproduce algo de los redonditos. Hey Gemma, reproduce algo de los redonditos. | 0.0165 | -0.0744 |
| 64.24s | 78.24s | Gemma, baja el volumen. Hey Gemma, sube el volumen al máximo. Gemma, sube el volumen al máximo. Hey Gemma, subí el volumen al máximo. Hey Gemma, subí el volumen al máximo. Hey Gemma, silencia el sistema. | 0.0165 | -0.0744 |
| 78.24s | 80.24s | Hey Gemma, ¿qué hora es? | 0.0165 | -0.0744 |
| 80.24s | 82.24s | Hey Gemma, ¿qué hora es? | 0.0146 | -0.0422 |
| 82.24s | 84.24s | Hey Gemma, ¿qué fecha es hoy? | 0.0146 | -0.0422 |
| 84.24s | 86.24s | Hey Gemma, ¿cuánto espacio me queda en el disco C? | 0.0146 | -0.0422 |
| 86.24s | 88.24s | Hey Gemma, ¿cuánto espacio me queda en el disco C? | 0.0146 | -0.0422 |
| 88.24s | 90.24s | Hey Gemma, ¿cuánto espacio me queda en el disco C? | 0.0146 | -0.0422 |
| 90.24s | 92.24s | Hey Gemma, ¿cuánto espacio me queda en el disco C? | 0.0146 | -0.0422 |
| 92.24s | 94.24s | Hey Gemma, ¿cuánta batería me queda? | 0.0146 | -0.0422 |
| 94.24s | 96.24s | Hey Gemma, ¿qué procesador tengo? | 0.0146 | -0.0422 |
| 96.24s | 98.24s | Hey Gemma, ¿qué procesador tengo? | 0.0146 | -0.0422 |
| 98.24s | 100.24s | Hey Gemma, ¿qué es la guerra de Troya? | 0.0146 | -0.0422 |
| 100.24s | 102.24s | Hey Gemma, ¿qué es la guerra de Troya? | 0.0146 | -0.0422 |
| 102.24s | 104.24s | Hey Gemma, ¿quién pintó la Mona Lisa? | 0.0146 | -0.0422 |
| 104.24s | 106.24s | Hey Gemma, ¿quién pintó la Mona Lisa? | 0.0146 | -0.0422 |
| 106.24s | 108.24s | Hey Gemma, ¿cuándo salió GTA V? | 0.0146 | -0.0422 |

*(98 more segments — see testaudio_groundtruth_full.json)*

## Per-wake alignment (small vs large)

| k | wake_ts | small_reject | verdict | WER | CER |
|---|---|---|---|---|---|
| 0 | 1.82s | ok | small_underproduced | 1.00 | 0.67 |
| 1 | 54.62s | ngram_repetition | small_rejected_false_positive | 0.36 | 0.10 |
| 2 | 108.61s | ngram_repetition | small_rejected_false_positive | 0.11 | 0.04 |
| 3 | 163.10s | ok | small_underproduced | 0.80 | 0.70 |
| 4 | 216.86s | ok | agree | 0.67 | 0.23 |
| 5 | 272.29s | ngram_repetition | small_rejected_false_positive | 0.19 | 0.07 |

### Verdict distribution

- **small_rejected_false_positive**: 3
- **small_underproduced**: 2
- **agree**: 1

### Per-turn detail

#### Turn k=0 (t=1.82s)

- **verdict**: small_underproduced
- **small reject**: `ok`
- **small raw text**:
  > Aurecrum
- **large text**:
  > Howdy crumb.
- WER: 100.00% · CER: 66.67%

#### Turn k=1 (t=54.62s)

- **verdict**: small_rejected_false_positive
- **small reject**: `ngram_repetition`
- **small raw text**:
  > Ponme musica tranquila. Gemma, ponme musica tranquila. Gemma, reproduce algo de los redonditos. Gemma, reproduce algo de los redonditos. Gemma, baja el volumen. Gemma, suba el volumen al máximo. Gemma.
- **large text**:
  > Ponme música tranquila. Gema, ponme música tranquila. Hey Gema, reproduce algo de los redonditos. Hey Gema, reproduce algo de los redonditos. Gema, baja el volumen. Hey Gema, sube el volumen al máximo. Gema.
- WER: 36.36% · CER: 10.14%

#### Turn k=2 (t=108.61s)

- **verdict**: small_rejected_false_positive
- **small reject**: `ngram_repetition`
- **small raw text**:
  > ¿Cuándo salió GTA V? Gemma. ¿Cuándo salió GTA V?
- **large text**:
  > ¿Cuándo salió GTA V? Gema, ¿cuándo salió GTA V?
- WER: 11.11% · CER: 4.26%

#### Turn k=3 (t=163.10s)

- **verdict**: small_underproduced
- **small reject**: `ok`
- **small raw text**:
  > manda un mensaje
- **large text**:
  > en dos minutos. Hey Gemma, mándale un mensaje a Juan.
- WER: 80.00% · CER: 69.81%

#### Turn k=4 (t=216.86s)

- **verdict**: agree
- **small reject**: `ok`
- **small raw text**:
  > Open Chrome. Gemma, Open Chrome
- **large text**:
  > Open Chrome, I say Open Chrome.
- WER: 66.67% · CER: 22.58%

#### Turn k=5 (t=272.29s)

- **verdict**: small_rejected_false_positive
- **small reject**: `ngram_repetition`
- **small raw text**:
  > Buca mi info sobre Benson Moon. Gemma, buca mi info sobre Benson Moon. Gemma, abre Counter-Strike 2 en Steam. Gemma, abre Counter-Strike 2 en Steam. Gemma, reproduce volumen Rhapsody.
- **large text**:
  > Búscame info sobre Benson Moon. Gemma, búscame info sobre Benson Moon. Gemma, abre Counter-Strike 2 en Steam. Gemma, abre Counter-Strike 2 en Steam. Gemma, reproduce Bohemian Rhapsody.
- WER: 18.52% · CER: 7.07%

---

*Ground truth is from Whisper-large-v3. NOT absolute truth — large can still err on dialect-specific forms (voseo) and uncommon proper nouns. Annotate corrections in `manual_correction` field of testaudio_groundtruth_full.json.*