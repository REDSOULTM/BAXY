# HOTFIX 2026-05-17 (N) — Whisper-large ground truth + WER/CER comparison

> Sprint para establecer un baseline objetivo de transcripción.
> El operador grabó `Grabación (2).m4a` (~5 min, repertorio amplio)
> y los sprints anteriores (L → M.1 → M.2 → M) lo usaron para
> diagnosticar bugs vía recordings. Pero hasta ahora no tenemos
> métrica objetiva de "qué tan lejos del óptimo está el pipeline
> Whisper-small actual". Este sprint corre Whisper-large-v3 sobre
> el mismo audio para usarlo como ground truth, y calcula WER/CER
> contra el output actual del pipeline.

---

## Por qué

El sprint M.2 expuso `whisper_raw_text` en el manifest, lo que nos
dejó ver qué texto produce Whisper-small antes del quality filter.
Vimos cosas como:

```
k=0  raw='Abre Chrome. Gemma, abre Steam. Gemma, abre Chrome...'
k=4  raw='Gemma, Open Chrome. Gemma, Open Chrome. Gemma, Close Steam.'
```

Whisper-small está transcribiendo razonablemente bien speech
rapid-fire, pero el quality filter lo mata con `ngram_repetition`.
**Pero también vemos cosas como**:

```
k=5  raw='Gemma, pon mi Stranger Things en Netflix...'
                ^^^ "pon mi" vs "ponme" — error chico pero real
```

Sin ground truth no podemos distinguir:
- ¿Whisper-small dijo "pon mi" porque el operador lo dijo así, o
  porque small es peor que large para voseo?
- ¿El reject del quality filter era legítimo (audio realmente
  ruidoso) o falso positivo (audio limpio rechazado)?

**Whisper-large como ground truth** responde estas preguntas
con autoridad. Y deja la infraestructura para que cuando otros
operadores (en cualquier idioma) graben su propio test set, la
misma comparación corra automáticamente.

---

## OBJETIVO

Un commit chico. Nuevo script `scripts/testaudio_groundtruth.py`
+ un report markdown + tests del shape del output. NO toca el
pipeline real.

Entregables concretos:

1. **`scripts/testaudio_groundtruth.py`**: toma un path al audio
   (default: `gemma4_agent/voice/tests/Grabación (2).m4a`).
   Convierte a WAV 16kHz mono si hace falta (vía ffmpeg).
   Corre `faster-whisper large-v3` con default settings + idioma
   auto-detect. Produce 2 JSONs.

2. **`testaudio_groundtruth_full.json`**: transcripción continua
   con timestamps por segment. Estructura:
   ```json
   {
     "source_file": "Grabación (2).m4a",
     "model": "large-v3",
     "language_detected": "es",
     "language_probability": 0.99,
     "total_duration_s": 292.8,
     "segments": [
       {"id": 0, "start": 0.0, "end": 5.4, "text": "...",
        "avg_logprob": -0.21, "no_speech_prob": 0.01},
       ...
     ],
     "manual_correction": "",
     "generated_at": "2026-05-18T..."
   }
   ```

3. **`testaudio_groundtruth_aligned.json`**: por cada wake
   detection del análisis existente (`testaudio_analysis.json`),
   extraer la ventana 15s post-wake del audio y transcribirla con
   Whisper-large. Estructura:
   ```json
   {
     "source_file": "Grabación (2).m4a",
     "alignment_source": "testaudio_analysis.json",
     "wake_count": 6,
     "turns": [
       {
         "k": 0,
         "wake_ts_s": 1.82,
         "small_raw_text": "Abre Chrome. Gemma, abre Steam. Gemma, abre Chrome...",
         "small_reject_reason": "ngram_repetition",
         "large_text": "Abre Chrome. Gemma, abre Steam.",
         "large_avg_logprob": -0.18,
         "large_no_speech_prob": 0.02,
         "wer": 0.32,
         "cer": 0.18,
         "verdict": "small_overproduced"  // see verdicts below
       },
       ...
     ]
   }
   ```

4. **`testaudio_groundtruth_report.md`**: legible para humanos.
   Resumen ejecutivo + tabla por turn + lista de issues
   identificados.

5. **Tests** del shape de los JSON outputs (`test_groundtruth_shape.py`)
   — NO integration tests que carguen Whisper-large (demasiado
   pesado para CI).

---

## REGLAS GENERALES

1. PortandoLoMejor. Un commit chico (`feat(voice): whisper-large
   ground truth for testaudio + WER/CER comparison`).
