# PLAN MAESTRO — Wake-word "Hey Carter"

> **RESUELTO 2026-06-04: la wake word final es BAXY** (recall **0.872**, supera a
> gemma **0.74**). Carter se descartó por la **/r/** rótica cross-idioma (esta es la
> lección que conserva el resto de este documento). La wake word del producto es ahora
> "Baxy" (sin "hey/oye"; variantes aceptadas: baxy / baxi / hey baxy). Ver commit de
> activación. El análisis de Carter de abajo se mantiene intacto como el porqué del
> descarte y la saga medida que llevó a Baxy.

Estado: **NO ENTRENAR** hasta orden explícita del usuario (instrucción 2026-06-03).
Este documento consolida lo MEDIDO y deja todo listo para decidir/ejecutar.
Última consolidación: 2026-06-03.

Convención: cada afirmación lleva una etiqueta.
- **[HECHO]** verificado esta línea de trabajo (medido en esta máquina o leído en código/fuente).
- **[HIPÓTESIS]** plausible y fundamentado, pero **no medido todavía** — hay que medirlo, no asumirlo.

Fuente de verdad cruzada: `memory/project_wake_word_carter_gotchas_2026_06_03.md`,
`data/livekit_train/configs/hey_carter.yaml`, y los scripts `scripts/_diag_wake_*` +
`scripts/_train_carter_throttled.py`.

---

## 1. Resumen ejecutivo

**Qué pasó.** Tras el rebrand "hey gemma" → "Carter" (2026-06-03), el wake-word reentrenado
con `livekit-wakeword` (pipeline Piper VITS / LibriTTS en-us) **no pasa el gate**: recall
held-out global **0.28** contra gate **≥ 0.60** (∧ fp/hr ≤ 1.0 @ threshold 0.25), sobre el
held-out universal de 25 voces / 13 idiomas. **[HECHO]**

**Causa raíz: fonética cross-idioma.** El TTS de training es **solo inglés**
(`data/piper/en-us-libritts-high.pt`, LibriTTS 904 voces en-us; espeak fonemiza todo en-us).
La palabra "carter" contiene **/r/ rótica**, el fonema que **más varía entre idiomas**. El
modelo aprende solo la /r/ anglo. El desglose por idioma lo prueba: **en_US ≈ 1.00**, pero
**it / fr / es / pl / ar ≈ 0.00**. El mismo pipeline con "gemma" (sin /r/, schwa final)
generaliza bien (**0.74 global, todos los idiomas**) — confirma que el problema es la /r/ +
train-EN-only, no el pipeline. **[HECHO]**

Confirmación fonética independiente (espeak-ng en esta máquina, mismo input "hey carter"):
- de → `kˈaɾtɜ` (tap), fr → `kaʁtˈEʁ` (R uvular), nl → `kˈɑrtər` (approximant),
  es → `kaɾtˈeɾ` (tap), en-us → ɹ rótica. **[HECHO]**

**Qué se descartó (no re-investigar):** no es el config (carter ≈ gemma salvo 2 claves
inertes), no es la longitud de la frase, no es memorización de voces, no es el probe (validado:
da 0.74 exacto en gemma con el mismo código), no es el casing (el pipeline hace `lower()`), no
son los acentos ortográficos (Piper fonemiza siempre en-us). **[HECHO]**

**Estado actual.** Diagnóstico cerrado. Tooling de eval rápido y orquestación de training ya
construido. Pendiente: **decisión del usuario** sobre cuál camino de fix tomar (multi-idioma
TTS, respelling, o ambos) y **orden de entrenar**.

---

## 2. Cronología de intentos (números MEDIDOS)

