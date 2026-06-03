# HOTFIX 2026-05-17 (R3) — Custom "hey gemma" wake-word model

> Sprint mediano, alto ROI. Sprint R2 + R2.5 dejaron:
>
>   1. La infra `WakeDetector` con backend openWakeWord vs Vosk.
>   2. El bench midiendo recall correcto con matching ±1s.
>   3. Vosk caracterizado: `precision=0.857` pero `recall=0.057`.
>   4. 105 wakes anotados por el operador en
>      `testaudio_v2_expected.json`.
>
> Sprint R3 entrena un modelo openWakeWord custom para
> "hey gemma" usando esos 105 wakes como dataset positivo seed.
> Objetivo: mover `wake_recall` de 0.057 a ≥0.70 **manteniendo
> precision ≥0.80** (no shippear un modelo ruidoso).
>
> Sprint del agente: armar pipeline completo (build dataset +
> notebook Colab + integración). Operador: subir notebook a
> Colab, run all, descargar `.onnx`, dropear, re-correr bench.

---

## Contexto crítico

### Caracterización de Vosk (memoria
[[project-vosk-baseline-characterization]])

| Métrica | Vosk actual |
|---|---|
| Fires | 7 |
| TP | 6 |
| FP | 1 |
| FN | 99 |
| Recall | 0.057 |
| **Precision** | **0.857** |
| F1 | 0.107 |

Vosk **no es ruidoso, es conservador**. El modelo custom no
debe optimizar recall a costa de precision. Acceptance bar:

- **Recall ≥ 0.70** (subir 12× sobre Vosk).
- **Precision ≥ 0.80** (mantener el floor de Vosk).
- Si custom logra recall 0.90 + precision 0.50 → **NO shippear**.
  Bench reporta FAIL del custom incluso si recall supera el
  target formal — la heurística de UX (falsos positivos
  interrumpen al operador) es más estricta.

### Dataset positivo seed (pre-calculado)

105 wakes en `testaudio_v2_expected.json`, ventanas no
solapadas posibles con `[-0.3s, +0.9s]` = 1.2s totales:

```
Total positivos: 105 clips de 1.2s
Solapamientos:   0 (gap mínimo 1.34s > 1.2s window)
Cobertura:       126s de 293s totales del audio
```

### Dataset negativo seed (hard negatives del mismo audio)

166.8s del audio NO están dentro de ninguna ventana positiva.
Extraíbles como ~139 clips de 1.2s. Estos son **hard negatives
oro**: misma voz, mismo micrófono, mismo ambiente, mismas
condiciones acústicas, pero SIN "hey gemma". Maximiza
discriminación.

### Dataset negativo adicional

openWakeWord upstream provee un dataset negativo grande
pre-generado (audiolibros, podcasts, música, ambient). El
notebook de training lo descarga automáticamente. NO hay que
generar más material — el hard negatives nuestros + el dataset
upstream son suficientes.

---

## OBJETIVO

Un commit chico aterriza scripts + notebook + integración.
**No incluye el `.onnx` entrenado** — ese sale del Colab del
operador. El sprint tiene 2 fases:

**Fase A (agente, todo en un commit)**:
1. `scripts/build_wake_dataset.py` — extrae positivos y hard
   negatives desde `Grabación (2).wav` + `testaudio_v2_expected.json`.
2. `scripts/notebooks/train_hey_gemma.ipynb` — notebook Colab
   listo con instructiones embebidas (upload .zip del dataset
   → train → download .onnx).
3. `gemma4_agent/voice/wake_oww.py` modificado para soportar
   modelo local custom además de los pre-trained de upstream.
4. `gemma4_agent/voice/models/oww/.gitkeep` + actualización
   de `.gitignore` para excluir `.onnx` del repo.
5. Tests del dataset builder.
6. Docs actualizados.

**Fase B (operador, after commit lands)**:
1. Correr `python scripts/build_wake_dataset.py` localmente
   para generar `wake_dataset.zip`.