2. **NO modifiques** el pipeline real: ni quality_check, ni VAD
   threshold, ni BoH list, ni el `_transcribe_buffer`. Este sprint
   solo agrega herramientas de medición offline.
3. **NO reemplaces** Whisper-small por large en el pipeline.
   Large es solo offline para ground truth.
4. **Operator memory: install authorization granted** —
   "User granted blanket permission to install missing deps
   without re-asking. Purchase-guard still applies to paid
   software." `jiwer` (~100KB pure Python, MIT license, free)
   se instala normalmente con `pip install jiwer`. Hacelo al
   inicio del script si el import falla:

   ```python
   try:
       import jiwer  # noqa: F401
   except ImportError:
       import subprocess, sys
       subprocess.check_call([sys.executable, "-m", "pip", "install", "jiwer"])
       import jiwer  # noqa: F401
   ```

   El módulo `faster_whisper` ya está. Si en tu entorno aparece
   otra dep faltante para Whisper-large (e.g. `ctranslate2`
   binarios), instalala con el mismo patrón.

   `requirements.txt` se actualiza con `jiwer` agregada al final.
5. **NO commitees** texto que pueda contener PII operator-side.
   Los JSONs sí van al repo (mismo treatment que
   `testaudio_analysis.json`), pero verificá visualmente que no
   incluyan nombres personales / contacto info antes del commit.
   Si encontrás PII, agregá una entry al `.gitignore` para ese
   JSON específico y comunicalo en el reporte.
6. NO `git add -A`.

---

## FIX N.1 — Script `scripts/testaudio_groundtruth.py`

### N.1.1 — Estructura del script

