# Research Prompt — Maximizing Local Speech-to-Text Accuracy (Whisper-small, CPU, Spanglish voice assistant)

> Copia este documento completo y pégalo en Claude / ChatGPT / Gemini con la
> instrucción: *"Actúa como un experto en ASR de producción. Lee el sistema
> descrito y respondé las preguntas del final con fuentes (papers, docs
> oficiales, benchmarks, repos). Distinguí lo verificado de lo especulativo."*

---

## 1. Contexto del producto

Asistente de voz **100% local** para Windows (laptop modesto). Restricciones de
producto NO negociables:

- **Todo open-source y gratis.** Sin Picovoice, sin APIs de pago, sin cloud.
- **Multi-usuario / multi-idioma / multi-acento.** No optimizar sobre una sola
  voz; debe funcionar para cualquier hablante. El idioma matriz por defecto es
  **español**, pero el sistema debe soportar inglés/portugués/otros por config.
- **Code-switching obligado ("Spanglish").** Los usuarios hablan español pero
  los nombres de apps/servicios son en inglés: *"abre **Spotify**", "pon
  **Daredevil** en **Disney+**", "abre **Counter-Strike** en **Steam**"*. Estos
  nombres propios en inglés DEBEN transcribirse bien.
- **Presupuesto de cómputo:** la GPU (6 GB) está 100% ocupada por un LLM local.
  **El STT corre en CPU.** Hardware target: laptop típico, 4-8 cores x86.
- **Latencia tier-Alexa.** Presupuesto por turno de voz completo (wake→STT→LLM→
  TTS) 4–5 s tope. El STT debe ser una fracción chica (idealmente <300-500 ms
  para clips de comando de ~2 s). 8 s es UX catastrófica.

## 2. Pipeline de voz actual (verificado en código)

```
mic (sounddevice, 16 kHz, int16, mono, chunks de 512 samples = 32 ms)
  → ring buffer (5 s)
  → Silero VAD v5 (ONNX, 512 samples/frame obligatorio) — gate anti-ruido
  → Wake word: LiveKit WakeWord "hey gemma" (ONNX, conv-attention,
        ventana 2 s, threshold 0.25; recall universal medido 0.83
        sobre 25 voces × 13 idiomas, fp/hr ~0)
  → State machine: IDLE → CAPTURE → TRANSCRIBE → COOLDOWN
        - PREROLL 0.5 s (audio antes del wake)
        - END_OF_SPEECH_SILENCE 1.4 s (silencio para cerrar captura)
        - MIN_CAPTURE 1.0 s, COMMAND_TIMEOUT 8 s
  → Silence gate (anti-alucinación): peak-window RMS (ventana 0.20 s) debe
        superar 350 (ref int16: sala ~50-250, habla ~800-4000), sino se
        descarta sin transcribir
  → STT: faster-whisper (CTranslate2), modelo "small", CPU, int8, 4 threads
  → Post-corrector: RapidFuzz contra inventario de dominio (apps/artistas/
        canciones/verbos), threshold 65, n-gramas 1-3
  → Filtro de alucinación post-STT: si el texto transcrito ES exactamente un
        artefacto conocido de Whisper-en-silencio ("¡Suscríbete!", "Gracias por
        ver el video", "subtítulos por la comunidad de Amara.org", "you", etc.)
        se descarta
```

### Config exacta de decoding de Whisper (faster-whisper)

```python
DECODE_KWARGS = dict(
    language="es",              # FIJO (no autodetect). Por idioma vía perfiles.
    task="transcribe",
    beam_size=1,                # greedy, por latencia
    best_of=1,
    temperature=0.0,            # determinista, SIN temperature fallback
    condition_on_previous_text=False,  # comandos independientes
    vad_filter=False,           # hacemos VAD propio aguas arriba (Silero)
    without_timestamps=True,
)
# initial_prompt dinámico, por idioma. Para 'es' (Spanglish):
#   "Conversación con el asistente Gemma en español rioplatense con nombres de
#    aplicaciones y canciones en inglés. Hey Gemma, abre Chrome. Hey Gemma, open
#    Chrome. Hey Gemma, abre Spotify. Hey Gemma, open Spotify. Apps: Chrome,
#    Firefox, ... Artistas: ... Canciones: ... Comandos breves en español con
#    nombres de apps en inglés, dirigidos al asistente Gemma."
#   (cap ~880 chars / <224 tokens; seed bilingüe ES+EN deliberado)
```

