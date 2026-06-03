# HOTFIX 2026-05-17 (S) — Acceptance gate + bench harness

> Sprint estratégico. Surgió del informe de investigación
> post-Sprint P. El proyecto tiene 26+ sprints, ~190 tests verdes,
> cero regresiones — y sin embargo no está production-ready, y no
> hay forma de probar lo contrario porque "production-ready"
> nunca se definió. Este sprint cierra ese gap: escribe el
> criterio + el harness que lo mide automáticamente.
>
> NO toca el voice pipeline, NO arregla bugs, NO calibra. Es la
> regla del juego para los próximos 4-9 sprints. Sin esto, los
> siguientes sprints son arbitrarios — con esto, cada commit
> nuevo puede medirse contra un baseline.

---

## Por qué este sprint, no otro

El informe del investigador post-Sprint P fue explícito:

> "Llevás 26 sprints, ~190 tests verdes, cero regresiones — y sin
> embargo el agente no está listo, y no podés probar lo contrario
> porque no definiste qué 'listo' significa."

Los próximos 4 bugs en cola (R2 wake recall, O ngram, R1
hotwords, Q model upgrade) son TODOS arreglos a una pipeline que
no tiene baseline numérico. Sin S, R2 puede tirar el wake recall
del 25% al 70% y nadie va a poder confirmar la mejora con un
número, solo con la sensación del operador.

**S no compite con R2/O/R1/Q. Los habilita.**

---

## OBJETIVO

Dos commits chicos:

1. **`docs(ops): production-ready acceptance gate`** — un
   `docs/PRODUCTION_READY.md` con 5 thresholds concretos y la
   tabla de qué cumple hoy.

2. **`feat(ops): bench harness for STT/wake/latency`** — un
   `scripts/bench.py` que corre los 5 thresholds contra
   `testaudio_v2.wav` (cuando exista) o el actual
   `Grabación (2).wav` como fallback, emite un JSON
   comparable + un report markdown.

El bench se corre con `python scripts/bench.py` y termina en <5
min en hardware del operador. Output: `bench_results/<timestamp>.json`
+ `bench_results/<timestamp>.md`.

---

## REGLAS GENERALES

1. PortandoLoMejor. 2 commits chicos.
2. **NO toques** el voice pipeline (stt.py, controller.py,
   wake.py, recorder.py). El sprint es PURA infraestructura de
   medición.
3. **NO toques** los 65 schemas, modes, prompts, router_v2.
4. **NO inventés thresholds nuevos** — usa exactamente los 5 que
   recomendó el informe (ver más abajo). Si encontrás que falta
   uno, agregalo como follow-up documentado, no en este sprint.
5. **NO requirás audio nativo `testaudio_v2.wav` aún** — usa
   `Grabación (2).wav` como fallback si v2 no existe. R2 va a
   exigir v2.
6. Auto-install OK para deps free.
7. NO `git add -A`.

---

## FIX S.1 — `docs/PRODUCTION_READY.md`

### S.1.1 — Contenido del documento

Crear `docs/PRODUCTION_READY.md`:

```markdown
# `gemma4_agent` — Production-Ready Acceptance Gate

> Esta es la regla del juego. Cuando los 5 thresholds están en
> verde simultáneamente en un commit, `gemma4_agent` se considera
> production-ready para un usuario. No antes, no en base a
> "sensación", no en base a "26 sprints sin regresiones". Estos 5
> números o nada.
>
> Origen: investigación post-Sprint P 2026-05-18.

## Los 5 thresholds

| # | Métrica | Threshold | Cómo se mide | Estado actual |
|---|---|---|---|---|
| 1 | **Wake recall** | ≥70% en `testaudio_v2.wav` (nativo WAV, no m4a) | `bench.py` cuenta wakes detectados vs wakes esperados (anotados en `testaudio_v2_expected.json`) | ❌ 25% en `Grabación (2).m4a`, sin medición en v2 |
| 2 | **Wake false-positive rate** | ≤1 FP / hora en 30min de audio idle | `bench.py` corre Vosk sobre `testaudio_idle.wav` (silencio + ruido de fondo, sin wake intencional) y cuenta fires | ❌ Sin medición |
| 3 | **STT WER medio** | <0.20 vs Whisper-large-v3 ground truth sobre `testaudio_v2.wav` | `bench.py` corre small vs large, computa WER con `jiwer` (Sprint N infra) | ❌ Sprint N reportó WER medio ~0.57 en `Grabación (2)` |
| 4 | **STT latency p95** | ≤1.2s para clips ≤3s, GPU disponible | `bench.py` mide `_transcribe_buffer` sobre clips sintetizados; p95 sobre 20 iteraciones por clip | ❌ Sprint N corrió en CPU/int8 (DLL missing) — invalida medición |
| 5 | **Voice end-to-end p95** | ≤5s wake→TTS start, sesión real con 20 comandos diversos | Sesión manual con 20 turnos, recorder anota timings en manifest; bench parsea | ❌ Sin medición; budget operator memory dice 4-5s |

## Métricas auxiliares (NO bloqueantes, solo informativas)

- **Filter false-positive rate**: % turns con `whisper_raw_text`
  no-vacío PERO `whisper_transcription` null en manifest. Si >20%
  sostenido en sesiones de uso real → calibrar filtros (Sprint O).
- **Silent fallback count per session**: trace events
  `silent_fallback`. Si ≥1 por sesión → V (except triage) sube
  prioridad.
- **TTS finish-to-next-wake median**: silencio post-reply.
  Indicador UX. No threshold, solo telemetry.

## Decisión

Los 5 thresholds se evalúan TODOS antes de declarar
production-ready. **AND, no OR**.

- 4/5 verde + 1 rojo → NO production-ready. Reportar cuál falla y
  arrancar sprint específico.
- 5/5 verde EN UN MISMO COMMIT → production-ready.
- Cualquier commit posterior que mueva alguno de los 5 a rojo →
  regresión bloqueante. Rollback o fix antes de mergear más.

## Cómo se corre

```bash
# Modo full (todos los thresholds, 5min en hardware operador):
python scripts/bench.py

