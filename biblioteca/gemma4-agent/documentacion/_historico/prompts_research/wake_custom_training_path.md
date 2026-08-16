# Wake-detection custom training path

> Outcome of Sprint R2 2026-05-18. **Implemented in Sprint R3
> 2026-05-18** (pipeline + tests + notebook). The actual training
> run is operator-side -- this doc is the runbook.

## TL;DR

- Vosk wake_recall over the operator's annotated testaudio is
  **0.057-0.076** (~6-8 detections out of 105 expected).
- openWakeWord with the `hey_jarvis` pre-trained model produced
  **0 detections at any tested threshold (0.05 .. 0.8)** on the
  same audio.
- Phonetic distance "hey gemma" vs "hey jarvis" is too large
  for the pre-trained model to fire even with aggressive
  threshold relaxation.
- **Pre-trained replacement is not viable.** Sprint R2 lands the
  infrastructure (orchestrator with both backends + the audit
  harness) but keeps Vosk as the active default. The next sprint
  (R2.1 / R3) trains a custom "hey gemma" detector.

## Audit raw numbers

```
| Backend           | Threshold | Fires | TP  | FP  | Recall | Precision | F1     |
|-------------------|-----------|-------|-----|-----|--------|-----------|--------|
| vosk              | n/a       | 7-8   | 6-8 | 0-1 | 0.057  | 0.857-1.0 | 0.107  |
| oww/hey_jarvis    | 0.05      | 0     | 0   | 0   | 0.000  | 0.000     | 0.000  |
| oww/hey_jarvis    | 0.10      | 0     | 0   | 0   | 0.000  | 0.000     | 0.000  |
| oww/hey_jarvis    | 0.30      | 0     | 0   | 0   | 0.000  | 0.000     | 0.000  |
| oww/hey_jarvis    | 0.50      | 0     | 0   | 0   | 0.000  | 0.000     | 0.000  |
| oww/hey_jarvis    | 0.80      | 0     | 0   | 0   | 0.000  | 0.000     | 0.000  |
```

The audit ran with a +/- 1.0s match tolerance against the 105
expected wake timestamps in `testaudio_v2_expected.json`.

## Why hey_jarvis doesn't transfer

openWakeWord models are trained on **a specific wake phrase**.
The model's first-layer features encode "hey jarvis"-specific
formant trajectories; "hey gemma" produces different spectral
patterns the model never learned to map to high score. The
upstream training notebook (Colab, "Custom Wake Word Models")
documents this directly: cross-phrase transfer is not a goal of
the architecture.

Other pre-trained models in the openWakeWord catalogue (`alexa`,
`hi_jeff`, `timer`) have the same problem: they're tuned for
their own phrase. None are phonetically close enough to "hey
gemma" to be useful as a surrogate.

## What custom training requires

### Dataset

- **Positives (~100-500 clips, ~1s each)**: clips of the
  operator saying "hey gemma". We already have a ready-made
  source: `gemma4_agent/voice/tests/Grabacion (2).wav` is
  annotated with 105 timestamps in `testaudio_v2_expected.json`,
  so cutting `[t-0.5s, t+0.5s]` windows around each one yields
  the positive dataset.
  - Note: the WAV is an m4a-to-WAV conversion (Windows Sound
    Recorder AAC original). AAC artifacts may degrade the
    training set; consider re-recording directly to PCM 16kHz
    if the initial training run plateaus. Not blocking for
    the first attempt.
- **Negatives (~500-2000 clips)**: any audio without "hey
  gemma". The openWakeWord training pipeline includes a
  pre-built negative set from Common Voice + Audioset; we
  augment with the silence stretches of `Grabacion (2).wav`
  between the positive windows. Plus background noise (kitchen
  appliances, music, TV).
- **Synthetic positives (optional, recommended)**: openWakeWord
  ships a Piper-TTS-based synthetic positive generator. Useful
  if real positives are < 200. Generates clips in many voices
  to improve speaker generalization.

### Training

Upstream provides:
- `openwakeword.train.train_custom_model_pipeline` (one-shot
  pipeline, 30-60 min on a free Colab GPU).
- Manual notebook for tighter control.

The output is a single ONNX file (~1-3 MB) that drops into our
`gemma4_agent/voice/wake_oww.py` by setting
`OWW_MODEL_NAME` to the new model name (or pointing to the
custom .onnx path directly).

