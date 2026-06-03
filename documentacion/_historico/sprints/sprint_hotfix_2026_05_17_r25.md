# HOTFIX 2026-05-17 (R2.5) — Fix bench wake_recall + add precision metric

> Sprint chico (~30min), alto ROI. Sprint R2 reveló un bug
> fundamental en `scripts/bench.py::measure_wake_recall`:
>
>   `recall = fires / expected_count`
>
> No hay matching por timestamp. Si Vosk dispara 105 veces
> aleatoriamente, `recall = 1.0`. Si dispara 6 veces correctas,
> "0.057". Si dispara 6 veces totalmente erradas, también
> "0.057". Los tres casos son indistinguibles para el bench.
>
> Antes de Sprint R3 (custom training), arreglá el bench para
> que mida la realidad. Si no, R3 podría entregar un modelo que
> dispara fantasmas y el bench diría "PASS".

---

## Contexto

El bug está en
[scripts/bench.py:165-180](../../../scripts/bench.py):

```python
CHUNK = 512
for i in range(0, len(audio) - CHUNK, CHUNK):
    det.feed(audio[i:i + CHUNK])
fires = len(detections)
if TEST_V2_EXPECTED.exists():
    with open(TEST_V2_EXPECTED, encoding="utf-8") as fh:
        expected = json.load(fh)
    expected_count = sum(1 for e in expected.get("wakes", []) if e.get("expected"))
    recall = fires / max(1, expected_count)  # <-- BUG
```

**Comparado con `scripts/wake_backend_audit.py` que SÍ está bien**:

```python
# scripts/wake_backend_audit.py:_match_detections
def _match_detections(detections_s, expected_s, tolerance_s=1.0):
    """Bipartite-greedy match. Each expected wake can absorb at
    most one detection within tolerance; remaining detections are
    false positives.
    Returns (tp, fp, fn).
    """
    used_expected = [False] * len(expected_s)
    tp = 0
    fp = 0
    for d in detections_s:
        best_i = -1
        best_gap = tolerance_s + 1.0
        for i, e in enumerate(expected_s):
            if used_expected[i]:
                continue
            gap = abs(d - e)
            if gap <= tolerance_s and gap < best_gap:
                best_i = i
                best_gap = gap
        if best_i >= 0:
            used_expected[best_i] = True
            tp += 1
        else:
            fp += 1
    fn = sum(1 for u in used_expected if not u)
    return tp, fp, fn
```

La lógica correcta ya existe — está en el audit del Sprint R2.
El sprint es **portarla al bench**, con tests que cubran los
casos degenerados (random fires, perfect match, etc.).

---

## OBJETIVO

Un commit chico. Reemplazar `recall = fires / expected_count` con
el matching real. Bonus: agregar **precision** como métrica
secundaria al bench (no es threshold formal pero se va a
necesitar en R3 para validar el modelo custom).

**No es trivial**:
1. No romper la API del `ThresholdResult` (otros scripts pueden
   leer los outputs JSON históricos).
2. Tests robustos contra los 3 casos degenerados que hoy el
   bench no distingue.
3. Mantener retrocompatibilidad: si `--threshold wake_recall`
   se corre sin `expected.json`, debe SKIP como ahora (no
   romper).

---

## REGLAS GENERALES

1. PortandoLoMejor. Un commit chico, prefijo `fix(ops):`.
2. **NO toques** `wake.py`, `wake_oww.py`, `wake_vosk.py`,
   `controller.py`, `recorder.py`, `stt.py`. Pure ops fix.
3. **NO crees un nuevo módulo de matching**. Importá la función
   de `scripts/wake_backend_audit.py` o copiala literal a
   `scripts/bench.py`. Una sola fuente de verdad.
4. NO `git add -A`.
5. **NO bajes el threshold formal del bench** (`wake_recall >=
   0.70`). El bug es del medidor, no del target.

---

## FIX R2.5 — Bench wake_recall matched

### R2.5.1 — Portar la lógica de matching

Decisión de diseño: ¿importar de `scripts/wake_backend_audit.py`
o copiar literal?

**Recomendado: copiar literal a `scripts/bench.py`**. Razones:
- `scripts/` no es un paquete Python (no tiene `__init__.py`).
  Importar de otro script requiere manipular `sys.path` o
  refactor mayor.
- La función `_match_detections` son ~20 líneas. La duplicación
  es trivial y los tests cubren ambas copias.
- Reduce coupling: el bench no depende de que el audit existe.