| # | Qué se entrenó | Recall held-out | Veredicto | Lección |
|---|----------------|-----------------|-----------|---------|
| Baseline | "hey gemma" (mismo pipeline en-us) | **0.744 global**, todos los idiomas | PASA gate histórico | El pipeline es sano; "gemma" generaliza (sin /r/, schwa final). **[HECHO]** |
| Intento 1 | "hey/oye/carter" mezclados (carter pelado incluido) | **0.27 global** | FALLA | Conflicto de etiquetas: el auto-generador (`include_partial_phrase=1.0`, `generate.py:387`) mete "carter" pelado como NEGATIVO → término positivo Y negativo a la vez. + sobreajuste. NUNCA mezclar la frase completa con su sub-palabra. **[HECHO]** |
| Intento 2/3 | "Hey Carter" (1 patrón, 5 variantes prosodia/h-drop, 5k/30k) — config actual `hey_carter.yaml` | **0.28 global**; **en_US ≈ 1.00**, **it/fr/es/pl/ar ≈ 0.00** | FALLA por idioma | El pivote a "hey carter" (jugada Hey Siri/Google/Alexa) resolvió la longitud, pero NO la /r/ cross-idioma. La validación interna del trainer ENGAÑA (0.78 interno vs 0.28 real held-out). **[HECHO]** |

Notas medidas:
- La **validación interna del trainer no sirve como gate** (0.78 interno vs 0.28 real). El gate
  honesto es el held-out de 25 voces / 13 idiomas NUNCA vistas. **[HECHO]**
- El control de equidad (gemma 0.74 / carter 0.28 con el MISMO código sobre el MISMO conjunto)
  prueba que el 0.28 es real (overfit a la /r/ anglo), no artefacto del test. **[HECHO]**
  (Harness: `scripts/_diag_wake_heldout_validate.py`.)

---

## 3. Los 7 gotchas y su fix (ya pagados caro — no repetir)

| # | Gotcha | Fix |
|---|--------|-----|
| 1 | **charmap UnicodeDecodeError en generate**: espeak-ng en Windows escupe UTF-8 pero el default es cp1252. | `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8` ANTES de lanzar el `.exe` (heredado por el subproceso hijo). Ya lo setea `_train_carter_throttled.py`. **[HECHO]** |
| 2 | **`\| head` mata el pipeline por SIGPIPE**: pipear la salida larga a `head` rompe el run. | Log a archivo (`_pipeline.log`), tee-a-disco; nunca pipear a `head`. **[HECHO]** |
| 3 | **OOM de Piper TTS** (acumulación con GPU compartida, no falta de VRAM). | GPU despejada antes del generate + `tts_batch_size` acotado en el config. El script AVISA de despejar VRAM; **NO mata procesos del usuario** (CLAUDE.md). **[HECHO]** |
| 4 | **Auto-adversariales**: el generador mete la sub-palabra de la frase como NEGATIVO (causa del intento 1). | NO mezclar la frase completa con su sub-palabra. Entrenar SOLO "hey carter"; "carter" pelado va explícito en `custom_negative_phrases`. El config ya lo respeta. **[HECHO]** |
| 5 | **El eval oficial CUELGA el PC**: `wake_universal_eval_livekit.py` carga 3 ONNX SIN `SessionOptions` → ORT usa los 24 cores + spinning → Windows inutilizable; + 5.323 negativos LibriSpeech (10.8h, ~57k inferencias = 2h+). | Eval rápido = onnxruntime **puro** + `_ort_throttle.apply()` ANTES de cargar ONNX (`scripts/_diag_wake_recall_probe.py`, 500 clips en ~12s). Para fp/hr acotar el oficial con `--max-negatives`. **[HECHO]** |
| 6 | **Feature-extraction clava la CPU (~40min)**: usa 2 ONNX hardcodeados a `CPUExecutionProvider` (`feature_extractor.py:42-45` y `:101-104`). | Patch-en-venv a `CUDAExecutionProvider` (patrón espeak, NO va al repo) + `onnxruntime-gpu`. Throttle por-fase (CPU phases) en `_train_carter_throttled.py`. Opcional: acelera, no es bloqueante. **[HECHO el diagnóstico; el patch GPU está pendiente de aplicar]** |
| 7 | **Solo 1 checkpoint Piper en-us en disco** → multi-idioma de TTS requiere DESCARGAR más. | Dejar script de descarga reproducible (CLAUDE.md). Ver sección 5. **[HECHO el diagnóstico]** |

