"""Eval END-TO-END de la cadena de transcripción: wake → captura → EOS →
transcripción → corrector → texto que llega al LLM.

A diferencia de los evals de STT (que miden el motor aislado), este alimenta
el VoicePipeline REAL chunk a chunk (512 samples, como el AudioPump) con
streams compuestos: [silencio calibración 1.5s] + [wake TTS "baxy"] +
[micro-pausa] + [comando de VOZ REAL del corpus RED] + [silencio 1.5s].

Mide por caso:
  - ¿despertó? (wake al inicio del stream)
  - latencia EOS: chunks desde el FIN real del comando hasta que el pipeline
    cerró la captura (el delay percibido al terminar de hablar)
  - texto FINAL (post corrector/strip) vs transcript esperado → WER de cadena
  - drops (gate de silencio / alucinación / filler) y sus motivos

Uso: python scripts/voice_chain_eval.py [--max-cases N] [--noise-snr DB]
     --noise-snr agrega voces LibriSpeech de fondo a TODO el stream (el caso
     película). Sin flag = silencio (baseline).
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import _ort_throttle  # noqa: F401,E402

os.environ.pop("GEMMA4_VOICE_MIN_CAPTURE_RMS", None)  # auto-cal activa

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from gemma4_agent.voice.pipeline import (  # noqa: E402
    VoicePipeline, State, CHUNK_SAMPLES, SAMPLE_RATE,
)

SEED = 20260611
MIC = ROOT / "data" / "stt_eval" / "real_mic"
POS = ROOT / "data" / "wake_universal_eval" / "positives_baxy"
NEG = ROOT / "data" / "wake_universal_eval" / "negatives"
TANDAS = ("20260523_015719", "20260523_020155")  # comandos RED con transcript


def wer(ref: str, hyp: str) -> float:
    r, h = ref.split(), hyp.split()
    if not r:
        return 0.0
    d = [[0] * (len(h) + 1) for _ in range(len(r) + 1)]
    for i in range(len(r) + 1):
        d[i][0] = i
    for j in range(len(h) + 1):
        d[0][j] = j
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1,
                          d[i - 1][j - 1] + (r[i - 1] != h[j - 1]))
    return d[len(r)][len(h)] / len(r)


def norm(t: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", (t or "").casefold())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() or c.isspace() else " "
                            for c in t).split())


def load_f32(path: Path) -> np.ndarray:
    d, sr = sf.read(str(path), dtype="float32")
    if d.ndim > 1:
        d = d[:, 0]
    assert sr == SAMPLE_RATE, f"{path}: {sr}"
    return d


def to_i16(x: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(x))) + 1e-9
    if peak > 1.0:
        x = x / peak
    return (x * 32767).astype(np.int16)


class ChainCase:
    def __init__(self) -> None:
        self.commands: list[tuple[str, float, str]] = []
        self.states: list[tuple[int, str]] = []   # (chunk_idx, state)
        self.wakes = 0
        self.chunk_idx = 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-cases", type=int, default=0)
    ap.add_argument("--noise-snr", type=float, default=None,
                    help="SNR dB de voces de fondo sobre TODO el stream")
    ap.add_argument("--force-wake", action="store_true",
                    help="inyecta _on_wake al final del clip de wake (mide la "
                         "captura bajo ruido aunque el modelo de wake no dispare)")
    args = ap.parse_args()
    rng = random.Random(SEED)

    rows = []
    for line in (MIC / "manifest.tsv").read_text(encoding="utf-8").splitlines():
        p = line.split("\t")
        if len(p) >= 6 and p[5] in TANDAS and (MIC / p[0]).exists():
            rows.append((MIC / p[0], p[1]))
    if args.max_cases:
        rows = rows[:args.max_cases]
    assert rows, "no hay comandos RED"

    noise_pool: list[np.ndarray] = []
    if args.noise_snr is not None:
        for p in sorted(NEG.glob("**/*.flac"))[:80]:
            try:
                n = load_f32(p)
                if n.size > 5 * SAMPLE_RATE:
                    noise_pool.append(n)
            except Exception:
                continue

    # wake TTS: probar candidatos es_* hasta encontrar uno que despierte.
    wake_clips = sorted(POS.glob("es_*.wav"))[:8]

    case = ChainCase()

    def on_command(text: str, secs: float, raw: str) -> None:
        case.commands.append((text, secs, raw))

    def on_state(s: str) -> None:
        case.states.append((case.chunk_idx, s))

    pipe = VoicePipeline(on_command=on_command, on_state=on_state,
                         on_wake_event=lambda: setattr(case, "wakes", case.wakes + 1))
    assert pipe.load(), pipe.last_error

    def feed_stream(stream_i16: np.ndarray, force_wake_at: int | None = None) -> None:
        # MIN_CAPTURE_S se mide en RELOJ DE PARED (time.monotonic): si
        # alimentamos a velocidad máxima, el EOS nunca se habilita. Pace real
        # (32 ms/chunk) SOLO mientras la captura es más joven que MIN_CAPTURE
        # — fiel a producción sin pagar tiempo real en todo el stream.
        from gemma4_agent.voice.pipeline import MIN_CAPTURE_S
        for i in range(0, stream_i16.size - CHUNK_SAMPLES + 1, CHUNK_SAMPLES):
            case.chunk_idx = i // CHUNK_SAMPLES
            pipe._on_chunk(stream_i16[i:i + CHUNK_SAMPLES])
            if force_wake_at is not None and case.chunk_idx == force_wake_at \
                    and pipe.state == State.IDLE:
                pipe._on_wake("baxy", 0.99)
            if pipe.state == State.CAPTURE and \
                    (time.monotonic() - pipe._capture_start_ts) < MIN_CAPTURE_S + 0.05:
                time.sleep(CHUNK_SAMPLES / SAMPLE_RATE)

    # encontrar un wake TTS que dispare en silencio
    wake_clip = None
    for wc in wake_clips:
        case = ChainCase()
        sil = (3e-4 * np.random.randn(int(1.5 * SAMPLE_RATE))).astype(np.float32)
        stream = to_i16(np.concatenate([sil, load_f32(wc),
                                        np.zeros(SAMPLE_RATE, np.float32)]))
        feed_stream(stream)
        if case.wakes:
            wake_clip = load_f32(wc)
            print(f"wake TTS elegido: {wc.name}")
            break
        pipe._cooldown_until = 0.0
        pipe._reset_to_idle("probe")
    assert wake_clip is not None, "ningún wake TTS despertó (¿modelo?)"

    results = []
    t0 = time.time()
    for k, (cmd_path, expected) in enumerate(rows):
        pipe._cooldown_until = 0.0
        pipe._reset_to_idle("next_case")
        pipe._wake.reset()
        case = ChainCase()
        cmd = load_f32(cmd_path)
        sil_lead = (3e-4 * np.random.randn(int(1.5 * SAMPLE_RATE))).astype(np.float32)
        gap = np.zeros(int(0.25 * SAMPLE_RATE), np.float32)   # micro-pausa post-wake
        tail = np.zeros(int(2.0 * SAMPLE_RATE), np.float32)   # silencio final
        stream = np.concatenate([sil_lead, wake_clip, gap, cmd, tail])
        if args.noise_snr is not None and noise_pool:
            nz = noise_pool[rng.randrange(len(noise_pool))]
            start = rng.randint(0, max(0, nz.size - stream.size))
            nseg = nz[start:start + stream.size]
            if nseg.size < stream.size:
                nseg = np.tile(nseg, stream.size // max(1, nseg.size) + 1)[:stream.size]
            p_s = float(np.mean(cmd ** 2)) + 1e-12
            p_n = float(np.mean(nseg ** 2)) + 1e-12
            stream = stream + nseg * np.sqrt(p_s / (p_n * 10 ** (args.noise_snr / 10)))
        # fin real del habla = fin del comando en el stream
        speech_end_chunk = (sil_lead.size + wake_clip.size + gap.size
                            + cmd.size) // CHUNK_SAMPLES
        wake_end_chunk = (sil_lead.size + wake_clip.size) // CHUNK_SAMPLES
        feed_stream(to_i16(stream),
                    force_wake_at=wake_end_chunk if args.force_wake else None)

        final = case.commands[0][0] if case.commands else ""
        raw = case.commands[0][2] if case.commands else ""
        eos_chunk = next((ci for ci, s in case.states if s == "TRANSCRIBING"), None)
        eos_ms = ((eos_chunk - speech_end_chunk) * CHUNK_SAMPLES / SAMPLE_RATE
                  * 1000) if eos_chunk is not None else None
        no_speech = any(s == "NO_SPEECH" for _, s in case.states)
        stuck = pipe.state == State.CAPTURE  # el stream terminó sin cerrar
        w = wer(norm(expected), norm(final)) if final else 1.0
        results.append({"file": cmd_path.name, "expected": expected,
                        "final": final, "raw": raw, "wake": case.wakes,
                        "eos_ms": eos_ms, "no_speech": no_speech, "wer": w,
                        "stuck": stuck})
        if (k + 1) % 20 == 0:
            print(f"  {k + 1}/{len(rows)} ({time.time() - t0:.0f}s)")

    n = len(results)
    woke = sum(1 for r in results if r["wake"])
    emitted = sum(1 for r in results if r["final"])
    dropped = sum(1 for r in results if r["wake"] and not r["final"])
    stuck = sum(1 for r in results if r.get("stuck"))
    if stuck:
        print(f"CAPTURAS QUE NUNCA CERRARON (EOS no disparó hasta fin de "
              f"stream): {stuck}/{n} -> en prod = timeout 8s + basura al LLM")
    wers = [r["wer"] for r in results if r["final"]]
    eoss = [r["eos_ms"] for r in results if r["eos_ms"] is not None]
    cond = ("silencio" if args.noise_snr is None
            else f"voces snr{args.noise_snr:.0f}dB")
    print(f"\n== CADENA ({cond}) n={n} ==")
    print(f"despertó: {woke}/{n} | comando emitido: {emitted}/{n} | "
          f"drops post-wake: {dropped}")
    if wers:
        print(f"WER de cadena (post-corrector): mean={np.mean(wers):.4f} "
              f"p50={np.median(wers):.4f}")
        print(f"casos WER=0 (texto EXACTO): "
              f"{sum(1 for w in wers if w == 0)}/{len(wers)}")
    if eoss:
        print(f"latencia EOS (fin-de-habla→corte): p50={np.median(eoss):.0f}ms "
              f"p90={np.percentile(eoss, 90):.0f}ms max={max(eoss):.0f}ms")
    bad = [r for r in results if r["wake"] and (not r["final"] or r["wer"] > 0.5)]
    if bad:
        print(f"\npeores casos ({len(bad)}):")
        for r in bad[:12]:
            print(f"  {r['file']}: esperado={r['expected'][:40]!r} "
                  f"final={r['final'][:40]!r} eos={r['eos_ms']}")
    print(f"total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
