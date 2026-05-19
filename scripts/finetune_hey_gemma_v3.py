"""v3 fine-tune: heavy augmentation + more negatives + load ONNX weights properly.

Diagnosis after v2:
- v2 had val F1=0.851 but audit shows only 8.6% recall in streaming mode.
- Root cause: small training set (130) + simple architecture causes overfit;
  the model learned EXACT feature patterns of the 105 operator clips, not
  the general acoustic pattern of "hey gemma" in the operator's voice.

v3 strategy:
1. Load ONNX weights from v1 (LibriTTS) as INITIALIZATION (transfer learning),
   not random init -- v1 already learned acoustic patterns of "hey gemma".
2. Apply audio augmentation to the 105 real clips (noise, time stretch,
   pitch shift) to multiply effective training data 10x.
3. Sample MANY more negative windows (sliding window across all gaps, not
   just non-overlapping).
4. Lower learning rate (1e-4 instead of 1e-3) to avoid clobbering v1 weights.
5. Use focal loss to handle class imbalance better.
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
MODEL_OUT_PATH = ROOT / "gemma4_agent" / "voice" / "models" / "oww" / "hey_gemma_v3.onnx"

WAKE_DATASET = ROOT / "wake_dataset"
POSITIVE_DIR = WAKE_DATASET / "positive"
EXPECTED_JSON = ROOT / "gemma4_agent" / "voice" / "tests" / "testaudio_v2_expected.json"
AUDIO_PATH = ROOT / "gemma4_agent" / "voice" / "tests" / "Grabación (2).wav"

SAMPLE_RATE = 16000
WINDOW_S = 1.2
WINDOW_SAMPLES = int(WINDOW_S * SAMPLE_RATE)


def _load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        assert wf.getframerate() == SAMPLE_RATE
        raw = wf.readframes(wf.getnframes())
    audio = np.frombuffer(raw, dtype=np.int16)
    if wf.getnchannels() > 1:
        audio = audio.reshape(-1, wf.getnchannels()).mean(axis=1).astype(np.int16)
    return audio


def augment_audio(audio: np.ndarray, rng: np.random.RandomState) -> np.ndarray:
    """Apply random augmentation to a clip."""
    audio_f = audio.astype(np.float32) / 32768.0

    # 50% chance: pitch shift
    if rng.random() < 0.5:
        n_steps = rng.uniform(-2, 2)
        audio_f = librosa.effects.pitch_shift(audio_f, sr=SAMPLE_RATE, n_steps=n_steps)

    # 50% chance: time stretch
    if rng.random() < 0.5:
        rate = rng.uniform(0.9, 1.1)
        audio_f = librosa.effects.time_stretch(audio_f, rate=rate)

    # 70% chance: add white noise
    if rng.random() < 0.7:
        noise_level = rng.uniform(0.001, 0.01)
        audio_f = audio_f + rng.normal(0, noise_level, size=len(audio_f)).astype(np.float32)

    # 30% chance: volume adjust
    if rng.random() < 0.3:
        gain = rng.uniform(0.5, 1.5)
        audio_f = audio_f * gain
        audio_f = np.clip(audio_f, -1.0, 1.0)

    # Resize back to WINDOW_SAMPLES (pad/trim)
    if len(audio_f) < WINDOW_SAMPLES:
        audio_f = np.pad(audio_f, (0, WINDOW_SAMPLES - len(audio_f)))
    else:
        audio_f = audio_f[:WINDOW_SAMPLES]

    return (audio_f * 32767).astype(np.int16)


def compute_features(audio_features: AudioFeatures, audio: np.ndarray) -> np.ndarray:
    """Compute 16x96 features for a 1.2s clip."""
    if len(audio) < WINDOW_SAMPLES:
        audio = np.pad(audio, (0, WINDOW_SAMPLES - len(audio)))
    else:
        audio = audio[:WINDOW_SAMPLES]
    audio_features.reset()
    chunk_size = 1280
    for offset in range(0, len(audio), chunk_size):
        chunk = audio[offset:offset + chunk_size]
        if len(chunk) < chunk_size:
            chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
        audio_features(chunk)
    return audio_features.get_features(n_feature_frames=16)


def build_dataset(verbose=True):
    af = AudioFeatures()

    # ====== Positives: 105 real + 10x augmentation ======
    pos_files = sorted(POSITIVE_DIR.glob("*.wav"))
    print(f"Building positive dataset: {len(pos_files)} clips × 10 aug = {len(pos_files) * 10} samples")
    pos_features = []
    rng = np.random.RandomState(42)
    for i, p in enumerate(pos_files):
        audio = _load_wav(p)
        # Original
        feats = compute_features(af, audio)
        pos_features.append(feats)
        # 9 augmentations
        for _ in range(9):
            aug_audio = augment_audio(audio, rng)
            feats = compute_features(af, aug_audio)
            pos_features.append(feats)
        if verbose and (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(pos_files)}")
    pos_features = np.stack(pos_features)
    print(f"Positives final: {pos_features.shape}")

    # ====== Negatives: sliding window across audio gaps ======
    audio = _load_wav(AUDIO_PATH)
    with open(EXPECTED_JSON, encoding="utf-8") as fh:
        expected = json.load(fh)
    wake_times = sorted(float(w["timestamp_s"]) for w in expected["wakes"])
    forbidden = [(ts - 0.3, ts + 0.9) for ts in wake_times]

    duration_s = len(audio) / SAMPLE_RATE
    step_s = 0.3  # dense sliding window for more negatives
    neg_features = []
    t = 0.0
    while t + WINDOW_S <= duration_s:
        window_end = t + WINDOW_S
        if not any(not (window_end <= f_start or t >= f_end)
                   for f_start, f_end in forbidden):
            start_idx = int(t * SAMPLE_RATE)
            end_idx = int(window_end * SAMPLE_RATE)
            clip = audio[start_idx:end_idx]
            feats = compute_features(af, clip)
            neg_features.append(feats)
        t += step_s
    neg_features = np.stack(neg_features)
    print(f"Negatives final: {neg_features.shape}")

    return pos_features, neg_features


class HeyGemmaModel(nn.Module):
    """Matches the openwakeword DNN architecture: layer1 + 1 block + last_layer."""

    def __init__(self, input_size=16 * 96, layer_size=32):
        super().__init__()
        self.flatten = nn.Flatten()
        # layer1: Linear + LayerNorm
        self.layer1 = nn.Linear(input_size, layer_size)
        self.layernorm1 = nn.LayerNorm(layer_size)
        # block 0: Linear + LayerNorm + ReLU
        self.block0_fcn = nn.Linear(layer_size, layer_size)
        self.block0_norm = nn.LayerNorm(layer_size)
        # last_layer
        self.last_layer = nn.Linear(layer_size, 1)

    def forward(self, x):
        x = self.flatten(x)
        x = self.layernorm1(self.layer1(x))
        x = F.relu(x)
        x = self.block0_norm(self.block0_fcn(x))
        x = F.relu(x)
        x = torch.sigmoid(self.last_layer(x))
        return x


def load_v1_weights(model: HeyGemmaModel, onnx_path: Path):
    """Load weights from the v1 ONNX into our PyTorch model."""
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
        for onnx_name, torch_name in mapping.items():
            if onnx_name not in init:
                print(f"WARN: missing in ONNX: {onnx_name}")
                continue
            param = dict(model.named_parameters())[torch_name]
            arr = torch.from_numpy(init[onnx_name].copy())
            if arr.shape != param.shape:
                print(f"WARN: shape mismatch {onnx_name}: onnx={arr.shape} torch={param.shape}")
                continue
            param.copy_(arr)
            loaded += 1
        print(f"Loaded {loaded}/{len(mapping)} weight tensors from v1 ONNX")


def main():
    pos_cache = WAKE_DATASET / "finetune_features" / "v3_positives.npy"
    neg_cache = WAKE_DATASET / "finetune_features" / "v3_negatives.npy"

    if pos_cache.exists() and neg_cache.exists():
        print("Loading v3 cached features...")
        pos = np.load(pos_cache)
        neg = np.load(neg_cache)
    else:
        pos, neg = build_dataset()
        pos_cache.parent.mkdir(parents=True, exist_ok=True)
        np.save(pos_cache, pos)
        np.save(neg_cache, neg)
    print(f"Positives: {pos.shape}, Negatives: {neg.shape}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = HeyGemmaModel().to(device)
    load_v1_weights(model, MODEL_V1_PATH)
    model.to(device)

    # Train/val split (stratified)
    rng = np.random.RandomState(42)
    pos_idx = rng.permutation(len(pos))
    neg_idx = rng.permutation(len(neg))
    pos_split = int(0.85 * len(pos))
    neg_split = int(0.85 * len(neg))
    train_pos = pos[pos_idx[:pos_split]]
    train_neg = neg[neg_idx[:neg_split]]
    val_pos = pos[pos_idx[pos_split:]]
    val_neg = neg[neg_idx[neg_split:]]

    X_train = np.concatenate([train_pos, train_neg]).astype(np.float32)
    y_train = np.concatenate([np.ones(len(train_pos)), np.zeros(len(train_neg))]).astype(np.float32)
    X_val = np.concatenate([val_pos, val_neg]).astype(np.float32)
    y_val = np.concatenate([np.ones(len(val_pos)), np.zeros(len(val_neg))]).astype(np.float32)

    print(f"Train: {len(X_train)} ({y_train.sum():.0f} pos)")
    print(f"Val:   {len(X_val)} ({y_val.sum():.0f} pos)")

    X_train_t = torch.from_numpy(X_train).to(device)
    y_train_t = torch.from_numpy(y_train).to(device).unsqueeze(1)
    X_val_t = torch.from_numpy(X_val).to(device)
    y_val_t = torch.from_numpy(y_val).to(device).unsqueeze(1)

    # Optimizer with low LR (transfer learning)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=200)

    # Focal loss for class imbalance
    def focal_loss(pred, target, gamma=2.0, alpha=0.75):
        eps = 1e-7
        pred = pred.clamp(eps, 1 - eps)
        pos_loss = -alpha * (1 - pred) ** gamma * target * torch.log(pred)
        neg_loss = -(1 - alpha) * pred ** gamma * (1 - target) * torch.log(1 - pred)
        return (pos_loss + neg_loss).mean()

    n_epochs = 200
    batch_size = 128
    best_val_f1 = 0.0
    best_state = None
    patience = 30
    epochs_no_improve = 0

    for epoch in range(n_epochs):
        model.train()
        perm = torch.randperm(len(X_train_t))
        losses = []
        for start in range(0, len(X_train_t), batch_size):
            idx = perm[start:start + batch_size]
            x = X_train_t[idx]
            y = y_train_t[idx]
            optimizer.zero_grad()
            out = model(x)
            loss = focal_loss(out, y)
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
        scheduler.step()

        # Validate at multiple thresholds, pick the best
        model.eval()
        with torch.no_grad():
            val_out = model(X_val_t).cpu().numpy().flatten()
            val_y = y_val_t.cpu().numpy().flatten()
            best_thr_f1 = 0
            best_thr_p = 0
            best_thr_r = 0
            best_thr = 0.5
            for thr in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
                pred = (val_out > thr).astype(np.float32)
                tp = ((pred == 1) & (val_y == 1)).sum()
                fp = ((pred == 1) & (val_y == 0)).sum()
                fn = ((pred == 0) & (val_y == 1)).sum()
                p = tp / max(1, tp + fp)
                r = tp / max(1, tp + fn)
                f1 = 2 * p * r / max(1e-9, p + r)
                if f1 > best_thr_f1:
                    best_thr_f1 = f1
                    best_thr_p = p
                    best_thr_r = r
                    best_thr = thr

        if epoch % 10 == 0 or epoch == n_epochs - 1:
            print(f"Epoch {epoch:3d}: loss={np.mean(losses):.4f}  "
                  f"val P={best_thr_p:.3f} R={best_thr_r:.3f} F1={best_thr_f1:.3f} "
                  f"(thr={best_thr})")

        if best_thr_f1 > best_val_f1:
            best_val_f1 = best_thr_f1
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            epochs_no_improve = 0
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= patience:
                print(f"Early stop at epoch {epoch} (patience {patience})")
                break

    print(f"\nBest val F1: {best_val_f1:.3f}")
    model.load_state_dict(best_state)
    model.eval().cpu()

    dummy = torch.zeros(1, 16, 96)
    torch.onnx.export(
        model, dummy, str(MODEL_OUT_PATH),
        input_names=["onnx::Flatten_0"],
        output_names=["output"],
        opset_version=14,
    )
    # Rename output 'output' -> '39' to match openwakeword convention
    import onnx as _onnx
    m = _onnx.load(str(MODEL_OUT_PATH))
    for o in m.graph.output:
        if o.name == "output":
            o.name = "39"
    for n in m.graph.node:
        for i, x in enumerate(n.output):
            if x == "output": n.output[i] = "39"
        for i, x in enumerate(n.input):
            if x == "output": n.input[i] = "39"
    _onnx.save(m, str(MODEL_OUT_PATH))

    print(f"\nWrote {MODEL_OUT_PATH}")
    print(f"Size: {MODEL_OUT_PATH.stat().st_size} bytes")


if __name__ == "__main__":
    main()