### Modelos en disco
- faster-whisper-small (~480 MB) y faster-whisper-base (descargados).
- Whisper-small: ~900 MB RAM en inferencia int8.

## 3. Restricciones que ya descartamos (con razón)

- **Subir a Whisper medium/large/large-v3-turbo:** DESCARTADO por latencia.
  Whisper-small es el techo del runtime productivo.
- **Fine-tuning de Whisper** (B-Whisper para rare-words, Calm-Whisper para
  alucinación): fuera de alcance por ahora (requiere datos + GPU + pipeline de
  entrenamiento). PERO nos interesa saber si hay un camino *barato* de FT.

## 4. Lo que YA medimos (no repetir, salvo que tengas un método mejor)

Banco de prueba: una grabación real de ~4.9 min con ~105 comandos Spanglish del
operador, transcrita con **faster-whisper large-v3** como referencia (ground
truth aproximado — OJO: el audio tiene eco y en algunos clips hasta large-v3
falla). Alineación correcta = **wake-anchored** (anclar cada comando al
timestamp del wake-word). La alineación por segmentos de timestamps de large-v3
da WER inflado por desalineación — NO usar.

Resultados medidos (config actual = "baseline"):

| Cambio probado | WER (wake-anchored, n=6) | Latencia media | Veredicto |
|---|---|---|---|
| baseline (beam=1, temp=0, sin thresholds) | **0.608** | **1585 ms** | mejor |
| beam_size=5 | 0.625 (peor) | 2048 ms (+30%) | descartado |
| beam5 + log_prob/compression/no_speech thresholds | 0.625 | 2049 ms | sin efecto |
| beam5 + temperature fallback [0,0.2,0.4] | 0.625 | 2049 ms | sin efecto |
| initial_prompt "enriquecido" (más nombres/ejemplos) | PEOR que original | — | revertido |

Hallazgos clave de literatura que ya encontramos:
- Cargar el `initial_prompt` con más nombres mejora las palabras del prompt
  pero **degrada las palabras comunes** (U-WER sube) — trade-off documentado
  (arxiv 2502.11572). Explica por qué nuestro prompt "mejorado" empeoró.
- Calm-Whisper (arxiv 2505.12969): -80% alucinación pero SOLO con fine-tuning
  de 3 "crazy heads".