2. Subir a Colab el notebook + el .zip.
3. Run all → esperar 30-60min.
4. Descargar `hey_gemma.onnx`.
5. Drop en `gemma4_agent/voice/models/oww/hey_gemma.onnx`.
6. Correr `python scripts/wake_backend_audit.py` para
   benchmark + `python scripts/bench.py` para validar.

Fase B no está en el commit del agente — son instrucciones
operacionales claras documentadas.

---

## REGLAS GENERALES

1. PortandoLoMejor. Un commit chico, prefijo `feat(voice):`.
2. **NO toques** `controller.py`, `recorder.py`, `stt.py`,
   `bench.py`, `wake.py`, `wake_vosk.py`. Solo `wake_oww.py`
   (cambios mínimos para cargar custom local) + scripts +
   notebook + docs.
3. **NO commitees el .onnx**. Es output del operador, no del
   sprint. Está gitignored.
4. **NO commitees el dataset .wav extraído**. También gitignored.
5. **NO subas el notebook a Colab vos mismo** ni intentes
   correrlo — el agente no tiene Colab. Solo prepará el archivo
   listo.
6. Auto-install OK para `librosa` y `soundfile` si hacen falta
   (probablemente `soundfile` ya está; `librosa` se usa para
   augmentation).
7. NO `git add -A`.

---

## FIX R3 — Custom wake-word training pipeline

### R3.1 — scripts/build_wake_dataset.py

CLI:
```bash
python scripts/build_wake_dataset.py
# Outputs: wake_dataset/positive/*.wav (105 clips)
#          wake_dataset/negative_hard/*.wav (~139 clips)
#          wake_dataset/positive_aug/*.wav (positives × 4-5 augmentations)
#          wake_dataset/manifest.json
#          wake_dataset.zip (todo lo anterior, listo para upload)
```

Argumentos opcionales:
- `--no-augmentation` — solo extrae raw clips, sin augmentation
  (más rápido, para debugging del cutting).
- `--out PATH` — directory de salida (default `wake_dataset/`).
- `--no-zip` — no genera el .zip al final.

#### Extracción de positivos

Lee `testaudio_v2_expected.json`, para cada wake con
`expected: True`:

```python
WIN_PRE_S = 0.3
WIN_POST_S = 0.9
clip_start_s = max(0, wake_ts - WIN_PRE_S)
clip_end_s = min(audio_duration, wake_ts + WIN_POST_S)
```

Cada clip:
- Mono 16kHz PCM 16-bit (formato openWakeWord-compatible).
- Naming: `wake_001.wav`, `wake_002.wav`, ..., `wake_105.wav`.
- Si por boundary del audio (primero o último wake) el clip
  sale más corto que `WIN_PRE_S + WIN_POST_S`, **paddeá con
  silencio** al tamaño esperado (1.2s exactos).

#### Augmentation del positivo

Por cada clip positivo, generar **4 variaciones**:
1. **Noise**: agregar gaussian noise SNR=20dB.
2. **Pitch shift**: ±2 semitonos (random 50/50).
3. **Time stretch**: rate 0.95 o 1.05 (random).
4. **Background music**: opcional, requiere bg track —
   skipear si no hay. NO bloqueante.

Usar `librosa.effects.pitch_shift` y `librosa.effects.time_stretch`.
Si `librosa` no está, instalar (es free dep).

Naming: `wake_001_aug1.wav`, `wake_001_aug2.wav`, etc.
Total esperado: 105 × 5 = 525 positivos (1 original + 4 aug).

Si augmentation falla en algún clip individual (librosa raise),
**skip ese aug específico** sin parar el script. Reporta cuántos
augs fueron generados al final.

#### Extracción de hard negatives

Sobre el mismo `Grabación (2).wav`, buscar regiones que NO estén
dentro de `[wake_ts - WIN_PRE_S, wake_ts + WIN_POST_S]` para
ningún wake. Cortar clips de 1.2s no-solapados en esas regiones:

```python
# Algorithm:
# 1. Mark intervals covered by positives as forbidden.
# 2. Walk the audio from 0 to duration, stepping by 1.2s.
# 3. If the candidate window doesn't intersect any forbidden
#    interval, emit it as a hard negative.
```

