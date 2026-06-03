# HOTFIX 2026-05-17 (R2) — openWakeWord backend; Vosk to fallback

> Sprint S → Q.0 → T → O dejaron el bench en un estado que
> finalmente apunta al verdadero bottleneck del proyecto:
>
>   `wake_recall = 0.067` — Vosk solo detecta 6 de 90 wakes
>   esperados sobre Grabación (2).wav (que vos anotaste con 105
>   wakes verdaderos).
>
> 93.3% de los wakes legítimos del operador no llegan al pipeline.
> Es el bug más grave del proyecto. Cada otro sprint optimiza
> una superficie que el usuario no toca el 93% del tiempo.
>
> Sprint R2 reemplaza Vosk por **openWakeWord** (modelo neural
> dedicado a wake-detection, no STT genérico). El objetivo es
> mover `wake_recall` de 0.067 a ≥0.70 sobre el audio existente,
> sin romper nada upstream.

---

## Contexto

### Por qué Vosk falla

Vosk es un STT genérico forzado a hacer wake-detection mediante
un `WAKE_VOCAB` restringido. Tres problemas conocidos:

1. **Modelo entrenado para reconocimiento general**, no para
   detección de wake-word específico. "Hey gemma" compite contra
   el lenguaje completo del modelo.
2. **Vocab restrictivo** (`["gemma", "hey gemma", "[unk]"]`) no
   evita falsos negativos — Vosk a veces emite `[unk]` para audio
   que humanamente es claramente "hey gemma".
3. **Sensibilidad fonética baja** para variantes del operador
   ("hey gema", "ey gemma", "hi gemma", ritmos rápidos).

El bench actual lo confirma: el bench reporta 90 wakes esperados
→ 6 detectados (los 105 anotados todos tienen `expected: true`,
así que la discrepancia 90 vs 105 es un bug a investigar en
R2.5 — hay 15 wakes que el bench no está contando; probable
issue con el conteo dentro de `measure_wake_recall`).

**Nota sobre la fuente de audio**: `gemma4_agent/voice/tests/Grabación
(2).wav` fue convertido desde un .m4a (AAC lossy) original de
Windows Sound Recorder. NO existe una versión PCM-nativa del
mismo audio. Los artifacts de compresión AAC pueden hacer que
los resultados de R2 sean **una cota inferior** del verdadero
performance de openWakeWord, no una sobrestimación. Eso es OK
para este sprint — la comparación relativa Vosk-vs-oww sobre el
mismo audio sigue siendo válida.

### Por qué openWakeWord

**openWakeWord** (KrombeBeam / dscripka) es un detector
**específico para wake-words**, no STT genérico. Características
clave para nuestro caso:

- Modelos pre-trained para wakes comunes (incluye "hey jarvis",
  "alexa", etc.) y soporta wake-words custom via fine-tuning.
- **Sin modelo para "hey gemma" oficial** — eso significa que
  vamos a usar el modelo más similar disponible (probablemente
  "hey jarvis" como surrogate inicial) o entrenar custom.
- Latencia: ~10ms por chunk de 80ms en CPU. Mucho más rápido
  que Vosk (~50-100ms).
- Threshold continuo (0–1) en vez de match/no-match. Permite
  calibrar `WAKE_MIN_CONFIDENCE` con datos reales.
- pip-installable, ONNX runtime. Sin compilar nada.

### Restricción importante

**El operador necesita seguir diciendo "hey gemma"**. Si
openWakeWord no tiene un modelo "hey gemma" y los modelos
similares (jarvis, alexa) tienen recall pobre sobre tu audio,
**el sprint debe documentar el camino a custom training** sin
necesariamente ejecutarlo. Custom training requiere ~100-500
clips positivos + negativos, generación sintética posible —
es un sprint dedicado siguiente, no este.

---

## OBJETIVO

Un commit chico que cumpla **una de estas dos opciones**, en
orden de preferencia:

**Opción A (preferida)**: openWakeWord con un modelo pre-trained
disponible (jarvis, alexa, o similar) levantado como backend
detrás de la misma API `WakeDetector`, con bench mostrando
`wake_recall ≥ 0.50` sobre Grabación (2).wav. Si el modelo
disponible no alcanza, **bajá el target** y documentá honesto:
el camino a >0.70 es custom training, sprint siguiente.

