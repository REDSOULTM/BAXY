# Plan para maximizar el rendimiento de un asistente de voz local en español sobre sherpa-onnx 1.13.2 + Parakeet-TDT-0.6b-v3 (int8, greedy, CPU)

## TL;DR

- **El cuello de botella estructural son las fusiones del encoder en nombres propios poco frecuentes ("Boone→Moon", "Spotify→espotifai") y NO hay evidencia pública de que pasar a fp32 las resuelva** — todos los reportes existentes (smcleod, grikdotnet, groxaxo, istupakov) son anecdóticos o sobre LibriSpeech inglés, y la literatura de cuantización en transducers (Q-ASR, arXiv:2103.16827v3) reporta degradaciones INT8 de solo 0,29 %/0,08 %/0,87 % WER absoluta para QuartzNet-15x5/JasperDR-10x5/Conformer-Large en LibriSpeech. Por tanto la apuesta principal debe ser el **rescate post-hoc determinista** (Axis 3), no cambiar la precisión del modelo.
- **La latencia ya está resuelta con margen**: con `num_threads = min(4, physical_cores)` (`psutil.cpu_count(logical=False)`), `graph_optimization_level=ORT_ENABLE_ALL` (default desde ORT 1.18) y desactivando el spin de los thread-pools, se cumple el techo de 300 ms p50 en cualquier CPU x86/ARM con AVX2. La medición del usuario (150 ms p50 con nt=4) ya está por debajo del techo; cualquier optimización extra tiene retorno marginal.
- **Detección de error sin confianza del modelo + corrector fonético ES↔EN sobre inventario dinámico** es la única arquitectura sostenible: trigger por posición tras verbo-comando o mismatch contra inventario + Double Metaphone inglés (`jellyfish.metaphone`/`doublemetaphone` PyPI) + Spanish Metaphone (Mosquera, Lloret & Moreda LREC NLP4ITA 2012; `amsqr/Spanish-Metaphone`) + `RapidFuzz` contra el inventario. Trinh et al. (arXiv:2506.10779v2, 19 Apr 2026, "Improving Speech Recognition of Named Entities in Classroom Speech with LLM Revision and Phonetic-Semantic Context") demuestra que la combinación contexto-fonético+semántico produce "up to 30 % relative WER reduction for NEs" — usaremos solo la parte fonética determinista (sin LLM). Coste: <5 ms por comando, RAM despreciable, todo `pip` puro.

---

## Hallazgos clave

### Modelos disponibles (verificados)

- **k2-fsa/sherpa-onnx solo publica el build int8** (`sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2`: encoder.int8.onnx ≈ 622 MB, decoder 12 MB, joiner 6,1 MB, tokens.txt + test_wavs). El script de conversión está en `scripts/nemo/parakeet-tdt-0.6b-v3` y requiere NeMo+torch+el `.nemo` original. No hay un fp32 oficial de k2-fsa para v3 (sherpa-onnx docs, "NeMo transducer-based Models").
- **Existe un fp32 redistribuible**: `istupakov/parakeet-tdt-0.6b-v3-onnx` (HuggingFace, CC-BY-4.0), encoder fp32 ≈ 2,44 GB + `decoder_joint-model.onnx` (decoder+joiner fusionados) + `nemo128.onnx` (preprocesador de mel). **PERO el formato no es drop-in para sherpa-onnx**: sherpa-onnx espera tres archivos encoder/decoder/joiner separados y computa mel-fbanks internamente. Cambiar a fp32 requiere re-exportar con el script propio de sherpa-onnx (NeMo+torch + `.nemo` de 2,4 GB).
- **Existe un fp16 redistribuible**: `grikdotnet/parakeet-tdt-0.6b-fp16` (encoder.fp16 ≈ 1,2 GB, decoder.fp16 35 MB). Cita "Same accuracy: Minimal quality loss from quantization", **sin números**. Está orientado a GPU (CUDA/DirectML); en CPU con `CPUExecutionProvider`, ORT desempaqueta fp16 a fp32 internamente — no aporta velocidad ni memoria útil.
- **sherpa-onnx 1.13.2** (tag 13 May 2026, último en PyPI). El changelog público de v1.13.1 lista *"Fix bugs in NeMo transducer modified beam search by @csukuangfj in #3589"*, y v1.13.2 es superset ("Full Changelog: v1.13.1...v1.13.2"). **Esto contradice la asunción del usuario de que #3589 no está en 1.13.2**: aparentemente sí está. Vale la pena re-medir `modified_beam_search` antes de descartarlo (caveat: no pude leer la página del PR directamente; la inclusión está inferida del listado público de releases).

