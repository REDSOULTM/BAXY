# Plan de reescritura del subsistema de voz (wake → STT → idioma)

**Rama:** `voz-reescritura-desde-cero`
**Fecha:** 2026-06-17
**Alcance:** reescritura completa de las tres etapas de precisión del pipeline de
voz — detección de wake-word, transcripción y manejo de idioma — conservando las
mismas tecnologías. La plomería (captura de audio, threading, VAD, máquina de
estados, AEC, ducking, latencia) se conserva con cambios mínimos: está medida y
sana, y la latencia no es un problema reportado.

**Restricción de motor STT (decisión de producto):** **solo Parakeet-TDT-0.6b-v3
vía sherpa-onnx. Whisper se elimina por completo** del pipeline de voz (deja de
ser fallback, deja de ser el motor del rescate de idioma). Esto cambia
sustancialmente la estrategia de idioma — ver §3.

---

## 1. Causa raíz de las tres fallas (evidencia)

Las fallas reportadas son **wake-word**, **transcripción** e **idioma**, con
frecuencia alta en uso normal. La latencia y los cuelgues NO son problema.

### 1.1 Wake-word
- LiveKit conv-attention es la arquitectura correcta para el caso: está
  recomendada **específicamente para frases fonéticamente similares**
  ("Baxy" vs "Bixby/Paxi/Max"). [LiveKit training docs]
- El recall multilingüe es estructuralmente más bajo porque **el embedding de
  voz congelado de Google es inglés-céntrico**; las representaciones para otros
  idiomas/acentos son más débiles. [LiveKit blog/docs]
- El umbral de disparo está fijo (0.25) y global; no se optimiza por entorno ni
  hay calibración del operador.
- **Hipótesis de causa raíz:** recall insuficiente en el acento/idioma real del
  usuario + umbral no óptimo → el wake no dispara cuando debe (o dispara con
  ruido). Requiere re-medición por idioma sobre held-out diverso.

### 1.2 Transcripción + 1.3 Idioma — **misma causa raíz**
- Model card oficial de NVIDIA, textual: *"Not recommended for word-for-word /
  incomplete sentences as accuracy varies based on the context of input text."*
  Un asistente de voz recibe exactamente eso: comandos cortos e incompletos.