**Opción B (fallback honesto)**: si openWakeWord no instala, o
ningún modelo pre-trained mueve la aguja sobre nuestro audio
(porque "hey gemma" es muy distinto fonéticamente a los
disponibles), el sprint termina con un commit que **solo
agrega la dependencia + harness de evaluación** + docs file
explicando "necesita custom training, así es el path".

NO hagas el rewrite ciego. El criterio es: medible mejora real
o documentación honesta del próximo paso.

---

## REGLAS GENERALES

1. PortandoLoMejor. Un commit chico, prefijo `feat(voice):` o
   `chore(voice):` según outcome.
2. **NO toques** `controller.py`, `recorder.py`, `stt.py`,
   `bench.py`. La API de `WakeDetector` se preserva
   exactamente. Solo cambia la implementación interna.
3. **Vosk se queda** como fallback. Si openWakeWord no carga
   (modelo missing, runtime error), el sistema cae a Vosk
   automáticamente. NO borres `wake.py` original.
4. Auto-install OK para `openwakeword` desde pip.
5. NO `git add -A`.
6. **NO entrenes modelos custom en este sprint.** Si lo necesitás,
   documentá el path en un docs file.

---

## FIX R2 — openWakeWord backend con fallback Vosk

### R2.1 — Estructura nueva

Refactor mínimo de `gemma4_agent/voice/wake.py`:

**ANTES** (situación actual):
```
wake.py
  WakeDetector (Vosk-only)
```

**DESPUÉS**:
```
wake.py
  WakeDetector (orchestrator — tries openWakeWord first, falls back to Vosk)
wake_vosk.py    # el código Vosk actual, movido literal
wake_oww.py     # el backend openWakeWord nuevo
```

**Reglas del refactor**:
- `wake.py` exporta la misma `WakeDetector` clase, misma firma
  pública (`load()`, `feed(chunk)`, `WakeCallback` signature).
- `wake_vosk.py` contiene **literalmente** el código Vosk
  actual movido (cut-paste). Cero cambios en lógica Vosk.
- `wake_oww.py` es código nuevo.
- `WakeDetector.__init__` recibe un parámetro nuevo
  `backend: Literal["auto", "oww", "vosk"] = "auto"`. Default
  `"auto"` → intenta oww primero, falls back a vosk si oww
  falla en `load()`.
- Env var override: `GEMMA4_WAKE_BACKEND=vosk|oww|auto` para
  forzar un backend en producción si es necesario.

### R2.2 — openWakeWord install + load

```python
# en wake_oww.py

OWW_MODEL_NAME = "hey_jarvis"  # surrogate inicial; custom training pending
OWW_THRESHOLD = 0.5            # default; calibrar en R2.5

def _ensure_openwakeword():
    try:
        import openwakeword
        return openwakeword
    except ImportError:
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "openwakeword"])
        import openwakeword
        return openwakeword
```

`OpenWakeWordDetector` class con la misma firma que
`WakeDetector` actual:
- `__init__(on_wake: WakeCallback)`
- `load() -> bool` — descarga modelos via
  `openwakeword.utils.download_models()` si no están,
  instancia `openwakeword.Model(wakeword_models=[OWW_MODEL_NAME])`.
- `feed(chunk: np.ndarray)` — chunk de int16 16kHz. openWakeWord
  espera ventanas de 80ms (1280 samples). Si el chunk del caller
  es menor, acumular en buffer interno; si es mayor, slicear.
- `feed` llama `model.predict(chunk)` y revisa
  `scores[OWW_MODEL_NAME]`. Si supera `OWW_THRESHOLD` y respeta
  `WAKE_DEBOUNCE_S`, dispara `on_wake(matched_phrase, ts, tail_s,
  confidence)`.
- **tail_s**: openWakeWord no expone "wake_end_relative_s" como
  Vosk. Usar una heurística: tail_s = max(0, time_since_wake) o
  asumir 0.3s de margen post-trigger (el modelo dispara cuando
  detecta la palabra, asumimos pequeño tail por defecto).

### R2.3 — Orquestador en wake.py