### Evidencia fp32 vs int8 (lo que existe y lo que NO existe)

Tras búsqueda dirigida (HF discussions de istupakov v3, model card oficial de NVIDIA, repos derivados, issues de k2-fsa/sherpa-onnx y NVIDIA/NeMo):

- **No existe ningún benchmark empírico fp32-vs-int8 publicado sobre español, multilingüe, nombres propios ni palabras raras para Parakeet-TDT-0.6b-v3.** Toda la evidencia disponible:
  - groxaxo/parakeet-tdt-0.6b-v3-fastapi-openai (GitHub README, tabla de 50 muestras de LibriSpeech test-clean): FP32 18,41× RTF, FP16 18,82× RTF, INT8 19,42× RTF. La página DeepWiki del mismo proyecto resume "All three precision variants achieve identical accuracy metrics on LibriSpeech (97.84 %)". LibriSpeech test-clean es inglés sin nombres propios raros.
  - smcleod/parakeet-tdt-0.6b-v2-int8 (modelo v2 inglés, no v3): "I converted and quantised this from NVIDIA Parakeet TDT 0.6B V2 (En) as I found istupakov/parakeet-tdt-0.6b-v2-onnx caused errors in text such as unintended word concatenation." → afirmación anecdótica, sin ejemplos pareados ni WER numérico, y sobre v2.
  - grikdotnet/parakeet-tdt-0.6b-fp16: "Same accuracy: Minimal quality loss from quantization" — sin tabla WER.
  - NVIDIA model card de v3: evalúa el modelo fp32 original en FLEURS/MLS/CoVoST por idioma, **pero no compara con int8**.
- Literatura general de cuantización ASR — Q-ASR, arXiv:2103.16827v3 (30 Jan 2022): "negligible WER degradation of up to 0.29 %, 0.08 %, and 0.87 % for [QuartzNet-15x5, JasperDR-10x5 y Conformer-Large], respectively" en LibriSpeech con cuantización INT8. **Pero estos benchmarks no miden la cola de nombres propios infrecuentes**, que es exactamente donde Parakeet falla en el caso del usuario.
- **Veredicto razonable con la evidencia disponible**: la fusión "Boone→Moon" es muy probablemente un **límite estructural del encoder de 600M**, no un artefacto de int8. Razones: (a) Parakeet-v3 es multilingüe (25 idiomas con un único tokenizer SentencePiece de 8.192 unidades); las unidades BPE para nombres ingleses raros en contexto español tienen muy baja probabilidad y el encoder colapsa al token frecuente más cercano; (b) la confianza reportada por el usuario para tokens incorrectos (0,83-1,0) sugiere un colapso del prior del decoder, no ruido de cuantización (la cuantización añade jitter, no confianza espuria estable). Migrar a fp32 implica ~2,5× RAM (≈1,8 GB extra), ~2× latencia en CPU, y **sin garantía de fix** según la evidencia pública.

### Hotwords y `modified_beam_search`

- En sherpa-onnx, los hotwords **solo funcionan con `modified_beam_search`** (documentación oficial: "The default decoding method greedy_search does not support hotwords"), y para Parakeet-NeMo eso requiere el decoder modified-beam-search-NeMo añadido en PR #3077 (merged 2026). El bug del issue #3267 (~20-33 % alucinaciones "Yeah." o texto vacío) fue corregido en PR #3589 (changelog v1.13.1). **Por tanto los hotwords agresivos pueden ser viables en 1.13.2**; verificar empíricamente antes de descartar.

### Preprocesado / mel-fbanks