# Modo CI (rápido, solo los thresholds que no requieren GPU/audio fresh):
python scripts/bench.py --ci

# Modo single (un threshold específico):
python scripts/bench.py --threshold wake_recall
```

Output: `bench_results/<YYYYMMDD_HHMMSS>.json` + `.md`.

## Audios requeridos

| Archivo | Cómo generar | Cuándo |
|---|---|---|
| `testaudio_v2.wav` | Operador graba 20-30 comandos diversos en WAV nativo (Audacity / Sound Recorder Windows). No m4a, sin compression. ES + EN mix, normal/fast/whispered. | Antes de R2 |
| `testaudio_v2_expected.json` | Manifest manual: por cada timestamp de wake intencional, marca `expected_wake: true`. Resto: `false`. | Operador lo arma post-grabación |
| `testaudio_idle.wav` | 30min de audio de la habitación SIN intentos de wake. Ruido base. | Antes del threshold #2 |

Si los audios no existen al correr `bench.py`, el harness usa
`Grabación (2).wav` como fallback degradado y marca los
thresholds como `SKIPPED — missing reference audio`. No
falla; reporta limpio.

## Política de re-medición

- Después de cada sprint que toque el voice pipeline, correr
  `bench.py` y commitear el resultado en `bench_results/`.
- Comparar contra el último resultado del previous sprint.
- Si alguno de los 5 retrocedió ≥10%, rollback del commit que
  lo introdujo (excepto si fue intencional + documentado).

## Lo que NO está acá (intencional)

- Multi-operator (X) y i18n (Y) NO son thresholds. Son
  capabilities que se evalúan recién cuando aparece la demanda.
  El informe lo aclaró.
- Tests unitarios verdes NO es threshold (es prerequisito básico).
- Cobertura de tools (65/65 con verifier) NO es threshold —
  ningún usuario va a sentir que `verify_xyz` no existe; los
  van a sentir cuando el flujo se rompa.

---
```

### S.1.2 — Commit

`docs(ops): production-ready acceptance gate (5 thresholds)`

Mensaje:

```
docs(ops): production-ready acceptance gate (5 thresholds)

Sprint estratégico post-investigación. El proyecto lleva 26+
sprints, ~190 tests verdes, cero regresiones documentadas, y sin
embargo no está production-ready y nadie podía probar lo
contrario porque no había criterio.

Fix: PRODUCTION_READY.md define 5 thresholds concretos:

1. Wake recall ≥70% en WAV nativo.
2. Wake FP rate ≤1/hour en idle audio.
3. STT WER medio <0.20 vs Whisper-large-v3 ground truth.
4. STT latency p95 ≤1.2s para clips ≤3s en GPU.
5. Voice end-to-end p95 ≤5s wake→TTS start en sesión real.

AND, no OR. Los 5 verdes simultáneos en un commit = production-
ready. Cualquier commit posterior que mueva uno a rojo =
regresión bloqueante.

Auxiliary metrics (filter FP rate, silent_fallback count,
TTS finish-to-next-wake) son informativas no bloqueantes.

Multi-operator e i18n NO son thresholds — son capabilities
diferidas hasta demanda real.

Pure docs. Bench harness real va en S.2.
```