### Validation criterion

After training, re-run `scripts/wake_backend_audit.py` against
the same `Grabacion (2).wav` + `testaudio_v2_expected.json`.

Acceptance bar for the follow-up sprint:
- **Recall >= 0.70** at a threshold that also keeps
  **precision >= 0.85**.
- F1 >= 0.75.

If those numbers land, flip the default backend in
`gemma4_agent/voice/wake.py:WakeDetector.__init__` from `"vosk"`
back to `"auto"`. Vosk stays as the fallback.

## Estimated effort

- Dataset cutting + augmentation: ~2 hours (script + manual
  inspection).
- Training run on Colab: ~1 hour.
- Audit + iteration on threshold: ~1 hour.
- **One dedicated sprint** (1-2 days end-to-end). The infra
  this sprint (R2) already landed -- orchestrator, env-var
  switch, audit harness -- so the follow-up just plugs the
  trained ONNX into the existing slot.

## Running the training (Sprint R3 runbook)

The pipeline this doc planned is now landed. **Operator-side**
workflow:

1. **Build the dataset locally** (~30s):
   ```
   python scripts/build_wake_dataset.py
   ```
   Produces `wake_dataset/` (positives + augmented + hard
   negatives + manifest.json) and `wake_dataset.zip`. Both are
   gitignored; the zip is the artifact you upload to Colab.

2. **Train on Colab** (~30-60 min on a free T4):
   - Open `scripts/notebooks/train_hey_gemma.ipynb` in Colab.
   - Runtime -> Change runtime type -> GPU (T4 is fine).
   - Run all cells. Cell 3 prompts you to upload
     `wake_dataset.zip`. Cell 7 downloads `hey_gemma.onnx`.

3. **Drop the trained model into the repo**:
   ```
   mv ~/Downloads/hey_gemma.onnx gemma4_agent/voice/models/oww/hey_gemma.onnx
   ```
   The `.onnx` is gitignored (operator output, not source
   artifact).

4. **Validate against the bench**:
   ```
   python -c "from pathlib import Path; p = Path('gemma4_agent/voice/models/oww/hey_gemma.onnx'); print(f'exists={p.exists()}, size={p.stat().st_size if p.exists() else 0}')"
   python scripts/wake_backend_audit.py    # sweep thresholds
   python scripts/bench.py                  # production-readiness check
   ```

5. **If acceptance bar met** (see below), flip the
   orchestrator default from `"vosk"` to `"auto"`:
   ```python
   # gemma4_agent/voice/wake.py:WakeDetector.__init__
   backend: BackendName = "auto",  # was "vosk"
   ```

## Acceptance bar

Per the [[project-vosk-baseline-characterization]] memory:

- **Recall >= 0.70** (12x Vosk's 0.057).
- **Precision >= 0.80** (don't regress below Vosk's 0.857 floor).

Both gates must pass simultaneously. A custom model that hits
recall but tanks precision (recall=0.90 + precision=0.50) is
**not shippable** -- false positives interrupt the operator and
are worse UX than the conservative Vosk baseline.

## What this sprint shipped instead

- `gemma4_agent/voice/wake_vosk.py`: verbatim cut-paste of the
  pre-R2 wake.py Vosk implementation. Class renamed to
  `VoskWakeDetector` for clarity.
- `gemma4_agent/voice/wake_oww.py`: openWakeWord backend with
  the same on_wake(phrase, ts, tail_s, confidence) signature.
- `gemma4_agent/voice/wake.py`: orchestrator. Default backend
  is **vosk**; `GEMMA4_WAKE_BACKEND=oww` or `auto` opts in to
  openWakeWord. Re-exports the Vosk constants + helpers so all
  existing imports keep working.
- `scripts/wake_backend_audit.py`: the audit harness. Re-run
  it any time to compare backends, sweep thresholds, or
  validate a new custom model.
- `gemma4_agent/test_wake_oww.py`: 9 tests covering orchestrator
  selection, env-var override, oww silence behavior, chunk
  buffering, callback signature preservation, and re-exports.

## Bench impact

`bench.py wake_recall` was reading the original `wake.py`
WakeDetector (now the orchestrator). With the new default
(backend="vosk"), the bench number doesn't change — Vosk is
still doing the detection. The custom-training sprint will move
the bench needle when the operator's "hey gemma" model lands.
