"""Sintetizador de bloques nativos (lado VENV) — CLI puro de síntesis.

Corre bajo .venv_livekit (torch + livekit); NO importa STT (eso vive en el
python principal — el orquestador gatea el contenido por subproceso).
Síntesis DIRECTA con sid puro (el slerp del paquete degenera checkpoints
MLS — medido), pico 0.85 (la lección del alemán susurrado), guard de
duración con reintentos.

Uso:
  .venv_livekit/Scripts/python.exe scripts/wake_native_block_builder.py \
      <voice_id> <length_scales_csv> <noise_scale_ws_csv> \
      probe <out_dir> <n>                 # n clips de prueba (probe_000.wav)
  ... block <train_start> <train_end> <val_start> <val_end>   # bloque real
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".venv_livekit" / "Lib" / "site-packages"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

import json  # noqa: E402
import numpy as np  # noqa: E402
import scipy.io.wavfile as wavf  # noqa: E402
from scipy.signal import resample_poly  # noqa: E402

PIPER = ROOT / "data" / "piper"
OUT_TRAIN = ROOT / "output" / "baxy" / "positive_train"
OUT_VAL = ROOT / "output" / "baxy" / "positive_test"
PHRASES = ["baxy", "baxy.", "Baxy!", "baxi", "backsy"]
TARGET_SR = 16000
MAX_DUR_S = 3.0
PEAK = 0.85


class Synth:
    def __init__(self, voice_id: str, ls: list[float], nsw: list[float]) -> None:
        import torch
        from livekit.wakeword.data.piper.synthesis import (
            _load_vits_model, get_phonemes,
        )
        self.torch = torch
        pt = PIPER / f"{voice_id}-p2.pt"
        self.cfg = json.load(open(pt.with_suffix(".json"), encoding="utf-8"))
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu")
        self.model = _load_vits_model(pt, self.device)
        self.sr = self.cfg["audio"]["sample_rate"]
        self.n_spk = max(1, int(self.cfg["num_speakers"]))
        self.ids = {p: get_phonemes(self.cfg, p,
                                    voice=self.cfg["espeak"]["voice"])
                    for p in PHRASES}
        self.ls, self.nsw = ls, nsw

    def synth(self, seed: int) -> "np.ndarray | None":
        from math import gcd
        rng = np.random.RandomState(seed)
        for attempt in range(6):
            phrase = PHRASES[(seed + attempt) % len(PHRASES)]
            x = self.torch.LongTensor([self.ids[phrase]]).to(self.device)
            xl = self.torch.LongTensor([len(self.ids[phrase])]).to(self.device)
            sid = self.torch.LongTensor(
                [int(rng.randint(0, self.n_spk))]).to(self.device) \
                if self.n_spk > 1 else None
            self.torch.manual_seed(seed * 13 + attempt)
            with self.torch.no_grad():
                a = self.model.infer(
                    x, xl, sid=sid, noise_scale=0.667,
                    length_scale=float(rng.choice(self.ls)),
                    noise_scale_w=float(rng.choice(self.nsw)))[0]
            a = a.squeeze().float().cpu().numpy()
            if 0.15 * self.sr < a.size <= MAX_DUR_S * self.sr:
                g = gcd(self.sr, TARGET_SR)
                a16 = resample_poly(a, TARGET_SR // g, self.sr // g)
                peak = float(np.max(np.abs(a16))) + 1e-9
                return (a16 / peak * 32767 * PEAK).astype(np.int16)
        return None


def main() -> int:
    voice_id = sys.argv[1]
    ls = [float(v) for v in sys.argv[2].split(",")]
    nsw = [float(v) for v in sys.argv[3].split(",")]
    mode = sys.argv[4]
    s = Synth(voice_id, ls, nsw)
    if mode == "probe":
        out_dir = Path(sys.argv[5])
        out_dir.mkdir(parents=True, exist_ok=True)
        n = int(sys.argv[6])
        made = 0
        for k in range(n):
            a = s.synth(900000 + k)
            if a is not None:
                wavf.write(str(out_dir / f"probe_{k:03d}.wav"), TARGET_SR, a)
                made += 1
        print(f"probe {voice_id}: {made}/{n} clips")
        return 0 if made >= n * 0.5 else 1
    # block
    t0, t1, v0, v1 = (int(v) for v in sys.argv[5:9])
    for out_dir, a, b in ((OUT_TRAIN, t0, t1), (OUT_VAL, v0, v1)):
        made = 0
        for i in range(a, b):
            au = s.synth(i)
            if au is None:
                continue
            wavf.write(str(out_dir / f"clip_{i:06d}.wav"), TARGET_SR, au)
            made += 1
        print(f"block {voice_id} [{a}:{b}]: {made}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