Output naming: `neg_001.wav`, etc. Esperado: ~139 clips.

Si una candidate window cae sobre silencio largo (RMS muy bajo
< 50), considerar skipearla — silence-only negatives no aportan
información discriminativa. Aplicar un filtro `if rms(clip) >=
SILENCE_RMS_THRESHOLD`. Reporta cuántos hard negatives quedaron
post-filter.

#### Manifest

Generar `wake_dataset/manifest.json` con metadata:

```json
{
  "source_audio": "Grabación (2).wav",
  "source_duration_s": 292.84,
  "window_pre_s": 0.3,
  "window_post_s": 0.9,
  "positives": {
    "raw_count": 105,
    "augmented_count": <N>,
    "total": 105 + <N>
  },
  "hard_negatives": {
    "count": <N>,
    "rms_filter_threshold": 50
  },
  "created_at": "2026-05-18T...",
  "audio_format": "PCM 16-bit, 16kHz, mono"
}
```

#### Tests

`gemma4_agent/test_build_wake_dataset.py`:

Mínimo 5 tests. Usan `tempfile` + `numpy` synthetic WAVs para
no depender del audio real.

1. `test_extract_positive_clip_window_pre_post` — clip de 1.2s
   con boundaries correctos. Validá samples exactos.
2. `test_extract_positive_clip_padding_at_boundary` — wake en
   ts=0.1s con WIN_PRE_S=0.3 → clip empieza en t=0 paddeado
   con silencio para llegar a 1.2s totales.
3. `test_hard_negatives_dont_overlap_positives` — synthetic
   audio + synthetic JSON con 3 wakes; valida que las regiones
   negative no intersectan las positive windows.
4. `test_silence_filter_skips_quiet_clips` — clip con RMS<50
   debe ser skipped. Clip con RMS≥50 debe ser emitido.
5. `test_augmentation_count_matches_expected` — N positivos
   con augmentation=True → 5×N clips totales (1 raw + 4 aug).
   Si librosa raise sobre 1 clip → 5×N - 1.

### R3.2 — scripts/notebooks/train_hey_gemma.ipynb

Notebook Colab con secciones:

**Cell 1 (markdown)**: introducción.
```
# Training "hey gemma" wake-word model

Sprint R3 of the gemma4_agent project. Trains a custom
openWakeWord model on the operator's annotated audio.

**Time**: ~30-60min on T4 GPU.
**Inputs**: wake_dataset.zip (uploaded in Cell 2).
**Output**: hey_gemma.onnx (downloaded in Cell 7).
```

**Cell 2 (code)**: install + setup.
```python
!pip install -q openwakeword onnxruntime
import openwakeword
print("openwakeword:", openwakeword.__version__)
```

**Cell 3 (code)**: upload dataset.
```python
from google.colab import files
print("Upload wake_dataset.zip from build_wake_dataset.py output:")
uploaded = files.upload()
!unzip -q wake_dataset.zip
!ls wake_dataset/
```

**Cell 4 (code)**: validate dataset.
```python
import json
with open("wake_dataset/manifest.json") as f:
    manifest = json.load(f)
print(f"Positives: {manifest['positives']['total']}")
print(f"Hard negatives: {manifest['hard_negatives']['count']}")
assert manifest['positives']['raw_count'] >= 100, "Need >=100 raw positives"
```

**Cell 5 (code)**: configure training. La API exacta de
openWakeWord training puede variar entre versiones —
**el agente DEBE chequear la versión instalada y usar la API
correcta**. Pseudo-código:

```python
from openwakeword.train import train_custom_model_pipeline

config = {
    "wake_word": "hey_gemma",
    "positive_clips_dir": "wake_dataset/positive",
    "positive_augmented_dir": "wake_dataset/positive_aug",
    "hard_negative_clips_dir": "wake_dataset/negative_hard",
    "use_default_negatives": True,  # download upstream negatives
    "target_metric": "f1",
    "target_metric_floor": 0.80,
    "training_steps": 10000,
    "batch_size": 64,
    "early_stopping": True,
    "early_stopping_patience": 5,
}
```

