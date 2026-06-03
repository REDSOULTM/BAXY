# STT local con biasing contextual real para Spanglish en CPU — qué existe y qué no

## TL;DR

- **La única solución madura, pip-installable, CPU-only, open-vocab, con biasing contextual REAL (no prompt-prepend) y con modelo Spanish nativo es `sherpa-onnx` (k2-fsa) usando un modelo Zipformer-Transducer o Parakeet-TDT en `modified_beam_search` con archivo de hotwords**. El biasing es shallow-fusion vía autómata Aho-Corasick sobre los tokens BPE — no es post-corrección, es decodificación.
- **El "modelo ideal" (Parakeet-TDT-0.6B-v3 multilingüe con hotwords) ya existe técnicamente** desde sherpa-onnx v1.13.1 (PR #3077 mergeado 5 feb 2026 + fix de estabilidad PR #3589 en la release v1.13.1, anterior al 13 may 2026), pero tiene gotchas serios: el `encoder.int8.onnx` pesa 622 MB y consume ~2 GB de RAM por instancia, latencia en frases cortas (~4 s de audio, 2 threads) ≈ 1.0–1.3 s (RTF ≈ 0.325) — comparable a faster-whisper-small int8, **no más rápido en comandos cortos**, y el code-switching es/en no está benchmarkeado por NVIDIA.
- **Recomendación**: probar la ruta sherpa-onnx + Parakeet-TDT-0.6B-v3 int8 con hotwords como motor primario (cumple las 6 restricciones), manteniendo faster-whisper-small como fallback. Si la RAM o la latencia en frases muy cortas son problema, no hay un Plan B "limpio" — el único modelo Spanish-only con hotwords reales en el ecosistema (bookbot Zipformer-es) emite fonemas IPA, no texto, lo cual rompe el contrato funcional.

## Hallazgos clave

### El biasing de sherpa-onnx es REAL (no es prompt-prepend)

La documentación oficial es explícita: *"In this section, we describe how we implement the hotwords (aka contextual biasing) feature with an Aho-corasick automaton (…) Only transducer models support hotwords in sherpa-onnx (…) Also, you have to change the decoding method to modified_beam_search to use hotwords. The default decoding method greedy_search does not support hotwords"* (k2-fsa.github.io/sherpa/onnx/hotwords/index.html). El score boost se aplica durante el beam search sobre los tokens BPE/cjkchar, con cancelación de score si el match parcial falla. Es decir: es shallow-fusion genuino, no prepend de prompt, y modifica el ranking de hipótesis con la evidencia acústica. Esto es exactamente lo que NeMo hace para Parakeet en GPU, pero corriendo en CPU vía ONNX Runtime.

### sherpa-onnx es pip-installable cross-platform con wheels precompilados

PyPI publica wheels para CPython 3.8–3.13 en Linux x86_64 / aarch64 / armv7l, macOS 10.15+ x86_64, macOS 11+ arm64, macOS universal2, **Windows x64 y Win32**. Versión actual v1.13.2 (release del 13 may 2026, según timestamp del asset). Instalación: `pip install sherpa-onnx`. No requiere compilar Kaldi, ni CUDA, ni Docker. La página de PyPI lista decenas de proyectos en producción usándolo (VoxSherpa, voice-typing GTK4, Xiaozhi ESP32 backend, etc.). Es maduro, con releases muy frecuentes (cadencia ~2 semanas) y ~10.7 k stars en GitHub (página pública del repo k2-fsa/sherpa-onnx).

### El modelo ideal para Spanish + Spanglish: `sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8`

- **Idiomas**: 25 europeos incluyendo Spanish, English, Portuguese, Italian, French, German, etc. Del paper *"Canary-1B-v2 & Parakeet-TDT-0.6B-v3: Efficient and High-Performance Models for Multilingual ASR and AST"* (Sekoyan, Koluguri, Tadevosyan, Zelasko et al., NVIDIA, arXiv:2509.14128 v2 25 sep 2025): *"We also release Parakeet-TDT-0.6B-v3, a successor to v2, offering multilingual ASR across the same 25 languages with just 600M parameters"*.
- **WER en español (model card oficial nvidia/parakeet-tdt-0.6b-v3)**: Fleurs **3.45 %**, MLS **4.39 %**, CoVoST **3.41 %** — entre los mejores de los 25 idiomas, con greedy y sin LM externo. La media de los 25 idiomas es 11.97 % (Fleurs), 7.83 % (MLS), 11.98 % (CoVoST), por lo que el español está varios puntos por debajo de la media. Para referencia general del leaderboard, el mismo modelo alcanza 6.32 % de WER promedio en Open ASR Leaderboard (Open ASR Leaderboard / paper arXiv:2604.14493v2).
- **Tokenizer unificado de 8.192 tokens SentencePiece compartido entre los 25 idiomas** — del model card: *"a unified SentencePiece Tokenizer with a vocabulary of 8,192 tokens (…) optimized across all 25 supported languages"*. Esto es estructuralmente bueno para Spanglish porque las sub-palabras inglesas existen en el mismo vocabulario que el español; la pieza `▁Steam` o `▁Chrome` o `▁Disney` puede emitirse en una utterance marcada como `es`.
- **Hotwords funcionando**: PR #3077 *"Add modified beam search and hotwords support for NeMo transducer models"* (mergeado 5 feb 2026, confirmado por el propio issue #3267 que cita la fecha textualmente) añadió `OfflineTransducerModifiedBeamSearchNeMoDecoder` que habilita hotwords contextuales para Parakeet-TDT vía la infraestructura ContextGraph existente.
- **Latencia/RTF en CPU x86**: el benchmark oficial de sherpa-onnx con greedy_search, 2 threads, INT8, sobre `en.wav` de 3.845 s reporta *"Elapsed seconds: 1.249 s / Real time factor (RTF): 1.249 / 3.845 = 0.325"*. En audio largo (334 s) baja a RTF 0.028 (~35× real-time). Memoria: encoder.int8.onnx = 622 MB en disco; ~2 GB RAM residente por recognizer activo (model card NVIDIA: *"Atleast 2GB RAM for model to load"*; consistente con el reporte de groxaxo/parakeet-tdt-0.6b-v3-fastapi-openai *"Each request consumes ~2GB RAM; size deployment accordingly"*).

### Gotcha #1 — bug de alucinación en MBS+TDT (RESUELTO en v1.13.1)

Issue #3267 reportó que con `modified_beam_search` + Parakeet-TDT en sherpa-onnx v1.12.25, ~20 % de las requests devolvían "Yeah." o texto vacío. **El bug fue arreglado por el PR #3589 *"Fix bugs in NeMo transducer modified beam search"* (csukuangfj), incluido en la release v1.13.1** (publicada antes del 13 may 2026; la release v1.13.2 inmediatamente posterior tiene assets con timestamp 2026-05-13T12:44:16Z). El root cause estaba en que el decoder TDT no añadía el log-prob de la duración a la hipótesis y en un problema de avance de frame. **Es imprescindible usar v1.13.1 o posterior — v1.13.0 todavía tiene el bug.**

### Gotcha #2 — code-switching no está validado para Spanglish

NVIDIA no publica ningún benchmark de code-switching es/en, y la model card del puerto NexaAI/parakeet-tdt-0.6b-v3-ane declara explícitamente: *"The model may produce transcription errors, particularly with code-switching or noisy input"*. La detección de idioma es automática **a nivel de utterance, no de frase**, lo que significa que el modelo se "compromete" con un idioma y el comportamiento en utterances mixtas no está caracterizado empíricamente. La buena noticia es que el biasing por hotwords es exactamente la mitigación correcta y documentada para forzar el reconocimiento de proper nouns en inglés dentro de un contexto español: el ContextGraph opera sobre tokens BPE y el tokenizer unificado de 8.192 piezas cubre subpalabras inglesas.

### Gotcha #3 — la latencia en comandos cortos NO mejora vs faster-whisper-small

El RTF de 0.325 en frases de 4 s (oficial, 2 threads) es comparable a faster-whisper-small int8 en el mismo hardware. La gran ventaja de Parakeet-TDT (RTF de 0.028 en audio largo) se diluye en frases cortas porque el coste fijo del encoder de 600M params domina. Un usuario en huggingface.co/nvidia/parakeet-tdt-0.6b-v3/discussions/10 confirma: *"after multiple inferences of the same 37s audio, the RTF is around 0.01. (…) for shorter audio, such as 10s, it is around 0.02 after multiple inferences. However, when I change the audio file during inference, its RTF can only be maintained at around 0.1"*. **Si el caso de uso es 100% comandos cortos (≤3 s), Parakeet-v3 no será dramáticamente más rápido que whisper-small** — la migración se justifica por la calidad del biasing y por la precisión, no por velocidad.

### Alternativas reales investigadas y descartadas

- **bookbot/sherpa-onnx-zipformer-streaming-robust-es-v0**: Zipformer-RNN-T streaming en español puro. Pip-installable con sherpa-onnx, hotwords funcionan. PERO está entrenado a **fonemas IPA**, no a palabras — del model card: *"this model was trained to predict sequence of phonemes, e.g. ['w', 'ɑ', 'ʃ', 'i', 'ɑ']. Therefore, the model's vocabulary contains the different IPA phonemes found in gruut"*. Esto rompe el contrato de "open-vocab en texto" del usuario: necesitas un G2P (gruut) para escribir cualquier proper noun como secuencia IPA antes de ponerlo como hotword, y la salida tampoco es texto sino fonemas. Útil sólo como prueba de concepto, no como motor de producción.
- **sherpa-onnx-nemo-canary-180m-flash-en-es-de-fr-int8**: 4 idiomas incluyendo español. Pero es Canary (attention encoder-decoder), no transducer — y sherpa-onnx **sólo soporta hotwords en modelos transducer**: *"Only transducer models support hotwords in sherpa-onnx (…) All other models don't support hotwords"*. Descartado por incompatibilidad con biasing.
- **WhisperBiasing (BriansIDP)**, **CB-Whisper (Li et al. LREC-COLING 2024)**, **OWSM-Biasing (Sudo et al. Interspeech 2025)**, **TCPGen-Whisper (Lall & Liu 2024, arXiv:2410.18363)**: papers con código pero (a) no empaquetados como librería pip, (b) requieren PyTorch + GPU implícito para reentrenar el componente de biasing en muchos casos, (c) sin modelos en español publicados. Son investigación, no productos.
- **CTranslate2 PR #1789** (shallow contextual biasing para Whisper, *"Adds an optional contextual biasing parameter to the Whisper model to enable shallow contextual biasing toward given sequences by modifying logits"*): **sigue OPEN, no mergeado**, comentarios de usuarios reclamando un release desde hace meses. Descartado por el propio usuario.
- **WeNet contextual biasing**: existe como shallow fusion CTC/WFST con context graph documentado, pero (a) no hay modelo español oficial mantenido, (b) el packaging para Windows no es pip-installable con wheels precompilados, (c) la propia roadmap "Next WeNet" admite *"poor rare word performance in contextual biasing, complicated LM solution since FST and token passing beam search are introduced"*.
- **onnx-asr** (istupakov, PyPI v0.11.0): wrapper Python liviano para Parakeet-v3/Canary en ONNX, pip-installable (`pip install onnx-asr[cpu,hub]`). **NO soporta hotwords / contextual biasing** — sólo `model.recognize(wav)`. Bueno como reemplazo plug-and-play de faster-whisper para Spanish, pero no resuelve el problema del biasing.
- **Vosk (Kaldi)**: tiene un modelo grande español (vosk-model-es-0.42, 1.4 GB) y "vocabulary injection" via grammar (closed-vocab), pero el biasing real con boost continuo y open-vocab no está expuesto en la API Python estable. Descartado por el constraint de open-vocab.

## Tabla de candidatos

| Solución | (1) Latencia CPU | (2) CPU-only | (3) Open-vocab | (4) Biasing REAL | (5) pip cross-platform | (6) Spanish + code-switch | Veredicto |
|---|---|---|---|---|---|---|---|
| **sherpa-onnx + Parakeet-TDT-0.6B-v3 int8 + hotwords** (v1.13.1+) | ⚠️ RTF 0.325 en frases cortas (≈1 s / 4 s audio, 2 threads) — equiparable a whisper-small, no mejor | ✅ ONNX Runtime CPU, sin GPU | ✅ Transducer libre, sin grammar | ✅ Aho-Corasick shallow-fusion sobre BPE en `modified_beam_search` | ✅ Wheels Win/macOS/Linux en PyPI | ✅ es WER 3.45–4.39 %, tokenizer unificado 25 idiomas; ⚠️ code-switch no benchmarkeado | **GANADOR** con caveats |
| sherpa-onnx + Zipformer es bookbot (fonemas) | ✅ Modelo pequeño, RTF muy bajo | ✅ | ⚠️ Open-vocab pero salida en IPA, no texto | ✅ (sobre fonemas) | ✅ | ⚠️ Sólo Spanish, sin English mix, requiere G2P externo | Descartado (salida fonémica) |
| sherpa-onnx + Canary 180M flash en-es-de-fr | ✅ | ✅ | ✅ | ❌ Canary es attn-enc-dec, sin hotwords en sherpa-onnx | ✅ | ✅ es nativo | Descartado (sin biasing) |
| onnx-asr (Parakeet-v3 / Canary wrapper, PyPI) | ✅ | ✅ | ✅ | ❌ No expone hotwords | ✅ `pip install onnx-asr[cpu,hub]` | ✅ | Descartado (sin biasing) |
| Vosk + grammar | ✅ Muy bajo | ✅ | ❌ Grammar = closed-vocab | ⚠️ Sólo grammar boost, no logit | ✅ | ⚠️ Spanish puro | Descartado (closed-vocab) |
| WhisperBiasing / CB-Whisper / TCPGen-Whisper (papers) | ⚠️ Whisper-base/small en CPU | ✅ | ✅ | ✅ (TCPGen / KWS) | ❌ No empaquetado pip | ❌ Sin modelos es publicados | Descartado (no producto) |
| WeNet + context graph | ⚠️ | ✅ | ✅ | ✅ Shallow-fusion CTC/WFST | ⚠️ Wheels Linux principalmente | ❌ Sin modelo es mantenido | Descartado (packaging + es) |
| CTranslate2 PR #1789 (Whisper logit bias) | ✅ | ✅ | ✅ | ✅ | ❌ PR sin mergear, fork frágil | ✅ | Descartado (no mergeado) |
| faster-whisper hotwords / initial_prompt (status quo) | ✅ | ✅ | ✅ | ❌ Sólo prepend de tokens, no biasing | ✅ | ⚠️ Genera "Aurekrom", "estímulo" | Status quo, problema actual |

## Detalle de los 2 ganadores

### #1 — sherpa-onnx + Parakeet-TDT-0.6B-v3 int8 (PRIMARIO RECOMENDADO)

**Cómo integrar**:

```bash
pip install "sherpa-onnx>=1.13.1"   # IMPORTANTE: NO usar 1.13.0 (bug MBS+TDT)
wget https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2
tar xvf sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2
```

```python
import sherpa_onnx
recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_transducer(
    encoder="sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8/encoder.int8.onnx",
    decoder="sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8/decoder.int8.onnx",
    joiner="sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8/joiner.int8.onnx",
    tokens="sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8/tokens.txt",
    num_threads=4,
    decoding_method="modified_beam_search",          # OBLIGATORIO para hotwords
    hotwords_file="hotwords.txt",                    # una por línea, p.ej. "Steam :3.0", "Daredevil :2.5"
    hotwords_score=2.0,
    modeling_unit="bpe",
    bpe_vocab="sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8/bpe.vocab",   # generado con export_bpe_vocab.py
)
```

El archivo `bpe.vocab` se genera una sola vez con el helper `export_bpe_vocab.py` que ya viene en el repo de sherpa-onnx (formato confirmado en el issue #1762 sobre el modelo coreano).

**Madurez**: ~10.7 k stars (página pública del repo), releases cada ~2 semanas, mantenido activamente por Fangjun Kuang (k2-fsa), licencia Apache 2.0. PR #3077 mergeado feb 2026, fix de estabilidad #3589 en la release v1.13.1 (anterior al 13 may 2026). Producción real en VoxSherpa, voice-typing GTK4, Xiaozhi ESP32, etc.

**Gotcha principal**: ~2 GB RAM residente. Si el LLM ya satura RAM (el usuario corre LLM 2–4B cuantizado en GPU pero también tiene memoria de sistema comprometida), esto importa. Si la frase es corta (≤3 s), la latencia es comparable a whisper-small, no menor. Probar empíricamente "abre Steam" / "pon Daredevil en Disney plus" antes de migrar: el code-switching no está benchmarkeado por NVIDIA.

### #2 — Fallback: bookbot/sherpa-onnx-zipformer-streaming-robust-es-v0 (sólo si Parakeet-v3 no entra en RAM)

Zipformer-Transducer streaming entrenado a fonemas IPA en español. Empaquetable igual con sherpa-onnx. Soporta hotwords nativamente. **Gotcha mayor**: la salida son fonemas IPA, no texto. Requiere un decoder fonema→grafema (gruut o equivalente) y los hotwords también hay que pasarlos como secuencias IPA. Es realista sólo si tu pipeline ya tolera ese paso adicional o si construyes un wrapper. No es la mejor opción si quieres que "Steam" salga literalmente como "Steam".

## Recomendaciones

1. **Próximo paso inmediato (1–2 días)**: hacer prueba A/B con un corpus pequeño (50–100 utterances Spanglish reales del usuario) comparando:
   - faster-whisper-small int8 (baseline)
   - sherpa-onnx Parakeet-TDT-0.6B-v3 int8 sin hotwords (greedy_search)
   - sherpa-onnx Parakeet-TDT-0.6B-v3 int8 con hotwords (modified_beam_search) — lista de hotwords = nombres de apps/juegos/series instaladas
   
   Métricas: WER global, U-WER (sobre proper nouns), latencia P50/P95 end-to-end, RAM peak.

2. **Si WER en proper nouns baja >30 % con hotwords, latencia P95 <1.5 s y RAM <2.5 GB → migrar**. Mantener faster-whisper como motor secundario por si Parakeet falla en una frase específica.

3. **Si el bug de hallucination volviera a aparecer en v1.13.1+**, reportarlo en el issue #3267 (que tú mismo creaste) y, mientras tanto, usar el workaround documentado: `greedy_search` por defecto y `modified_beam_search` sólo cuando hay hotwords activos para esa sesión.

4. **No invertir en CB-Whisper, TCPGen ni en el fork de CTranslate2 con shallow biasing**. Son investigación; el coste de mantener un fork compilado para 3 OS supera el beneficio dado que sherpa-onnx ya da el mismo resultado funcional con wheels.

5. **Threshold para abandonar Parakeet-v3 y volver al status quo + fuzzy corrector**: si la migración no reduce U-WER en proper nouns en al menos 25 % relativo respecto a whisper-small + RapidFuzz/Double Metaphone que ya tienes, no vale la pena el ~2 GB adicional de RAM ni el cambio de stack.

## Caveats

- **Code-switching es/en no tiene benchmark público** para Parakeet-TDT-0.6B-v3. La evidencia de que funcionará bien es estructural (tokenizer unificado, datos Granary multilingual) e indirecta. El usuario debe medir en su propio corpus antes de comprometerse.
- **La cifra de latencia 0.325 RTF en frase corta** viene de un único benchmark oficial (`en.wav` 3.845 s, 2 threads, sin VAD warm-up). Con `num_threads=4` y warm-up adecuado puede bajar a ~0.1–0.15 RTF; con 1 thread sube. Hay que medir en la máquina objetivo, no asumir.
- **El RAM de ~2 GB es por recognizer activo**. Si el usuario corre múltiples instancias (un proceso wake-word + un proceso comando, por ejemplo), se acumula. Compartir el modelo entre threads es viable pero requiere cuidado con la API offline (no streaming) que es la que tiene buena precisión.
- **sherpa-onnx en Windows necesita Visual Studio 2022 si se quiere compilar desde fuente**, pero los wheels precompilados de PyPI evitan eso. No usar MinGW (*"MinGW is known not to work with sherpa-onnx"*).
- **Bookbot es-zipformer emite fonemas IPA** — no es lo que el usuario pidió pero está listado como la única alternativa Spanish con biasing real en sherpa-onnx si Parakeet-v3 no entra en RAM. Es un compromiso significativo del contrato funcional.
- **Datos de entrenamiento de Parakeet-v3 son europeos (Granary)** — sesgo hacia castellano de España. Para un hablante latinoamericano con muchos nombres de apps/juegos en inglés, esto añade un riesgo extra al code-switching ya no validado.
- **El issue #3267 fue presentado por un AI coding agent en nombre de un desarrollador** según la propia descripción — coincide con el contexto del usuario que reporta haber verificado v1.12.x. La pregunta de raíz ya está siendo trabajada upstream. El fix existe y está en v1.13.1; usarlo.