Si más adelante hay un 3er consumer, refactorizar a un módulo
compartido en `gemma4_agent/voice/_matching.py`. Hoy con 2
consumers no se justifica.

### R2.5.2 — Cambio exacto en bench.py

Reemplazar las líneas 165-189 con:

```python
CHUNK = 512
for i in range(0, len(audio) - CHUNK, CHUNK):
    det.feed(audio[i:i + CHUNK])

# Sprint R2.5 2026-05-18: convert detection wall-clock timestamps
# to audio-relative timestamps. The detector reports time.monotonic()
# at the moment of the callback, NOT the position in the audio file.
# We compute audio position via len-fed proxy.
# Actually: easier path -- iterate with index and stamp the chunk
# midpoint as the audio-relative time of any fire that landed in
# that window. See R2.5.2.a below.

# After the loop above, `detections` is a list of (wall_ts, phrase,
# confidence) tuples. We need audio-relative timestamps for matching
# against expected_s (which are audio-relative).
# ...
```

**Detalle crítico — convertir wall_clock_ts a audio-relative**:

El `WakeDetector` callback recibe `time.monotonic()` (wall-clock)
no la posición en el audio. Para matchear contra el JSON expected
(que tiene `timestamp_s` audio-relative) hay que convertir. Dos
opciones:

**Opción 1**: Reinstrumentar el feed loop para stampear cada
fire con el offset del audio:

```python
detections_audio_s: list[float] = []

def _on_wake(phrase: str, ts: float, tail_s: float = 0.0,
             confidence: float = 0.0) -> None:
    # NOTE: ts is wall-clock; we don't use it for matching.
    # The current audio offset is captured by the enclosing
    # loop via a mutable [last_offset_s].
    detections_audio_s.append(_last_offset[0])

_last_offset = [0.0]
det = WakeDetector(on_wake=_on_wake)
if not det.load():
    return ThresholdResult(...)

CHUNK = 512
for i in range(0, len(audio) - CHUNK, CHUNK):
    _last_offset[0] = i / SAMPLE_RATE
    det.feed(audio[i:i + CHUNK])
```

Esto está bien para tolerance ±1s. El error de localización es
máximo `CHUNK/SAMPLE_RATE = 32ms`, muy debajo del ±1s window.

**Opción 2**: post-procesar las wall_clock_ts pero requiere
sincronizar reloj inicial. Más frágil. **NO usar.**

### R2.5.3 — Estructura final del medidor

```python
def measure_wake_recall() -> ThresholdResult:
    audio_path, note = _pick_reference_audio()
    if audio_path is None: ...  # idem
    if not TEST_V2_EXPECTED.exists() and audio_path == TEST_V2: ...

    audio = _load_wav(audio_path)
    from gemma4_agent.voice.wake import WakeDetector

    detections_audio_s: list[float] = []
    _last_offset = [0.0]

    def _on_wake(phrase, ts, tail_s=0.0, confidence=0.0):
        detections_audio_s.append(_last_offset[0])

    det = WakeDetector(on_wake=_on_wake)
    if not det.load():
        return ThresholdResult(... note=f"Wake load failed: {det.last_error}")

    CHUNK = 512
    for i in range(0, len(audio) - CHUNK, CHUNK):
        _last_offset[0] = i / SAMPLE_RATE
        det.feed(audio[i:i + CHUNK])

    if not TEST_V2_EXPECTED.exists():
        # No ground truth -- report fires raw, SKIP.
        return ThresholdResult(... passed=None,
            note=f"fires={len(detections_audio_s)} on {audio_path.name}; no expected.json",
            details={"fires": len(detections_audio_s)})

    with open(TEST_V2_EXPECTED, encoding="utf-8") as fh:
        expected = json.load(fh)
    expected_s = sorted(
        float(w["timestamp_s"])
        for w in expected.get("wakes", [])
        if w.get("expected", True)
    )

    tp, fp, fn = _match_detections(detections_audio_s, expected_s)
    fires = tp + fp
    recall = tp / max(1, len(expected_s))
    precision = tp / max(1, fires) if fires > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)

    return ThresholdResult(
        "wake_recall", recall,
        THRESHOLDS["wake_recall"]["target"],
        THRESHOLDS["wake_recall"]["op"],
        passed=_compare(recall, THRESHOLDS["wake_recall"]["target"],
                        THRESHOLDS["wake_recall"]["op"]),
        note=f"audio={audio_path.name} ({note}); tp={tp} fp={fp} fn={fn}",
        details={
            "fires": fires,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "expected": len(expected_s),
            "precision": round(precision, 3),
            "f1": round(f1, 3),
        },
    )
```

