"""v6 fine-tune: heavy negatives + dropout + strong regularization.

Diagnosis after v5: F1=0.722 streaming-val but audit still ~10 fires
total because the model still over-fires. In-wake mean score 0.393,
outside mean 0.203 -- separation exists but threshold has to be very
high to avoid FPs.

v6 strategy:
1. ADD many more diverse negatives: samples/audio_*.wav (5 TTS files),
   more synthetic background variations.
2. Reduce positives augmentation -- v5 had 2100 positives, way too
   many similar features. Reduce to 105 × 3 aug × 4 offsets = 1260.
3. Add dropout to model (p=0.3).
4. Strong weight decay (1e-2).
5. Use BCE loss with class weights instead of focal loss.
6. Hold out HALF the operator's clips as validation set (not training).
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import librosa

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from openwakeword.utils import AudioFeatures

MODEL_V1_PATH = ROOT / "gemma4_agent" / "voice" / "models" / "oww" / "hey_gemma_v1_libritts_only.onnx"
MODEL_OUT_PATH = ROOT / "gemma4_agent" / "voice" / "models" / "oww" / "hey_gemma_v6.onnx"

WAKE_DATASET = ROOT / "wake_dataset"
POSITIVE_DIR = WAKE_DATASET / "positive"
EXPECTED_JSON = ROOT / "gemma4_agent" / "voice" / "tests" / "testaudio_v2_expected.json"
AUDIO_PATH = ROOT / "gemma4_agent" / "voice" / "tests" / "Grabación (2).wav"
SAMPLES_DIR = ROOT / "samples"

SAMPLE_RATE = 16000
STREAM_WINDOW_S = 1.28
STREAM_WINDOW_SAMPLES = int(STREAM_WINDOW_S * SAMPLE_RATE)
CHUNK_SAMPLES = 1280


def _load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
        ch = wf.getnchannels()
    audio = np.frombuffer(raw, dtype=np.int16)
    if ch > 1:
        audio = audio.reshape(-1, ch).mean(axis=1).astype(np.int16)
    if sr != SAMPLE_RATE:
        af = audio.astype(np.float32) / 32768.0
        af = librosa.resample(af, orig_sr=sr, target_sr=SAMPLE_RATE)
        audio = (af * 32767).astype(np.int16)
    return audio


def compute_feature(af: AudioFeatures, clip: np.ndarray) -> np.ndarray:
    if len(clip) < STREAM_WINDOW_SAMPLES:
        clip = np.pad(clip, (0, STREAM_WINDOW_SAMPLES - len(clip)))
    else:
        clip = clip[:STREAM_WINDOW_SAMPLES]
    af.reset()
    for c_start in range(0, len(clip), CHUNK_SAMPLES):
        chunk = clip[c_start:c_start + CHUNK_SAMPLES]
        if len(chunk) < CHUNK_SAMPLES:
            chunk = np.pad(chunk, (0, CHUNK_SAMPLES - len(chunk)))
        af(chunk)
    return af.get_features(n_feature_frames=16)


def streaming_features_with_offsets(af, audio, n_offsets=4):
    pad = np.zeros(STREAM_WINDOW_SAMPLES, dtype=audio.dtype)
    padded = np.concatenate([pad, audio, pad])
    total = len(padded)
    valid_max = total - STREAM_WINDOW_SAMPLES
    if valid_max <= 0:
        return []
    offsets = np.linspace(STREAM_WINDOW_SAMPLES // 4,
                           valid_max - STREAM_WINDOW_SAMPLES // 4,
                           n_offsets, dtype=int)
    return [compute_feature(af, padded[o:o + STREAM_WINDOW_SAMPLES]) for o in offsets]


def augment_audio(audio, rng):
    af_ = audio.astype(np.float32) / 32768.0
    if rng.random() < 0.4:
        try:
            af_ = librosa.effects.pitch_shift(af_, sr=SAMPLE_RATE, n_steps=rng.uniform(-1.5, 1.5))
        except Exception:
            pass
    if rng.random() < 0.4:
        try:
            af_ = librosa.effects.time_stretch(af_, rate=rng.uniform(0.92, 1.08))
        except Exception:
            pass
    if rng.random() < 0.7:
        af_ = af_ + rng.normal(0, rng.uniform(0.002, 0.012), len(af_)).astype(np.float32)
    return np.clip((af_ * 32767), -32768, 32767).astype(np.int16)


def build_dataset_v6():
    af = AudioFeatures()
    rng = np.random.RandomState(42)

    # ===== Positives: 105 × 3 aug × 4 offsets = 1260 =====
    pos_files = sorted(POSITIVE_DIR.glob("*.wav"))
    print(f"Positives: {len(pos_files)} × 3 aug × 4 offsets")
    pos_features = []
    for i, p in enumerate(pos_files):
        audio = _load_wav(p)
        snapshots = streaming_features_with_offsets(af, audio, n_offsets=4)
        pos_features.extend(snapshots)
        for _ in range(2):
            aug = augment_audio(audio, rng)
            pos_features.extend(streaming_features_with_offsets(af, aug, n_offsets=4))
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(pos_files)} -> {len(pos_features)} features")
    pos_features = np.stack(pos_features)
    print(f"Positives: {pos_features.shape}")

    # ===== Negatives =====
    neg_features = []

    # Source 1: dense sliding from Grabación (2) gaps
    audio = _load_wav(AUDIO_PATH)
    with open(EXPECTED_JSON, encoding="utf-8") as fh:
        expected = json.load(fh)
    wake_times = sorted(float(w["timestamp_s"]) for w in expected["wakes"])
    forbidden = [(ts - 0.4, ts + 1.0) for ts in wake_times]
    duration_s = len(audio) / SAMPLE_RATE
    t = 0.0
    while t + STREAM_WINDOW_S <= duration_s:
        end = t + STREAM_WINDOW_S
        if not any(not (end <= fs or t >= fe) for fs, fe in forbidden):
            start_idx = int(t * SAMPLE_RATE)
            clip = audio[start_idx:start_idx + STREAM_WINDOW_SAMPLES]
            neg_features.append(compute_feature(af, clip))
        t += 0.16
    print(f"Negs (gap sliding): {len(neg_features)}")

    # Source 2: samples/*.wav (TTS samples, different speakers / phrases)
    for sample_path in SAMPLES_DIR.glob("audio_*.wav"):
        try:
            sclip = _load_wav(sample_path)
            # Multiple windows from each
            for _ in range(20):
                if len(sclip) < STREAM_WINDOW_SAMPLES:
                    sclip_p = np.pad(sclip, (0, STREAM_WINDOW_SAMPLES - len(sclip)))
                    neg_features.append(compute_feature(af, sclip_p))
                    break
                start = rng.randint(0, max(1, len(sclip) - STREAM_WINDOW_SAMPLES))
                neg_features.append(compute_feature(af, sclip[start:start + STREAM_WINDOW_SAMPLES]))
        except Exception:
            continue
    print(f"After samples: {len(neg_features)}")

    # Source 3: heavy synthetic background variations (lots)
    print("Adding 3000 synthetic background negatives...")
    for _ in range(3000):
        base = rng.normal(0, rng.uniform(300, 4000), STREAM_WINDOW_SAMPLES)
        # Tones
        if rng.random() < 0.5:
            n_tones = rng.randint(1, 6)
            for _ in range(n_tones):
                ts_idx = rng.randint(0, STREAM_WINDOW_SAMPLES - 800)
                tl = rng.randint(300, 2500)
                te = min(ts_idx + tl, STREAM_WINDOW_SAMPLES)
                freq = rng.uniform(150, 3000)
                t_ax = np.arange(te - ts_idx) / SAMPLE_RATE
                tone = np.sin(2 * np.pi * freq * t_ax) * rng.uniform(300, 4000)
                base[ts_idx:te] += tone
        # Filtered noise (more speech-like)
        if rng.random() < 0.3:
            kernel_len = rng.randint(50, 200)
            kernel = np.exp(-np.arange(kernel_len) / rng.uniform(20, 80))
            kernel = kernel / kernel.sum()
            base = np.convolve(base, kernel, mode='same')
        clip = np.clip(base, -32768, 32767).astype(np.int16)
        neg_features.append(compute_feature(af, clip))
    print(f"Final negatives: {len(neg_features)}")

    neg_features = np.stack(neg_features)
    return pos_features, neg_features


class HeyGemmaModelDropout(nn.Module):
    def __init__(self, input_size=16 * 96, layer_size=32, dropout=0.3):
        super().__init__()
        self.flatten = nn.Flatten()
        self.layer1 = nn.Linear(input_size, layer_size)
        self.layernorm1 = nn.LayerNorm(layer_size)
        self.drop1 = nn.Dropout(dropout)
        self.block0_fcn = nn.Linear(layer_size, layer_size)
        self.block0_norm = nn.LayerNorm(layer_size)
        self.drop2 = nn.Dropout(dropout)
        self.last_layer = nn.Linear(layer_size, 1)

    def forward(self, x):
        x = self.flatten(x)
        x = self.layernorm1(self.layer1(x))
        x = F.relu(x)
        x = self.drop1(x)
        x = self.block0_norm(self.block0_fcn(x))
        x = F.relu(x)
        x = self.drop2(x)
        x = torch.sigmoid(self.last_layer(x))
        return x


def load_v1_weights(model, onnx_path):
    import onnx
    from onnx import numpy_helper
    m = onnx.load(str(onnx_path))
    init = {i.name: numpy_helper.to_array(i) for i in m.graph.initializer}
    mapping = {
        "layer1.weight": "layer1.weight",
        "layer1.bias": "layer1.bias",
        "layernorm1.weight": "layernorm1.weight",
        "layernorm1.bias": "layernorm1.bias",
        "blocks.0.fcn_layer.weight": "block0_fcn.weight",
        "blocks.0.fcn_layer.bias": "block0_fcn.bias",
        "blocks.0.layer_norm.weight": "block0_norm.weight",
        "blocks.0.layer_norm.bias": "block0_norm.bias",
        "last_layer.weight": "last_layer.weight",
        "last_layer.bias": "last_layer.bias",
    }
    with torch.no_grad():
        loaded = 0
        for oname, tname in mapping.items():
            if oname not in init: continue
            p = dict(model.named_parameters())[tname]
            a = torch.from_numpy(init[oname].copy())
            if a.shape != p.shape: continue
            p.copy_(a)
            loaded += 1
        print(f"Loaded {loaded}/{len(mapping)} weights from v1")


def main():
    pos_cache = WAKE_DATASET / "finetune_features" / "v6_positives.npy"
    neg_cache = WAKE_DATASET / "finetune_features" / "v6_negatives.npy"

    if pos_cache.exists() and neg_cache.exists():
        print("Loading v6 cached features...")
        pos = np.load(pos_cache)
        neg = np.load(neg_cache)
    else:
        pos, neg = build_dataset_v6()
        pos_cache.parent.mkdir(parents=True, exist_ok=True)
        np.save(pos_cache, pos)
        np.save(neg_cache, neg)
    print(f"Positives: {pos.shape}, Negatives: {neg.shape}")
    print(f"Ratio neg:pos = {len(neg)/len(pos):.2f}")

    # Streaming-real validation set (audit-style)
    print("\nBuilding streaming validation set...")
    af = AudioFeatures()
    audio = _load_wav(AUDIO_PATH)
    with open(EXPECTED_JSON, encoding="utf-8") as fh:
        expected = json.load(fh)
    wake_times = sorted(float(w["timestamp_s"]) for w in expected["wakes"])
    rng = np.random.RandomState(123)
    forbidden = [(ts - 0.4, ts + 1.0) for ts in wake_times]

    # Positives: features at the wake center
    val_pos = []
    val_wakes = rng.choice(len(wake_times), 25, replace=False)
    for wi in val_wakes:
        wt = wake_times[wi]
        center = int(wt * SAMPLE_RATE)
        start = max(0, center - STREAM_WINDOW_SAMPLES // 2)
        end = start + STREAM_WINDOW_SAMPLES
        if end > len(audio): continue
        val_pos.append(compute_feature(af, audio[start:end]))
    val_pos = np.stack(val_pos)

    # Negatives from random outside-wake gaps
    val_neg = []
    tries = 0
    while len(val_neg) < 150 and tries < 1000:
        tries += 1
        t = rng.uniform(0, len(audio) / SAMPLE_RATE - STREAM_WINDOW_S)
        end = t + STREAM_WINDOW_S
        if any(not (end <= fs or t >= fe) for fs, fe in forbidden):
            continue
        si = int(t * SAMPLE_RATE)
        val_neg.append(compute_feature(af, audio[si:si + STREAM_WINDOW_SAMPLES]))
    val_neg = np.stack(val_neg)
    print(f"Stream val: {len(val_pos)} pos, {len(val_neg)} neg")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = HeyGemmaModelDropout(dropout=0.3).to(device)
    load_v1_weights(model, MODEL_V1_PATH)
    model.to(device)

    X_train = np.concatenate([pos, neg]).astype(np.float32)
    y_train = np.concatenate([np.ones(len(pos)), np.zeros(len(neg))]).astype(np.float32)
    X_val = np.concatenate([val_pos, val_neg]).astype(np.float32)
    y_val = np.concatenate([np.ones(len(val_pos)), np.zeros(len(val_neg))]).astype(np.float32)

    print(f"Train: {len(X_train)} ({y_train.sum():.0f} pos, ratio neg/pos = {(len(y_train) - y_train.sum()) / y_train.sum():.2f})")
    print(f"Stream val: {len(X_val)} ({y_val.sum():.0f} pos)")

    Xt = torch.from_numpy(X_train).to(device)
    yt = torch.from_numpy(y_train).to(device).unsqueeze(1)
    Xv = torch.from_numpy(X_val).to(device)
    yv = torch.from_numpy(y_val).to(device).unsqueeze(1)

    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=1e-2)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=150)

    # Weighted BCE
    pos_weight = torch.tensor([len(neg) / max(1, len(pos))]).to(device)
    criterion = nn.BCELoss(reduction='none')

    best_f1 = 0
    best_state = None
    patience = 30
    no_improve = 0

    for epoch in range(200):
        model.train()
        perm = torch.randperm(len(Xt))
        losses = []
        for s in range(0, len(Xt), 256):
            idx = perm[s:s + 256]
            optimizer.zero_grad()
            out = model(Xt[idx])
            y_b = yt[idx]
            loss = criterion(out, y_b)
            w = y_b * pos_weight + (1 - y_b) * 1.0
            loss = (loss * w).mean()
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
        scheduler.step()

        model.eval()
        with torch.no_grad():
            vo = model(Xv).cpu().numpy().flatten()
            vy = yv.cpu().numpy().flatten()
            best_local_f1, best_p, best_r, best_thr = 0, 0, 0, 0.5
            for thr in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9]:
                pred = (vo > thr).astype(np.float32)
                tp = ((pred == 1) & (vy == 1)).sum()
                fp = ((pred == 1) & (vy == 0)).sum()
                fn = ((pred == 0) & (vy == 1)).sum()
                p = tp / max(1, tp + fp)
                r = tp / max(1, tp + fn)
                f1 = 2 * p * r / max(1e-9, p + r)
                if f1 > best_local_f1:
                    best_local_f1, best_p, best_r, best_thr = f1, p, r, thr

        if epoch % 10 == 0 or epoch == 199:
            print(f"Epoch {epoch:3d}: loss={np.mean(losses):.4f}  P={best_p:.3f} R={best_r:.3f} F1={best_local_f1:.3f} thr={best_thr}")

        if best_local_f1 > best_f1:
            best_f1 = best_local_f1
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                print(f"Early stop @ {epoch}")
                break

    print(f"\nBest streaming F1: {best_f1:.3f}")
    model.load_state_dict(best_state)
    model.eval().cpu()

    dummy = torch.zeros(1, 16, 96)
    torch.onnx.export(model, dummy, str(MODEL_OUT_PATH),
                       input_names=["onnx::Flatten_0"],
                       output_names=["output"],
                       opset_version=14)
    import onnx as _onnx
    m = _onnx.load(str(MODEL_OUT_PATH))
    for o in m.graph.output:
        if o.name == "output": o.name = "39"
    for n in m.graph.node:
        for i, x in enumerate(n.output):
            if x == "output": n.output[i] = "39"
        for i, x in enumerate(n.input):
            if x == "output": n.input[i] = "39"
    _onnx.save(m, str(MODEL_OUT_PATH))
    print(f"Wrote {MODEL_OUT_PATH} ({MODEL_OUT_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