- **No se puede forzar el idioma** en Parakeet-TDT-v3: la detección es 100%
  automática. `forced_decoder_ids` es una API exclusiva de Whisper y el modelo
  Parakeet ni siquiera la reconoce (NeMo Discussion #14620, sin resolución;
  FluidAudio #303 es un *feature request* abierto para exponer un language hint).
  sherpa-onnx tampoco expone control de idioma.
- En audio corto y de baja confianza, **Parakeet cae a inglés por default**.
- **Consecuencia:** las fallas de transcripción incorrecta y de idioma
  equivocado son **el mismo defecto del modelo en clips cortos**, no un defecto
  de cómo está escrito el código actual. El `_lid_rescue` existente es un parche
  que re-transcribía con Whisper (idioma fijado) — pero Whisper se elimina, así
  que ese escape desaparece.

---

## 2. Implicancia de eliminar Whisper

Con Whisper fuera, **desaparece la única vía de transcripción con idioma
forzado**. Por lo tanto:

- El idioma **no se puede *curar* a nivel STT** (no hay re-transcripción con
  idioma fijo). Solo se puede **mitigar**.
- La mitigación legítima y respaldada por evidencia es: **maximizar el contexto
  de audio que ve Parakeet** (su auto-LID es malo en clips cortos pero bueno con
  más contexto) y **derivar una señal de idioma detectada** para el agente.
- Esto es un límite **inherente a la decisión de producto** (Parakeet-only), no
  una limitación de la implementación. Queda documentado como tal.

---

## 2bis. Contraste adversarial del plan (2ª ronda de investigación)

Se buscó evidencia que **refutara** las suposiciones del plan. Resultado: dos
suposiciones se corrigen y aparece una palanca nueva.

- **REFUTADO (parcial) — "más contexto cura el idioma/accuracy".** La literatura
  (arxiv 2011.10538 *Context Audio for RNN-T*, 2210.16238 *Contextual-Utterance
  Training*) muestra que el contexto baja WER >6%, pero es contexto **lingüístico
  / de entrenamiento**, NO padding de silencio en inferencia. Corrección: dar a
  Parakeet **más habla real** (incluir el wake-word y no recortar de más) ayuda a
  su auto-LID porque tiene más señal; **rellenar con silencio no aporta nada**.
  El plan ya no promete que el contexto "cure" — solo mejora la confianza del
  auto-LID, y se mide cuánto.

- **NUEVO LEVER (refuta el comentario viejo del código) — biasing contextual
  para Parakeet en sherpa-onnx.** El código actual dice "hotwords NO viable para
  nemo_transducer". **Eso quedó desactualizado:** sherpa-onnx mergeó
  (PR #3077, 2026-02-05) un `modified_beam_search` con hotwords/ContextGraph
  para transducers NeMo, incluido Parakeet TDT (`--hotwords-file`,
  `--hotwords-score`, `--modeling-unit=bpe`). Esto ataca la falla de
  **transcripción** de raíz: se pueden **boostear los nombres propios**
  (apps/artistas) que Parakeet destroza, en vez de depender solo del corrector
  fonético downstream. **CAVEAT medido:** ese MBS con Parakeet TDT
  **alucina o devuelve vacío ~20% de las veces** (sherpa-onnx Issue #3267),
  coherente con la medición previa del repo (beam pierde en la cadena). → Se
  evalúa como **experimento gateado**: si el rate de vacíos/alucinación en el
  harness de cadena es alto, se vuelve a greedy + corrector. No es un win gratis.

- **CONFIRMADO — recall multilingüe del wake exige datos diversos, no solo
  umbral.** Evidencia: hablantes no-nativos ~30% más de fallo en asistentes; la
  vía validada es **modelo entrenado con habla acento-agnóstica/diversa**
  (patente US20230368786, HEiMDaL arxiv 2210.15425), más enrollment por-usuario
  estilo Snowboy. → El reentreno del wake sube de "opcional" a **probablemente
  necesario**, gateado por la re-medición de la Fase 3.

- **A VIGILAR — bug español en NeMo.** Issue #14854: `get_words_offsets()`
  crashea con puntuación inicial española (`¡Hola!`). Es un path de NeMo; hay que
  verificar que NO afecte al int8 vía sherpa-onnx (test específico en Fase 0).

## 3. Arquitectura nueva por etapa

> Principio rector: separar **mecanismo** (medible, testeable, sin estado oculto)
> de **política** (umbrales calibrados por entorno/idioma). Cada borde decide por
> señal estructural o estado del SO, nunca por listas hardcoded (regla de
> producto: el LLM responde).

### 3.1 Captura y segmentación (CONSERVAR, refactor menor)
- WASAPI + resample 16k, chunks de 512 samples, ring buffer, pump thread,
  AEC loopback, ducking: **se conservan**. Limpieza: extraer constantes,
  documentar contratos de I/O, tests de invariantes.

### 3.2 Wake-word (REESCRIBIR detección + RE-MEDIR modelo)
- Runtime ONNX puro (3 grafos: mel → embedding → clasificador): se conserva el
  mecanismo, se reescribe limpio con contratos explícitos.
- **Política nueva:**
  - Re-evaluar el modelo `baxy.onnx` sobre held-out diverso y reportar
    **recall por idioma** (anti-regresión por idioma). Gate: ningún idioma
    fuerte por debajo del baseline actual.
  - **Threshold óptimo por barrido** (scan 0.01–0.99 maximizando recall a
    FPPH ≤ objetivo), no un 0.25 mágico. [LiveKit eval docs]
  - Mantener throttle (predict cada N chunks) y cooldown.
  - Si la re-medición muestra recall multilingüe insuficiente: **reentrenar**
    con la receta medida (focal loss γ=2, peso de negativos hasta 1500×,
    embedding mixup Beta(0.2,0.2), label smoothing 0.025/0.975, checkpoint
    averaging, negativos adversariales fonéticos + ACAV100M + ruido MUSAN).
    [LiveKit training docs] — **probablemente necesario** (no solo opcional): la
    evidencia dice que el recall multilingüe/acento se gana con datos diversos,
    no solo con umbral. Sujeto al gate de re-medición de la Fase 3.
- Gate de energía anti-falso-wake + calibración de piso por mic: se conservan.

### 3.3 STT — Parakeet-only (REESCRIBIR limpio)
- sherpa-onnx OfflineRecognizer, int8, CPU, greedy + blank_penalty (medido mejor
  que beam en la cadena real): se conserva el mecanismo.
- **Foco en transcripción correcta** (lo controlable sin Whisper):
  - Audio limpio y bien segmentado a Parakeet (energy-trim, VAD-trim, AEC).
  - **Maximizar contexto**: no recortar de más; incluir margen. Su LID y su
    accuracy mejoran con más audio.
  - Re-evaluar decoding (greedy vs beam) y blank_penalty con el harness de
    cadena, no con clips aislados (lección medida).
  - **Biasing contextual de nombres propios (NUEVO, gateado):** sherpa-onnx ya
    soporta hotwords para Parakeet TDT (PR #3077, 2026-02-05) vía
    `modified_beam_search` + `--hotwords-file` con los nombres del inventario
    (apps/artistas). Ataca la falla de transcripción de raíz. PERO el MBS de
    NeMo TDT alucina/vacía ~20% (Issue #3267) → se mide en el harness de cadena
    y solo se adopta si el rate de vacíos no empeora los emitidos; si no, greedy
    + corrector fonético (el camino actual, ya sólido).
- **Sin fallback a Whisper.** Si Parakeet no carga, la voz falla limpio con
  mensaje claro (no hay caída silenciosa).

### 3.4 Idioma (REESCRIBIR como MITIGACIÓN honesta)
- Eliminar el `_lid_rescue` basado en Whisper.
- **Estrategia nueva (Parakeet-only):**
  - Dar a Parakeet más **habla real** (incluir el wake-word, no recortar de más)
    para que su auto-LID tenga más señal. OJO: rellenar con silencio NO ayuda
    (el contexto útil es lingüístico, no padding) — corrección de la 2ª ronda.
  - **Señal de idioma para el agente:** detectar el idioma del usuario (perfil
    configurado `GEMMA4_VOICE_LANG` + heurística estructural sobre la salida) y
    pasarla como hint al runner, para que el agente responda en el idioma
    correcto aunque la transcripción haya leakeado inglés. Esto ataca la
    sub-falla "responde en idioma equivocado" sin re-transcribir.
  - **Opción evaluable (no compromiso):** un LID dedicado torch-free. El de
    sherpa-onnx usa encoder Whisper (descartado). VoxLingua/ECAPA es torch
    (pesado, contra el objetivo de soltar torch). Si se necesita LID dedicado,
    se evalúa un clasificador ONNX chico — sujeto a gate de RAM/latencia.
- `lang_profiles.py` (idioma fijo + prompt bilingüe anti-fonetización) se
  conserva como fuente del perfil; el `initial_prompt` ya no va a Whisper pero el
  código de idioma sigue gobernando la señal al agente.

### 3.5 Corrector fonético (CONSERVAR, ya es sólido)
- strip-wake (exacto + fonético dual ES/EN), gate posicional, stopwords, cap de
  longitud, Metaphone dual: se conservan. Es la pieza más madura y medida.

### 3.6 Handoff al agente (CONSERVAR)
- VoiceRunner → RUNNER.submit → run_text: se conserva. Se agrega el campo de
  hint de idioma al turno.

---

## 4. Catálogo de regresiones = GATES (no romper ninguna)

Cada ítem es un comportamiento medido que la reescritura DEBE preservar. Se
codifica como test antes de reescribir la etapa correspondiente.

**Captura/plomería**
1. WASAPI, no MME (MME devuelve ceros a 16k). Fallback a 16k directo si falla.
2. Chunks de exactamente 512 samples @16k (Silero v5 lo exige).
3. Callback de PortAudio sin I/O (solo copy + put_nowait); pump thread aparte.
4. AEC en bypass seguro si no hay loopback (nunca rompe el mic).
5. stop() resetea la máquina de estados (no turnos fantasma al re-enable).

**Wake**
6. Alimentar el wake con TODOS los chunks (NO gatear con VAD aguas arriba: tiró
   recall 7/105 → 0/105).
7. Ventana de 2s con padding correcto (audio al final; el padding al inicio
   colapsa el score a ~0.002).
8. Gate de energía anti-falso-wake sobre el preroll (piso calibrado por mic).
9. Cooldown de misma-frase (no múltiples disparos por un "Baxy").
10. Pausa del wake mientras TTS habla (anti-eco por software).
11. Recall por idioma no degrada bajo baseline en ningún idioma fuerte.

**Captura de comando / EOS**
12. MIN_CAPTURE_S protege la micro-pausa post-wake (no cortar antes de hablar).
13. EOS tri-estado para fondo hablado (sin él, 75/84 capturas se cuelgan a SNR 5).
14. Timeout duro de comando (8s).
15. Segunda oportunidad si el transcript queda vacío tras strip (paridad Alexa).

**Gates de no-comando (anti-turno-fantasma)**
16. Silence-gate por RMS pico (no transcribir silencio).
17. No-user-evidence gate (ninguna ventana supera fondo×factor → NO_SPEECH).
18. Filler-only / non-lexical drop ("mm", "uh").
19. Feedback NO_SPEECH a la UI (no drop silencioso).

**STT**
20. blank_penalty solo con greedy (con beam empeora; medido).
21. Decoding decidido por la cadena real, no clips aislados (beam pierde e2e).
22. Warm-up al cargar (no pagar el frío en la p50 del usuario).
23. No alucina en silencio (ventaja de Parakeet; preservar exención de la lista
    de alucinaciones que aplicaba a Whisper).

**Corrector / idioma**
24. strip-wake fonético (Baxy mal oído como Bixby/Paxi/Max no leakea al comando).
25. Gate posicional del corrector (no corromper habla declarativa).
26. Cap de longitud (≤8 tokens) — no tocar enunciados largos.
27. Stopwords españolas no se corrigen contra el inventario.
28. Código de idioma del perfil gobierna la señal al agente.

---

## 5. Plan por fases (cada fase con gate medible)

> Cada fase se mide EN VIVO contra el agente real (regla del repo), no solo con
> tests mockeados. Nada se da por cerrado sin número contra gate definido antes.

- **Fase 0 — Red de seguridad.** Codificar los gates §4 como suite de tests +
  reactivar/extender el harness de cadena (`voice_chain_eval.py`) y el de wake
  (`wake_universal_eval_livekit.py`). Baseline medido del sistema actual ANTES de
  tocar nada (números crudos por etapa e idioma). **Gate:** baseline reproducible
  registrado.

- **Fase 1 — STT Parakeet-only.** Reescribir el motor + sacar Whisper y el
  LID-rescue. Re-evaluar decoding/blank_penalty/contexto con el harness de cadena.
  **Gate:** WER de cadena ≤ baseline y emitidos ≥ baseline; 0 referencias a
  Whisper en el pipeline de voz.

- **Fase 2 — Idioma (mitigación).** Hint de idioma al agente + máximo contexto a
  Parakeet. **Gate:** en held-out multilingüe, el agente responde en el idioma
  del usuario ≥ baseline; medir cuántos clips cortos Parakeet aún leakea (reporte
  honesto del límite residual).

- **Fase 3 — Wake.** Reescribir detección + barrido de umbral + recall por
  idioma. **Gate:** recall global ≥ baseline, FPPH ≤ baseline, ningún idioma
  fuerte degradado. (Reentreno del modelo = sub-fase opcional solo si la
  re-medición no pasa el gate.)

- **Fase 4 — Integración + verificación en vivo.** Cadena completa contra el
  agente real, fraseos múltiples y caminos de tool alternativos. **Gate:**
  los 28 gates §4 verdes + demo en vivo de los tres ejes (wake/STT/idioma).

---

## 6. Métricas y harness

- **Wake:** recall, FPPH, AUT, recall POR IDIOMA, sobre held-out diverso
  (clips wake + negativos fonéticos adversariales + horas de habla general).
- **STT:** WER de cadena (buffer compuesto preroll+wake+pausa+comando), exactos,
  emitidos, por idioma. Clips aislados solo como diagnóstico secundario.
- **Idioma:** % de respuestas del agente en el idioma correcto; % de clips
  cortos con leak de inglés (límite residual reportado).
- **Latencia:** p50/p90 por turno (gate: no regresar el presupuesto actual).

---

## 7. Fuentes

- NVIDIA, *parakeet-tdt-0.6b-v3* model card (limitación de frases cortas;
  auto-LID; sin forzado de idioma). https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3
- NVIDIA NeMo, Discussion #14620 *(Define output language for multilingual
  parakeet-tdt-0.6b-v3)* — sin resolución; `forced_decoder_ids` no aplica al TDT.
- FluidInference/FluidAudio Issue #303 *(expose language hint)* — feature request abierto.
- NVIDIA NeMo Issue #15097 *(detected language output para Parakeet TDT v3)*.
- LiveKit, *wakeword training docs* (3 fases, focal loss γ=2, neg-weight 1500×,
  embedding mixup, label smoothing, checkpoint averaging, threshold scan).
  https://github.com/livekit/livekit-wakeword/blob/main/docs/training.md
- LiveKit, *wakeword evaluation docs* (AUT, recall@thr, FPPH; held-out).
  https://github.com/livekit/livekit-wakeword/blob/main/docs/evaluation.md
- LiveKit, *Open-source wake word training* (conv-attention: 60× menos AUT,
  100× menos FP/hr, +17% recall vs OWW; multilingüe más débil por embedding EN).
  https://livekit.com/blog/livekit-wakeword
- dscripka/openWakeWord (VAD gating para reducir FP; targets recall≥0.5,
  FPPH≤0.2; no entrenar con negativos demasiado parecidos).
  https://github.com/dscripka/openWakeWord
- k2-fsa/sherpa-onnx — LID example usa encoder Whisper (descartado).
  https://github.com/k2-fsa/sherpa-onnx
- SpeechBrain VoxLingua107 ECAPA-TDNN (LID dedicado, torch, 6.7% err) — evaluable.
  https://huggingface.co/speechbrain/lang-id-voxlingua107-ecapa
- arxiv 2509.14128 — Canary-1B-v2 & Parakeet-TDT-0.6B-v3 (modelo, multilingüe).

**Contraste adversarial (2ª ronda):**
- k2-fsa/sherpa-onnx PR #3077 — hotwords/MBS para transducers NeMo (Parakeet TDT),
  mergeado 2026-02-05. https://github.com/k2-fsa/sherpa-onnx/pull/3077
- k2-fsa/sherpa-onnx Issue #3267 — MBS con Parakeet TDT alucina/vacía ~20%.
  https://github.com/k2-fsa/sherpa-onnx/issues/3267
- sherpa-onnx Hotwords (contextual biasing) docs.
  https://k2-fsa.github.io/sherpa/onnx/hotwords/index.html
- arxiv 2011.10538 — *Improving RNN-T ASR Accuracy Using Context Audio* (>6% WER).
- arxiv 2210.16238 — *Contextual-Utterance Training for ASR*.
- NVIDIA NeMo Issue #14854 — crash español `¡Hola!` en get_words_offsets().
- arxiv 2210.15425 — *HEiMDaL* (wake-word eficiente) + patente US20230368786
  (wake-word acento-agnóstico por datos diversos).