Gotcha extra de TRAIN (no contar como uno de los 7, pero registrarlo): **"Input type Half and
bias type float" en train** — causado por aplicar `_ort_throttle` (OMP_NUM_THREADS + cpu_affinity)
al TRAIN, que confunde a cuDNN. El throttle es **solo para fases CPU** (generate/augment/export);
el TRAIN usa GPU/PyTorch y NO debe throttlearse. `_train_carter_throttled.py` aplica env por-fase
(CPU_PHASES), no global. **[HECHO]**

---

## 4. Pipeline robusto definitivo (comandos exactos)

Intérprete de training: **`.venv_livekit/Scripts/python.exe`** (Python 3.11; el runtime del
agente es 3.10 y NO debe importar el paquete livekit). El **generador de held-out de eval** usa
el **python del SISTEMA** (que tiene piper), NO el `.venv_livekit`.

Orquestador único (encadena setup → generate → augment+feature-extraction → train → export,
GPU donde se puede, sin colgar el PC, sin perder datos entre fases):

```
scripts\_train_carter_throttled.py
```

Reglas duras del pipeline (las implementa el orquestador):
- **UTF-8 (gotcha 1):** `PYTHONUTF8=1` y `PYTHONIOENCODING=utf-8` exportados antes de cualquier
  subproceso.
- **Log a archivo (gotcha 2):** toda la salida a `_pipeline.log`; nunca `| head`.
- **Throttle por-fase (gotchas 5/6 + train):** `_ort_throttle` solo en fases CPU
  (generate/augment/export). El TRAIN corre en GPU sin throttle.
- **Idempotencia / no-borra-datos:** el paquete livekit reanuda splits ya generados
  (`generate.py`). El orquestador NO borra `output/hey_carter` entre fases. Para un run limpio,
  borrar `output/hey_carter` **a mano** (decisión explícita; CLAUDE.md: confirmá lo irreversible).
  `--clean-features` borra SOLO los `.npy` de features (no los clips) para re-extraer en GPU tras
  patchear, y pide confirmación.

### GPU para la fase lenta (feature-extraction, ~40min en CPU) — opcional pero recomendado

`.venv_livekit` hoy tiene `onnxruntime 1.26.0` SIN `CUDAExecutionProvider` (providers = Azure+CPU).
**[HECHO]** Para acelerar:

1. Instalar el paquete GPU (matchear CUDA):
   ```
   .venv_livekit\Scripts\python.exe -m pip install onnxruntime-gpu
   ```
2. Patchear `feature_extractor.py:42-45` y `:101-104` de
   `providers=['CPUExecutionProvider']` → `providers=['CUDAExecutionProvider','CPUExecutionProvider']`.
   Patch-en-venv (como espeak): **NO va al repo**. Dejar un script reaplicable
   (`scripts/_patch_livekit_gpu.py` / `_patch_feature_extractor_gpu.py`) por si se recrea el venv.
3. CPU también funciona (solo más lento) → el patch GPU **no es bloqueante** para la viabilidad.

Disco libre: 203 GB (sobra para ~810 MB de checkpoints multi-idioma). **[HECHO]**

---

## 5. Fix multi-idioma (camino principal) + alternativa respelling

### 5.A — Multi-idioma TTS (cubrir la /r/ no-inglesa)

**VIABLE pero PARCIAL.** **[HECHO, vía GitHub API + lectura del paquete]**

El pipeline de TRAINING (`livekit-wakeword`) **NO usa** los `.onnx` de `rhasspy/piper-voices`
(eso es solo el lado EVAL). Usa el VITS vendido de `dscripka/rhasspy/piper-sample-generator`,
que carga un `state_dict` `.pt` + JSON con clave `"synthesizer"` (`synthesis.py:39-63`
`_load_vits_model`). Checkpoints `.pt` en ESE formato **solo existen para 4 idiomas** en los
releases de `piper-sample-generator`:

- en (en-us-libritts-high 255MB v1.0.0 = **el de disco**; en_US-libritts_r-medium 204MB v2.0.0)
- de_DE-mls-medium 202.7MB v2.0.0
- fr_FR-mls-medium 202.5MB v2.0.0
- nl_NL-mls-medium 202.3MB v2.0.0

