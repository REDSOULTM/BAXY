"""Test EN VIVO del AEC: captura mic + loopback simultáneos con la música
REAL del usuario sonando, corre el EchoCanceller y mide ERLE + delay.

Fase 1 (música sola): ¿el cancelador atenúa el eco real de la sala con la
deriva de reloj real? ERLE esperado >= 6-10 dB para validar.
Fase 2 (--with-wake): el usuario dice "Baxy" durante la captura; score del
wake (modelo prod) crudo vs cancelado.

Uso: python scripts/_diag/_aec_live_test.py [--secs 15] [--with-wake]
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

import _ort_throttle  # noqa: F401,E402

import numpy as np  # noqa: E402
import scipy.io.wavfile as wavf  # noqa: E402

from gemma4_agent.voice.aec import EchoCanceller, CHUNK  # noqa: E402
from gemma4_agent.voice.audio_io import (  # noqa: E402
    AudioCapture, LoopbackReference, SAMPLE_RATE,
)

OUT = ROOT / "documentacion" / "_aec_live"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=float, default=15.0)
    ap.add_argument("--with-wake", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    mic_chunks: list[np.ndarray] = []
    ref_chunks: list[np.ndarray] = []
    lb = LoopbackReference()
    assert lb.start(), f"loopback no arranco: {lb.last_error}"

    lock = threading.Lock()

    def on_chunk(c: np.ndarray) -> None:
        with lock:
            mic_chunks.append(c.copy())
            ref_chunks.append(lb.latest(CHUNK))

    cap = AudioCapture(on_chunk=on_chunk)
    assert cap.start(), f"mic no arranco: {cap.last_error}"
    if args.with_wake:
        # cuenta regresiva con BEEP de largada: el usuario habla recién al
        # beep (la vez anterior la captura arrancó antes de que leyera).
        import winsound
        for k in (3, 2, 1):
            print(f"  ...{k}")
            time.sleep(1)
        winsound.Beep(880, 250)
        print(">>> AHORA: decí 'Baxy' (pausa) 'Baxy' (pausa) 'Baxy' <<<")
    print(f"capturando {args.secs:.0f}s... (música sonando"
          + (" + decí 'Baxy' 3 veces)" if args.with_wake else ")"))
    time.sleep(args.secs)
    cap.stop()
    lb.stop()

    mic = np.concatenate(mic_chunks)
    ref = np.concatenate(ref_chunks)
    n = min(mic.size, ref.size)
    mic, ref = mic[:n], ref[:n]
    rms = lambda x: float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))  # noqa: E731
    print(f"mic rms={rms(mic):.0f}  ref rms={rms(ref):.0f}  ({n / 16000:.1f}s)")
    if rms(ref) < 50:
        print("WARN: la referencia está casi en silencio — ¿hay música sonando?")

    aec = EchoCanceller()
    out = np.empty_like(mic)
    t0 = time.time()
    for i in range(0, n - CHUNK + 1, CHUNK):
        out[i:i + CHUNK] = aec.process(mic[i:i + CHUNK], ref[i:i + CHUNK])
    out = out[:n]
    rt_factor = (n / 16000) / (time.time() - t0)
    print(f"delay estimado: {aec._delay_est.delay} samples "
          f"({(aec._delay_est.delay or 0) / 16:.0f} ms) | "
          f"proceso {rt_factor:.1f}x tiempo-real")

    # ERLE por tercios (convergencia): atenuación del eco residual
    third = n // 3
    for k, name in enumerate(("inicio", "medio", "final")):
        s = slice(k * third, (k + 1) * third)
        p_in = float(np.mean(mic[s].astype(np.float64) ** 2)) + 1e-9
        p_out = float(np.mean(out[s].astype(np.float64) ** 2)) + 1e-9
        print(f"  ERLE {name}: {10 * np.log10(p_in / p_out):5.1f} dB")

    wavf.write(str(OUT / "mic_crudo.wav"), SAMPLE_RATE, mic)
    wavf.write(str(OUT / "mic_cancelado.wav"), SAMPLE_RATE, out)
    wavf.write(str(OUT / "referencia.wav"), SAMPLE_RATE, ref)
    print(f"wavs en {OUT}")

    if args.with_wake:
        from gemma4_agent.voice.livekit_runtime import LiveKitWakeRuntime
        rt = LiveKitWakeRuntime(
            ROOT / "gemma4_agent" / "voice" / "models" / "livekit", "baxy")
        assert rt.load()
        win, hop = 2 * SAMPLE_RATE, SAMPLE_RATE // 4

        def fires(x: np.ndarray) -> int:
            count, cool = 0, -1.0
            for s in range(0, x.size - win + 1, hop):
                t = s / SAMPLE_RATE
                if t < cool:
                    continue
                if float(rt.predict(x[s:s + win])) >= 0.25:
                    count += 1
                    cool = t + 2.0
            return count
        print(f"wake fires: crudo={fires(mic)}  cancelado={fires(out)} "
              f"(dijiste 'Baxy' ~3 veces)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
