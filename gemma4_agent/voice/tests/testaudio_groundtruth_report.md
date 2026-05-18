# testaudio ground-truth report

- Source: `Grabación (2).m4a`
- Model: `faster-whisper large-v3`
- Language: `es` (prob=0.9424)
- Duration: 292.84s (4.88 min)
- Segments (continuous): 118
- Generated: 2026-05-18T14:57:36

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
| 0 | 1.82s | ngram_repetition | small_rejected_false_positive | 0.41 | 0.12 |
| 1 | 54.62s | ngram_repetition | small_rejected_false_positive | 0.36 | 0.11 |
| 2 | 106.21s | ngram_repetition | small_rejected_false_positive | 0.31 | 0.19 |
| 3 | 158.30s | ok | small_underproduced | 0.65 | 0.50 |
| 4 | 211.81s | ngram_repetition | small_underproduced | 0.89 | 0.66 |
| 5 | 264.86s | no_speech_prob (0.69) | small_rejected_false_positive | 0.77 | 0.41 |

### Verdict distribution

- **small_rejected_false_positive**: 4
- **small_underproduced**: 2

### Per-turn detail

#### Turn k=0 (t=1.82s)

- **verdict**: small_rejected_false_positive
- **small reject**: `ngram_repetition`
- **small raw text**:
  > Abre Chrome. Gemma, abre Steam. Gemma, abre Chrome. Gemma, abre Steam. Gemma, cierra Whatsapp. Gemma, cierra Whatsapp. Gemma, minimiza.
- **large text**:
  > Abre Chrome, Gemma, abre Steam, hey Gemma, abre Chrome, Gemma, abre Steam, hey Gemma, cierra WhatsApp, Gemma, cierra WhatsApp, hey Gemma, minimiza.
- WER: 40.91% · CER: 12.24%

#### Turn k=1 (t=54.62s)

- **verdict**: small_rejected_false_positive
- **small reject**: `ngram_repetition`
- **small raw text**:
  > Ponme musica tranquila. Gemma, ponme musica tranquila. Gemma, reproduce algo de los redonditos. Gemma, reproduce algo de los redonditos. Gemma, baja el volumen. Gemma, suba el volumen al máximo. Gemma, suba el volumen.
- **large text**:
  > Ponme música tranquila. Gema, ponme música tranquila. Hey, Gema, reproduce algo de los redonditos. Hey, Gema, reproduce algo de los redonditos. Gema, baja el volumen. Hey, Gema, sube el volumen al máximo. Gema, sube el volumen.
- WER: 36.11% · CER: 11.01%

#### Turn k=2 (t=106.21s)

- **verdict**: small_rejected_false_positive
- **small reject**: `ngram_repetition`
- **small raw text**:
  > Gemma, cuándo salió GTA V? Gemma, cuándo salió GTA V? Gemma, ¿cuál es la capital de Australia? Gemma, ¿cuál es la capital de Australia? Gemma, hola, Gemma, hola.
- **large text**:
  > invito a la Mona Lisa. Hey Gemma, ¿cuándo salió GTA V? Gemma, ¿cuándo salió GTA V? Hey Gemma, ¿cuál es la capital de Australia? Gemma, ¿cuál es la capital de Australia? Hey Gemma, hola. Gemma, hola.
- WER: 30.56% · CER: 19.19%

#### Turn k=3 (t=158.30s)

- **verdict**: small_underproduced
- **small reject**: `ok`
- **small raw text**:
  > mandalo un mensaje Juan. Gemma, que llegan diez minutos. Gemma, que es el Steam Deck
- **large text**:
  > Mándale un mensaje a Juan, que yo llego en dos minutos. Hey, Gemma, mándale un mensaje a Juan. Gemma, que llego en diez minutos. Hey, Gemma, ¿qué es el Steam Deck?
- WER: 64.52% · CER: 50.31%

#### Turn k=4 (t=211.81s)

- **verdict**: small_underproduced
- **small reject**: `ngram_repetition`
- **small raw text**:
  > Gemma, Open Chrome. Gemma, Open Chrome. Gemma, Close Steam.
- **large text**:
  > vez que diga foco prende el modo enfoque el gema open cross el gema open chrome gema open chrome el gema close steam el gema no sé hablar
- WER: 89.29% · CER: 66.42%

#### Turn k=5 (t=264.86s)

- **verdict**: small_rejected_false_positive
- **small reject**: `no_speech_prob (0.69)`
- **small raw text**:
  > Gemma, pon mi Stranger Things en Netflix. Gemma, buca mi Infos sobre Vents on Moon. Gemma, buca mi Infos sobre Vents on Moon. Gemma, abre Counter-Strike 2 en Netflix.
- **large text**:
  > Youtube. Gemma ponme Stranger Things en Netflix. Gemma ponme Stranger Things en Netflix. Gemma búscame info sobre Benson Moon. Gemma búscame info sobre Benson Moon. Gemma abre Counter Strike 2 en
- WER: 77.42% · CER: 40.51%

---

*Ground truth is from Whisper-large-v3. NOT absolute truth — large can still err on dialect-specific forms (voseo) and uncommon proper nouns. Annotate corrections in `manual_correction` field of testaudio_groundtruth_full.json.*