- Para code-switching, fijar el idioma matriz es correcto; autodetect flipea de
  idioma a mitad de frase y no vuelve (openai/whisper #2009).

NOTA sobre n=6: nuestro ground-truth bien-alineado es chico. Un método para
generar MÁS datos de evaluación bien-alineados y de bajo costo es de interés.

## 5. Síntomas concretos a resolver

1. **Anglicismos fonetizados** por Whisper-small con `language=es`:
   "Chrome"→"Aurekrom"/"cross", "abre Chrome"→"Howdy crumb", el wake "Gemma"→
   "Jema"/"Chileman"/"Ejema". El corrector fuzzy atrapa SOLO lo que matchea el
   inventario; nombres fuera de él pasan mal.
2. **Clips cortos (~2 s) con eco/ruido** transcriben mal o alucinan ("¿qué hora
   es?"→"kill it ace"). El silence-gate + filtro de alucinación atrapan los
   casos de silencio puro, no los de habla degradada.
3. **Verbos de comando mal oídos** ("pon"→"prende") cambian la intención.

## 6. Preguntas para la investigación (respondé con fuentes)

**A. Decoding / inferencia (sin cambiar de modelo, sin FT):**
1. ¿Hay parámetros de faster-whisper/CTranslate2 que mejoren rare-words/
   anglicismos en clips cortos sin costo de latencia inaceptable? (`hotwords`,
   `prefix`, `suppress_tokens`, `patience`, `length_penalty`,
   `repetition_penalty`, `word_timestamps`, `multilingual`, etc.) ¿Cuáles
   tienen evidencia real, no folclore?
2. ¿Conviene padear el clip corto a una longitud mínima (p.ej. 1-3 s de
   silencio) o eso EMPEORA (Whisper paddea a 30 s internamente)? ¿Evidencia?
3. ¿`hotwords` (faster-whisper) es mejor que `initial_prompt` para sesgar
   nombres propios SIN degradar palabras comunes? ¿Cómo se comparan?

**B. Pre-procesamiento de audio (CPU-friendly):**
4. ¿Denoising / AGC / normalización (RNNoise, DeepFilterNet, WebRTC NS, simple
   spectral subtraction) antes de Whisper mejora WER en clips con eco/ruido?
   ¿Cuál tiene mejor relación costo-CPU / ganancia? ¿Latencia añadida?
5. ¿Cancelación de eco acústico (AEC) software (WebRTC APM, SpeexDSP) ayuda
   dado que el TTS y el mic comparten el mismo dispositivo?

**C. Arquitecturas / modelos alternativos OSS y gratis (CPU, ≤ small en costo):**
6. ¿Hay modelos ASR OSS **más precisos que Whisper-small a igual o menor costo
   de CPU** para español + code-switching? Candidatos a evaluar: distil-whisper,
   whisper-small fine-tunes comunitarios (es), NVIDIA Parakeet/Canary (licencia?
   CPU?), Moonshine (diseñado para edge/short-form), Vosk, Kaldi, wav2vec2-es,
   SeamlessM4T, Faster-Distil-Whisper. Para cada uno: WER es vs Whisper-small,
   licencia, latencia CPU, RAM, soporte code-switching.
7. ¿Moonshine u otros modelos "short-form / streaming" baten a Whisper-small en
   comandos cortos en CPU? (Whisper paddea a 30 s — ineficiente para 2 s.)

**D. Corrección / post-procesamiento (donde ya tenemos un fuzzy corrector):**
8. Mejores prácticas para un post-corrector de entidades: ¿fonético
   (Metaphone/Soundex/Double-Metaphone para español) vs edit-distance
   (RapidFuzz)? ¿Cómo manejar anglicismos pronunciados con fonología española?
9. ¿Vale la pena un LLM chico (el que ya corre) para corrección/normalización
   del transcript con el inventario como contexto, sin inflar latencia?

**E. Fine-tuning barato (si lo anterior no alcanza):**
10. ¿Cuál es el camino MÁS BARATO de fine-tunear Whisper-small para
    code-switching es-en + nuestros nombres propios? (LoRA/PEFT, cuántos datos,
    cuántas GPU-horas, riesgo de degradar generalidad multi-usuario.) ¿Se puede
    sin destruir el uso universal?
11. ¿Generación de datos sintéticos de entrenamiento/eval con TTS (Piper) para
    comandos Spanglish es viable y representativo? ¿Trampas conocidas?

**F. Evaluación:**
12. ¿Cómo construir un set de evaluación bien-alineado, multi-voz, multi-idioma,
    de bajo costo, para comandos cortos? Métricas más allá de WER (entity-WER,
    intent accuracy, keyword recall). ¿Herramientas OSS?

## 7. Formato de respuesta deseado

Para cada recomendación: **(a)** qué cambiar concretamente, **(b)** ganancia
esperada con fuente/benchmark, **(c)** costo de latencia/CPU/RAM, **(d)** riesgo
para el uso universal (multi-voz/idioma), **(e)** esfuerzo de implementación.
Ordenar por ROI (mejor relación ganancia/costo/riesgo primero). Separar
**"evidencia sólida"** de **"vale la pena probar pero sin garantía"**. Citar
papers/repos/docs con links.
```