Y agregá la función `_match_detections` cerca del top del
módulo (después de los imports). Copiada literal del audit.

### R2.5.4 — Tests

`gemma4_agent/test_bench_wake_recall.py`:

Mínimo 5 tests. NO requieren audio real ni Vosk — usan fakes
del WakeDetector vía monkey-patching o llamando directo a
`_match_detections`.

1. `test_match_perfect`: detections == expected → tp = N, fp = 0,
   fn = 0, recall = 1.0, precision = 1.0.

2. `test_match_no_detections`: detections vacías → tp = 0,
   fp = 0, fn = len(expected), recall = 0.0, precision = 0.0.

3. **`test_match_random_fires_dont_inflate_recall`** (el test
   crítico — caso degenerado del bug):
   ```python
   # 100 random fires uniformly spread across 300s of audio.
   # 50 expected wakes at fixed timestamps far from random ones.
   # Old buggy bench: recall = 100/50 = 2.0 (>>1.0 nonsensical).
   # New bench: recall <= 1.0, likely very low.
   detections = [3.0 * i for i in range(100)]   # 0, 3, 6, ..., 297
   expected = [1.5, 4.5, 7.5, ..., 148.5]        # 0.5s offset, never matches
   tp, fp, fn = _match_detections(detections, expected, tolerance_s=0.25)
   assert tp == 0
   assert recall == 0.0
   ```

4. `test_match_within_tolerance`: detection at 10.4s vs expected
   at 10.0s with tolerance 1.0 → tp = 1 (matched).
   Outside tolerance: detection at 12.0s vs expected at 10.0s
   with tolerance 1.0 → tp = 0, fp = 1.

5. `test_match_one_to_one_no_double_counting`: 2 detections both
   near the same expected wake → only 1 tp (the closer one),
   1 fp.
   ```python
   detections = [10.1, 10.2]  # both within tolerance of expected[0]
   expected = [10.0]
   tp, fp, fn = _match_detections(detections, expected)
   assert tp == 1 and fp == 1 and fn == 0
   ```

6. (Opcional, recomendado) `test_measure_wake_recall_smoke`:
   Test integral con monkey-patched `WakeDetector` que dispara
   `on_wake` en timestamps controlados. Validá que el bench
   reporta tp/fp/fn/precision/f1 correctos en `details`.

### R2.5.5 — Re-correr el bench

```bash
python scripts/bench.py --threshold wake_recall
```

Esperado: `wake_recall` ahora es matched recall verdadero.
Probablemente **menos** que el 0.076 actual porque algunos
fires de Vosk pueden estar lejos de wakes esperados. Si la
nueva métrica es ~0.05-0.06 con tp/fp/fn visible en `details`,
eso es honesto y el bench ya no miente.

Reportá los 5 thresholds. `stt_wer_mean=0.521`, `stt_latency_p95`
sin degradar, `wake_recall` con número real, los otros 2
SKIPPED.

### R2.5.6 — Commit

```
fix(ops): bench wake_recall now uses ±1s matching (was fires/expected)

scripts/bench.py::measure_wake_recall was computing
recall = fires / expected_count, with no timestamp alignment.
Random fires would score 1.0; 6 perfect detections and 6 wildly
wrong detections were indistinguishable (both reported "0.057").

Fix: port the bipartite-greedy matcher from
scripts/wake_backend_audit.py (which has had correct matching
since Sprint R2). Each expected wake absorbs at most one
detection within ±1.0s; remaining detections are FP.

Changes:
- bench.py gains a top-level _match_detections() (copied
  literal from wake_backend_audit; no shared module yet --
  refactor when a 3rd consumer appears).
- measure_wake_recall now stamps each fire with its audio-relative
  offset (via _last_offset[0] mutable in the feed loop) and
  passes to the matcher. Localization error is bounded by
  CHUNK/SAMPLE_RATE = 32ms, well within the ±1s tolerance.
- ThresholdResult.details now includes tp, fp, fn, precision,
  f1 in addition to the existing fires/expected count.
- ThresholdResult.note format updated to include "tp=X fp=Y fn=Z".

Threshold formal unchanged: wake_recall >= 0.70 vs target. Bug
was in the meter, not the target.

Bench output post-fix:
  wake_recall  FAIL  <new>  audio=... tp=<X> fp=<Y> fn=<Z>

Tests: test_bench_wake_recall.py covers 5 cases including the
critical "random fires don't inflate recall" regression (which
the old code failed at recall=2.0).

Sprint R3 (custom training "hey gemma") can now trust the
bench to distinguish a real model from a fantasy-firing one.
```

