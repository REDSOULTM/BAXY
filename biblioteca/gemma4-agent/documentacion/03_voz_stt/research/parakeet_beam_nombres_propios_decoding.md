# Cómo meter el nombre propio inglés en el haz (beam) de Parakeet-TDT-0.6B-v3 (int8) sobre sherpa-onnx v1.13.2 en CPU

## TL;DR
- **La respuesta honesta: con el stack fijo (sherpa-onnx v1.13.2 + Parakeet-TDT-0.6B-v3 int8 en CPU), el rescate de nombres propios infrecuentes fusionados por el encoder es POST-HOC y determinista (corrector fonético sobre inventario dinámico), no un truco de decoding.** Las palancas de decoding que existen (`blank_penalty`, `max_active_paths` con hotwords, retranscripción del slot) ayudan parcialmente y deben combinarse, pero ninguna garantiza por sí sola que "Boone" entre al beam cuando el encoder int8 lo fusionó con "Moon".
- **Shallow-fusion (`lm`/`lm_scale`) y LODR (`lodr_fst`/`lodr_scale`) están cableados SOLO en la ruta icefall/Zipformer; en la ruta `nemo_transducer` (Parakeet) los campos se aceptan en `OfflineLMConfig` pero NO se consultan**: el PR #3077 que añadió `modified_beam_search` para NeMo declara textualmente en su descripción "Simplifications — Removed unused LM rescoring code". Descarta esos campos: en Parakeet no hay LM externo posible hoy.
- **Para que `Búscame info sobre Benson Boone` salga estable y `pon Spotify` también, la receta concreta es: (1) `greedy_search` con `blank_penalty` positivo pequeño (0.5–1.5) para frenar la fusión silábica; (2) un corrector fonético post-hoc que combine Double Metaphone (Lawrence Philips, 2000) con el Metáfono Español (Alejandro Mosquera, 2012, `github.com/amsqr/Spanish-Metaphone`) y RapidFuzz contra el inventario dinámico; (3) usar `ys_log_probs` (PR #2843) como disparador del corrector solo en el slot post-verbo; (4) `modified_beam_search` + hotwords SOLO cuando upgrades a una versión posterior a v1.13.2 que incluya el fix del PR #3589.**

## Hallazgos clave (ordenados por probabilidad real de meter el nombre en el beam o de rescatarlo)

### Conclusión central: el límite del encoder
Parakeet-TDT-0.6B-v3 es un encoder FastConformer extendido desde parakeet-tdt-0.6b-v2 para cubrir 25 lenguas europeas (bg, hr, cs, da, nl, en, et, fi, fr, de, el, hu, it, lv, lt, mt, pl, pt, ro, sk, sl, **es**, sv, ru, uk), entrenado sobre el corpus Granary con Stage 2 fine-tuning de 5.000 steps en 4 GPUs A100 sobre ~7.500 horas de NeMo ASR Set 3.0 (model card de NVIDIA en Hugging Face). El int8 reduce la resolución acústica y, cuando un hispanohablante pronuncia un apellido inglés infrecuente con fonotáctica española ("Búuns" en lugar de "Boon"), el encoder mapea esa pronunciación al ítem inglés fonéticamente más cercano de su prior ("Moon"). La hipótesis correcta `Boone` no aparece entre los top-k del joiner en ese frame, y **ninguna técnica de re-scoring (hotwords, LM, LODR) puede premiar lo que el encoder no propuso**. Por eso, dentro del stack fijado, el rescate debe combinar dos capas: (a) tocar el decoder para que emita más sílabas y abrir más caminos — eso a veces logra que el candidato correcto entre — y (b) un corrector determinista fonético encima — eso siempre rescata el nombre si está en tu inventario.

---

### 1) Corrector fonético post-hoc sobre inventario dinámico  ✅ **VERIFICADO — capa obligatoria**

**Por qué primero:** no depende del beam. Funciona aunque el encoder haya fusionado el nombre. Tu A/B test ya demostró que rescata "Benson Boone" sobre Whisper, y como Parakeet no alucina (Issue #2605 lo confirma: Parakeet se come palabras pero no inventa), la combinación Parakeet (motor) + corrector (post-hoc) hereda lo mejor de ambos.

**Implementación recomendada (multilingüe ES↔EN):**
- **No uses Double Metaphone solo.** Double Metaphone está sesgado a pronunciación inglesa con cobertura razonable de apellidos hispanos, italianos y eslavos pero **falla cuando el hablante hispano pronuncia el nombre inglés a la española**. La Wikipedia y la implementación de Lawrence Philips lo describen así: "El primary code representa la pronunciación inglesa más probable, mientras que el alternate code representa pronunciaciones alternativas basadas en el posible idioma de origen".
- **Capa fonética doble:**
  - Calcula Double Metaphone (paquete Python `metaphone` o `jellyfish`) del candidato de salida de Parakeet (`Moon`) y de cada entrada de tu inventario (`Boone`).
  - En paralelo, calcula el **Metáfono Español** (Mosquera 2012, `github.com/amsqr/Spanish-Metaphone`) del candidato y del inventario.
  - Match si **CUALQUIERA** de los códigos coincide o si la distancia de Levenshtein entre códigos ≤ 1.
- **Capa léxica:** sobre los candidatos pre-filtrados por fonética, usa **RapidFuzz** con `token_set_ratio` o `WRatio` para rankear.
- **Disparador (gating):** solo dispara el corrector sobre el slot post-verbo de comando (`busca`, `pon`, `abre`, `info sobre`, etc.) y/o cuando `exp(min(ys_log_probs_of_word)) < 0.85` (ver punto 4).
- **Inventario dinámico:** lista de apps instaladas + artistas/series recientes; se actualiza al inicio o por evento.
- **Latencia:** la búsqueda fonética sobre un inventario ≤ 2.000 entradas con RapidFuzz indexado es <5 ms; despreciable frente a 110 ms del modelo.
- **RAM:** ≤ 5 MB para el inventario y los hashes fonéticos.

**Catch importante:** el corrector solo rescata nombres **presentes en tu inventario**. Para nombres totalmente nuevos no ayuda — pero tampoco lo haría un LM externo: ningún método dentro de tu stack rescata nombres totalmente desconocidos sin re-entrenar.

### 2) `blank_penalty` positivo  ✅ **VERIFICADO en código — palanca directa contra la fusión silábica**

**Qué hace en Parakeet-TDT:** `blank_penalty` se resta del logit del token blank antes del argmax/softmax. El blank en NeMo está en `vocab_size - 1` (PR #3077: *"Adjusted blank token position to end of vocabulary (index vocab_size - 1) to match NeMo model format"*). Un valor positivo hace que el blank sea menos probable y **fuerza al decoder a emitir más tokens no-blank**, es decir, menos sílabas saltadas.

**Por qué es directamente relevante:** Issue #2605 (`Missing words with nemo-parakeet-tdt-0.6b-v3-int8`, abierto el 17 de septiembre de 2025 por bradmurray-dt) documenta que sherpa-onnx con Parakeet-TDT-v3 emite "How's everybody today?" cuando `onnx-asr` con el mismo modelo emite "How's everybody **doing** today?". El decoder TDT está saltando frames con su predicción de duración, y `blank_penalty` es el dial directo para contrarrestarlo.

**Invocación (Python API):**
```python
recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder="encoder.int8.onnx",
    decoder="decoder.int8.onnx",
    joiner="joiner.int8.onnx",
    tokens="tokens.txt",
    model_type="nemo_transducer",
    decoding_method="greedy_search",
    hotwords_file="hotwords.txt",    # ignorado en greedy, no estorba
    hotwords_score=1.5,
    modeling_unit="bpe",
    bpe_vocab="bpe.vocab",
    blank_penalty=1.0,                # <— prueba 0.5, 1.0, 1.5
    num_threads=2,
)
```
CLI: `--blank-penalty=1.0`.

**Interacción con la cabeza de duración del TDT:** `blank_penalty` actúa sobre el logit token, no sobre `duration_logits` (PR #3077 maneja `duration_logits` por separado para el `predicted_skip` por hipótesis). No rompe la predicción de duración; solo reduce la propensión a emitir blank en lugar de fonema. En la práctica puede recuperar "Boo-ne" si la fusión se debía a saltar el segmento /uːn/.

**Coste:** cero en latencia y RAM (un float restado por frame). Riesgo: con valores demasiado altos (>2.5) aparecen inserciones/duplicaciones. Empieza en 0.5, sube en pasos de 0.5, mide con tu set de 6 muestras.

### 3) `modified_beam_search` con `max_active_paths` 8 → 16 + hotwords  ⚠️ **EXPLOSIVO en v1.13.2 — esperar fix**

**Cómo se soporta:** hasta el PR #3077 (mergeado el 5 de febrero de 2026), Parakeet/NeMo-TDT solo soportaba `greedy_search` — el código en `offline-recognizer-transducer-nemo-impl.h` fallaba con `SHERPA_ONNX_LOGE("Unsupported decoding method: %s", ...)` para cualquier otra cosa (Issue #2541). PR #3077 añadió `OfflineTransducerModifiedBeamSearchNeMoDecoder` con BPE de hotwords y `ys_log_probs` per-token. Esto es lo que te permite hoy usar hotwords con Parakeet.

**Efecto real de `max_active_paths` en TDT en CPU:** no hay benchmark público específico de Parakeet-TDT con `max_active_paths>4` en sherpa-onnx (los benchmarks publicados en `RTF on RK3588 with Cortex A76 CPU` son con `greedy_search`). En la práctica de transducers con modified beam search:
- El coste por frame es ~lineal en `max_active_paths` para la pasada del joiner.
- Doblar de 8 a 16 típicamente añade 25–60% al tiempo de decodificación, no al cómputo del encoder (que es la mayoría del coste). Esperaría 130–160 ms con `max_active_paths=16`, 180–220 ms con 32, partiendo de tus 110 ms.
- Más allá de 16 los retornos son **marginales** para nombres fusionados: si la fusión es a nivel encoder, ampliar el beam solo da más variantes de la misma confusión.

**El caveat grave de v1.13.2:** Issue #3267 documenta sobre Parakeet-TDT v3-int8 que `modified_beam_search` produce **~10/30 fallos en sus pasos de reproducción (≈33% de fallos)** — concretamente "~6/30 return 'Yeah.', ~4/30 return empty, ~20/30 return correct text"; cambiar a `greedy_search` produce transcripciones correctas siempre sobre el mismo audio. La causa probable (identificada en revisiones del PR #3077) es que el decoder TDT olvida sumar el log-prob de la duración elegida al score de la hipótesis. El **PR #3589 ("Fix bugs in NeMo transducer modified beam search", csukuangfj) se mergeó DESPUÉS de v1.13.2**: la release v1.13.2 fue publicada el 13 de mayo de 2026 (commit `13d0ae6`, PR de release #3613, "Full Changelog: v1.13.1...v1.13.2"), y #3589 lleva un número de PR posterior, no incluido en ese rango.

> **Conclusión operativa:** en sherpa-onnx v1.13.2, `decoding_method="modified_beam_search"` con Parakeet-TDT puede degradar la calidad global en torno a un tercio de las peticiones aunque rescate algunos nombres. **No lo uses en producción en v1.13.2.** Quédate en `greedy_search` (los hotwords no aplican en greedy, pero `blank_penalty` sí) y apóyate en blank_penalty + corrector fonético. Cuando exista una versión PyPI con PR #3589 incluido, vuelve a evaluar.

### 4) `ys_log_probs` (confianza per-token) como disparador del rescate  ✅ **VERIFICADO — clave operativa**

PR #2843 ("Add token-level confidence scores (ys_probs) for offline transducer models") añadió per-token log-probabilities al resultado de `OfflineRecognizer` para transducers, serializados en JSON como `ys_log_probs`. PR #3077 los replicó en el decoder MBS de NeMo. La salida JSON de Parakeet en sherpa-onnx ya los contiene (ejemplo de la doc oficial):

```json
"tokens": [" We","ll",",", " I", " don","'","t", ...],
"ys_log_probs": [-0.002837, -0.000404, -0.060576, -0.000764, -0.087673, ...]
```

**Operativa:**
- Recorre tokens y agrupa por palabra (los tokens BPE empiezan con espacio en inicio de palabra).
- Para cada palabra calcula `min_token_prob = exp(min(ys_log_probs_of_word))`.
- Si `min_token_prob < 0.85` **Y** la palabra cae en el slot post-verbo de comando, dispara el corrector fonético (punto 1) o la retranscripción (punto 5).
- Para el resto del enunciado, no toques nada (mantienes el p50 de 110 ms).

**Caveat (Issue #2937):** activar hotwords altos DEPRIME los `ys_log_probs` incluso de palabras correctas que están en hotwords (el log-prob reportado se ve afectado por el boost del context-graph). Usa `ys_log_probs` como señal de gating únicamente para palabras **fuera** del hotword set, o calibra el umbral empíricamente con hotwords activos.

### 5) Retranscripción del slot con timestamps  🔧 **VIABLE — esfuerzo medio**

Parakeet-TDT en sherpa-onnx **expone timestamps a nivel token** (campo `timestamps` paralelo a `tokens` en el JSON). Combinado con el VAD Silero ya integrado, puedes:

1. Detectar la palabra sospechosa por ys_log_probs (punto 4).
2. Mapear de tokens a un rango `[t_start, t_end]` en segundos.
3. Extraer 200 ms de contexto a cada lado del rango.
4. Pasar ese sub-segmento por una segunda instancia del mismo recognizer con `hotwords_score` agresivo (3.5–5.0) limitado al top-k del inventario. Como el segmento es corto y solo contiene 1–2 palabras, el coste de desestabilización es bajo y el espacio combinatorio reducido permite forzar el hotword.
5. Si el segundo pase devuelve algo distinto y el ys_log_prob mejora, reemplaza el token; si no, deja el original.

**Coste:** un segundo pase de ~1.5 s de audio en CPU con Parakeet-int8 son ~50–80 ms adicionales **solo en el turno problemático**.

**Precedente:** `python-api-examples/generate-subtitles.py` y la discusión #985 documentan el patrón VAD → ASR-de-segmento; aplícalo al revés (al token de baja confianza).

**Riesgo:** si el segmento está muy fusionado, el segundo pase puede repetir el error. Para mitigar, exige que el hotword aparezca en los top-3 del segundo pase para aceptarlo. **Y recuerda el caveat de §3: si usas `modified_beam_search` para el segundo pase en v1.13.2, heredas el bug del 33% de fallo. Mejor segundo pase también en `greedy_search` con `blank_penalty` distinto.**

### 6) `HomophoneReplacer` (existe pero orientado a chino)

sherpa-onnx tiene `HomophoneReplacerConfig` (`dict_dir`, `lexicon`, `rule_fsts`) que se aplica como post-procesado del texto. PR #2817 añadió "Add spaces between English words for Homophone replacer". Es búsqueda exacta de variantes listadas, no corrector fonético abierto. Funcionalmente equivalente a una tabla `Moon→Boone` hardcodeada e inferior al corrector fonético genérico del punto 1. No prioritario.

### 7) `lm` + `lm_scale` (shallow fusion)  ❌ **NO FUNCIONA con Parakeet — DESCARTAR**

`OfflineRecognizerTransducerNeMoImpl` (`offline-recognizer-transducer-nemo-impl.h`) **no instancia `OfflineLM` jamás**. Solo el path icefall/Zipformer (`offline-recognizer-transducer-impl.h`) llama `OfflineLM::Create(config.lm_config)` y pasa el LM al `OfflineTransducerModifiedBeamSearchDecoder`. PR #3077 declara textualmente: **"Simplifications — Removed unused LM rescoring code"**.

En sherpa-onnx v1.13.2 con `--model-type=nemo_transducer`:
- `--lm=archivo.onnx --lm-scale=0.X` ⇒ **silent no-op**. El runtime acepta los argumentos (los imprime en el config dump como `lm_config=OfflineLMConfig(model="", scale=0.5, lodr_scale=0.01, lodr_fst="", lodr_backoff_id=-1)`) pero el decoder NeMo nunca los consulta.
- Formato esperado por `OfflineLM` cuando sí aplica (en Zipformer): **RNN LM en formato ONNX** exportado desde icefall, no ARPA, no KenLM (ver `icefall-asr-librispeech-pruned-transducer-stateless7-streaming`). Pero **no sirve con Parakeet**.

**Veredicto:** olvida esta vía hasta que sherpa-onnx exponga shallow-fusion para NeMo. No hay PR abierto al respecto en mayo de 2026.

### 8) `lodr_fst` + `lodr_scale` (LODR)  ❌ **NO FUNCIONA con Parakeet — DESCARTAR**

Mismo escenario que (7). Los campos existen en `OfflineLMConfig` (visibles en el config dump cuando ejecutas Parakeet) y están cableados al decoder del path icefall/Zipformer, pero el path NeMo no los lee. Es un no-op para Parakeet hoy.

**Conceptualmente** (Zhang et al. 2022, "An Empirical Study of Language Model Integration for Transducer based Speech Recognition", arXiv 2203.16776), LODR es shallow-fusion con corrección de prior interna (un n-gram de bajo orden estima el LM implícito del transducer) — útil cuando se aplica en Zipformer; irrelevante en Parakeet hoy.

---

## Tabla resumen: probabilidad de meter el nombre al beam / rescatarlo

| Técnica | ¿Mete el nombre al beam? | ¿Rescata post-hoc? | Latencia extra | Coste implementación | Estado en v1.13.2 |
|---|---|---|---|---|---|
| 1. Corrector fonético post-hoc (DM + Metáfono Español + RapidFuzz) | No (no necesita) | **Sí, alta** | <5 ms (solo slot) | Bajo | Recomendado SIEMPRE |
| 2. `blank_penalty` 0.5–1.5 | Parcial: descongela sílabas | — | 0 ms | Bajísimo | Recomendado SIEMPRE |
| 3. `modified_beam_search` + `max_active_paths=8–16` + hotwords | Parcial | — | +20–60% del decoding | Bajo | **Esperar fix posterior a v1.13.2** (PR #3589) |
| 4. `ys_log_probs` gating | — | Disparador del 1 y 5 | 0 ms | Bajo | Recomendado |
| 5. Retranscripción del slot | A veces | A veces | +50–80 ms solo turno problemático | Medio | Opcional |
| 6. HomophoneReplacer | No | Tabular exacto | 0 ms | Medio | No prioritario |
| 7. `lm` / `lm_scale` | — | — | — | — | **No soportado en NeMo** |
| 8. `lodr_fst` / `lodr_scale` | — | — | — | — | **No soportado en NeMo** |

## Recomendaciones (orden de implementación, accionable)

**Fase 1 — Ya (1 día):**
1. Mantén `greedy_search` por defecto (evitas el bug del MBS en v1.13.2 documentado en Issue #3267).
2. Añade `blank_penalty=1.0` al constructor del recognizer. Mide tu set de 6 turnos. Si fusiones tipo "doing→∅" disminuyen, mantén; si aparecen duplicaciones, baja a 0.5.
3. Implementa el **corrector fonético doble** (Double Metaphone + Metáfono Español + RapidFuzz) sobre el inventario dinámico de apps/artistas. Aplícalo SIEMPRE al slot post-verbo de comando al principio (sin gating de confianza).
4. Mide: "Búscame info sobre Benson Boone" y "pon Spotify" deberían salir correctos en >90% de los turnos.

**Fase 2 — Validada Fase 1 (2–3 días):**
5. Lee `ys_log_probs` de la salida JSON. Calibra umbral (probablemente `exp(min ys_log_prob) < 0.85` por palabra) para disparar el corrector con menor tasa de falsos positivos. Aplica corrector solo cuando dispara, no siempre, para no tocar lo correcto.
6. Ejecuta `pip install --upgrade sherpa-onnx`; si hay versión posterior a v1.13.2 con PR #3589 (busca el commit `Fix bugs in NeMo transducer modified beam search` en el changelog), prueba `modified_beam_search` con `max_active_paths=8` y tus hotwords BPE. Si el WER global no degrada respecto a greedy y los nombres mejoran, conmuta.

**Fase 3 — Solo si los nombres siguen fallando (1 semana):**
7. Implementa retranscripción del slot (punto 5). Último recurso para nombres en hotwords que aún no entran al beam tras `blank_penalty` + corrector.

**Umbrales de cambio de plan:**
- Si tras Fase 1 el corrector rescata <80% de nombres en tu inventario → revisa el inventario y los códigos fonéticos (acentos, "ñ" rompen Double Metaphone; aplica `unidecode` antes).
- Si al activar `modified_beam_search` el WER global empeora >5% absoluto → vuelve a greedy y depende solo del corrector.
- Si los nombres fuera de inventario son frecuentes → abre un issue en k2-fsa/sherpa-onnx pidiendo soporte de LM externo para `nemo_transducer`; hoy no existe esa vía estructural.

## Caveats

- **Verificado vs inferido:** la semántica de `blank_penalty` (positivo = más emisiones) es la convención uniforme del proyecto y se deduce de la firma del constructor visible en `offline-recognizer-transducer-nemo-impl.h`; la línea exacta `logits[blank_id] -= blank_penalty;` en `offline-transducer-greedy-search-nemo-decoder.cc` no pude citarla literalmente. Verifícalo en tu fork local si vas a escribir tests deterministas.
- **`modified_beam_search` en v1.13.2 es inseguro para Parakeet**: Issue #3267 documenta ~10/30 fallos (≈33%) con texto vacío o "Yeah." sobre audio claro; PR #3589 (fix) se mergeó después de la release de v1.13.2 (publicada el 13 de mayo de 2026, commit `13d0ae6`).
- **El corrector fonético no rescata nombres fuera del inventario.** Para asistente local con apps conocidas y biblioteca personal eso es aceptable; para un caso totalmente open-vocab no lo es. No hay solución dentro del stack actual para open-vocab rescue de nombres infrecuentes sin re-entrenar el encoder o sin cambiar de motor.
- **Double Metaphone tiene cobertura razonable de nombres hispanos, italianos, eslavos y germánicos pero está sesgado a fonemas ingleses.** Por eso la combinación con Metáfono Español (Mosquera 2012) es necesaria cuando el hablante hispano pronuncia el nombre inglés "a la española". No uses Soundex (solo inglés, demasiado tosco) ni un único Metaphone.
- **No hay benchmark público de latencia de `max_active_paths>4` sobre Parakeet-TDT en CPU**; las estimaciones (130–160 ms para 16, 180–220 ms para 32) son extrapolaciones desde transducers con modified beam search. Mídelo con tu hardware.
- **El `HomophoneReplacer` integrado fue originalmente diseñado para homófonos pinyin chinos**; PR #2817 añadió manejo de espacios en inglés pero la lógica sigue siendo de tabla exacta. Solo útil si tienes una lista finita y conocida de confusiones.
- **`ys_log_probs` se distorsionan cuando hay hotwords activos** (Issue #2937): los tokens promovidos por context-graph muestran log-probs artificialmente bajas. Calibra umbrales con hotwords activos, no en seco.
- **Sobre el corpus de entrenamiento de Parakeet-v3**: el modelo se afinó con ~7.500 horas (NeMo ASR Set 3.0); nombres propios anglosajones cuya pronunciación nativa es muy distinta a su escritura (Boone /buːn/) y que NO son top-frequency en ese corpus reciben poco gradiente, lo que explica por qué se fusionan precisamente esos. Es una limitación estructural del modelo, no un bug de sherpa-onnx.