```python
class WakeDetector:
    """Public API unchanged. Internally picks oww or vosk."""

    def __init__(self, on_wake, backend="auto"):
        backend = os.environ.get("GEMMA4_WAKE_BACKEND", backend)
        self._backend_name = backend
        self._oww = None
        self._vosk = None
        self._on_wake = on_wake

    def load(self) -> bool:
        if self._backend_name in {"auto", "oww"}:
            try:
                from .wake_oww import OpenWakeWordDetector
                self._oww = OpenWakeWordDetector(on_wake=self._on_wake)
                if self._oww.load():
                    logger.info("WakeDetector backend: openWakeWord")
                    return True
                else:
                    logger.warning("openWakeWord load failed, falling back to Vosk")
                    self._oww = None
            except Exception as exc:
                logger.warning("openWakeWord init failed: %s", exc)
                self._oww = None
        # Fall back to Vosk
        from .wake_vosk import VoskWakeDetector
        self._vosk = VoskWakeDetector(on_wake=self._on_wake)
        if self._vosk.load():
            logger.info("WakeDetector backend: Vosk")
            return True
        return False

    def feed(self, chunk):
        if self._oww is not None:
            self._oww.feed(chunk)
        elif self._vosk is not None:
            self._vosk.feed(chunk)

    @property
    def last_error(self):
        return getattr(self._oww or self._vosk, "last_error", None)
```

### R2.4 — Tests

`gemma4_agent/test_wake_oww.py`:

Mínimo 6 tests. Algunos requieren openwakeword instalado (skip
limpio si missing):

1. `test_orchestrator_prefers_oww_when_loaded` — patcheá
   `OpenWakeWordDetector.load` para devolver True, validá que
   `WakeDetector` use el oww instance.
2. `test_orchestrator_falls_back_to_vosk_on_oww_fail` — patcheá
   `OpenWakeWordDetector.load` para devolver False, validá que
   el `VoskWakeDetector` se instancie.
3. `test_env_var_forces_vosk` — set
   `GEMMA4_WAKE_BACKEND=vosk`, validá que oww nunca se intente
   cargar.
4. `test_oww_threshold_calibration_smoke` (skip if oww missing) —
   carga el modelo, feedeá silencio (np.zeros), validá que el
   score esté <0.1 (no debe disparar wake en silencio).
5. `test_oww_chunk_buffering` — feedeá chunks de tamaños raros
   (e.g. 512 samples) y validá que el predictor reciba ventanas
   de 1280 samples (acumulación correcta).
6. `test_wake_callback_signature_preserved` — el callback que
   recibe oww debe coincidir con la firma Vosk
   `(phrase, ts, tail_s, confidence)`. Test que verifica que
   recorder/controller no rompen.

### R2.5 — Benchmark + calibración

**Crítico**. El sprint NO termina sin medir esto.

Crear `scripts/wake_backend_audit.py` que:

1. Toma `gemma4_agent/voice/tests/Grabación (2).wav` (o `testaudio_v2.wav` si existe).
2. Toma `gemma4_agent/voice/tests/testaudio_v2_expected.json`.
3. Corre AMBOS backends sobre el audio:
   - Vosk con la implementación actual
   - openWakeWord con `OWW_THRESHOLD` barriendo `[0.3, 0.4, 0.5, 0.6, 0.7, 0.8]`
4. Para cada (backend, threshold), calcula:
   - **recall** = fires_matched / expected_wakes
   - **precision** = fires_matched / total_fires (cuántos fires
     fueron cerca de un wake esperado, ±1s)
   - **F1**
5. Tabula:

```
Backend         Threshold    Fires    TP    FP    Recall    Precision    F1
vosk            (n/a)         6        6     0     0.067     1.000        0.125
oww/jarvis      0.3           XX       XX    XX    XX.XXX    XX.XXX       XX.XXX
oww/jarvis      0.5           ...
...
```

Sugiere el threshold óptimo de openWakeWord para nuestro audio
y reporta la mejora vs Vosk en F1.

### R2.6 — Re-correr el bench

```bash
python scripts/bench.py --threshold wake_recall
```

Esperado **uno de los siguientes outcomes honestos**:

- **A**: `wake_recall` mejora de 0.067 a algo notablemente
  mayor (e.g. 0.30+). Commit lo refleja en el mensaje.