**NO hay checkpoint `.pt`** para es/it/pt/ru/pl en este formato. **Con el camino
Piper-multi-checkpoint cubrís solo en+de+fr+nl.** El **español (idioma del operador) y el resto
NO se cubren por esta vía.** Es una mejora real (uvular fr + tap de = vecinos del tap es/it/pt)
pero **NO universalidad completa.** **[HECHO]**

**Qué descargar (3 checkpoints nuevos, ~607MB; en-us ya está):** **[HECHO la URL+tamaño]**
- `de_DE-mls-medium.pt` 202.7MB → `https://github.com/rhasspy/piper-sample-generator/releases/download/v2.0.0/de_DE-mls-medium.pt`
- `fr_FR-mls-medium.pt` 202.5MB → `https://github.com/rhasspy/piper-sample-generator/releases/download/v2.0.0/fr_FR-mls-medium.pt`
- `nl_NL-mls-medium.pt` 202.3MB → `https://github.com/rhasspy/piper-sample-generator/releases/download/v2.0.0/nl_NL-mls-medium.pt`
- (opcional) `en_US-libritts_r-medium.pt` 204MB v2.0.0 — 2º acento inglés.
- JSON configs (en el repo, NO en releases) vía GitHub contents API:
  `https://api.github.com/repos/rhasspy/piper-sample-generator/contents/models/<name>.pt.json`
  (campo `content` base64). espeak.voice verificado: de='de', fr='fr', nl='nl'. **[HECHO]**

**Script de descarga reproducible (CLAUDE.md) — `scripts/wake_train_download_checkpoints.py`:**
tabla `(url_pt, nombre, sha-opcional)` + JSON vía contents API; bajar a `data/piper/<name>.pt` y
`data/piper/<name>.pt.json`; idempotente (skip si existe y size>0); urllib stdlib. **Clonar el
patrón de `scripts/wake_universal_download_voices.py`** (ya hace download idempotente con retry).

**CAVEAT de formato (medido): construir el bloque `"synthesizer"`.** **[HECHO el caveat]**
Los `.pt.json` stock de de/fr/nl NO traen la clave `"synthesizer"` que `_load_vits_model`
(`synthesis.py:51`) EXIGE; tienen `num_symbols=256` (n_vocab medium) y num_speakers 236/125/52.
Hay que construir el bloque con los hiperparámetros VITS **medium** (distintos del **high** del
en-us de disco):

| param | medium (de/fr/nl) | high (en-us disco) |
|-------|-------------------|--------------------|
| resblock | '2' | '1' |
| resblock_kernel_sizes | [3,5,7] | [3,7,11] |
| upsample_rates | [8,8,4] | [8,8,2,2] |
| upsample_initial_channel | 256 | 512 |
| n_vocab | 256 | 130 |

Script: `scripts/wake_train_make_synth_json.py` que por cada `.pt.json` stock inyecte
`"synthesizer"` con preset medium:
```
{n_vocab:<num_symbols=256>, spec_channels:513, segment_size:32, inter_channels:192,
 hidden_channels:192, filter_channels:768, n_heads:2, n_layers:6, kernel_size:3,
 p_dropout:0.1, resblock:'2', resblock_kernel_sizes:[3,5,7],
 resblock_dilation_sizes:[[1,2],[2,6],[3,12]], upsample_rates:[8,8,4],
 upsample_initial_channel:256, upsample_kernel_sizes:[16,16,8],
 n_speakers:<num_speakers del json>, gin_channels:512, use_sdp:true}
```
RECOMENDADO antes de confiar (smoke test, CLAUDE.md): cargar el `.pt` con
`torch.load(weights_only=True)` e inferir `n_vocab` de `enc_p.emb.weight.shape[0]`, `n_speakers`
de `emb_g.weight.shape[0]`, `upsample_initial_channel` de `dec.conv_pre`, para VALIDAR el preset
contra los pesos reales. Guardar como `data/piper/<name>.json` (sufijo `.json`, como el en-us de
disco). Smoke: generar 5 clips con `synthesize_clips(vits_model_path=<de.pt>)` y verificar que no
son silencio.

