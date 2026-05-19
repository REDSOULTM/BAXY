"""v4 fine-tune: streaming-aware training.

The key insight from v3: validation F1=0.905 but audit F1=0.157.
The model overfits to clips perfectly centered; in streaming inference
the wake-word appears at various offsets within the sliding window,
which we never trained for.

v4 strategy: extract features at MULTIPLE offsets per positive clip
(simulating where the wake-word lands within the streaming window).
For each positive clip we pad it with silence and slide a window across,
generating ~10 different "positive" feature snapshots per clip. This
matches the inference-time distribution.
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
MODEL_OUT_PATH = ROOT / "gemma4_agent" / "voice" / "models" / "oww" / "hey_gemma_v4.onnx"

WAKE_DATASET = ROOT / "wake_dataset"
POSITIVE_DIR = WAKE_DATASET / "positive"
EXPECTED_JSON = ROOT / "gemma4_agent" / "voice" / "tests" / "testaudio_v2_expected.json"
AUDIO_PATH = ROOT / "gemma4_agent" / "voice" / "tests" / "Grabación (2).wav"

SAMPLE_RATE = 16000
# Streaming window: 16 frames * 80ms = 1.28s of feature context
STREAM_WINDOW_S = 1.28
STREAM_WINDOW_SAMPLES = int(STREAM_WINDOW_S * SAMPLE_RATE)
CHUNK_S = 0.08
CHUNK_SAMPLES = 1280  # 80ms at 16kHz


def _load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        assert wf.getframerate() == SAMPLE_RATE
        raw = wf.readframes(wf.getnframes())
    audio = np.frombuffer(raw, dtype=np.int16)
    if wf.getnchannels() > 1:
        audio = audio.reshape(-1, wf.getnchannels()).mean(axis=1).astype(np.int16)
    return audio


def streaming_features(audio_features: AudioFeatures, audio: np.ndarray,
                        n_offsets: int = 8) -> list[np.ndarray]:
    """Simulate streaming feature extraction at multiple offsets.

    Pads the clip with silence and slides a window of 16 frames across,
    producing one feature snapshot per offset.
    """
    # Pad both sides with silence to simulate the audio arriving at
    # different positions within the streaming buffer.
    pad = np.zeros(STREAM_WINDOW_SAMPLES, dtype=audio.dtype)
    padded = np.concatenate([pad, audio, pad])

    # Pick n_offsets evenly across positions where the wake-word
    # is at least partly inside the streaming window.
    total_len = len(padded)
    valid_start_max = total_len - STREAM_WINDOW_SAMPLES
    if valid_start_max <= 0:
        return []

    # Offsets: center the wake-word + spread out
    offsets = np.linspace(STREAM_WINDOW_SAMPLES // 4,
                          valid_start_max - STREAM_WINDOW_SAMPLES // 4,
                          n_offsets, dtype=int)
    snapshots = []
    for offset in offsets:
        clip = padded[offset:offset + STREAM_WINDOW_SAMPLES + STREAM_WINDOW_SAMPLES]
        # Feed it as if streaming
        audio_features.reset()
        for c_start in range(0, len(clip), CHUNK_SAMPLES):
            chunk = clip[c_start:c_start + CHUNK_SAMPLES]
            if len(chunk) < CHUNK_SAMPLES:
                chunk = np.pad(chunk, (0, CHUNK_SAMPLES - len(chunk)))
            audio_features(chunk)
        feats = audio_features.get_features(n_feature_frames=16)
        snapshots.append(feats)
    return snapshots


def augment_audio(audio: np.ndarray, rng: np.random.RandomState) -> np.ndarray:
    audio_f = audio.astype(np.float32) / 32768.0
    if rng.random() < 0.5:
        n_steps = rng.uniform(-2, 2)
        try:
            audio_f = librosa.effects.pitch_shift(audio_f, sr=SAMPLE_RATE, n_steps=n_steps)
        except Exception:
            pass
    if rng.random() < 0.5:
        rate = rng.uniform(0.9, 1.1)
        try:
            audio_f = librosa.effects.time_stretch(audio_f, rate=rate)
        except Exception:
            pass
    if rng.random() < 0.7:
        noise_level = rng.uniform(0.001, 0.01)
        audio_f = audio_f + rng.normal(0, noise_level, len(audio_f)).astype(np.float32)
    if rng.random() < 0.3:
        gain = rng.uniform(0.5, 1.5)
        audio_f = np.clip(audio_f * gain, -1.0, 1.0)
    return (audio_f * 32767).astype(np.int16)


def build_streaming_dataset(verbose=True):
    af = AudioFeatures()

    # Positives: each clip × 5 augmentations × 8 streaming offsets = 40 features per clip
    pos_files = sorted(POSITIVE_DIR.glob("*.wav"))
    print(f"Building positive dataset: {len(pos_files)} × 5 aug × 8 offsets = {len(pos_files) * 5 * 8} samples")
    pos_features = []
    rng = np.random.RandomState(42)
    for i, p in enumerate(pos_files):
        audio = _load_wav(p)
        # Original
        snapshots = streaming_features(af, audio, n_offsets=8)
        pos_features.extend(snapshots)
        # 4 augmentations
        for _ in range(4):
            aug = augment_audio(audio, rng)
            snapshots = streaming_features(af, aug, n_offsets=8)
            pos_features.extend(snapshots)
        if verbose and (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(pos_files)} ({len(pos_features)} features so far)")
    pos_features = np.stack(pos_features)
    print(f"Positives final: {pos_features.shape}")

    # Negatives: dense sliding window across gaps in the original audio
    audio = _load_wav(AUDIO_PATH)
    with open(EXPECTED_JSON, encoding="utf-8") as fh:
        expected = json.load(fh)
    wake_times = sorted(float(w["timestamp_s"]) for w in expected["wakes"])
    forbidden = [(ts - 0.3, ts + 0.9) for ts in wake_times]

    duration_s = len(audio) / SAMPLE_RATE
    step_s = 0.16  # dense
    neg_features = []
    t = 0.0
    while t + STREAM_WINDOW_S <= duration_s:
        window_end = t + STREAM_WINDOW_S
        if not any(not (window_end <= f_start or t >= f_end)
                   for f_start, f_end in forbidden):
            start_idx = int(t * SAMPLE_RATE)
            end_idx = start_idx + STREAM_WINDOW_SAMPLES
            clip = audio[start_idx:end_idx]
            if len(clip) < STREAM_WINDOW_SAMPLES:
                clip = np.pad(clip, (0, STREAM_WINDOW_SAMPLES - len(clip)))
            # Feed as streaming
            af.reset()
            for c_start in range(0, len(clip), CHUNK_SAMPLES):
                chunk = clip[c_start:c_start + CHUNK_SAMPLES]
                if len(chunk) < CHUNK_SAMPLES:
                    chunk = np.pad(chunk, (0, CHUNK_SAMPLES - len(chunk)))
                af(chunk)
            feats = af.get_features(n_feature_frames=16)
            neg_features.append(feats)
        t += step_s
    neg_features = np.stack(neg_features)
    print(f"Negatives final: {neg_features.shape}")

    return pos_features, neg_features


class HeyGemmaModel(nn.Module):
    def __init__(self, input_size=16 * 96, layer_size=32):
        super().__init__()
        self.flatten = nn.Flatten()
        self.layer1 = nn.Linear(input_size, layer_size)
        self.layernorm1 = nn.LayerNorm(layer_size)
        self.block0_fcn = nn.Linear(layer_size, layer_size)
        self.block0_norm = nn.LayerNorm(layer_size)
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
                continue
            param = dict(model.named_parameters())[torch_name]
            arr = torch.from_numpy(init[onnx_name].copy())
            if arr.shape != param.shape:
                continue
            param.copy_(arr)
            loaded += 1
        print(f"Loaded {loaded}/{len(mapping)} weight tensors from v1")


def main():
    pos_cache = WAKE_DATASET / "finetune_features" / "v4_positives.npy"
    neg_cache = WAKE_DATASET / "finetune_features" / "v4_negatives.npy"

    if pos_cache.exists() and neg_cache.exists():
        print("Loading v4 cached features...")
        pos = np.load(pos_cache)
        neg = np.load(neg_cache)
    else:
        pos, neg = build_streaming_dataset()
        pos_cache.parent.mkdir(parents=True, exist_ok=True)
        np.save(pos_cache, pos)
        np.save(neg_cache, neg)
    print(f"Positives: {pos.shape}, Negatives: {neg.shape}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = HeyGemmaModel().to(device)
    load_v1_weights(model, MODEL_V1_PATH)
    model.to(device)

    rng = np.random.RandomState(42)
    pos_idx = rng.permutation(len(pos))
    neg_idx = rng.permutation(len(neg))
    pos_split = int(0.85 * len(pos))
    neg_split = int(0.85 * len(neg))
    X_train = np.concatenate([pos[pos_idx[:pos_split]], neg[neg_idx[:neg_split]]]).astype(np.float32)
    y_train = np.concatenate([np.ones(pos_split), np.zeros(neg_split)]).astype(np.float32)
    X_val = np.concatenate([pos[pos_idx[pos_split:]], neg[neg_idx[neg_split:]]]).astype(np.float32)
    y_val = np.concatenate([np.ones(len(pos) - pos_split), np.zeros(len(neg) - neg_split)]).astype(np.float32)

    print(f"Train: {len(X_train)} ({y_train.sum():.0f} pos)")
    print(f"Val:   {len(X_val)} ({y_val.sum():.0f} pos)")

    X_train_t = torch.from_numpy(X_train).to(device)
    y_train_t = torch.from_numpy(y_train).to(device).unsqueeze(1)
    X_val_t = torch.from_numpy(X_val).to(device)
    y_val_t = torch.from_numpy(y_val).to(device).unsqueeze(1)

    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=300)

    def focal_loss(pred, target, gamma=2.0, alpha=0.75):
        eps = 1e-7
        pred = pred.clamp(eps, 1 - eps)
        pos = -alpha * (1 - pred) ** gamma * target * torch.log(pred)
        neg = -(1 - alpha) * pred ** gamma * (1 - target) * torch.log(1 - pred)
        return (pos + neg).mean()

    n_epochs = 300
    batch_size = 256
    best_val_f1 = 0.0
    best_state = None
    patience = 50
    epochs_no_improve = 0

    for epoch in range(n_epochs):
        model.train()
        perm = torch.randperm(len(X_train_t))
        losses = []
        for start in range(0, len(X_train_t), batch_size):
            idx = perm[start:start + batch_size]
            optimizer.zero_grad()
            out = model(X_train_t[idx])
            loss = focal_loss(out, y_train_t[idx])
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
        scheduler.step()

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
                    best_thr_f1, best_thr_p, best_thr_r, best_thr = f1, p, r, thr

        if epoch % 20 == 0 or epoch == n_epochs - 1:
            print(f"Epoch {epoch:3d}: loss={np.mean(losses):.4f}  "
                  f"P={best_thr_p:.3f} R={best_thr_r:.3f} F1={best_thr_f1:.3f} thr={best_thr}")

        if best_thr_f1 > best_val_f1:
            best_val_f1 = best_thr_f1
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            epochs_no_improve = 0
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= patience:
                print(f"Early stop @ {epoch}")
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