Si la API real de `openwakeword.train` difiere de lo de arriba,
el agente DEBE adaptar este cell para que matche la versión.
Consultar `dir(openwakeword.train)` y docstrings del package
instalado.

**Cell 6 (code)**: training run + métricas en vivo.

**Cell 7 (code)**: export to ONNX + download.
```python
from google.colab import files
files.download("hey_gemma.onnx")
print("Save to: gemma4_agent/voice/models/oww/hey_gemma.onnx")
```

**Cell 8 (markdown)**: instrucciones post-download.
```
## Después de descargar

1. Drop `hey_gemma.onnx` en
   `gemma4_agent/voice/models/oww/hey_gemma.onnx`.
2. Run: `python scripts/wake_backend_audit.py`
3. Run: `python scripts/bench.py --threshold wake_recall`

Expected: wake_recall ≥0.70 y precision ≥0.80.
Si no llega: ver R3 follow-ups en sprint doc.
```

### R3.3 — gemma4_agent/voice/wake_oww.py cambios mínimos

Cargar modelo local custom si existe, fallback a pre-trained.

ANTES (en R2):
```python
OWW_MODEL_NAME = "hey_jarvis"
...
self._model = openwakeword.Model(
    wakeword_models=[OWW_MODEL_NAME]
)
```

DESPUÉS:
```python
OWW_CUSTOM_MODEL_PATH = ROOT / "voice/models/oww/hey_gemma.onnx"
OWW_FALLBACK_MODEL_NAME = "hey_jarvis"  # used if custom missing

def _load_model(self):
    if OWW_CUSTOM_MODEL_PATH.exists():
        logger.info("Loading custom hey_gemma model from %s",
                    OWW_CUSTOM_MODEL_PATH)
        return openwakeword.Model(
            wakeword_models=[str(OWW_CUSTOM_MODEL_PATH)]
        ), "hey_gemma"
    else:
        logger.warning(
            "Custom hey_gemma model not found at %s -- falling back to %s. "
            "Run Sprint R3 to train it.",
            OWW_CUSTOM_MODEL_PATH, OWW_FALLBACK_MODEL_NAME
        )
        return openwakeword.Model(
            wakeword_models=[OWW_FALLBACK_MODEL_NAME]
        ), OWW_FALLBACK_MODEL_NAME
```

`self._model_name` recibe el nombre devuelto por `_load_model`
para usar en `scores[self._model_name]` cuando hace `predict`.

### R3.4 — .gitignore + .gitkeep

```
# Add to .gitignore:
gemma4_agent/voice/models/oww/*.onnx
wake_dataset/
wake_dataset.zip
```

```
# Create empty file:
gemma4_agent/voice/models/oww/.gitkeep
```

Esto asegura que el directorio existe (para que `_load_model`
no falle por dir missing) pero no committea el modelo (es output
del operador).

### R3.5 — Docs

Actualizar `docs/architecture/wake_custom_training_path.md`
(creado en Sprint R2):

- Marcar "PENDING" → "IMPLEMENTED in Sprint R3 (commit <hash>)".
- Agregar sección "Running the training" con los pasos de
  Fase B.
- Documentar acceptance bar (recall ≥0.70 AND precision ≥0.80)
  citando memoria [[project-vosk-baseline-characterization]].

Si el docs file no existe (porque R2 outcome fue distinto),
crear `docs/architecture/wake_training_runbook.md` con todo
desde cero.

### R3.6 — Tests adicionales para wake_oww

`gemma4_agent/test_wake_oww.py` (extender el existente):

1. `test_custom_model_loaded_when_exists` — mockeá
   `OWW_CUSTOM_MODEL_PATH.exists() = True`, validá que
   `Model(wakeword_models=[<path>])` se llama con el path
   absoluto.
