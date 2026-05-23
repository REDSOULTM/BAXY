# Sprint 8 — Maximizar recall del wake-word "hey gemma"

## Contexto (estado al cierre de Sprint 7, 2026-05-19)

El wake-word funciona por primera vez en 7 sprints. Modelo LiveKit
conv-attention entrenado y conectado al runtime:

- **recall universal = 0.744** @ threshold 0.25 (vs baseline v9 = 0.110)
- **fp/hr = 0.000** sobre 7.7h de LibriSpeech
- Modelo: `gemma4_agent/voice/models/livekit/hey_gemma.onnx` (864 KB)
- Runtime: `gemma4_agent/voice/livekit_runtime.py` (ONNX puro, Python 3.10)
- Entrenamiento: `.venv_livekit` (Python 3.11) + `data/livekit_train/configs/hey_gemma.yaml`

### Recall por idioma (threshold 0.30)
```
FUERTE:  en 0.94  it 0.97  pl 0.90  es 0.85  ru 0.85  fr 0.80  ar 0.75
MEDIO:   de 0.65  sv 0.55  pt 0.53
CERO:    nl 0.00  vi 0.00  zh 0.00   <- arrastran el promedio
```

**El recall global 0.744 está limitado por 3 idiomas en cero (nl/vi/zh).**
Sobre los 10 idiomas restantes el recall ya es ~0.85. La causa raíz: el
modelo se entrenó SOLO con voces inglesas (Piper LibriTTS, 904 speakers
EN). Holandés/vietnamita/mandarín nunca se vieron en training.

## Objetivo Sprint 8

Subir recall universal de 0.744 hacia 0.88-0.93 manteniendo fp/hr ≤ 1.0.

## Plan (3 palancas, en orden de impacto)

### Palanca 1 — Escala completa del MISMO dataset EN (bajo riesgo)
Subir la config de "experimento" a "producción":
- `n_samples`: 5000 → 25000
- `steps`: 30000 → 100000
- `augmentation.rounds`: 3 (mantener)
Esperado: en/it/es/ru suben a 0.90+, recall global ~0.80-0.82.
NO arregla nl/vi/zh. Costo: ~3-4h GPU. **Hacer esto primero como baseline.**

### Palanca 2 — Datos multi-idioma (alto impacto, ataca los ceros)
El gran salto. Generar "hey gemma" con voces NO inglesas:
- Opción A: otros checkpoints Piper multi-speaker (de_DE-mls, fr_FR-mls,
  nl_NL-mls). El backend `piper_vits` de LiveKit acepta UN checkpoint;
  hay que generar afuera con piper-sample-generator (rhasspy) — soporta
  `--model` múltiple — y meter los .wav generados a `livekit-wakeword
  augment` directamente (saltear su `generate`).
- Opción B: resolver el segfault VoxCPM en RTX 40-series. VoxCPM da 30+
  idiomas con 34 voice-design prompts. El segfault es en SDPA durante
  warm-up; intentar workaround `torch.nn.attention.sdpa_kernel(
  [SDPBackend.MATH])` envolviendo `model.generate()`, o correr VoxCPM en
  CPU (`device='cpu'`, lento pero estable, ~5s/clip).
Esperado: recall global 0.85-0.92. Costo: ~4-6h.

### Palanca 3 — Ambas combinadas (máximo)
25k EN + ~10k multi-idioma, 100k steps. Costo: ~6-10h (una noche).
Esperado: 0.88-0.93.

## Restricciones operativas (NO olvidar — causaron 2 reinicios forzados)

1. **ONNX Runtime congela la PC** si no se limita. SIEMPRE importar
   `scripts/_ort_throttle.py` ANTES de cargar cualquier modelo en evals
   batch. Sin eso, ONNX usa los 24 cores + busy-wait → 100% CPU clavado.
   El operador tuvo que reiniciar a la fuerza 2 veces.

2. **Antes de generate/train: cerrar procesos GPU** (juegos, llama-server,
   wallpaper engine). Verificar con `nvidia-smi`. Necesita ≥12GB VRAM libre.

3. **Si el operador está jugando, PARAR.** No competir por GPU.

4. **VoxCPM segfaulta en RTX 40-series** (Ada Lovelace). Si se usa, aplicar
   workaround SDPA-math o CPU mode.

5. **El modelo espera la wake-phrase al FINAL del 2s window.** En eval,
   pad clips cortos al INICIO (audio al final). Pad al final → score ~0.
   Ver `scripts/wake_universal_eval_livekit.py::_score_audio`.

6. **espeak-ng en Windows**: el patch UTF-8 en `_espeak_phonemize` está
   en el venv (`.venv_livekit/.../piper/synthesis.py`), NO en el repo.
   Si se recrea el venv, re-aplicar (text=False + decode utf-8 replace).

## Pasos concretos

```powershell
# 1. Cerrar GPU procs, confirmar VRAM libre
nvidia-smi

# 2. Editar data/livekit_train/configs/hey_gemma.yaml (Palanca 1):
#    n_samples: 25000, steps: 100000

# 3. Pipeline (cada paso ~min/horas, correr en background):
.venv_livekit/Scripts/livekit-wakeword.exe generate data/livekit_train/configs/hey_gemma.yaml
.venv_livekit/Scripts/livekit-wakeword.exe augment  data/livekit_train/configs/hey_gemma.yaml
.venv_livekit/Scripts/livekit-wakeword.exe train    data/livekit_train/configs/hey_gemma.yaml
.venv_livekit/Scripts/livekit-wakeword.exe export   data/livekit_train/configs/hey_gemma.yaml

# 4. Copiar a runtime
cp output/hey_gemma/hey_gemma.onnx gemma4_agent/voice/models/livekit/hey_gemma.onnx

# 5. Eval (con throttle ya integrado en el script)
.venv_livekit/Scripts/python.exe scripts/wake_universal_eval_livekit.py \
    --model gemma4_agent/voice/models/livekit/hey_gemma.onnx \
    --threshold 0.25 --max-negatives 800 --tag sprint8
```

## Gate de aceptación Sprint 8
- recall universal ≥ 0.85 (subir desde 0.744)
- fp/hr ≤ 1.0
- ningún idioma de los "fuertes" actuales baja de 0.80 (no regresión)

## Pendiente independiente: smoke test real
Falta validar con la VOZ REAL del operador (todo el eval fue sintético +
LibriSpeech). Decir "hey gemma" 10-20 veces al micrófono y medir recall.
Arrancar voice mode: `POST /voice/start` (server) o el botón en la UI.
Si engancha ≥8/10 ya es usable; si no, ese dato dice si el training extra
vale la pena antes que cualquier número sintético.
```
```