```python
"""Whisper-large ground truth generation for testaudio (Sprint N).

Runs faster-whisper large-v3 offline over an operator-provided
audio file to produce a high-quality reference transcription. The
output is used to compare against the production pipeline (Whisper-
small + quality_check) by computing WER/CER per turn.

Usage:
    python scripts/testaudio_groundtruth.py
    python scripts/testaudio_groundtruth.py path/to/audio.m4a
    python scripts/testaudio_groundtruth.py --no-aligned

Outputs (siblings of the audio file's parent dir):
    testaudio_groundtruth_full.json     — continuous transcription
                                           with per-segment timestamps
    testaudio_groundtruth_aligned.json  — per-wake alignment vs the
                                           Sprint M.1 analysis output
    testaudio_groundtruth_report.md     — human-readable report

NOT a unit-tested module — this is operator tooling. Tests cover
the JSON shape (shape contract), not the integration with Whisper.

Model download: first run will fetch faster-whisper large-v3
(~1.5 GB int8 weights) into the standard HF cache. Subsequent
runs reuse it.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np

# Resolve repo root regardless of cwd.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.voice.audio_io import SAMPLE_RATE  # noqa: E402

logger = logging.getLogger("groundtruth")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


# --- WER/CER -------------------------------------------------------

def _ensure_jiwer():
    """Import jiwer; install it on first run if missing (operator
    install-authorization is granted per project memory)."""
    try:
        import jiwer  # type: ignore
        return jiwer
    except ImportError:
        logger.info("Installing jiwer (one-time, ~100KB)...")
        import subprocess as _sp
        _sp.check_call([sys.executable, "-m", "pip", "install", "jiwer"])
        import jiwer  # type: ignore
        return jiwer


def _compute_wer_cer(reference: str, hypothesis: str) -> tuple[float | None, float | None]:
    """Return (WER, CER) for a reference/hypothesis pair.

    Both reference and hypothesis are normalized: lower-cased,
    leading/trailing whitespace stripped. We do NOT strip
    punctuation — punctuation differences are legit transcription
    errors (e.g. small puts a period where large doesn't).

    Returns (None, None) when the reference is empty (WER/CER
    are undefined in that case). Otherwise returns floats.
    """
    jiwer = _ensure_jiwer()
    ref = (reference or "").strip().lower()
    hyp = (hypothesis or "").strip().lower()
    if not ref:
        return None, None
    wer = jiwer.wer(ref, hyp)
    cer = jiwer.cer(ref, hyp)
    return float(wer), float(cer)


# --- Audio conversion -----------------------------------------------

def _ensure_wav(audio_path: Path) -> Path:
    """Convert audio to WAV 16kHz mono int16 if it isn't already.

    Returns the WAV path (same dir, .wav extension). Idempotent —
    if the WAV exists and is newer than the source, reuses it."""
    if audio_path.suffix.lower() == ".wav":
        # Trust the operator that an existing .wav is in the right
        # format. If not, faster-whisper will read it anyway via
        # its own loader.
        return audio_path
    wav_path = audio_path.with_suffix(".wav")
    if wav_path.exists() and wav_path.stat().st_mtime >= audio_path.stat().st_mtime:
        logger.info(f"Reusing existing {wav_path.name}")
        return wav_path
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "ffmpeg not found in PATH. Install with: winget install ffmpeg"
        )
    logger.info(f"Converting {audio_path.name} -> {wav_path.name} (16kHz mono int16)")
    cmd = [
        "ffmpeg", "-y", "-i", str(audio_path),
        "-ac", "1", "-ar", str(SAMPLE_RATE), "-sample_fmt", "s16",
        str(wav_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-500:]}")
    return wav_path


def _load_audio_int16(wav_path: Path) -> np.ndarray:
    """Read a WAV into a 1-D int16 numpy array."""
    with wave.open(str(wav_path), "rb") as wf:
        assert wf.getframerate() == SAMPLE_RATE, (
            f"Expected {SAMPLE_RATE} Hz, got {wf.getframerate()}"
        )
        assert wf.getnchannels() == 1, "Expected mono"
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16)


# --- Whisper-large loader -------------------------------------------

def _load_whisper_large(model_size: str = "large-v3"):
    """Load faster-whisper large-v3. ~1.5GB download on first run.

    Uses int8 compute type on CPU for memory efficiency. On GPU,
    fp16. The default settings are TOO conservative: we deliberately
    disable the in-model VAD filter because the operator pipeline
    already had its own VAD; we want raw Whisper output."""
    from faster_whisper import WhisperModel  # lazy import
    logger.info(f"Loading faster-whisper {model_size}... "
                "(first run downloads ~1.5GB)")
    t0 = time.time()
    # Try GPU first; fall back to CPU.
    try:
        model = WhisperModel(model_size, device="cuda", compute_type="float16")
        logger.info(f"Loaded on cuda/float16 in {time.time() - t0:.1f}s")
    except Exception as exc:
        logger.info(f"GPU load failed ({exc}); falling back to CPU/int8")
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        logger.info(f"Loaded on cpu/int8 in {time.time() - t0:.1f}s")
    return model


# --- Full transcription --------------------------------------------

def _transcribe_full(model, wav_path: Path) -> dict[str, Any]:
    """Run Whisper-large on the full file. Returns the structured
    JSON-ready dict."""
    logger.info("Running large-v3 over full audio...")
    t0 = time.time()
    segments, info = model.transcribe(
        str(wav_path),
        language=None,           # auto-detect
        vad_filter=False,        # no VAD — we want raw output
        beam_size=5,             # default for large
        temperature=0.0,
        # NOTE: NO initial_prompt. We want unbiased ground truth.
    )
    # `segments` is a generator; force materialization.
    out_segments = []
    for s in segments:
        out_segments.append({
            "id": int(s.id),
            "start": round(float(s.start), 3),
            "end": round(float(s.end), 3),
            "text": s.text.strip(),
            "avg_logprob": round(float(s.avg_logprob), 4),
            "no_speech_prob": round(float(s.no_speech_prob), 4),
            "compression_ratio": round(float(s.compression_ratio), 4),
        })
    elapsed = time.time() - t0
    logger.info(f"Full transcription done in {elapsed:.1f}s "
                f"({len(out_segments)} segments)")
    with wave.open(str(wav_path), "rb") as wf:
        total_s = wf.getnframes() / wf.getframerate()
    return {
        "source_file": wav_path.name,
        "model": "large-v3",
        "language_detected": info.language,
        "language_probability": round(float(info.language_probability), 4),
        "total_duration_s": round(total_s, 2),
        "segments": out_segments,
        "manual_correction": "",  # operator fills in if needed
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "transcribe_elapsed_s": round(elapsed, 2),
    }


# --- Aligned per-wake transcription ---------------------------------

def _verdict(small_raw: str, small_reason: str, large_text: str) -> str:
    """Classify the small-vs-large divergence.

    - 'agree': both transcribed roughly the same; pipeline rejected
      for a legitimate reason.
    - 'small_overproduced': small's raw_text is significantly longer
      than large's — the rapid-fire / window-too-long bug.
    - 'small_underproduced': small produced less than large — STT
      under-coverage.
    - 'small_rejected_legit': small rejected AND large agrees there
      isn't useful speech (no_speech_prob > 0.5 on large).
    - 'small_rejected_false_positive': small rejected but large
      has clear speech — calibration target.
    - 'undetermined': default when none of the above fits.
    """
    if not large_text.strip():
        if small_reason in ("no_speech", "no_speech_prob", "too_short"):
            return "small_rejected_legit"
        return "undetermined"
    if not small_raw.strip():
        return "small_underproduced"
    small_len = len(small_raw.split())
    large_len = len(large_text.split())
    if small_len > large_len * 1.4:
        return "small_overproduced"
    if small_len < large_len * 0.6:
        return "small_underproduced"
    if small_reason and small_reason != "ok":
        return "small_rejected_false_positive"
    return "agree"


def _transcribe_aligned(model, audio: np.ndarray,
                        analysis_path: Path) -> dict[str, Any] | None:
    """Per-wake-detection transcription. Returns None if the analysis
    file isn't found."""
    if not analysis_path.exists():
        logger.warning(f"{analysis_path} not found — skipping aligned pass")
        return None
    with open(analysis_path, encoding="utf-8") as fh:
        analysis = json.load(fh)
    WINDOW_S = 15.0
    WAKE_TAIL_S = 0.5
    turns = []
    for entry in analysis.get("all_results", []):
        wake_idx = int(entry.get("wake_sample_idx", -1))
        if wake_idx < 0:
            continue
        start_idx = max(0, wake_idx - int(WAKE_TAIL_S * SAMPLE_RATE))
        end_idx = min(len(audio), wake_idx + int(WINDOW_S * SAMPLE_RATE))
        segment = audio[start_idx:end_idx].astype(np.float32) / 32768.0
        small_raw = entry.get("whisper_raw_text") or entry.get("text") or ""
        small_reason = entry.get("reject_reason") or ""
        t0 = time.time()
        segs, info = model.transcribe(
            segment,
            language=None,
            vad_filter=False,
            beam_size=5,
            temperature=0.0,
        )
        large_pieces = []
        large_no_speech = []
        large_logprob = []
        for s in segs:
            large_pieces.append(s.text.strip())
            large_no_speech.append(float(s.no_speech_prob))
            large_logprob.append(float(s.avg_logprob))
        large_text = " ".join(p for p in large_pieces if p).strip()
        avg_no_speech = float(np.mean(large_no_speech)) if large_no_speech else None
        avg_logprob = float(np.mean(large_logprob)) if large_logprob else None
        wer, cer = _compute_wer_cer(large_text, small_raw)
        elapsed = time.time() - t0
        turns.append({
            "k": entry.get("k"),
            "wake_ts_s": entry.get("wake_ts_s"),
            "small_raw_text": small_raw,
            "small_reject_reason": small_reason,
            "large_text": large_text,
            "large_avg_logprob": round(avg_logprob, 4) if avg_logprob is not None else None,
            "large_no_speech_prob": round(avg_no_speech, 4) if avg_no_speech is not None else None,
            "wer": round(wer, 4) if wer is not None else None,
            "cer": round(cer, 4) if cer is not None else None,
            "verdict": _verdict(small_raw, small_reason, large_text),
            "large_elapsed_s": round(elapsed, 2),
        })
        logger.info(f"  k={entry.get('k')} verdict={turns[-1]['verdict']} "
                    f"wer={turns[-1]['wer']}")
    return {
        "source_file": analysis.get("source_file"),
        "alignment_source": analysis_path.name,
        "wake_count": len(turns),
        "turns": turns,
    }


# --- Report markdown -----------------------------------------------

def _write_report(full: dict, aligned: dict | None, out_path: Path) -> None:
    lines = []
    lines.append(f"# testaudio ground-truth report")
    lines.append("")
    lines.append(f"- Source: `{full['source_file']}`")
    lines.append(f"- Model: `faster-whisper {full['model']}`")
    lines.append(f"- Language: `{full['language_detected']}` "
                 f"(prob={full['language_probability']})")
    lines.append(f"- Duration: {full['total_duration_s']}s "
                 f"({full['total_duration_s']/60:.2f} min)")
    lines.append(f"- Segments (continuous): {len(full['segments'])}")
    lines.append(f"- Generated: {full['generated_at']}")
    lines.append("")

    # Continuous transcription preview
    lines.append("## Continuous transcription (first 20 segments)")
    lines.append("")
    lines.append("| Start | End | Text | no_speech | logprob |")
    lines.append("|---|---|---|---|---|")
    for s in full["segments"][:20]:
        text = s["text"].replace("|", "\\|")
        lines.append(f"| {s['start']:.2f}s | {s['end']:.2f}s | {text} | "
                     f"{s['no_speech_prob']} | {s['avg_logprob']} |")
    if len(full["segments"]) > 20:
        lines.append(f"\n*({len(full['segments']) - 20} more segments — "
                     f"see testaudio_groundtruth_full.json)*")
    lines.append("")

    # Aligned comparison
    if aligned is not None:
        lines.append("## Per-wake alignment (small vs large)")
        lines.append("")
        lines.append("| k | wake_ts | small_reject | verdict | WER | CER |")
        lines.append("|---|---|---|---|---|---|")
        for t in aligned["turns"]:
            wer = f"{t['wer']:.2f}" if t['wer'] is not None else "—"
            cer = f"{t['cer']:.2f}" if t['cer'] is not None else "—"
            reason = t['small_reject_reason'] or "ok"
            lines.append(f"| {t['k']} | {t['wake_ts_s']:.2f}s | {reason} | "
                         f"{t['verdict']} | {wer} | {cer} |")
        lines.append("")

        # Verdict distribution
        from collections import Counter
        counts = Counter(t["verdict"] for t in aligned["turns"])
        lines.append("### Verdict distribution")
        lines.append("")
        for verdict, n in counts.most_common():
            lines.append(f"- **{verdict}**: {n}")
        lines.append("")

        # Detailed per-turn comparison
        lines.append("### Per-turn detail")
        lines.append("")
        for t in aligned["turns"]:
            lines.append(f"#### Turn k={t['k']} (t={t['wake_ts_s']:.2f}s)")
            lines.append("")
            lines.append(f"- **verdict**: {t['verdict']}")
            lines.append(f"- **small reject**: `{t['small_reject_reason']}`")
            lines.append(f"- **small raw text**:")
            lines.append(f"  > {t['small_raw_text'] or '(empty)'}")
            lines.append(f"- **large text**:")
            lines.append(f"  > {t['large_text'] or '(empty)'}")
            if t["wer"] is not None:
                lines.append(f"- WER: {t['wer']:.2%} · CER: {t['cer']:.2%}")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Ground truth is from Whisper-large-v3. NOT absolute "
                 "truth — large can still err on dialect-specific forms "
                 "(voseo) and uncommon proper nouns. Annotate corrections "
                 "in `manual_correction` field of testaudio_groundtruth_full.json.*")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Wrote report to {out_path}")


# --- CLI ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate Whisper-large ground truth for an audio file."
    )
    parser.add_argument(
        "audio_path",
        nargs="?",
        default=str(ROOT / "gemma4_agent" / "voice" / "tests" / "Grabación (2).m4a"),
        help="Path to operator's audio. Default: Grabación (2).m4a"
    )
    parser.add_argument(
        "--no-aligned",
        action="store_true",
        help="Skip the per-wake alignment pass (faster; only continuous output)",
    )
    parser.add_argument(
        "--model",
        default="large-v3",
        help="faster-whisper model size (default: large-v3)",
    )
    args = parser.parse_args()

    audio_path = Path(args.audio_path)
    if not audio_path.exists():
        sys.exit(f"Audio not found: {audio_path}")
    out_dir = audio_path.parent
    full_out = out_dir / "testaudio_groundtruth_full.json"
    aligned_out = out_dir / "testaudio_groundtruth_aligned.json"
    report_out = out_dir / "testaudio_groundtruth_report.md"
    analysis_path = out_dir / "testaudio_analysis.json"

    wav_path = _ensure_wav(audio_path)
    audio = _load_audio_int16(wav_path)

    model = _load_whisper_large(args.model)

    full = _transcribe_full(model, wav_path)
    # Preserve operator's original filename in source_file (not the .wav)
    full["source_file"] = audio_path.name
    with open(full_out, "w", encoding="utf-8") as fh:
        json.dump(full, fh, indent=2, ensure_ascii=False)
    logger.info(f"Wrote {full_out}")

    aligned = None
    if not args.no_aligned:
        aligned = _transcribe_aligned(model, audio, analysis_path)
        if aligned is not None:
            with open(aligned_out, "w", encoding="utf-8") as fh:
                json.dump(aligned, fh, indent=2, ensure_ascii=False)
            logger.info(f"Wrote {aligned_out}")

    _write_report(full, aligned, report_out)

    print()
    print("=" * 60)
    print(f"Ground truth: {full_out.name}")
    if aligned is not None:
        print(f"Aligned:      {aligned_out.name}")
    print(f"Report:       {report_out.name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

### N.1.2 — Ejecutar el script

Después de crearlo, correrlo:

```bash
python scripts/testaudio_groundtruth.py
```

Esperado:
- Primera corrida: ~5 min para descargar large-v3 + 5-20 min de
  transcripción (depende si GPU está disponible).
- Genera los 3 archivos en `gemma4_agent/voice/tests/`.

Si la descarga del modelo falla por red:
- Reportá la falla.
- Marcá los outputs como SKIPPED.
- Commiteá el script igual; el operador podrá correrlo después.

### N.1.3 — Verificación visual del output

Antes de commitear los JSONs, ABRÍ y mirá:

a. `testaudio_groundtruth_full.json`: los primeros 5 segments
   deberían tener texto coherente y `no_speech_prob` razonable
   (< 0.5 si hay speech, > 0.5 si es silencio).

b. `testaudio_groundtruth_aligned.json`: verificá que la
   `verdict` distribution tenga sentido — si todo cae en
   `agree`, algo está roto.

c. `testaudio_groundtruth_report.md`: leer la sección "Per-turn
   detail" y confirmar que `small_raw_text` vs `large_text` se
   ve razonable.

### N.1.4 — PII scan

Antes del commit, scan visual de los 3 archivos:

```bash
grep -iE "(juan|maria|pedro|hermana|novia|esposo|esposa|@gmail|@hotmail|@outlook|\+[0-9]{2,})" \
     gemma4_agent/voice/tests/testaudio_groundtruth_*.json \
     gemma4_agent/voice/tests/testaudio_groundtruth_report.md