---

## FIX S.2 — `scripts/bench.py`

### S.2.1 — Estructura

`scripts/bench.py` (~300 LOC, modular):

```python
"""Production-readiness bench harness for gemma4_agent.

Measures the 5 thresholds defined in docs/PRODUCTION_READY.md:

  1. wake_recall: fraction of expected wakes Vosk detects.
  2. wake_fp_rate: false-positive fires per hour over idle audio.
  3. stt_wer_mean: WER vs Whisper-large-v3 ground truth.
  4. stt_latency_p95: p95 latency of _transcribe_buffer over
     short clips (GPU-only; CPU mode reports SKIPPED).
  5. voice_e2e_p95: parsed from a real session manifest (if
     provided via --session-jsonl).

Usage:
    python scripts/bench.py
    python scripts/bench.py --ci             # skip GPU+audio-fresh
    python scripts/bench.py --threshold wake_recall
    python scripts/bench.py --session-jsonl path/to/manifest.jsonl

Outputs:
    bench_results/<YYYYMMDD_HHMMSS>.json
    bench_results/<YYYYMMDD_HHMMSS>.md

Exit code:
    0 → all measured thresholds pass.
    1 → at least one threshold failed.
    2 → harness error (missing dep, missing audio, etc.).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import statistics
import sys
import time
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.voice.audio_io import SAMPLE_RATE  # noqa: E402

logger = logging.getLogger("bench")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

# --- Thresholds (mirror PRODUCTION_READY.md) ------------------------

THRESHOLDS = {
    "wake_recall":      {"target": 0.70, "op": ">="},
    "wake_fp_rate":     {"target": 1.0,  "op": "<="},   # per hour
    "stt_wer_mean":     {"target": 0.20, "op": "<"},
    "stt_latency_p95":  {"target": 1.2,  "op": "<="},   # seconds
    "voice_e2e_p95":    {"target": 5.0,  "op": "<="},   # seconds
}

# --- Audio fixtures ------------------------------------------------

VOICE_TESTS = ROOT / "gemma4_agent" / "voice" / "tests"
TEST_V2 = VOICE_TESTS / "testaudio_v2.wav"
TEST_V2_EXPECTED = VOICE_TESTS / "testaudio_v2_expected.json"
TEST_IDLE = VOICE_TESTS / "testaudio_idle.wav"
TEST_FALLBACK = VOICE_TESTS / "Grabación (2).wav"


@dataclass
class ThresholdResult:
    name: str
    measured: float | None
    target: float
    op: str
    passed: bool | None  # None means SKIPPED
    note: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        if self.passed is None:
            return "SKIPPED"
        return "PASS" if self.passed else "FAIL"


def _compare(measured: float, target: float, op: str) -> bool:
    if op == ">=": return measured >= target
    if op == ">":  return measured > target
    if op == "<=": return measured <= target
    if op == "<":  return measured < target
    raise ValueError(f"unknown op: {op}")


# --- jiwer auto-install ---------------------------------------------

def _ensure_jiwer():
    try:
        import jiwer  # type: ignore
        return jiwer
    except ImportError:
        logger.info("Installing jiwer (one-time)...")
        import subprocess as _sp
        _sp.check_call([sys.executable, "-m", "pip", "install", "jiwer"])
        import jiwer  # type: ignore
        return jiwer


# --- Audio loading helpers -----------------------------------------

def _load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        assert wf.getframerate() == SAMPLE_RATE
        assert wf.getnchannels() == 1
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16)


def _pick_reference_audio() -> tuple[Path | None, str]:
    """Return (path, note). Prefers testaudio_v2.wav; falls back
    to Grabación (2).wav with a degradation note."""
    if TEST_V2.exists():
        return TEST_V2, "native WAV (v2)"
    if TEST_FALLBACK.exists():
        return TEST_FALLBACK, "fallback (m4a-converted; v2 not available)"
    return None, "no reference audio"


# --- Threshold 1: wake_recall ---------------------------------------

def measure_wake_recall() -> ThresholdResult:
    audio_path, note = _pick_reference_audio()
    if audio_path is None:
        return ThresholdResult(
            "wake_recall", None,
            THRESHOLDS["wake_recall"]["target"],
            THRESHOLDS["wake_recall"]["op"],
            passed=None,
            note="no reference audio found",
        )
    # Need annotated expected wakes. If v2 isn't annotated yet,
    # SKIP rather than guess.
    if not TEST_V2_EXPECTED.exists() and audio_path == TEST_V2:
        return ThresholdResult(
            "wake_recall", None,
            THRESHOLDS["wake_recall"]["target"],
            THRESHOLDS["wake_recall"]["op"],
            passed=None,
            note="testaudio_v2_expected.json missing",
        )
    # For fallback path, we don't have an annotated count; report
    # only the raw fires count for visibility.
    audio = _load_wav(audio_path)
    from gemma4_agent.voice.wake import WakeDetector  # lazy
    detections: list = []
    def _on_wake(phrase: str, ts: float, tail_s: float = 0.0,
                 confidence: float = 0.0) -> None:
        detections.append((ts, phrase, confidence))
    det = WakeDetector(on_wake=_on_wake)
    if not det.load():
        return ThresholdResult(
            "wake_recall", None,
            THRESHOLDS["wake_recall"]["target"],
            THRESHOLDS["wake_recall"]["op"],
            passed=None,
            note=f"Vosk load failed: {det.last_error}",
        )
    CHUNK = 512
    for i in range(0, len(audio) - CHUNK, CHUNK):
        det.feed(audio[i:i + CHUNK])
    fires = len(detections)
    if TEST_V2_EXPECTED.exists():
        with open(TEST_V2_EXPECTED, encoding="utf-8") as fh:
            expected = json.load(fh)
        expected_count = sum(1 for e in expected.get("wakes", []) if e.get("expected"))
        recall = fires / max(1, expected_count)
        return ThresholdResult(
            "wake_recall", recall,
            THRESHOLDS["wake_recall"]["target"],
            THRESHOLDS["wake_recall"]["op"],
            passed=_compare(recall, THRESHOLDS["wake_recall"]["target"], THRESHOLDS["wake_recall"]["op"]),
            note=f"audio={audio_path.name} ({note})",
            details={"fires": fires, "expected": expected_count},
        )
    # Fallback: no expected file → report fires count only,
    # SKIPPED. The operator still gets visibility.
    return ThresholdResult(
        "wake_recall", None,
        THRESHOLDS["wake_recall"]["target"],
        THRESHOLDS["wake_recall"]["op"],
        passed=None,
        note=f"fires={fires} on {audio_path.name} ({note}); no expected.json",
        details={"fires": fires},
    )


# --- Threshold 2: wake_fp_rate ---------------------------------------

def measure_wake_fp_rate() -> ThresholdResult:
    if not TEST_IDLE.exists():
        return ThresholdResult(
            "wake_fp_rate", None,
            THRESHOLDS["wake_fp_rate"]["target"],
            THRESHOLDS["wake_fp_rate"]["op"],
            passed=None,
            note="testaudio_idle.wav missing",
        )
    audio = _load_wav(TEST_IDLE)
    duration_h = len(audio) / SAMPLE_RATE / 3600
    from gemma4_agent.voice.wake import WakeDetector
    fires = []
    def _on_wake(phrase: str, ts: float, tail_s: float = 0.0,
                 confidence: float = 0.0) -> None:
        fires.append((ts, phrase))
    det = WakeDetector(on_wake=_on_wake)
    if not det.load():
        return ThresholdResult(
            "wake_fp_rate", None,
            THRESHOLDS["wake_fp_rate"]["target"],
            THRESHOLDS["wake_fp_rate"]["op"],
            passed=None,
            note=f"Vosk load failed: {det.last_error}",
        )
    CHUNK = 512
    for i in range(0, len(audio) - CHUNK, CHUNK):
        det.feed(audio[i:i + CHUNK])
    rate = len(fires) / max(0.001, duration_h)
    return ThresholdResult(
        "wake_fp_rate", rate,
        THRESHOLDS["wake_fp_rate"]["target"],
        THRESHOLDS["wake_fp_rate"]["op"],
        passed=_compare(rate, THRESHOLDS["wake_fp_rate"]["target"], THRESHOLDS["wake_fp_rate"]["op"]),
        note=f"{len(fires)} fires in {duration_h*60:.1f}min idle",
        details={"fires": len(fires), "duration_h": duration_h},
    )


# --- Threshold 3: stt_wer_mean --------------------------------------

def measure_stt_wer_mean() -> ThresholdResult:
    """Compute WER of production small vs large-v3 ground truth.

    Reuses testaudio_groundtruth_aligned.json from Sprint N if
    available — that file already has small and large transcriptions
    aligned per wake. If missing, SKIPPED."""
    aligned = VOICE_TESTS / "testaudio_groundtruth_aligned.json"
    if not aligned.exists():
        return ThresholdResult(
            "stt_wer_mean", None,
            THRESHOLDS["stt_wer_mean"]["target"],
            THRESHOLDS["stt_wer_mean"]["op"],
            passed=None,
            note="testaudio_groundtruth_aligned.json missing — run scripts/testaudio_groundtruth.py",
        )
    with open(aligned, encoding="utf-8") as fh:
        d = json.load(fh)
    jiwer = _ensure_jiwer()
    wers = []
    for t in d.get("turns", []):
        ref = (t.get("large_text") or "").strip().lower()
        hyp = (t.get("small_raw_text") or t.get("small_text") or "").strip().lower()
        if not ref:
            continue
        wer = float(jiwer.wer(ref, hyp))
        wers.append(wer)
    if not wers:
        return ThresholdResult(
            "stt_wer_mean", None,
            THRESHOLDS["stt_wer_mean"]["target"],
            THRESHOLDS["stt_wer_mean"]["op"],
            passed=None,
            note="no non-empty references in aligned JSON",
        )
    mean_wer = statistics.fmean(wers)
    return ThresholdResult(
        "stt_wer_mean", mean_wer,
        THRESHOLDS["stt_wer_mean"]["target"],
        THRESHOLDS["stt_wer_mean"]["op"],
        passed=_compare(mean_wer, THRESHOLDS["stt_wer_mean"]["target"], THRESHOLDS["stt_wer_mean"]["op"]),
        note=f"n={len(wers)} turns",
        details={"wers": [round(w, 3) for w in wers]},
    )


# --- Threshold 4: stt_latency_p95 -----------------------------------

def measure_stt_latency_p95(ci_mode: bool = False) -> ThresholdResult:
    """Measure _transcribe_buffer p95 latency over synthesized
    short clips. GPU-only; CPU mode → SKIPPED."""
    if ci_mode:
        return ThresholdResult(
            "stt_latency_p95", None,
            THRESHOLDS["stt_latency_p95"]["target"],
            THRESHOLDS["stt_latency_p95"]["op"],
            passed=None,
            note="--ci flag: GPU bench skipped",
        )
    try:
        import torch  # type: ignore
    except ImportError:
        return ThresholdResult(
            "stt_latency_p95", None,
            THRESHOLDS["stt_latency_p95"]["target"],
            THRESHOLDS["stt_latency_p95"]["op"],
            passed=None,
            note="torch not installed",
        )
    if not torch.cuda.is_available():
        return ThresholdResult(
            "stt_latency_p95", None,
            THRESHOLDS["stt_latency_p95"]["target"],
            THRESHOLDS["stt_latency_p95"]["op"],
            passed=None,
            note="CUDA not available (fix DLL — see Sprint Q.0)",
        )
    # Build 3 synthetic clips: 1s, 2s, 3s of white noise (just to
    # exercise the pipeline; we don't care about transcription
    # quality here, only latency).
    from gemma4_agent.voice.stt import StreamingSTT  # lazy
    stt = StreamingSTT()
    if not stt.load():
        return ThresholdResult(
            "stt_latency_p95", None,
            THRESHOLDS["stt_latency_p95"]["target"],
            THRESHOLDS["stt_latency_p95"]["op"],
            passed=None,
            note=f"STT load failed: {stt.last_error}",
        )
    latencies = []
    for clip_s in [1.0, 2.0, 3.0]:
        clip = (np.random.randn(int(clip_s * SAMPLE_RATE)) * 2000).astype(np.int16)
        # Warm-up.
        stt._transcribe_buffer(clip)
        for _ in range(20):
            t0 = time.perf_counter()
            stt._transcribe_buffer(clip)
            latencies.append(time.perf_counter() - t0)
    p95 = float(np.percentile(latencies, 95))
    return ThresholdResult(
        "stt_latency_p95", p95,
        THRESHOLDS["stt_latency_p95"]["target"],
        THRESHOLDS["stt_latency_p95"]["op"],
        passed=_compare(p95, THRESHOLDS["stt_latency_p95"]["target"], THRESHOLDS["stt_latency_p95"]["op"]),
        note=f"n={len(latencies)} runs over clips 1-3s",
        details={"p50": round(float(np.percentile(latencies, 50)), 3),
                 "p95": round(p95, 3),
                 "max": round(float(np.max(latencies)), 3)},
    )


# --- Threshold 5: voice_e2e_p95 -------------------------------------

def measure_voice_e2e_p95(session_jsonl: Path | None) -> ThresholdResult:
    """Parse a real session manifest for wake→TTS-finished
    timings. Requires --session-jsonl path; SKIPPED otherwise."""
    if session_jsonl is None or not session_jsonl.exists():
        return ThresholdResult(
            "voice_e2e_p95", None,
            THRESHOLDS["voice_e2e_p95"]["target"],
            THRESHOLDS["voice_e2e_p95"]["op"],
            passed=None,
            note="--session-jsonl not provided or missing",
        )
    # Manifest format: one JSON line per turn with started_at /
    # finished_at fields (recorder schema post-Sprint M.1).
    elapsed_per_turn = []
    with open(session_jsonl, encoding="utf-8") as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("duration_s") and e.get("whisper_transcription"):
                elapsed_per_turn.append(float(e["duration_s"]))
    if len(elapsed_per_turn) < 5:
        return ThresholdResult(
            "voice_e2e_p95", None,
            THRESHOLDS["voice_e2e_p95"]["target"],
            THRESHOLDS["voice_e2e_p95"]["op"],
            passed=None,
            note=f"only {len(elapsed_per_turn)} turns in manifest; need ≥5",
        )
    p95 = float(np.percentile(elapsed_per_turn, 95))
    return ThresholdResult(
        "voice_e2e_p95", p95,
        THRESHOLDS["voice_e2e_p95"]["target"],
        THRESHOLDS["voice_e2e_p95"]["op"],
        passed=_compare(p95, THRESHOLDS["voice_e2e_p95"]["target"], THRESHOLDS["voice_e2e_p95"]["op"]),
        note=f"n={len(elapsed_per_turn)} turns from {session_jsonl.name}",
        details={"p50": round(float(np.percentile(elapsed_per_turn, 50)), 3),
                 "p95": round(p95, 3),
                 "max": round(float(np.max(elapsed_per_turn)), 3)},
    )


# --- Output writers --------------------------------------------------

def _write_outputs(results: list[ThresholdResult], out_dir: Path) -> tuple[Path, Path]:
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{ts}.json"
    md_path = out_dir / f"{ts}.md"

    payload = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "thresholds": [asdict(r) for r in results],
        "summary": {
            "total":    len(results),
            "passed":   sum(1 for r in results if r.passed is True),
            "failed":   sum(1 for r in results if r.passed is False),
            "skipped":  sum(1 for r in results if r.passed is None),
            "production_ready": all(r.passed is True for r in results),
        },
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                          encoding="utf-8")

    lines = []
    lines.append(f"# Bench results — {payload['generated_at']}")
    lines.append("")
    s = payload["summary"]
    lines.append(f"**Summary**: {s['passed']}/{s['total']} passed, "
                 f"{s['failed']} failed, {s['skipped']} skipped.")
    if s["production_ready"]:
        lines.append("")
        lines.append("✅ **PRODUCTION READY** — all 5 thresholds green.")
    else:
        lines.append("")
        lines.append("❌ **Not production ready** — at least one threshold red or skipped.")
    lines.append("")
    lines.append("| Threshold | Status | Measured | Target | Note |")
    lines.append("|---|---|---|---|---|")
    for r in results:
        measured = "—" if r.measured is None else f"{r.measured:.3f}"
        target = f"{r.op} {r.target}"
        lines.append(f"| `{r.name}` | **{r.status}** | {measured} | {target} | {r.note} |")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


# --- CLI -----------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="gemma4_agent production-readiness bench harness."
    )
    parser.add_argument(
        "--ci", action="store_true",
        help="Skip GPU-required + audio-fresh thresholds (for CI runs)",
    )
    parser.add_argument(
        "--threshold", choices=list(THRESHOLDS.keys()),
        help="Run only the named threshold",
    )
    parser.add_argument(
        "--session-jsonl", type=Path, default=None,
        help="Path to a recorder manifest.jsonl for voice_e2e_p95 measurement",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=ROOT / "bench_results",
        help="Where to write the JSON+md outputs (default: bench_results/)",
    )
    args = parser.parse_args()

    results = []
    selected = [args.threshold] if args.threshold else list(THRESHOLDS.keys())

    if "wake_recall" in selected:
        logger.info("Running wake_recall...")
        results.append(measure_wake_recall())
    if "wake_fp_rate" in selected:
        logger.info("Running wake_fp_rate...")
        results.append(measure_wake_fp_rate())
    if "stt_wer_mean" in selected:
        logger.info("Running stt_wer_mean...")
        results.append(measure_stt_wer_mean())
    if "stt_latency_p95" in selected:
        logger.info("Running stt_latency_p95...")
        results.append(measure_stt_latency_p95(ci_mode=args.ci))
    if "voice_e2e_p95" in selected:
        logger.info("Running voice_e2e_p95...")
        results.append(measure_voice_e2e_p95(args.session_jsonl))

    json_path, md_path = _write_outputs(results, args.out_dir)
    logger.info(f"Wrote {json_path}")
    logger.info(f"Wrote {md_path}")

    print()
    print("=" * 60)
    print(f"Results: {md_path}")
    print("=" * 60)
    for r in results:
        m = "—" if r.measured is None else f"{r.measured:.3f}"
        print(f"  {r.name:20s} {r.status:8s} {m:>8s}  {r.note}")

    if any(r.passed is False for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### S.2.2 — Tests

`gemma4_agent/test_bench_harness.py`:

```python
"""Tests for the production-readiness bench harness shape.

These don't load Whisper/Vosk/torch — pure unit tests against the
ThresholdResult dataclass + writer logic + comparator.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "bench",
        ROOT / "scripts" / "bench.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bench"] = mod
    spec.loader.exec_module(mod)
    return mod


class ThresholdsTest(unittest.TestCase):
    def test_five_thresholds_defined(self) -> None:
        b = _load_module()
        self.assertEqual(set(b.THRESHOLDS.keys()), {
            "wake_recall", "wake_fp_rate", "stt_wer_mean",
            "stt_latency_p95", "voice_e2e_p95",
        })

    def test_thresholds_match_production_ready_doc(self) -> None:
        # If you change values here, update docs/PRODUCTION_READY.md.
        b = _load_module()
        self.assertEqual(b.THRESHOLDS["wake_recall"]["target"], 0.70)
        self.assertEqual(b.THRESHOLDS["wake_fp_rate"]["target"], 1.0)
        self.assertEqual(b.THRESHOLDS["stt_wer_mean"]["target"], 0.20)
        self.assertEqual(b.THRESHOLDS["stt_latency_p95"]["target"], 1.2)
        self.assertEqual(b.THRESHOLDS["voice_e2e_p95"]["target"], 5.0)


class ComparatorTest(unittest.TestCase):
    def test_greater_equal(self) -> None:
        b = _load_module()
        self.assertTrue(b._compare(0.75, 0.70, ">="))
        self.assertFalse(b._compare(0.65, 0.70, ">="))

    def test_less_than(self) -> None:
        b = _load_module()
        self.assertTrue(b._compare(0.15, 0.20, "<"))
        self.assertFalse(b._compare(0.20, 0.20, "<"))


class WriterTest(unittest.TestCase):
    def test_output_shape(self) -> None:
        b = _load_module()
        results = [
            b.ThresholdResult(
                name="wake_recall", measured=0.85, target=0.70,
                op=">=", passed=True, note="test",
            ),
            b.ThresholdResult(
                name="wake_fp_rate", measured=None, target=1.0,
                op="<=", passed=None, note="skipped",
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            json_path, md_path = b._write_outputs(results, Path(tmp))
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(data["summary"]["total"], 2)
            self.assertEqual(data["summary"]["passed"], 1)
            self.assertEqual(data["summary"]["skipped"], 1)
            self.assertFalse(data["summary"]["production_ready"])
            md = md_path.read_text(encoding="utf-8")
            self.assertIn("wake_recall", md)
            self.assertIn("PASS", md)
            self.assertIn("SKIPPED", md)

    def test_all_passed_says_production_ready(self) -> None:
        b = _load_module()
        results = [
            b.ThresholdResult(name=k, measured=v["target"],
                              target=v["target"], op=v["op"],
                              passed=True, note="ok")
            for k, v in b.THRESHOLDS.items()
        ]
        with tempfile.TemporaryDirectory() as tmp:
            json_path, _ = b._write_outputs(results, Path(tmp))
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertTrue(data["summary"]["production_ready"])


if __name__ == "__main__":
    unittest.main()
```

### S.2.3 — `.gitignore` update

Agregar al final del `.gitignore` (preserva bench_results out of
git — son artifacts, no source):

```
# Bench harness outputs (regenerable per commit).
bench_results/
```

### S.2.4 — Smoke run

Después de crear todo, correr:

```bash
python scripts/bench.py
```

Expectativa **realista** (no PASS, eso es el punto):
- `wake_recall`: SKIPPED (testaudio_v2_expected.json missing) o
  un número desnudo (fires count).
- `wake_fp_rate`: SKIPPED (testaudio_idle.wav missing).
- `stt_wer_mean`: computado (Sprint N alignment existe).
- `stt_latency_p95`: SKIPPED (CUDA DLL missing → Sprint Q.0) o
  FAIL si corre en CPU.
- `voice_e2e_p95`: SKIPPED (--session-jsonl no provided).

El bench produce `bench_results/<timestamp>.json` y `.md` que
sirven como **baseline inicial**. Cada commit posterior se mide
contra esto.

Si todo es SKIPPED y/o FAIL, **es el resultado correcto**.
Significa que el agente NO está production-ready, y ahora podemos
probarlo.

### S.2.5 — Commit

`feat(ops): bench harness measuring 5 production-ready thresholds`

Mensaje:

```
feat(ops): bench harness measuring 5 production-ready thresholds

Companion to docs/PRODUCTION_READY.md. scripts/bench.py
implements the 5 threshold measurements:

1. wake_recall — Vosk fires over annotated WAV; expected vs actual.
2. wake_fp_rate — Vosk fires over idle-audio reference.
3. stt_wer_mean — reuses Sprint N alignment JSON; small vs large.
4. stt_latency_p95 — measures _transcribe_buffer on synthetic
   short clips; GPU-only (CPU mode → SKIPPED with note).
5. voice_e2e_p95 — parses recorder manifest.jsonl from a real
   session; needs --session-jsonl arg.

Each measurement returns a ThresholdResult with
{measured, target, op, passed, note, details}. Output is JSON +
markdown sibling files in bench_results/, gitignored (artifacts,
not source).

Exit code: 0 if all PASS, 1 if any FAIL, 2 if harness error.

Modes:
  --ci: skip GPU + audio-fresh thresholds (CI runs).
  --threshold X: run only one.
  --session-jsonl PATH: voice_e2e_p95 source.

Auto-installs jiwer (operator install-authorization granted).

When all 5 PASS in a single commit, the agent is production-ready
per docs/PRODUCTION_READY.md. Today, most will SKIP (missing
testaudio_v2.wav, testaudio_idle.wav, CUDA DLL). That's the point
— now the agent has eyes to know what it doesn't have.

Tests cover: threshold constants match the doc, comparator
correctness, output JSON/md shape, production_ready flag only
turns True when all PASS.

NO change to voice pipeline, router, prompts, tools. Pure
measurement infra.
```

---

## REPORTE FINAL

Devolveme:

1. Hashes de los 2 commits.
2. Output de:
   ```
   python -m pytest gemma4_agent/test_bench_harness.py -v
   ```
3. Output de `python -m pytest gemma4_agent/ -q --tb=line`
   (suite completa, debe seguir verde).
4. Output completo de la primera corrida real:
   ```
   python scripts/bench.py
   ```
   Pegame:
   - El output del console (los 5 thresholds + status).
   - El contenido del `.md` generado en `bench_results/`.
5. **El JSON generado**: pegame el JSON completo. Eso es el
   baseline inicial contra el que se va a medir todo lo que
   sigue.

## CRITERIO DE ÉXITO

- 2 commits aterrizados.
- `docs/PRODUCTION_READY.md` creado y completo.
- `scripts/bench.py` corre en <5min y produce JSON+md.
- ≥4 tests nuevos verdes.
- Suite completa verde.
- `bench_results/<timestamp>.json` generado con los 5 thresholds.
- Al menos 1 threshold con `passed=True`, `False` o `None`
  (alguno se mide; no todos skipean).
- `.gitignore` excluye `bench_results/`.

## NO HACER (anti-scope)

- NO toques voice pipeline ni nada del runtime. Pure
  observability + docs.
- NO inventés thresholds nuevos. Si encontrás un gap, doc-eá
  como follow-up.
- NO bajés los thresholds para que pasen hoy. Los thresholds son
  la regla del juego; cumplirlos requiere los próximos sprints.
- NO commitees los outputs de `bench_results/` — gitignored a
  propósito. El JSON committeable solo aparece cuando todos
  PASS y mergeás `bench_results/<commit>.json` explícitamente.
- NO modifiques los tests del Sprint N ni el groundtruth JSON
  para que el bench los lea. Si el shape no matchea, ajustá el
  bench, no la fuente.
- Si Vosk / Whisper load fallan al medir, NO bypasses con mock.
  Reportá SKIPPED con la razón concreta — eso es el dato.

## Follow-ups documentados

1. **`testaudio_v2.wav` + `testaudio_v2_expected.json`**: el
   operador graba ~20-30 comandos en WAV nativo y anota qué
   timestamps son wakes intencionales. Trabajo operator-side,
   ~15min. Necesario antes de R2.

2. **`testaudio_idle.wav`**: 30min de la habitación del operador
   sin hablar. Sirve para `wake_fp_rate`. Trabajo operator-side,
   30min de paciencia.

3. **Q.0 — CUDA DLL fix**: necesario antes de que
   `stt_latency_p95` deje de skipear.

4. **`bench.py --diff PREV CURR`**: feature futura. Compara 2
   resultados y dice si alguna métrica retrocedió. Cuando el
   operador empiece a medir consistente, esa herramienta paga.

5. **CI integration**: agregar `python scripts/bench.py --ci` al
   suite de tests de cada PR. Una vez que `stt_wer_mean` deja
   de fluctuar mucho, vale la pena hacerlo bloqueante.