**CAVEAT 2 (medido):** `normalize_phrases_for_piper` (`text.py:44`, llamado en `piper_backend`)
lowercasea y expande palabras vía **CMUDict INGLÉS** — "hey carter" pasa intacto (palabras
inglesas), pero ojo si se agregan frases con ortografía no-inglesa. **[HECHO]**

**Mezclar SIN parchear el core (verificado en código):** **[HECHO la arquitectura]**
`config.py:78 PiperTtsConfig.checkpoint_relpath` es UN solo string; `get_tts_backend`
(`backends.py:39`) crea UN backend. NO hay soporte nativo multi-checkpoint. PERO:
- `generate.py:200 synthesize_clips(phrases, output_dir, n_samples, vits_model_path, start_index=...)`
  es entry-point de librería que toma checkpoint y offset explícitos.
- `run_generate` (`generate.py:331`) y `augment.py:206` cuentan/globean `clip_######.wav` en
  `positive_train` SIN importar qué checkpoint los generó (`glob('*.wav')`).
- El espeak voice se lee POR-checkpoint del JSON (`synthesis.py:160`).

→ Approach correcto: **generar por-checkpoint dentro del MISMO `positive_train` con
`start_index` acumulado** (round-robin de idiomas), luego augment/train normal. Crear
`scripts/wake_generate_multilang.py` que importe `synthesize_clips`, defina
`checkpoints=[en,de,fr,nl]` con % por idioma, y para cada split
(`positive_train n=5000`, `positive_test n=1000`) reparta `n_samples` por idioma con offset
creciente. Negativos/background quedan en en-us (el generador de adversariales es CMUDict-EN).
Correr con `PYTHONUTF8=1` y `_ort_throttle` solo en fase CPU.

**% por idioma recomendado (fundamentado):** el embedding congelado de Google es EN-céntrico →
mantener EN fuerte para no degradar `en_US 1.00`, y repartir el resto entre los róticos.
- **en 40% / de 20% / fr 20% / nl 20%** sobre 5000 = en2000 / de1000 / fr1000 / nl1000.
- Justificación: fr aporta la R uvular (caso extremo), de/nl el tap/approximant (vecinos del
  es/it/pt). **[HIPÓTESIS: que estos 4 idiomas levanten es/it/pt por transferencia fonética hay
  que MEDIRLO con el probe por-idioma, no asumirlo.]**

### 5.B — Alternativa / complemento: respelling

Idea: alterar la ortografía de la frase de training para forzar a espeak en-us a producir
fonemas más cercanos a los róticos no-ingleses (p.ej. variantes que aproximen tap/uvular). Es
**barata** (no requiere descargar checkpoints) y **combinable** con 5.A.

Estado: **[HIPÓTESIS]** — el harness `scripts/_diag_wake_carter_bylang.py` está pensado
justamente para ver "qué idiomas un respelling podría plausiblemente rescatar vs cuáles están
fonéticamente fuera de alcance para un TTS espeak en-US". No hay un número medido todavía. Riesgo:
respelling agresivo puede degradar `en_US` (subgrupo fuerte) → medir anti-regresión por idioma.

Recomendación: usar respelling como **complemento** del multi-idioma (cubre es/it/pt/ru/pl que el
camino Piper NO cubre), nunca como sustituto sin medir.

---

## 6. Gates y eval rápido

**Gate de aceptación (de antemano, CLAUDE.md "medí no celebres"):**
- **Global:** `recall ≥ 0.60 ∧ fp/hr ≤ 1.0 @ threshold 0.25`.
- **Por idioma (anti-regresión, universalidad):** NINGÚN subgrupo fuerte debe colapsar; en
  particular `en_US` NO debe caer por debajo de su 1.00 actual. Un gate global no alcanza para un
  sistema multi-usuario. **[HECHO el criterio]**

**Held-out honesto:** `data/wake_universal_eval/positives_carter` — 25 voces / 13 idiomas NUNCA
vistas. DEBE matchear el patrón entrenado o mide ruido (entrenar "hey carter" → evaluar "hey
carter"). Generador: `scripts/wake_universal_generate_positives.py` (`GEMMA4_EVAL_WAKE=carter`,
frases en `_PHRASE_SETS`, corre con el python del SISTEMA que tiene piper, NO `.venv_livekit`).
**[HECHO]**

