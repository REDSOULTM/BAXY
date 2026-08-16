# sherpa-onnx 1.13.2 + Parakeet-TDT-0.6B-v3: cómo (y hasta dónde) forzar nombres propios ingleses dentro de español

> **Nota de nomenclatura:** la wake word del producto es hoy **"Baxy"**. Los
> ejemplos "Hey Gemma → A Hema" de abajo son **mediciones de error de ASR sobre
> la wake word de entonces ("Gemma")** y se conservan tal cual como hallazgo de
> research. El **modelo** sigue siendo Gemma 4 (de Google); no confundir la wake
> word con el LLM.

## TL;DR
- El motivo más probable de que `hotwords_score=3.0` empeore la salida es una combinación de tres cosas: (a) **formato de `bpe.vocab` incorrecto** (el modelo no trae `bpe.vocab` ni `bpe.model`, y un tokenizador BPE hecho a mano desde `tokens.txt` NO es compatible — sherpa-onnx espera el formato SentencePiece de dos columnas `pieza\tlog_prob`); (b) **score demasiado alto** (los ejemplos oficiales usan 1.5–2.0, no 3.0); (c) un bug conocido del decodificador NeMo+MBS+TDT (#3267) que sólo se arregló en **v1.13.2 vía PR #3589** — estás en la versión correcta, pero ese fix no elimina toda la inestabilidad; el path MBS sigue siendo más frágil que `greedy_search` en este modelo.
- La calidad base mala en Spanglish (`Hey Gemma → A Hema`, `Stranger Things → Ponstrom Gertis`) **no es bug tuyo**: los propios autores de NVIDIA confirman en la discusión “Code switching” del model card que Parakeet-TDT-0.6B-v3 *“its not fully tuned for codeswitching capabilities”* y el model card avisa *“The model may produce transcription errors, particularly with code-switching or noisy input.”* Sí, parte de tu medición está sesgada por TTS Piper, pero el límite duro del modelo es real. Validar con voz humana es imprescindible antes de tomar decisiones grandes.
- Recomendación práctica: **(1)** quédate en `greedy_search` para el camino caliente (110 ms p50); **(2)** genera `bpe.vocab` correctamente con `scripts/nemo/generate_bpe_vocab.py` (necesitas el checkpoint NeMo, no basta `tokens.txt`); **(3)** prueba MBS+hotwords con `hotwords_score=1.5`, `max_active_paths=8`, `modeling_unit="bpe"` y mide; **(4)** complementa con post-proceso determinista (mapeo de errores conocidos vía `rule_fsts` o un dict en Python) — es la única defensa estable hoy contra el sesgo europeo del modelo en code-switching.

## Key Findings

### Sobre los hotwords (Problema 1)

1. **El formato correcto cuando NO tienes `bpe.model`.** sherpa-onnx no consume `bpe.model` (sentencepiece protobuf); consume `bpe.vocab`, que es el archivo de dos columnas que `spm_train` emite junto al `.model` — una línea por pieza con `pieza\tlog_prob`. La documentación lo afirma textualmente: *“We need bpe.vocab rather than bpe.model, because we don't introduce sentencepiece c++ codebase into sherpa-onnx (which has a depandancy issue of protobuf), we implement a simple sentencepiece encoder and decoder which takes bpe.vocab as input.”* (k2-fsa/sherpa docs, hotwords/index.html). El `tokens.txt` que trae el modelo es `pieza id` por línea y **no contiene** las probabilidades necesarias para reconstruir un `.vocab` válido — por eso tu tokenizador hecho a mano produce un archivo que sherpa-onnx no interpreta como esperas.

2. **El script oficial existe y se llama `scripts/nemo/generate_bpe_vocab.py`** (introducido en PR #3077 junto con el soporte de MBS+hotwords para NeMo transducers). Uso documentado por el autor del PR (verbatim en el thread del PR #3077): `python scripts/nemo/generate_bpe_vocab.py --model nvidia/parakeet-tdt-0.6b-v2 --output sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8\bpe.vocab` → `Writing bpe.vocab to: sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8\bpe.vocab Done!`. El mismo comando funciona con `--model nvidia/parakeet-tdt-0.6b-v3`. **Requiere `pip install nemo_toolkit[asr]` y descargar el checkpoint NeMo de HuggingFace** (la primera vez tira de internet); no funciona desde `tokens.txt` solo. El script más viejo `scripts/export_bpe_vocab.py --bpe-model bpe.model` también sirve si consigues el `bpe.model` interno del `.nemo`.

3. **El bundle de v3 NO incluye `bpe.vocab`.** El listado oficial de `sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2` contiene sólo `encoder.int8.onnx`, `decoder.int8.onnx`, `joiner.int8.onnx`, `tokens.txt`, `test_wavs/`. Eso es esperado: el soporte MBS+hotwords para NeMo se añadió en PR #3077, descrito por el propio issue #3267 como *“PR Add modified beam search and hotwords support for NeMo transducer models #3077: Added modified_beam_search support for NeMo transducer models (merged Feb 5, 2026)”* — mucho después de subir el modelo. Si quieres hotwords, te toca generar `bpe.vocab` tú.

4. **`modeling_unit` correcto = `"bpe"`.** El tokenizador de Parakeet-TDT-0.6B-v3 es SentencePiece BPE unificado (~8k pieces) para 25 idiomas europeos. Para sherpa-onnx eso significa `modeling_unit="bpe"`. **NO** uses `cjkchar+bpe` (eso es para modelos mixtos chino+inglés) ni `cjkchar` (sólo chino). En tu API: pasa `modeling_unit="bpe"` y `bpe_vocab="ruta/al/bpe.vocab"` generado por el script de arriba.

5. **Bug MBS+TDT (#3267) y el fix en v1.13.2.** El issue reporta, verbatim, *“~6/30 return 'Yeah.', ~4/30 return empty, ~20/30 return correct text”* — es decir, ~33% de fallo (10/30), no 20% como dice el resumen del issue; el reportero combina dos modos de fallo. Esto ocurría con `modified_beam_search` + Parakeet TDT v3, **incluso con el archivo de hotwords vacío**. La causa raíz fue identificada en el code review de PR #3077: el decodificador NeMo MBS no sumaba el log-prob de la duración a la puntuación de la hipótesis (`The code was selecting predicted_skip from duration_logits but never adding the duration's log-probability to the hypothesis score`). El fix se mergeó como **PR #3589 “Fix bugs in NeMo transducer modified beam search”** y aparece en las release notes de **v1.13.2** (`Fix bugs in NeMo transducer modified beam search. by @csukuangfj in #3589`). Estás en v1.13.2, así que ese bug específico ya no debería darte “8 mal.” por nada; sin embargo, el camino MBS para NeMo TDT sigue siendo nuevo (Feb 2026), tiene menos rodaje que el camino MBS de Zipformer, y la propia issue #845 documenta un patrón parecido en Zipformer no resuelto.

6. **`hotwords_score=3.0` es agresivo.** Los ejemplos oficiales y reproducibles usan `2.0` (k2-fsa/sherpa-onnx hotwords doc) y el #3267 documenta `1.5`. El default del SDK es `1.5` (confirmado en `sherpa-onnx/c-api/c-api.cc`: `recognizer_config.hotwords_score = SHERPA_ONNX_OR(config->hotwords_score, 1.5)`). La puntuación se aplica **por token**, no por palabra (la doc lo dice: *“We match the hotwords at token level, so the hotwords-score is applied at token level”*), así que multiplicarla a 3.0 sobre nombres con 3–4 BPE pieces fuerza al beam a recompensas de +9..+12 — suficiente para que la mejor hipótesis sea cualquier cosa con esas piezas, incluso fragmentos. Recomendación: empezar con `1.5`, subir en pasos de 0.5 midiendo en tu lote de 25 clips.

7. **`max_active_paths` (default 4) probablemente es bajo.** El boosting sólo ayuda a hipótesis que existan en el beam: si el camino correcto cae fuera del top-4, los hotwords no tienen a quién premiar. Sube a 8 (o 16 si la latencia lo aguanta — son ~2-3x el coste por frame, no por utterance). En tu p50 ~110 ms hay margen.

8. **Alternativas de biasing dentro de sherpa-onnx para nombres propios:**
   - **`lm` + `lm_scale` (shallow fusion):** existe en el constructor `from_transducer` y compila un n-grama externo. **Pero** requiere ese n-grama como `.onnx` (RNN-LM-style), no como ARPA simple; sólo está validado para Zipformer transducers, y no he encontrado ejemplos de uso con Parakeet-TDT. Riesgo medio.
   - **`lodr_fst` + `lodr_scale`:** sustracción de densidad (LODR). Los defaults son `lodr_scale=0.01`, `lodr_backoff_id=-1`. Mismo problema: pensado para Zipformer/icefall, no documentado para NeMo TDT.
   - **`hr` (homophone replacer):** **NO aplica a tu caso.** La documentación oficial repite literalmente tres veces *“只支持对汉字进行替换”* (“Only supports replacement of Han/Chinese characters”) y añade *“目前没计划实现对非汉字的字符进行替换”* (“no hay planes de soportar caracteres no-Han”). Descártalo.
   - **`rule_fsts` (text-normalization FSTs):** sí sirve. Es una sustitución textual aplicada al string de salida (no biasing acústico). Puedes compilar un FST con pares fijos `Hema → Gemma`, `Hablestan → Steam`, `Netfix → Netflix`, `Trikenstein → Counter-Strike`. Es la herramienta más estable y la única que **no toca el decodificador**, así que no introduce hallucinations. Limitación: corrige sólo errores observados, no generaliza.

### Sobre la calidad base en Spanglish (Problema 2)

9. **Confirmación oficial de NVIDIA.** En la discusión del model card (`nvidia/parakeet-tdt-0.6b-v3/discussions/1` titulada “Code switching”), el autor reconoce: *“Its not fully tuned for codeswitching capabilities.”* El model card en HuggingFace añade: *“The model may produce transcription errors, particularly with code-switching or noisy input.”* Y el technical report (arXiv:2509.14128, Sekoyan et al., NVIDIA, Sep 2025) confirma: *“The model was trained on 1.7M hours of total data samples, including Granary and NeMo ASR Set 3.0.”* La arquitectura tiene detección automática de idioma — es decir, internamente el encoder decide “este audio es español” y entonces el decoder favorece fonotáctica española. Por eso `Steam` → `Hablestan` (`abla-estam` en español).

10. **El sesgo a español europeo es esperado y NVIDIA lo documenta con un proxy.** Granary y NeMo ASR Set 3.0 son corpora multilingües de NVIDIA. El model card admite explícitamente un sesgo análogo en otra lengua: *“Performance differences may be partly attributed to Portuguese variant differences - our training data uses European Portuguese while most benchmarks use Brazilian Portuguese.”* El paper no cuantifica el split es-ES vs es-419, pero el patrón es estructural. No hay un Parakeet-TDT-v3 “Latam” oficial.

11. **Sí, parte de tu medida es ruido del TTS Piper.** Piper genera prosodia menos natural, especialmente para anglicismos en mitad de una frase española; un humano hispanohablante que pronuncie *“abre Steam”* tiende a hacer un micro-corte y cambiar de modo articulatorio en la palabra inglesa, lo que el modelo capta mejor que la TTS plana. **Antes de descartar Parakeet-v3, repite el test con 25 clips de voz humana real**. El issue #2605 muestra que incluso con voz humana clara (Obama.wav, 15 s) el modelo todavía omite tokens (`doing` desaparece de “How's everybody doing today?”), así que algo de error queda; pero la magnitud del salto humano→sintético en code-switching es típicamente sustancial en ASR transducer. No tengo cifra sólida para tu caso concreto — **mídela tú**, es el experimento clave.

12. **No hay un modelo de la zoo de sherpa-onnx que sea transducer + español + inglés + hotwords estables.**
   - `sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20`: chino+inglés, no español.
   - `sherpa-onnx-streaming-paraformer-trilingual-zh-cantonese-en`: no transducer (no soporta hotwords).
   - `sherpa-onnx-nemo-parakeet-unified-en-0.6b`: sólo inglés.
   - `bookbot/sherpa-onnx-zipformer-streaming-robust-es-v0`: español, **pero predice fonemas IPA**, no palabras — inservible para tu caso (requiere lexicon adicional y no maneja inglés).
   - **Conclusión honesta**: si el requisito es transducer + español + inglés + hotwords sin compilar nada, **Parakeet-TDT-0.6B-v3 es lo mejor que hay hoy en la zoo**. SenseVoice (multilingüe es/en/zh/ja/ko/yue) tiene buena calidad pero **no es transducer y por tanto no soporta hotwords** según la doc oficial (*“Only transducer models support hotwords in sherpa-onnx”*). Quedarte con tu stack es la decisión correcta.

13. **Trucos documentados que mejoran nombres propios sin reentrenar:**
   - **Endurecer el VAD** y aceptar utterances más completas — `silero-vad` con `min_speech_duration=0.2` y `min_silence_duration=0.5` (defaults sensatos). Los clips de 1.7 s con anglicismos al final son los peores casos.
   - **`blank_penalty` positivo (0.5 a 1.5)** en `greedy_search`: penaliza emisión de blank y por tanto reduce deleciones (Parakeet TDT tiende a saltarse sílabas en code-switching, ver issue #2605 donde `doing` se omite). El parámetro existe en tu API; default 0.0.
   - **No forzar token de idioma**: el modelo v3 hace LID interno; no expone “language token” como Canary, así que ese truco de Whisper/Canary no aplica.
   - **Procesar el segmento del nombre por separado en un segundo modelo inglés** es viable pero rompe tu requisito de latencia (haría falta diarización por palabra primero).

## Details

### Solución concreta al Problema 1, ordenada por probabilidad de éxito

**S1 (más probable que funcione, *evidencia verificada*) — Generar `bpe.vocab` real y bajar el score.**

```bash
# Requisito: instalar NeMo (sólo para esta operación, no en runtime)
pip install -q "nemo_toolkit[asr]"   # descargará torch+lightning; sólo necesario una vez
# Bajar el script desde el repo de sherpa-onnx:
curl -L -o generate_bpe_vocab.py \
  https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/master/scripts/nemo/generate_bpe_vocab.py
python generate_bpe_vocab.py \
  --model nvidia/parakeet-tdt-0.6b-v3 \
  --output sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8/bpe.vocab
```

El archivo resultante tiene formato SentencePiece dos columnas (`pieza\tlog_prob`). Luego en Python:

```python
import sherpa_onnx
rec = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder="…/encoder.int8.onnx",
    decoder="…/decoder.int8.onnx",
    joiner="…/joiner.int8.onnx",
    tokens="…/tokens.txt",
    num_threads=4,
    model_type="nemo_transducer",
    decoding_method="modified_beam_search",
    max_active_paths=8,           # subir del default 4
    modeling_unit="bpe",
    bpe_vocab="…/bpe.vocab",      # generado arriba
    hotwords_file="hotwords.txt", # ver formato abajo
    hotwords_score=1.5,           # bajar de 3.0; default del SDK
    blank_penalty=0.0,
)
```

`hotwords.txt` (palabras como aparezcan, una por línea, **NO pre-tokenizadas** — sherpa-onnx las tokeniza internamente con `bpe.vocab`; opcional `:score`):

```
Steam :2.0
Netflix :2.0
Disney :2.0
Daredevil :2.5
Spotify :2.0
Stranger Things :2.5
Counter-Strike :2.5
Gemma :3.0
```

Pon scores más altos sólo a los nombres que más fallan (Gemma cae siempre, Daredevil rara vez). Si NO usas el `:score` por línea, todos heredan `hotwords_score=1.5` globalmente.

**S2 (alta probabilidad, *funciona en todas las plataformas*) — Mantener `greedy_search` + post-proceso con `rule_fsts`.**

`greedy_search` no acepta hotwords (la doc lo dice explícitamente: *“The default decoding method greedy_search does not support hotwords”*), pero **sí acepta `rule_fsts`**, que reemplaza substrings en el texto final usando un FST de OpenFST. Compila uno con `pynini` (igual que el ejemplo de Chinese homophone replacer, pero textual sin pinyin):

```python
import pynini
from pynini import cdrewrite
from pynini.lib import utf8
sigma = utf8.VALID_UTF8_CHAR.star
rules = (
    pynini.cross("hema", "Gemma") |
    pynini.cross("ablestan", "Steam") |
    pynini.cross("hablestan", "Steam") |
    pynini.cross("netfix", "Netflix") |
    pynini.cross("trikenstein", "Counter-Strike") |
    pynini.cross("ponstrom gertis", "Stranger Things") |
    pynini.cross("eigenma", "Gemma") |
    pynini.cross("ey jamma", "hey Gemma")
).optimize()
rule = cdrewrite(rules, "", "", sigma)
rule.write("replace.fst")
```

Y en Python: `OfflineRecognizer.from_transducer(..., decoding_method="greedy_search", rule_fsts="replace.fst")`. Mantiene tu latencia p50 ~110 ms intacta (el FST se aplica al string, no al beam). Esta es la **única solución verificable que NO toca el decodificador y por tanto no puede empeorar la salida**: para entradas que no matchean el FST, la salida es idéntica a la actual.

Limitación: corrige errores **observados**; no generaliza a nombres nuevos. Para un set cerrado de ~30 apps/series el balance esfuerzo/beneficio es óptimo.

**S3 (sólo si S1 no basta, *worth trying*) — `lm` + `lm_scale` con un n-grama dominado por tu vocabulario.**

Compila un 3-gram tipo KenLM con frases sintéticas (`"abre Steam", "pon Daredevil en Disney", "abre Spotify", ...`) y conviértelo al formato ONNX que `OfflineLMConfig` espera. Es la herramienta más cercana a “bias suave” que tienes, pero no he encontrado un ejemplo end-to-end con Parakeet-TDT en la documentación; el código del LM en `sherpa-onnx/csrc/offline-lm.h` muestra que la API existe y acepta `lodr_fst` adicional. Trátalo como experimental.

**Lo que descarto explícitamente:**
- `hr` (homophone replacer) — **sólo soporta caracteres Han; no aplica a español/inglés** (confirmado 3 veces en la doc oficial).
- Pasar hotwords ya pre-tokenizados a IDs/tokens — no es el formato esperado; sherpa-onnx tokeniza internamente con `bpe.vocab`. Si lo intentas, la cadena se reinterpreta como texto literal y no matchea nada.
- Subir `hotwords_score` por encima de 2.5 — empeora estadísticamente (consistente con el comportamiento de Aho-Corasick boosting documentado: a score alto el modelo entra en estado de match parcial y se queda atrapado).

### Solución concreta al Problema 2, ordenada por probabilidad de éxito

**S4 (primera acción obligatoria) — Validar con voz humana real.** Graba 25 clips espejo de tu set con tu propia voz y mide. Si el WER de nombres baja sensiblemente respecto a Piper, el problema base ya no es bloqueante y puedes resolverlo todo con S1+S2 más buenas reglas de post-proceso. Si apenas mejora, el límite es estructural del modelo.

**S5 — Normalizar audio.** Parakeet v3 espera 16 kHz mono, `dither=0`, `normalize_samples=True` (defaults correctos en `OfflineRecognizer`). Asegúrate de que tu pipeline Piper→sherpa-onnx no introduce DC offset ni clipping. Pico recomendado −3 dBFS.

**S6 — Subir contexto.** Si tu wake-word + comando son < 2 s, mete 200–300 ms de silencio padding al inicio. Parakeet TDT tiene tendencia a deleciones en el primer token (issue #2605: `doing` desaparece). Padding al inicio amortigua el efecto.

**S7 (si nada de lo anterior alcanza) — Cambiar de modelo dentro de la zoo.** El único candidato razonable es **SenseVoice multilingüe** (`sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17-int8`, también acepta español como “otro” idioma en modo `auto`), **pero pierdes hotwords** porque no es transducer. Sería un downgrade salvo si combinas con S2 (rule_fsts) agresivamente. Mide WER en tu set: si SenseVoice te da mejor base, vale la pena perder hotwords y pasar a S2 puro.

## Recommendations

Etapas con criterios de salto:

1. **Hoy (30 min):** repite los 25 clips con voz humana. Mide WER de nombres propios.
   - Si WER nombres ≤ 15% → salta directo a S2 (rule_fsts) sobre los errores residuales y ya tienes el sistema.
   - Si WER nombres > 30% → sigue al paso 2.

2. **Generar `bpe.vocab` correcto (S1).** Aprovecha que ya tienes Python 3.10. Crea un venv temporal `pip install nemo_toolkit[asr]`, corre `generate_bpe_vocab.py`. Si la descarga de NeMo es problemática, **alternativa pragmática**: busca en HuggingFace forks que ya hayan publicado `bpe.vocab` para `sherpa-onnx-nemo-parakeet-tdt-0.6b-v3`. Si nada funciona, queda S2 como plan B garantizado.

3. **Probar S1 con la config sugerida** (`hotwords_score=1.5`, `max_active_paths=8`). Mide WER nombres y latencia.
   - Threshold de aceptación: WER nombres ↓ ≥ 20% **sin** subir latencia p50 por encima de 200 ms.
   - Si la latencia se va a 300+ ms → baja `max_active_paths` a 6.
   - Si MBS empieza a alucinar (“yeah.”, vacíos), confirma con `debug=True` que `sherpa-onnx` reporta `1.13.2` en su banner; si sí y aún alucina, abre un issue en el repo (es regression sobre #3589 y los maintainers lo querrán saber).

4. **Combinar con S2 (`rule_fsts`).** Aún con S1 funcionando, monta un FST con los 10–15 errores residuales que aún se observen. Es defensa en profundidad y no cuesta latencia.

5. **No invertir más en hotwords si** después de 3+4 sigues con > 25% WER en nombres. Eso indica que el encoder está perdiendo la información acústica del anglicismo (no hay hipótesis correcta en el beam) y ningún rescoring lo arregla. En ese punto: o aceptas el límite + S2 más exhaustivo, o cambias de modelo a SenseVoice + S2 puro.

6. **Plan B si abandonas Parakeet:** la única alternativa transducer-con-hotwords-estables en la zoo para español sería un Zipformer ES propio (icefall + CommonVoice ES + LibriVox ES), que se sale del requisito “sin reentrenar”. No lo hagas a menos que ya tengas todo lo demás validado.

## Caveats

- **El fix de #3589 está en v1.13.2 pero no es exhaustivo.** El issue #845 (mismo síntoma en Zipformer) lleva años abierto. El path MBS de Parakeet NeMo se mergeó en Feb 2026 y tiene poco rodaje; espera regresiones puntuales. Mantén `greedy_search` como fallback con un flag.
- **No he podido confirmar el contenido exacto byte a byte de `scripts/nemo/generate_bpe_vocab.py`** (GitHub bloqueó la lectura del blob raw en mi investigación); inferí su comportamiento del PR #3077, las code reviews y la doc. Si el script falla, abre issue en el repo — los maintainers responden rápido.
- **TTS Piper en Spanglish:** no es un benchmark fiable. Tus números actuales (`Steam → Hablestan`, etc.) están inflados respecto a lo que verás en producción con humanos. **El paso 1 de la recomendación no es opcional**. No tengo cifras publicadas que cuantifiquen la mejora humano-vs-Piper para Parakeet-TDT-v3 en code-switching específicamente; tienes que medirlo en tu lote.
- **`hotwords_score=2.0` puede ser óptimo en tu dominio o puede ser demasiado.** No hay una constante universal; el rango sensato según la doc y los ejemplos oficiales es 1.5–2.5 para nombres de 2–4 BPE pieces. Mide.
- **Latencia.** Cambiar de `greedy_search` a `modified_beam_search` con `max_active_paths=8` suele **multiplicar latencia por ~1.5–2× en transducers offline** (regla empírica reportada por usuarios en issues del repo; no medido en tu hardware exacto). Si tu p50 de 110 ms ya es crítico, MBS te lo llevará a 170–220 ms. S2 (`rule_fsts` sobre greedy) es la única ruta que respeta tu budget de latencia sin condiciones.
- **No existe un Parakeet-TDT-0.6B-v3 “Latin American Spanish” oficial ni un fork al que conozca.** El sesgo europeo es estructural en Granary + NeMo ASR Set 3.0.
- **NeMo word boosting nativo** existe para TDT desde NVIDIA-NeMo PR #14277, incluido en la release NeMo v2.5.0 (confirmado en `nvidia/parakeet-tdt-0.6b-v3` discussions/3 y discussions/31 de HuggingFace), pero **vive en NeMo, no en sherpa-onnx**: requiere correr el modelo .nemo en Python con torch — fuera de tus restricciones (CPU + sin GPU + sin reentrenar + dentro de sherpa-onnx). Mencionado sólo para que sepas que río arriba el feature equivalente existe; no es aplicable a tu stack actual.
- **Issue #3267 falla con ~33% (no 20%) cuando se hace la cuenta exacta.** El reportero combina dos modos de fallo (alucinación “Yeah.” + vacío) que sumados dan 10/30. El resumen del título del issue (“~20%”) sólo cuenta uno de los dos. La estabilidad real del path MBS en v1.12.25 era peor de lo que parece a primera vista; v1.13.2 (con #3589) debería estar significativamente mejor, pero no he visto reportes de re-test independientes después del fix.