2. `test_fallback_to_jarvis_when_custom_missing` — sin file,
   validá que se carga `hey_jarvis` y se loggea warning con
   mención a "Run Sprint R3".
3. `test_model_name_attribute_matches_loaded` — `self._model_name`
   refleja qué modelo se cargó (importante para `scores[name]`
   lookup).

### R3.7 — Validación post-download (instrucciones operator)

Al terminar Colab, el operador corre:

```bash
# 1. Validate the file landed correctly:
python -c "
from pathlib import Path
p = Path('gemma4_agent/voice/models/oww/hey_gemma.onnx')
print(f'exists: {p.exists()}, size: {p.stat().st_size if p.exists() else 0} bytes')
"
# Expected: exists=True, size~1-3MB

# 2. Run backend audit:
python scripts/wake_backend_audit.py
# Expected: oww/hey_gemma with recall >>0.057 + precision >=0.80

# 3. Run bench:
python scripts/bench.py
# Expected: wake_recall metric reflects the custom model
```

### R3.8 — Commit

```
feat(voice): custom hey-gemma wake-word training pipeline

Sprint R2 + R2.5 left:
  - WakeDetector with oww/vosk backend orchestration
  - bench measuring true recall with ±1s matching
  - Vosk characterized: precision=0.857, recall=0.057

This commit lands the pipeline for training a custom
"hey gemma" openWakeWord model:

1. scripts/build_wake_dataset.py extracts 105 positive clips
   (1.2s windows, no overlap) + ~139 hard negatives from the
   gaps in Grabación (2).wav. Augmentation produces ~525 total
   positives (5x via noise/pitch/time-stretch).

2. scripts/notebooks/train_hey_gemma.ipynb is a ready-to-run
   Colab notebook. Operator uploads wake_dataset.zip, runs
   all cells (~30-60min on free T4), downloads hey_gemma.onnx.

3. wake_oww.py auto-detects gemma4_agent/voice/models/oww/hey_gemma.onnx
   on load. Falls back to hey_jarvis with a clear warning if
   missing.

4. .gitignore excludes the .onnx (operator-output, not repo
   artifact).

Acceptance bar for the trained model (per
project-vosk-baseline-characterization memory):
  - recall >= 0.70  (12x improvement over Vosk's 0.057)
  - precision >= 0.80  (don't regress below Vosk's 0.857 floor)

Sprint outcome is the pipeline + integration. The actual
training run happens operator-side after this commit lands.
Re-run of scripts/bench.py post-training will measure the
true effect.

Tests: test_build_wake_dataset.py (5 tests) + extensions to
test_wake_oww.py (3 new tests). Suite green.
```

---

## REPORTE FINAL

Devolveme:

1. Hash del commit.
2. Output de `python -m pytest gemma4_agent/test_build_wake_dataset.py -v`.
3. Output de `python -m pytest gemma4_agent/test_wake_oww.py -v`
   (debe incluir los 3 nuevos tests + los 10 existentes).
4. Output de `python -m pytest gemma4_agent/ -q --tb=line`
   (suite completa).
5. Output de `python scripts/build_wake_dataset.py` corriendo
   contra `Grabación (2).wav` real. Esperás:
   ```
   Reading testaudio_v2_expected.json...
   Loaded 105 wakes from operator annotations.
   Extracting positive clips...
   Wrote 105 positives to wake_dataset/positive/
   Generating augmentations (4x per clip)...
   Wrote N augmented clips (~420 expected, fewer if some failed)
   Extracting hard negatives...
   Wrote N hard negatives to wake_dataset/negative_hard/ (~139 expected)
   Wrote manifest.json
   Wrote wake_dataset.zip (NN MB)
   Done.
   ```
   El .zip generado **NO** debe committearse.
6. **Auditoría del notebook**: pegame el output de
   `head -50 scripts/notebooks/train_hey_gemma.ipynb` o un
   pretty-print del JSON del notebook para que pueda verificar
   estructura sin abrirlo en Colab.