**Eval rápido (NO el oficial que cuelga 2h):**
- **Recall por idioma (EL gate anti-regresión):**
  `python scripts/_diag_wake_recall_probe.py [N] [--threshold 0.25] [--model PATH]`
  — onnxruntime puro + `_ort_throttle`, 500 clips en ~12s, imprime recall GLOBAL + tabla
  por-idioma + worst-language, marca `<-- COLLAPSE` si un idioma < 0.30. **[HECHO]**
- **Desglose por idioma+voz (read-only, sin training):**
  `scripts/_diag_wake_carter_bylang.py`. **[HECHO]**
- **Validación de equidad carter-vs-gemma (¿el 0.28 es real?):**
  `scripts/_diag_wake_heldout_validate.py`. **[HECHO]**
- **fp/hr (axis separado):** acotar el eval oficial con `--max-negatives` (NO correr los 5.323
  negativos completos: cuelga). Otros probes: `scripts/_diag_wake_neg_probe.py`,
  `scripts/_diag_wake_neg_volume.py`, `scripts/_diag_wake_predict_cost.py`. **[HECHO]**

**Recordatorio:** la validación interna del trainer engaña (0.78 interno vs 0.28 held-out real).
El gate es SIEMPRE el held-out. **[HECHO]**

---

## 7. Árbol de decisión honesto (con probabilidades estimadas)

Las probabilidades son **[HIPÓTESIS]** (estimación de ingeniería, no medidas). Norte: pasar
`recall ≥ 0.60` global **sin colapsar ningún idioma** y manteniendo `en_US` alto.

```
¿Querés universalidad completa (es/it/pt/ru/pl incluidos)?
│
├─ NO (basta en+de+fr+nl) ──────────────────────────────────────────────┐
│                                                                         │
│   Camino A: Multi-idioma TTS Piper (4 checkpoints).                     │
│   Costo: ~607MB descarga + construir synthesizer JSON + re-generate +   │
│          re-train (~40min features en CPU, menos con GPU).              │
│   Prob. de pasar gate GLOBAL ≥0.60:        ALTA  (~70-80%) [HIPÓTESIS]  │
│   Prob. de levantar es/it/pt por transfer: MEDIA (~40-55%) [HIPÓTESIS]  │
│   Riesgo de regresión en_US:               BAJO si EN se mantiene 40%.  │
│                                                                         │
└─ SÍ (cubrir el idioma del operador, español, y el resto) ──────────────┤
                                                                          │
    Camino A NO basta solo (no hay checkpoint .pt es/it/pt/ru/pl).        │
    Opciones:                                                             │
    ├─ A + B (multi-idioma TTS + respelling para los faltantes)          │
    │     Prob. universalidad razonable:  MEDIA (~45-60%) [HIPÓTESIS]     │
    │     Riesgo: respelling degrada en_US → medir por-idioma SIEMPRE.    │
    │                                                                     │
    ├─ Solo B (respelling, barato, sin descargas)                        │
    │     Prob. de pasar gate global:     BAJA-MEDIA (~30-45%) [HIPÓTESIS]│
    │     Útil como sonda barata ANTES de descargar nada.                │
    │                                                                     │
    └─ Pivotar la PALABRA (nombre sin /r/, p.ej. tipo "gemma")           │
          Prob. de pasar gate:            ALTA (el baseline ya dio 0.74)  │
          Costo de producto: cambiar el nombre del wake-word (decisión   │
          del usuario, no técnica).                                       │
```

**Recomendación de secuencia (mínimo-experimento primero, CLAUDE.md):**
1. **Sonda barata B (respelling)** con `_diag_wake_carter_bylang.py` para ver qué idiomas son
   alcanzables por TTS en-us — **sin descargar nada, sin entrenar de verdad** (smoke). **[paso de medición]**