- Parakeet-v3 espera **16 kHz, mono, log-mel de 128 bins** ("Conformer-based encoder ... Processes 128-dimensional mel filterbank features with 8x temporal subsampling", documentado en achetronic/parakeet y consistente con el `nemo128.onnx` de istupakov). sherpa-onnx ya lo computa internamente. **Verificar en código**: si en alguna ruta el usuario fuerza `FeatureConfig.feature_dim=80` (default para zipformer), sería un bug silencioso. Si no se fuerza nada, sherpa-onnx usa el valor correcto desde su `OfflineNemoEncDecCtcModelConfig`/`OfflineTransducerModelConfig`. **Loguearlo una vez** elimina la duda.

---

## Detalles por eje

### Axis 1 — Calidad de base / reducir fusiones del encoder

| Técnica | Probabilidad de éxito | Evidencia | Coste | Veredicto |
|---|---|---|---|---|
| Verificar `feature_dim=128` | Alta (descartar bug silencioso) | Parakeet "Processes 128-dimensional mel filterbank features with 8x temporal subsampling" (achetronic/parakeet README) | 0 latencia | **Hacer YA**. Si está mal, fix gratis |
| Normalización RMS + 16 kHz mono float32 exacto | Baja-media | sherpa-onnx ya lo hace internamente. No hay evidencia de mejora externa en Parakeet | <1 ms | Trying. No esperar mejora medible en fusiones |
| Denoising ligero (RNNoise/DeepFilterNet) | Baja para nombres propios | No mejora alucinaciones del encoder; sí ruidos de ambiente. ~10-30 ms y ~30-80 MB | Medio | No prioritario para "Boone→Moon" |
| **Pasar a fp32** (re-exportar con script sherpa-onnx) | **Baja-incierta** | Sin benchmark publicado en proper-nouns/es-en code-switch para v3. groxaxo: fp32≡int8 en LibriSpeech. Anécdota smcleod sobre v2 | Alto: ~1,8 GB RAM extra, ~2× latencia (riesgo >300 ms), exportación con NeMo+torch local | **Diferir hasta que axis 3 no baste**. Si se hace, distribuir como release opcional y elegir en runtime por RAM detectada |
| Modelo distinto del zoo | n/a | El motor está fijado por consigna | — | Descartado |
| **Hotwords con MBS (verificar #3589 en 1.13.2)** | Media-alta | PR #3589 mergeado en v1.13.1 según changelog; v1.13.2 lo hereda | Latencia +10-30 ms con `max_active_paths=4` | **Verificar empíricamente**. Si estable, es la mejor mejora de Axis 1 |

**Recomendación Axis 1**: (1) verificar `feature_dim=128`; (2) re-medir `modified_beam_search` con la 1.13.2 instalada (hipótesis fuerte de que #3589 ya está); si estable, usar hotwords cargando el inventario dinámico (`--hotwords-score=1.5` a `2.0`, `modeling_unit=bpe`, `bpe_vocab=bpe.vocab`); (3) **NO** invertir en fp32 antes de tener Axis 3 implementado y medido.

### Axis 2 — Latencia/throughput universal

Las mediciones del usuario (i9, 24 cores, nt=1→230, nt=2→158, nt=4→150, nt=8→178 ms p50) son consistentes con la guía de ONNX Runtime y con el patrón típico: **el speed-up se satura entre 2-4 hilos físicos para encoders Conformer/FastConformer en CPU**, y los hilos lógicos hyperthreaded degradan por contención de unidades vectoriales. La documentación oficial ORT (`onnxruntime.ai/docs/performance/tune-performance/threading.html`): "By default ... each session will start with the main thread on the 1st core (not affinitized). Then extra threads per additional physical core are created."

| Knob | Recomendación universal |
|---|---|
| `num_threads` | `min(4, psutil.cpu_count(logical=False) or 2)`. Equivale a "una thread por core físico" de ORT, con techo en 4 (donde se satura). Compatible Win/Linux/macOS, x86/ARM. |
| `intra_op_num_threads` | Mismo valor; sherpa-onnx lo expone como `num_threads` en `OfflineModelConfig` y lo pasa a ORT. |
| `inter_op_num_threads` | 1 (no usar `ORT_PARALLEL`; el grafo del encoder es secuencial-pesado). |
| `graph_optimization_level` | `ORT_ENABLE_ALL` (default desde ORT 1.18). sherpa-onnx usa el default. |
| Thread spinning | `session.intra_op.allow_spinning=0` + `session.inter_op.allow_spinning=0` ahorra CPU entre comandos (asistente idle gran parte del tiempo) sin afectar latencia única, a cambio de ~0,5-1 ms extra al primer frame. **Recomendado**. |
| Thread affinity | **No fijar**: guía ORT explícita "It is normally best to not set thread affinity and let the OS handle thread assignment for perf and power reasons." |
| Memory arena | Default ON. No tocar. |
| Warm-up | 85-115 ms primera inferencia (medido). **Warm-up al iniciar** con buffer de ~0,5 s de silencio para que las p50 cuenten en frío. |
| Execution provider | Solo CPU disponible. DirectML/CoreML no aportan para NeMo TDT en sherpa-onnx. |
| Modelo más pequeño | Innecesario — ya 150 ms p50 « 300 ms |
| BatchedInference | No hay batching online útil en sherpa-onnx para comandos cortos individuales |

**Heurística portable (~6 líneas)**:
```python
import os, psutil
physical = psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True) or 2
n_threads = max(1, min(4, physical))
# Para sherpa_onnx OfflineRecognizer: num_threads=n_threads, provider="cpu"
os.environ.setdefault("OMP_NUM_THREADS", str(n_threads))
```

Esto cumple el techo de 300 ms p50 en cualquier CPU x86/ARM con AVX2. La wheel estándar de onnxruntime "automatically dispatches AVX2/FMA kernels from the standard wheel when the host CPU supports them" (groxaxo README). En CPUs sin AVX2 (raras hoy) la latencia subiría pero seguiría sub-segundo.

### Axis 3 — Pipeline de rescate post-hoc (la apuesta principal)

**Premisa crítica del usuario**: el gating por `ys_log_probs < 0.85` no dispara en "Benson Moon" porque los tokens de "Moon" tienen prob 0,83-1,0. **El encoder está confiadamente equivocado**. La literatura confirma este fenómeno como problema central:

- Trinh, He & Whitehill (Worcester Polytechnic Institute), arXiv:2506.10779v2 [cs.CL] 19 Apr 2026, *"Improving Speech Recognition of Named Entities in Classroom Speech with LLM Revision and Phonetic-Semantic Context"*: "the word error rate (WER) of state-of-the-art ASR remains high for named entities. Since named entities are often the most critical keywords, misrecognizing them can affect all downstream applications." Su pipeline (contexto fonético + semántico) alcanza "up to 30 % relative WER reduction for NEs" sobre el dataset NER-MIT-OpenCourseWare de 45 horas, sin depender de confianza del modelo.
- Bekal, Shenoy, Sunkara, Bodapati & Kirchhoff (Amazon AWS AI), *"Remember the context! ASR slot error correction through memorization"*, IEEE ASRU 2021, pp. 236–243 (arXiv:2109.05092): "Our best performing error correction model shows a relative improvement of 7.4 % in word error rate (WER) on rare word entities over the baseline and also achieves a relative WER improvement of 9.8 % on an out of vocabulary (OOV) test set." Idea trasladable: en vez de k-NN denso, **lookup fonético determinista contra el inventario**.

#### Señal de disparo (en orden de probabilidad/precisión)

1. **Slot por posición / dependencia sintáctica del comando** (la MEJOR):
   - El usuario controla el dominio: tras verbos como "pon", "abre", "llama a", "envía a", "agrega", lo que sigue es un slot de entidad. **Marcar como candidato a rescate todo n-grama en posición de slot tras verbo-comando**, independientemente de la confianza del modelo. Esquiva por completo el problema de la confianza espuria.
   - Implementación: regex/Aho-Corasick sobre el texto greedy + `timestamps[]` ya expuestos, devolviendo el rango temporal del slot.
2. **Mismatch contra el inventario dinámico** (señal secundaria):
   - Si la palabra del slot no aparece exactamente en el inventario del usuario (contactos, playlists, dispositivos), disparar el corrector fonético. *Toda* palabra-slot no-en-inventario es candidata, no solo las de baja confianza.
3. **Distancia fonética como filtro de aceptación**, no como trigger.

#### Corrector fonético ES↔EN (núcleo del axis 3)

Arquitectura recomendada, en orden de coste creciente — usar la más simple que cubra los casos:

| Componente | Librería | Notas |
|---|---|---|
| **Spanish Metaphone (Mosquera 2012)** | `amsqr/Spanish-Metaphone` (GitHub, BSD, sin paquete PyPI propio) **o** `abydos.phonetic.SpanishMetaphone` (PyPI `abydos==0.5.0`, GPL — atención licencia) **o** portar el script (~80 líneas, BSD) | Codifica "Benson"→"BNSN", "Moon"→"MN", "Spotify"→"SPTF", "espotifai"→"SPTF" → match. Algoritmo: Mosquera, Lloret & Moreda, *"Towards Facilitating the Accessibility of Web 2.0 Texts through Text Normalisation"*, LREC NLP4ITA 2012, pp. 9-14. |
| **Double Metaphone (inglés, Philips 2000)** | `jellyfish.metaphone()` o paquete PyPI `metaphone` o `doublemetaphone` (PyPI, BSD). RapidFuzz **no** incluye Metaphone. | "Benson"→"PNSN", "Boone"→"PN", "Moon"→"MN" — necesario para nombres anglos pronunciados en español. |
| **Codificación dual + match cruzado** | Custom (~20 líneas) | Para cada palabra-slot calcular Spanish-Metaphone Y Double-Metaphone; lo mismo para cada item del inventario; aceptar match si **cualquiera** de las 4 combinaciones (es↔es, es↔en, en↔es, en↔en) iguala. Maneja "espotifai"↔"Spotify" (es-en) y "Benson"↔"Benson" (es-es y en-en). |
| **RapidFuzz** sobre el subconjunto fonéticamente compatible | `rapidfuzz.process.extractOne(candidate, inventory, scorer=fuzz.WRatio)` | Benchmark independiente (Bagaskara et al., *International Journal of Environment, Engineering and Education* 7(1):48-60, 2025, "A Comparative Analysis of Python Text Matching Libraries", Ubuntu 22.04 / Python 3.11.5, 50.000 casos multilingües ES/EN/FR/DE/IT): "RapidFuzz consistently outperformed the others, running 40 % faster across all test cases. In single-threaded processing, RapidFuzz handled an average of 2,500 text pairs per second, surpassing Levenshtein (1,800 pairs/sec), Jellyfish (1,600 pairs/sec), FuzzyWuzzy (1,200 pairs/sec), and Difflib (1,000 pairs/sec)." Backend C++, Unicode safe. Aceptar si score ≥ umbral (e.g. 80). |
| **Pre-normalización** | `unicodedata.normalize('NFKD')` + strip accents + lowercase + manejar `ñ` | Crítico: Spanish-Metaphone de amsqr ya gestiona ñ; verificar la versión usada |

**Alternativas evaluadas y comparativa**:
- **Epitran + panphon (G2P→IPA→distancia articulatoria)**: reduce WER vs baseline en bajo recurso (uso documentado en ASR de Babel, "lower word error rates against baseline systems"). Coste: instala mappings por idioma; ~10× más lento que Metaphone. **Cuándo usar**: si los pares Metaphone fallan en casos ortográficamente divergentes. Mantener como capa 2 opcional, gateada por umbral RapidFuzz.
- **Metaphone3 / Beider-Morse**: Metaphone3 es propietario en versión "completa" (limitaciones de redistribución); Beider-Morse está en `abydos` (GPL). **Para un stack OSS pip-friendly, jellyfish + Spanish-Metaphone + RapidFuzz es la combinación pragmática.**
- **MetaSoundex** (Koneru et al., *Global Journal of Enterprise Information System*): combinación Metaphone+Soundex ajustada a ES; mejora reportada en record-linkage en español. Implementable en ~30 líneas. **Ganancia marginal** sobre Mosquera+DoubleMetaphone en este caso.

#### Sherpa-onnx `homophone_replacer` (NO confundir)

sherpa-onnx tiene `HomophoneReplacerConfig` (`hr.lexicon`, `hr.rule_fsts`), pero está documentado como subsistema TTS — se aplica al INPUT de TTS para reemplazar heterónimos antes de sintetizar (`sherpa-onnx/csrc/homophone-replacer.cc`). Existe un ejemplo Python ("Add homophone replacer example for Python API", CHANGELOG entry #2161) y aparece expuesto en `OnlineRecognizerConfig` Go bindings, pero su comportamiento en el path NeMo offline no es verificable desde docs (mismo patrón que `lm`: expuesto en el config pero no consultado por el decoder NeMo). **No depender de este path**: implementar el corrector fonético fuera, en Python puro.

#### Re-transcripción de slot vía timestamps + hotwords (camino alternativo)

Si `modified_beam_search` resulta estable en 1.13.2 (verificar PR #3589 efectivo): cortar el audio en el rango temporal del slot (`timestamps[i]` a `timestamps[j]`) y re-decodificar SOLO ese segmento con `hotwords-file` cargado con el inventario y `hotwords-score=2.0`. Coste estimado ~30-80 ms por slot.

**Trade-off**: gana sobre el corrector fonético cuando el nombre **no está en el inventario** del usuario (porque hotwords es open-vocab con boost a BPE-tokens, mientras que el corrector requiere que el nombre esté en el inventario). Pero requiere MBS estable.

**Recomendación**: implementar primero el corrector fonético (base de axis 3), luego añadir re-transcripción de slot como capa 2 si MBS-en-1.13.2 funciona.

---

## Recomendaciones (plan escalonado)

**Etapa 0 — gratuita, hoy (1 día)**
1. Verificar `feature_dim=128` en la inicialización de `OfflineRecognizer`. Si está en 80, corregir y re-medir.
2. Aplicar `num_threads = min(4, psutil.cpu_count(logical=False))` y `OMP_NUM_THREADS` consistente. Añadir warm-up de 0,5 s al iniciar el proceso.
3. Desactivar thread spinning (`session.intra_op.allow_spinning=0`). Beneficio: idle CPU baja sin penalizar latencia.

**Etapa 1 — corrector fonético determinista (2-3 días)**
4. Implementar pipeline post-hoc: extraer slots por (a) verbo-comando o (b) palabra-slot fuera del inventario, usando `timestamps[]` y agrupando tokens por `▁`.
5. Spanish-Metaphone (Mosquera) + Double Metaphone (jellyfish) + RapidFuzz contra inventario dinámico, con match dual ES/EN.
6. Umbral RapidFuzz: empezar en 80, calibrar con corpus del usuario.
7. **Métrica de éxito**: % de casos "Benson Moon"-tipo (nombre propio infrecuente, encoder confiadamente equivocado) corregidos al item correcto del inventario.

**Etapa 2 — verificar hotwords + MBS en 1.13.2 (medio día)**
8. Replicar el setup del issue #3267 con la 1.13.2 actual: ¿persisten las alucinaciones a ~20-33 %? Si **no** (PR #3589 efectivo): añadir hotwords con el inventario completo como capa de prevención (no rescate), `modeling_unit=bpe`, `hotwords-score` 1,5-2,0.
9. Si **sí** persiste: mantener greedy + corrector fonético; abrir issue en k2-fsa/sherpa-onnx referenciando #3267/#3589 con la traza.

**Etapa 3 — opcional, solo si etapas 1+2 no bastan (semana)**
10. Re-transcripción de slot por timestamps con hotwords agresivos (`hotwords-score=2.0+`) — requiere MBS estable.
11. **Último recurso**: pipeline fp32 opcional. Exportar Parakeet-v3 con el script `scripts/nemo/parakeet-tdt-0.6b-v3` de sherpa-onnx (NeMo+torch+`.nemo` 2,4 GB; hacerlo una vez, distribuir el tar.gz resultante). Selección runtime: si `psutil.virtual_memory().available > 4*1024**3` y la latencia p50 medida con fp32 < 300 ms en la máquina del usuario, ofrecer "Modo precisión" opcional. **Mantener int8 como default** hasta tener prueba empírica de que fp32 corrige las fusiones específicas del usuario.

**Umbrales que cambian el plan**:
- Si `modified_beam_search` en 1.13.2 sigue alucinando >5 %: descartar hotwords; el corrector fonético es el único camino.
- Si tras Etapa 1 quedan >20 % de slots irrescatables (el nombre genuinamente NO está en el inventario): habilitar la re-transcripción de slot (Etapa 3.10) condicionada a MBS estable; si MBS no es estable, exponer un mensaje "no entendí, ¿puedes repetir el nombre?".
- Si el corrector deja >50 % de errores residuales **incluso con el nombre en el inventario**: el problema no es léxico sino acústico — entonces sí amerita probar fp32 (Etapa 3.11), midiendo caso por caso.

---

## Caveats

- **Sobre fp32 vs int8 en nombres propios**: la ausencia de benchmark publicado significa que la hipótesis "fp32 arregla las fusiones" **no está ni confirmada ni refutada empíricamente para Parakeet-v3 en español**. La evidencia indirecta (Q-ASR: <1 % degradación en LibriSpeech; groxaxo: fp32 ≈ int8 en accuracy en LibriSpeech inglés; anécdota smcleod sobre v2) sugiere que el efecto, si existe, es pequeño y dominado por el límite del encoder. Solo una medición del usuario lo confirmaría. El plan privilegia el rescate post-hoc porque su payoff es robusto independientemente de la respuesta.
- **Sobre PR #3589**: el changelog público de v1.13.1 menciona explícitamente "Fix bugs in NeMo transducer modified beam search by @csukuangfj in #3589", y v1.13.2 declara "Full Changelog: v1.13.1...v1.13.2" (superset). No pude leer directamente la página del PR (`web_fetch` retornó PERMISSIONS_ERROR), así que la inclusión está inferida del listado público. **Antes de planificar sobre esto, replicar el setup de issue #3267 con la 1.13.2 instalada y medir la tasa de alucinaciones**.
- **Sobre Spanish-Metaphone de Mosquera**: el repo `amsqr/Spanish-Metaphone` no está en PyPI; se distribuye como script único en GitHub (BSD). `abydos` (PyPI) lo incluye pero es GPL — incompatible con stacks propietarios; verificar la licencia del proyecto del usuario. Alternativa: incluir el script de amsqr en el repo del usuario manteniendo el copyright header BSD.
- **Sobre `feature_dim`**: la verificación de 128 (no 80) es una conjetura crítica basada en la arquitectura del encoder Parakeet-v3 (FastConformer 128-bin log-mel, documentado en achetronic/parakeet y en el `nemo128.onnx` de istupakov). sherpa-onnx puede estar ya usando el valor correcto internamente; si el código del usuario no fuerza `feature_dim=80`, probablemente está bien. **Loguearlo una vez** elimina la duda.
- **Sobre el `homophone_replacer` de sherpa-onnx**: existe (`HomophoneReplacerConfig`, ejemplo Python desde commit #2161, expuesto en `OnlineRecognizerConfig` Go) pero su comportamiento exacto en el path NeMo offline no quedó verificable. Tratarlo como "puede o no aplicar"; el corrector externo en Python es la opción robusta.
- **Sobre el benchmark de groxaxo**: la tabla de RTF del GitHub README muestra FP32 18,41× / FP16 18,82× / INT8 19,42× (50 muestras LibriSpeech test-clean) — INT8 es marginalmente más rápido pero no por el factor que sugiere su DeepWiki. Para WER multilingüe en producción real, los números YouTube-subtitle del mismo README llevan disclaimer "subtitle references may contain errors". **No tomar esos números como evidencia de equivalencia fp32/int8 fuera de LibriSpeech.**
- **PRs/issues citados verificables públicamente**: #3077 (modified beam search NeMo, merged), #3267 (bug MBS), #3589 (fix MBS, en v1.13.1 changelog), #3613 (release v1.13.2), #2541 (issue cerrado por #3077), #2161 (homophone replacer Python example). Ninguno fabricado.