---

## REPORTE FINAL

Devolveme:

1. Hash del commit.
2. Output de `python -m pytest gemma4_agent/test_bench_wake_recall.py -v`.
3. Output de `python -m pytest gemma4_agent/ -q --tb=line`
   (suite completa, no regresa).
4. Output completo de `python scripts/bench.py` (los 5
   thresholds, con el nuevo `wake_recall` y los `tp/fp/fn` en
   note/details).
5. Confirmá explícitamente que `details` del JSON output ahora
   incluye `tp`, `fp`, `fn`, `precision`, `f1`. Pegame el
   bloque JSON del `wake_recall` threshold.
6. **El test crítico #3 (random fires) debe FALLAR si lo corrés
   contra la versión vieja del bench**. Verificá esto pegando la
   salida de:
   ```bash
   git stash  # save the fix
   python -m pytest gemma4_agent/test_bench_wake_recall.py::test_match_random_fires_dont_inflate_recall -v
   # expected: FAIL (the old code would compute recall=2.0)
   git stash pop  # restore the fix
   python -m pytest gemma4_agent/test_bench_wake_recall.py::test_match_random_fires_dont_inflate_recall -v
   # expected: PASS
   ```
   Si esto no se puede hacer cleanly (porque el test importa de
   bench.py donde ya está el fix), simplemente confirmá que el
   test pasa Y que su lógica testea el escenario degenerado del
   bug.

## CRITERIO DE ÉXITO

- 1 commit aterrizado.
- `scripts/bench.py` ya no usa `fires / expected_count`.
- `_match_detections` existe en bench.py (copiada de audit).
- ≥5 tests nuevos verdes.
- Suite completa verde (baselines 3a + E.5 + flaky timing
  admitidos).
- `bench.py --threshold wake_recall` reporta tp/fp/fn/precision/f1.
- `wake_recall` post-fix es honesto (probablemente igual o menor
  que 0.076 anterior; lo importante es que ahora signifique
  algo).

## NO HACER (anti-scope)

- NO refactorices a un módulo `_matching.py` compartido.
  Dos copias trivialmente sincronizables están bien por ahora.
- NO toques `wake_backend_audit.py`. Está bien como está.
- NO cambies el `tolerance_s = 1.0`. Es el mismo que usa el audit
  — consistencia entre métricas matters.
- NO bajes el threshold formal del bench. El bug era de medición,
  no de target.
- NO toques `wake_fp_rate`. Ese threshold tiene su propio camino
  (requiere testaudio_idle.wav operator-side).
- NO toques `measure_stt_wer_mean` aunque tenga un bug parecido
  (lee `small_raw_text` en vez de `small_text`). Eso es Sprint
  O.1 si se decide hacer, no R2.5.
- NO inventes una métrica F0.5 o F2 ponderada. F1 está bien
  para este sprint.

## Follow-ups documentados

1. **R3 — Custom training "hey gemma"**: ahora con bench honesto.
   El sprint puede correr `bench.py` después de entrenar el
   modelo y los números van a significar lo que dicen.

2. **R2.6 — Posible refactor matching**: si en un sprint futuro
   aparece un 3er consumer (e.g. un script de calibración
   continua), refactorizar `_match_detections` a
   `gemma4_agent/voice/_matching.py`. Hoy con 2 consumers no se
   justifica.

3. **Bench precision como threshold formal**: hoy precision es
   métrica secundaria (en details). Si después de R3 el modelo
   custom tiene buen recall pero precision baja (muchos FP), el
   bench podría querer un threshold `wake_precision >= 0.70`.
   Cuando ocurra, agregarlo al `THRESHOLDS` dict + producción
   ready doc. NO ahora.

4. **Localización fina**: el current method estampa el offset
   del chunk donde se llamó `on_wake`. Vosk puede haber juntado
   varios chunks antes de emitir el fire — el offset real puede
   estar hasta 1-2s ANTES del callback. El tolerance ±1s lo
   absorbe pero si en R3 se observa que detecciones legítimas
   caen fuera del ±1s, considerar subir tolerance a ±1.5s o
   usar un timestamp más preciso (Vosk reporta wake_end_s internamente,
   ya pasa a través del callback como `tail_s` que se podría
   restar). Investigación menor — no bloqueante.