2. Si el usuario aprueba entrenar: **Camino A** (descargar 4 checkpoints, construir synthesizer
   JSON validado contra pesos, generar 40/20/20/20, re-train) → medir recall por-idioma.
3. Si es/it/pt siguen bajos y se quiere universalidad: **A + B**.
4. El pivote de palabra es la salida de mayor probabilidad pero es decisión de PRODUCTO del
   usuario (cambia el nombre del asistente).

**Caveat de honestidad:** la transferencia fonética de+fr+nl → es/it/pt es **plausible pero NO
medida**. El único número que vale es el del `_diag_wake_recall_probe.py` por-idioma tras entrenar.

---

## 8. Qué NO repetir

- **NO mezclar la frase completa con su sub-palabra** como positivos (causó el 0.27 del intento 1:
  el generador mete la sub-palabra como negativo). "carter" pelado va solo en
  `custom_negative_phrases`.
- **NO confiar en la validación interna del trainer** (0.78) — el gate es el held-out (0.28). El
  held-out DEBE matchear el patrón entrenado.
- **NO correr el eval oficial completo** (`wake_universal_eval_livekit.py` con los 5.323
  negativos) — cuelga el PC 2h+ por falta de `SessionOptions` + spinning. Usar el probe rápido.
- **NO aplicar `_ort_throttle` al TRAIN** (rompe cuDNN: "Input type Half and bias type float"). El
  throttle es solo para fases CPU.
- **NO pipear la salida del pipeline a `| head`** (SIGPIPE lo mata) — log a archivo.
- **NO asumir que casing/acentos ortográficos ayudan** — el pipeline hace `lower()` y Piper
  fonemiza siempre en-us.
- **NO esperar checkpoints `.pt` de es/it/pt/ru/pl** en el formato de piper-sample-generator: no
  existen. El camino Piper cubre solo en+de+fr+nl.
- **NO usar los `.pt.json` stock tal cual** — les falta la clave `"synthesizer"`; hay que
  construirla con el preset VITS **medium** (NO el high del en-us) y validarla contra los pesos.
- **NO flipear el default del runtime a `hey_carter`** (`wake.py:LIVEKIT_MODEL_STEM`) hasta que el
  modelo pase el gate. Sigue en `hey_gemma` hasta entonces.
- **NO entrenar hasta la orden explícita del usuario** (instrucción vigente 2026-06-03).
- **NO matar procesos del usuario** (juegos/LLM en GPU) para despejar VRAM sin avisar/confirmar.

---

### Apéndice: scripts ya creados (reusar, no reescribir)

- `scripts/_train_carter_throttled.py` — orquestador robusto del pipeline (generate→augment→train→export), por-fase, anti-7-gotchas.
- `scripts/_diag_wake_recall_probe.py` — eval rápido recall por-idioma (EL gate).
- `scripts/_diag_wake_carter_bylang.py` — recall por idioma+voz (read-only).
- `scripts/_diag_wake_heldout_validate.py` — equidad carter-vs-gemma.
- `scripts/_diag_wake_neg_probe.py`, `_diag_wake_neg_volume.py`, `_diag_wake_predict_cost.py` — sondas de negativos / costo (fp/hr).
- `scripts/wake_universal_generate_positives.py` — genera el held-out (`GEMMA4_EVAL_WAKE=carter`).
- `scripts/wake_universal_download_voices.py` — patrón de descarga idempotente a clonar.
- `scripts/_ort_throttle.py` — anti-freeze (aplicar ANTES de cargar ONNX, solo CPU).

### Apéndice: scripts a crear (pendientes de la decisión, NO entrenar aún)

- `scripts/wake_train_download_checkpoints.py` — descarga de_DE/fr_FR/nl_NL `.pt` + `.pt.json` (idempotente, urllib).
- `scripts/wake_train_make_synth_json.py` — inyecta el bloque `"synthesizer"` (preset medium) validado contra pesos.
- `scripts/wake_generate_multilang.py` — round-robin de checkpoints en `positive_train` con `start_index` acumulado.
- `scripts/_patch_livekit_gpu.py` (o `_patch_feature_extractor_gpu.py`) — patch-en-venv CPU→CUDA para feature-extraction (reaplicable).