```

Si aparecen matches (probablemente sí — la lista de comandos del
operador incluía "mandale un mensaje a Juan"), eso es PII
potencial. Decisión:

- Si los nombres son **claramente comandos del repertorio de test**
  (Juan, etc), commitealos. Son ficticios para testing.
- Si son **claramente personales** del operador, reportalo y
  agregá los archivos al `.gitignore`:
  ```
  # Operator-provided ground truth contains PII; not committed.
  gemma4_agent/voice/tests/testaudio_groundtruth_full.json
  gemma4_agent/voice/tests/testaudio_groundtruth_aligned.json
  gemma4_agent/voice/tests/testaudio_groundtruth_report.md
  ```

Default: asumí que es test data (commitealo). Si dudás, gitignore
y reportalo en el commit message.

---

## FIX N.2 — Tests del shape

`gemma4_agent/test_groundtruth_shape.py`:

```python
"""Shape contract for the Sprint N ground truth outputs.

These tests do NOT run Whisper-large — they validate that IF the
script produced an output, it has the right structure. Integration
testing (does Whisper-large actually run?) is a manual smoke step.

If the JSON outputs don't exist yet, all tests skip cleanly.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GT_DIR = ROOT / "voice" / "tests"
FULL = GT_DIR / "testaudio_groundtruth_full.json"
ALIGNED = GT_DIR / "testaudio_groundtruth_aligned.json"


class GroundTruthFullShapeTest(unittest.TestCase):
    @unittest.skipUnless(FULL.exists(), f"{FULL} not yet generated")
    def test_full_has_required_top_level_fields(self) -> None:
        with open(FULL, encoding="utf-8") as fh:
            d = json.load(fh)
        for k in [
            "source_file", "model", "language_detected",
            "language_probability", "total_duration_s",
            "segments", "manual_correction", "generated_at",
        ]:
            self.assertIn(k, d, f"missing field: {k}")

    @unittest.skipUnless(FULL.exists(), f"{FULL} not yet generated")
    def test_full_segments_have_required_fields(self) -> None:
        with open(FULL, encoding="utf-8") as fh:
            d = json.load(fh)
        self.assertGreater(len(d["segments"]), 0, "no segments produced")
        for s in d["segments"][:5]:
            for k in ["id", "start", "end", "text",
                      "avg_logprob", "no_speech_prob"]:
                self.assertIn(k, s, f"segment missing field: {k}")
            self.assertIsInstance(s["text"], str)
            self.assertGreaterEqual(s["end"], s["start"])

    @unittest.skipUnless(FULL.exists(), f"{FULL} not yet generated")
    def test_full_model_is_large(self) -> None:
        with open(FULL, encoding="utf-8") as fh:
            d = json.load(fh)
        self.assertIn("large", d["model"].lower(),
                      f"model should be a large variant, got {d['model']!r}")


class GroundTruthAlignedShapeTest(unittest.TestCase):
    @unittest.skipUnless(ALIGNED.exists(), f"{ALIGNED} not yet generated")
    def test_aligned_has_required_top_level_fields(self) -> None:
        with open(ALIGNED, encoding="utf-8") as fh:
            d = json.load(fh)
        for k in ["source_file", "alignment_source",
                  "wake_count", "turns"]:
            self.assertIn(k, d, f"missing field: {k}")

    @unittest.skipUnless(ALIGNED.exists(), f"{ALIGNED} not yet generated")
    def test_aligned_turns_have_required_fields(self) -> None:
        with open(ALIGNED, encoding="utf-8") as fh:
            d = json.load(fh)
        for t in d["turns"]:
            for k in ["k", "wake_ts_s", "small_raw_text",
                      "small_reject_reason", "large_text", "verdict"]:
                self.assertIn(k, t, f"turn missing field: {k}")

    @unittest.skipUnless(ALIGNED.exists(), f"{ALIGNED} not yet generated")
    def test_aligned_verdicts_are_valid(self) -> None:
        valid = {
            "agree", "small_overproduced", "small_underproduced",
            "small_rejected_legit", "small_rejected_false_positive",
            "undetermined",
        }
        with open(ALIGNED, encoding="utf-8") as fh:
            d = json.load(fh)
        for t in d["turns"]:
            self.assertIn(t["verdict"], valid,
                          f"unexpected verdict: {t['verdict']!r}")


class WerCerTest(unittest.TestCase):
    """The script auto-installs jiwer if missing (per operator
    install-authorization memory). After running the script once,
    jiwer should be importable and WER/CER should produce numeric
    results for non-empty references."""

    def test_compute_wer_cer_perfect_match_is_zero(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "testaudio_groundtruth",
            ROOT.parent / "scripts" / "testaudio_groundtruth.py",
        )
        if spec is None or spec.loader is None:
            self.skipTest("script not importable")
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:
            self.skipTest(f"script imports failed: {exc}")
        wer, cer = mod._compute_wer_cer("hello world", "hello world")
        self.assertIsNotNone(wer, "jiwer should auto-install on demand")
        self.assertEqual(wer, 0.0)
        self.assertEqual(cer, 0.0)

    def test_compute_wer_cer_empty_reference_is_none(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "testaudio_groundtruth",
            ROOT.parent / "scripts" / "testaudio_groundtruth.py",
        )
        if spec is None or spec.loader is None:
            self.skipTest("script not importable")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        wer, cer = mod._compute_wer_cer("", "anything")
        self.assertIsNone(wer)
        self.assertIsNone(cer)


if __name__ == "__main__":
    unittest.main()
```

---

## FIX N.3 — Commit

```
feat(voice): whisper-large ground truth + WER/CER comparison

Establishes a baseline of "what Whisper-large-v3 would transcribe"
for the operator's testaudio recording, then compares it against
the production pipeline (Whisper-small + quality_check) per wake
detection.

Sprint context:
  L:   recorded audio + manifest in ~/.gemma4/recordings/
  M.1: 4 recorder polish fixes (race, conf, reason, eager)
  M.2: wake debounce 2.0→0.8 + Whisper raw_text exposed
  M:   BoH 'musica' false-positive eliminated
  N:   ↑ this — large-v3 ground truth for the same audio

The script is operator tooling, not pipeline code. It runs offline,
takes minutes, and produces:
  - testaudio_groundtruth_full.json — continuous transcription
    of the entire audio with timestamps & per-segment confidence.
  - testaudio_groundtruth_aligned.json — per-wake-detection
    comparison: small_raw_text vs large_text + WER/CER + verdict
    classification (agree / small_overproduced / small_under /
    small_rejected_legit / small_rejected_false_positive).
  - testaudio_groundtruth_report.md — human-readable summary.

Verdict classes are the actionable signal:
  - 'small_overproduced': pipeline catches multiple commands in
    a 15s window (rapid-fire); large bounds it tighter. Suggests
    we need VAD-based endpointing in the wake→trim pipeline.
  - 'small_rejected_false_positive': quality_check killed speech
    that large transcribed cleanly. Suggests filter is too
    aggressive (next calibration sprint).
  - 'small_rejected_legit': quality_check killed garbage that
    large also marks as no_speech. Filter works correctly here.
  - 'agree': both transcribed roughly the same; no action.

NO pipeline changes. Pure measurement infrastructure.

Dependencies: faster-whisper (already installed). jiwer (~100KB,
MIT) is auto-installed via pip on first script run; per operator
install-authorization memory, missing free deps are installed
automatically. Added to requirements.txt for reproducibility.

PII note: the operator's testaudio includes commands like
'mandale un mensaje a Juan'. Those names are test repertoire,
not personal contacts, and are committed. If a future audio
includes real personal data, the script's PII grep step will
catch it before commit.

Tests cover the JSON shape contract; integration is a manual
smoke (run the script once, verify outputs look reasonable).
```

---

## REPORTE FINAL

Devolveme:
1. Hash del commit.
2. Output de `python scripts/testaudio_groundtruth.py` (la
   primera corrida — esperás ~10-25 min total con descarga +
   transcripción).
3. Output de `python -m pytest gemma4_agent/test_groundtruth_shape.py -v`.
4. Output de `python -m pytest gemma4_agent/ -q --tb=line`
   (suite completa).
5. Contenido completo de
   `gemma4_agent/voice/tests/testaudio_groundtruth_report.md`.
6. Verdict distribution del aligned JSON (Counter de verdicts).
7. Si encontraste PII en los outputs, el grep + decisión tomada.

## CRITERIO DE ÉXITO

- 1 commit aterrizado.
- Suite completa verde (modulo Sprint 3a + E.5 xfail).
- `testaudio_groundtruth_full.json` con ≥1 segment transcripto.
- `testaudio_groundtruth_aligned.json` con `wake_count` matcheando
  los wakes del análisis existente (6 post-M.2.2).
- `testaudio_groundtruth_report.md` legible y con verdict
  distribution clara.
- ≥5 tests nuevos verdes (shape contracts).
- `jiwer` queda instalado (auto-install en primera corrida) y
  agregado a `requirements.txt`.
- WER/CER calculados para cada turn que tenga `large_text` no
  vacío.

## NO HACER (anti-scope)

- NO reemplaces Whisper-small por large en el pipeline real.
  Large es offline-only para ground truth.
- NO modifiques el `quality_check`, BoH list, VAD threshold,
  logprob thresholds, ngram threshold. Acción sobre eso requiere
  un sprint propio CON el data de este sprint como evidencia.
- Auto-install de deps faltantes está autorizado (operator
  memory: install-authorization). NO le pidas permiso al
  operador para `pip install jiwer` ni para cualquier otra dep
  free que falte. Para software pagado / con licencia comercial
  sí hay que pedir permiso (purchase-guard).
- NO toques el recorder, controller, planner, router, las 65
  tools, los prompts. Cero cambios al runtime path.
- NO commitees nombres personales del operador si los detectás
  en los outputs. Si dudás, gitignore.
- NO cargues Whisper-large en los tests. Demasiado pesado para
  CI/dev loop. Los shape tests usan los JSONs YA generados, NO
  re-corren la transcripción.
- Si la descarga del modelo falla, reportá el error y commiteá
  el script igual. El operador puede correr el script más tarde
  cuando tenga conectividad.

## Follow-ups documentados (NO en este sprint)

1. **Si verdict distribution muestra ≥3 `small_overproduced`**:
   confirmación del bug arquitectónico (ventana 15s post-wake
   atrapa rapid-fire). Próximo sprint: VAD-based endpointing en
   `_transcribe_buffer` para cerrar la ventana al primer silencio
   sostenido (~700ms).
2. **Si verdict distribution muestra ≥2
   `small_rejected_false_positive`**: el quality_check está muy
   estricto. Datos para un sprint de threshold tuning con probes
   específicos.
3. **Si WER promedio > 0.40 en `agree` cases**: Whisper-small en
   este corpus está mucho peor que large. Considerar upgrade a
   `small-v3` o `medium` si latency lo permite.
4. **Si large transcribe voseo perfectamente y small no**:
   confirmación de que el tamaño del modelo importa para
   dialectos minoritarios. Argumento para considerar el upgrade.
5. **Sprint follow-up para `testaudio_v2/`**: nuevo audio nativo
   en WAV (no m4a) para descartar la hipótesis de codec damage
   del Sprint M.2. Si Vosk recall sube en WAV nativo, el problema
   era conversion; si no, es Vosk small es-0.42.