- **B**: `wake_recall` sin mejora significativa porque
  "hey jarvis" no es lo suficiente parecido a "hey gemma".
  En ese caso, el commit incluye un docs file
  `docs/architecture/wake_custom_training_path.md`
  explicando:
  - Por qué pre-trained no alcanza.
  - Cuántas muestras hace falta (~100-500 positivas).
  - El workflow para entrenar custom (`openwakeword`
    tiene scripts de training).
  - Estimación de esfuerzo (~1 sprint dedicado + recolección
    audio del operador).

NO bajes el threshold del bench para hacerlo PASS. El threshold
queda en 0.70. Si el sprint deja `wake_recall = 0.30`, eso
sigue siendo FAIL — pero es **un FAIL 4.5× mejor que el FAIL
actual de 0.067**, y eso es progreso real medible.

### R2.7 — Commit

Dependiendo de outcome:

**Outcome A** (oww funciona):
```
feat(voice): openWakeWord backend; wake_recall 0.067 -> <new>

Vosk small es-0.42 was producing wake_recall = 0.067 on
Grabación (2).wav (6 of 90 expected wakes detected). The
operator reported "le decía 'hey gemma' por lo menos 6 veces y
ninguna me oyó" -- the bench now confirms this quantitatively.

Vosk is a generic STT forced to do wake-detection via vocab
restriction. openWakeWord is a wake-word-specific neural
detector with a continuous threshold (0-1 score). Pre-trained
"hey_jarvis" model is used as surrogate; custom "hey gemma"
training is documented as the next path.

Architecture: same WakeDetector public API. Internal orchestrator
tries openWakeWord first, falls back to Vosk on load failure or
when GEMMA4_WAKE_BACKEND=vosk. Vosk code moved verbatim to
wake_vosk.py; new code in wake_oww.py.

scripts/wake_backend_audit.py sweeps thresholds and reports
recall/precision/F1 for each backend. Optimal threshold for
oww/jarvis on this audio: <X>.

Bench: wake_recall now <new value>. Still FAIL vs 0.70 target,
but <X.X>x improvement over Vosk baseline. Custom training to
reach 0.70+ is a follow-up sprint.

Tests: test_wake_oww.py covers orchestrator preference logic,
fallback path, env var override, chunk buffering, and signature
preservation. Vosk regression: all existing wake tests still
pass against wake_vosk.py.
```

**Outcome B** (oww no mejora suficiente):
```
chore(voice): openWakeWord harness + custom-training path docs

Vosk wake_recall is 0.067 on Grabación (2).wav. Sprint R2
explored openWakeWord as replacement. Pre-trained models
available (hey_jarvis, alexa) achieve recall <X.XXX> on our
audio -- not sufficient to ship as default.

This commit:
- Adds openwakeword as an optional dependency.
- Implements WakeDetector orchestrator with oww/vosk backends
  (GEMMA4_WAKE_BACKEND env var or auto-fallback).
- Vosk remains the active default; oww available for benchmarking.
- scripts/wake_backend_audit.py for backend comparison.
- docs/architecture/wake_custom_training_path.md documents
  the path to a "hey gemma"-specific model: ~100-500 audio
  samples, openwakeword training scripts, estimated effort.

Bench: wake_recall unchanged at 0.067 (Vosk still default).
The harness lets us track recall on alternative models in
future sprints without rewiring the pipeline.
```

---

## REPORTE FINAL

Devolveme:

1. Hash del commit.
2. Output completo de `python scripts/wake_backend_audit.py`
   (la tabla por-backend / threshold con recall/precision/F1).
3. Cuál outcome elegiste (A o B) y POR QUÉ.
4. Si A: el nuevo `wake_recall` del bench. Si B: link al docs
   file con el path a custom training.
5. Output de `python -m pytest gemma4_agent/test_wake_oww.py -v`.
6. Output de `python -m pytest gemma4_agent/ -q --tb=line`
   (suite completa). Confirmá que test_wake_debounce.py,
   test_wake_match.py, test_gx_features.py, test_voice_recorder_m1.py
   siguen pasando — son los que tocan la API de WakeDetector.
7. Output de `python scripts/bench.py` (los 5 thresholds).
8. Confirmación de que `GEMMA4_WAKE_BACKEND=vosk` fuerza el
   path Vosk legacy (test manual o test automated).

## CRITERIO DE ÉXITO

- 1 commit aterrizado (outcome A o B).
- API de `WakeDetector` preservada — controller/recorder no
  tocados.