7. Confirmá que `python scripts/bench.py --threshold wake_recall`
   sigue corriendo (debe usar `hey_jarvis` como fallback porque
   el .onnx custom aún no existe). El número debe ser
   ~igual al de R2.5 (0.057 con Vosk default; si oww/jarvis
   se activa explícitamente, ~0.000).

## CRITERIO DE ÉXITO

- 1 commit aterrizado.
- `scripts/build_wake_dataset.py` corre sin error contra el
  audio real y produce `wake_dataset.zip` consumible por Colab.
- `scripts/notebooks/train_hey_gemma.ipynb` es un .ipynb válido
  con 8 cells según R3.2.
- `gemma4_agent/voice/wake_oww.py` carga `.onnx` local si
  existe, fallback a `hey_jarvis` si no.
- `.gitignore` excluye `wake_dataset/`, `wake_dataset.zip`,
  `*.onnx` en el path de models.
- ≥5 tests del builder + ≥3 tests nuevos del oww (total ≥8).
- Suite completa verde (baselines 3a + E.5 + flaky timing).
- Docs actualizados con runbook.

## NO HACER (anti-scope)

- NO entrenes el modelo. Eso es operator-side post-commit.
- NO descargues modelos `.onnx` "de internet" para pretend que
  entrenaste. El sprint produce el PIPELINE; el modelo sale
  del Colab del operador.
- NO commitees el `.zip` ni los `.wav` extraídos. Son outputs
  derivables.
- NO toques `bench.py`. La métrica ya es correcta (R2.5). Si
  el custom requiere ajustar threshold de oww, eso es post-R3.
- NO toques `WAKE_DEBOUNCE_S` ni timing constants. Calibrar
  esos sobre el detector custom es post-R3, sprint dedicado
  separado.
- NO inventes hyperparameters del training. Usar defaults
  sensatos según docstrings de `openwakeword.train`. Si los
  defaults no son adecuados (raro), documentar por qué se
  cambian en un comment.
- NO commitees el notebook con outputs ejecutados. Cells
  deben estar limpios (sin output) para que git diff sea claro
  en sprints futuros.

## Follow-ups documentados

1. **Sprint R3.1 (operator)**: correr el Colab. No es trabajo
   del agente. ETA ~30-60min Colab + 10min download/install.

2. **Sprint R3.2 — Threshold calibration**: una vez que el
   custom esté funcionando, sweepear `OWW_THRESHOLD` (hoy 0.5)
   con `wake_backend_audit.py` para encontrar el punto óptimo
   F1 sobre Grabación (2) Y respetando precision ≥0.80. Sprint
   chico (~30min) post-R3.

3. **Si recall <0.70 con dataset actual**: opciones:
   (a) Grabar 30-50 muestras adicionales del operador en
       sesiones distintas (distinto día, micrófono, ambiente
       acústico) para diversificar el dataset. Re-correr R3.
   (b) Aumentar augmentation: más SNRs, más pitch shifts,
       reverb, room impulse responses.
   (c) Esperar a tener una segunda sesión grabada del operador
       (futuro testaudio_v3.wav) y entrenar con dataset
       combinado.
   Todas son sprints chicos. (a) es probablemente el path más
   efectivo si dataset homogéneo es el problema.

4. **Si precision <0.80**: hard negative mining más agresivo.
   Generar negatives sintéticos con TTS diciendo palabras
   foneticamente cercanas: "ay gema", "hey jefe", "ven Lema",
   "hi gema", "tema", "ay vela". Re-entrenar.

5. **Custom model en `~/.gemma4/models` vs repo**: hoy va al
   repo (path relativo). Cuando el modelo sea estable y
   versionado, considerar moverlo a `~/.gemma4/models/oww/`
   para consistencia con Vosk + Whisper. Hoy en el repo es
   más simple para iterar.

6. **Migración a backend default oww**: una vez que custom
   pase el bench, cambiar el default de `wake.py` orchestrator
   de `"auto"` (preferir oww si carga) a explícito
   `"oww-required"` con error claro si falta. Hoy auto+fallback
   es defensivo; cuando confiemos en oww, fail-fast es mejor.