- Vosk legacy disponible vía env var.
- ≥6 tests nuevos verdes.
- Suite completa verde (baselines 3a + E.5 admitidos).
- `scripts/wake_backend_audit.py` corre y reporta números.
- Si outcome A: `wake_recall` movido sensiblemente (mínimo
  3× el baseline, idealmente >0.30).
- Si outcome B: docs file con path a custom training existe.

## NO HACER (anti-scope)

- NO entrenes modelos custom en este sprint. Si necesitás,
  documentá el path. Custom training es sprint dedicado siguiente.
- NO toques `controller.py`, `recorder.py`, `stt.py`,
  `bench.py`. Si la API de WakeDetector necesita cambiar,
  parar y replantear.
- NO borres `wake.py` ni movés Vosk a un módulo "deprecated".
  Vosk es el fallback funcional — se queda como backend
  válido.
- NO bajes el threshold del bench (0.70). Si el sprint
  no llega ahí, eso es FAIL real y honesto. El próximo sprint
  ataca esa parte.
- NO commitees el modelo openWakeWord al repo (son ~10-100MB
  por modelo). El `download_models()` los baja a `~/.cache`
  en runtime.
- NO toques `WAKE_DEBOUNCE_S` ni `WAKE_MIN_CONFIDENCE`. Esos
  son para Vosk. openWakeWord usa su propio threshold
  (`OWW_THRESHOLD`). Si después de R2 el operador sigue notando
  los 3s de gap entre wakes consecutivos, eso es un sprint
  dedicado a barge-in / debounce-tuning (memory
  [[project-wake-gap-ux-2026-05-18]]).
- NO inventes métricas nuevas en `wake_backend_audit.py`. Recall,
  precision, F1 son suficientes. Latency es bonus opcional —
  pero no es bloqueante.

## Follow-ups documentados

1. **Custom training "hey gemma"** — sprint dedicado siguiente
   (R2.1 o R3 según naming). Recolecta:
   - ~100 positivos del operador (el JSON actual ya tiene 105
     wakes anotados con timestamps; cortar ventanas de ~1s
     alrededor de cada uno produce el dataset positivo).
     **Nota sobre el audio**: Grabación (2).m4a y .wav son la
     misma fuente — el .m4a es la grabación original de Windows
     Sound Recorder (AAC lossy), no PCM crudo. Si custom training
     muestra que los artifacts de compresión AAC degradan el
     dataset positivo, considerar re-grabar el audio del operador
     directamente a PCM 16kHz (script con sounddevice.rec o
     Audacity con export WAV nativo). NO bloqueante — empezar con
     el m4a-derived dataset; re-grabar solo si los resultados lo
     justifican.
   - ~500 negativos (cualquier audio sin "hey gemma" — música,
     conversación, silencio).
   - Entrenar con `openwakeword` training scripts (existen en
     el repo upstream).
   - Validar contra Grabación (2) con expected.json y meta
     wake_recall ≥0.85.

2. **Bench-vs-annotation mismatch** — la nota en R2 menciona
   "90 wakes esperados vs 105 anotados". Investigar si
   `measure_wake_recall` filtra `expected: true` (los 105
   actuales todos lo tienen, así que el conteo debería ser
   105). Si el bench reporta 90, hay un bug. Confirmar en
   R2.5 con un print debug.

3. **Calibración de WAKE_DEBOUNCE_S sobre el nuevo backend**
   — la distribución de gaps en los 105 wakes del operador
   tiene median 2.31s, min 1.34s. Si openWakeWord es más
   sensible y dispara en gaps de 1-2s, podría haber double-fires
   problemáticos. Sprint chico de calibración post-R2.

4. **Si después de R2 el bottleneck sigue siendo grave**
   (recall <0.50): considerar Picovoice Porcupine como
   alternativa comercial (free tier limitado pero permite
   custom keywords). Es plan B si openWakeWord training es
   demasiado costoso.

5. **wake_fp_rate** — bench sigue SKIPPED esperando
   testaudio_idle.wav. Sprint R2 puede agregar al
   wake_backend_audit.py un modo "synthetic idle" que
   feedea silencio + ruido blanco al detector para estimar
   FP rate sin requerir grabación operator-side. No
   bloqueante.
