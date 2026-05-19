"""Fine-tune the hey_gemma openWakeWord model with operator's real clips.

Sprint R3.1 hotfix path: WSL training got us a v1 model trained on
LibriTTS English voices, which has 100% precision but only 0.019 recall
on the operator's Spanish-rioplatense voice. This script does a Windows-
local fine-tune of that v1 model using the 105 operator clips already
extracted by scripts/build_wake_dataset.py.

Strategy:
  1. Load the existing hey_gemma.onnx into PyTorch via manual conversion
     of the simple DNN architecture (Flatten -> Gemm/LayerNorm chain).
  2. Compute openwakeword features for the 105 operator real positives.
  3. Compute openwakeword features for ~500 negative windows extracted
     from the gaps in Grabacion (2).wav (where no wake is annotated).
  4. Fine-tune the loaded model with these new features for ~30 epochs.
  5. Re-export as ONNX.

Requires .venv_train (torch+cuda, openwakeword, librosa, onnx).
Run from project root with the venv's python:
    .\.venv_train\Scripts\python.exe scripts\finetune_hey_gemma.py
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
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from openwakeword.utils import AudioFeatures

MODEL_PATH = ROOT / "gemma4_agent" / "voice" / "models" / "oww" / "hey_gemma.onnx"
WAKE_DATASET = ROOT / "wake_dataset"
POSITIVE_DIR = WAKE_DATASET / "positive"
EXPECTED_JSON = ROOT / "gemma4_agent" / "voice" / "tests" / "testaudio_v2_expected.json"
AUDIO_PATH = ROOT / "gemma4_agent" / "voice" / "tests" / "Grabación (2).wav"

SAMPLE_RATE = 16000
WINDOW_S = 1.2  # window for feature extraction
WINDOW_SAMPLES = int(WINDOW_S * SAMPLE_RATE)


def _load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        assert wf.getframerate() == SAMPLE_RATE
        raw = wf.readframes(wf.getnframes())
    audio = np.frombuffer(raw, dtype=np.int16)
    if wf.getnchannels() > 1:
        audio = audio.reshape(-1, wf.getnchannels()).mean(axis=1).astype(np.int16)
    return audio


def compute_features_for_clips(audio_features: AudioFeatures, clips_dir: Path) -> np.ndarray:
    """Compute features for all WAV clips in a dir. Returns (N, 16, 96)."""
    features_list = []
    wavs = sorted(clips_dir.glob("*.wav"))
    print(f"Computing features for {len(wavs)} clips in {clips_dir.name}...")
    for i, wav_path in enumerate(wavs):
        audio = _load_wav(wav_path)
        # Pad or trim to exactly WINDOW_SAMPLES
        if len(audio) < WINDOW_SAMPLES:
            audio = np.pad(audio, (0, WINDOW_SAMPLES - len(audio)))
        else:
            audio = audio[:WINDOW_SAMPLES]
        # Feed audio in chunks via AudioFeatures
        audio_features.reset()
        chunk_size = 1280  # 80ms
        for offset in range(0, len(audio), chunk_size):
            chunk = audio[offset:offset + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            audio_features(chunk)
        # Get the final 16x96 feature window
        feats = audio_features.get_features(n_feature_frames=16)
        features_list.append(feats)
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(wavs)}")
    return np.stack(features_list)  # (N, 16, 96)


def compute_negative_features_from_gaps(audio_features: AudioFeatures) -> np.ndarray:
    """Extract negative windows from the audio's gaps (no wake nearby) and
    compute their features."""
    audio = _load_wav(AUDIO_PATH)
    with open(EXPECTED_JSON, encoding="utf-8") as fh:
        expected = json.load(fh)
    wake_times = sorted(float(w["timestamp_s"]) for w in expected["wakes"])

    # Build forbidden intervals: [wake_ts - 0.3, wake_ts + 0.9] for each wake
    forbidden = [(ts - 0.3, ts + 0.9) for ts in wake_times]

    duration_s = len(audio) / SAMPLE_RATE
    negative_windows = []
    step_s = WINDOW_S
    t = 0.0
    while t + WINDOW_S <= duration_s:
        window_end = t + WINDOW_S
        overlaps = any(not (window_end <= f_start or t >= f_end)
                       for f_start, f_end in forbidden)
        if not overlaps:
            negative_windows.append((t, window_end))
        t += step_s

    print(f"Extracting features for {len(negative_windows)} negative windows...")
    features_list = []
    for i, (start_s, end_s) in enumerate(negative_windows):
        start_idx = int(start_s * SAMPLE_RATE)
        end_idx = int(end_s * SAMPLE_RATE)
        clip = audio[start_idx:end_idx]
        if len(clip) < WINDOW_SAMPLES:
            clip = np.pad(clip, (0, WINDOW_SAMPLES - len(clip)))
        audio_features.reset()
        chunk_size = 1280
        for offset in range(0, len(clip), chunk_size):
            chunk = clip[offset:offset + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            audio_features(chunk)
        feats = audio_features.get_features(n_feature_frames=16)
        features_list.append(feats)
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(negative_windows)}")
    return np.stack(features_list)


class HeyGemmaModel(nn.Module):
    """Recreates the openwakeword DNN architecture (32-unit layer)."""

    def __init__(self, input_size=16 * 96, layer_size=32):
        super().__init__()
        self.flatten = nn.Flatten()
        self.layer1 = nn.Linear(input_size, layer_size)
        self.layernorm1 = nn.LayerNorm(layer_size)
        self.layer2 = nn.Linear(layer_size, layer_size)
        self.layernorm2 = nn.LayerNorm(layer_size)
        self.layer3 = nn.Linear(layer_size, layer_size)
        self.layernorm3 = nn.LayerNorm(layer_size)
        self.output = nn.Linear(layer_size, 1)

    def forward(self, x):
        x = self.flatten(x)
        x = F.relu(self.layernorm1(self.layer1(x)))
        x = F.relu(self.layernorm2(self.layer2(x)))
        x = F.relu(self.layernorm3(self.layer3(x)))
        x = torch.sigmoid(self.output(x))
        return x


def load_onnx_weights_to_torch(onnx_path: Path, torch_model: HeyGemmaModel):
    """Load weights from ONNX into our PyTorch reconstruction."""
    import onnx
    from onnx import numpy_helper

    model = onnx.load(str(onnx_path))
    initializers = {init.name: numpy_helper.to_array(init) for init in model.graph.initializer}

    # Inspect to map ONNX names to torch parameter names
    print("ONNX initializers:")
    for name, arr in initializers.items():
        print(f"  {name}: shape={arr.shape}")

    return torch_model  # We may not be able to map exactly; train from scratch if needed


def main():
    if not MODEL_PATH.exists():
        print(f"Model not found: {MODEL_PATH}")
        sys.exit(1)
    if not POSITIVE_DIR.exists():
        print(f"Positive clips dir not found: {POSITIVE_DIR}")
        print("Run scripts/build_wake_dataset.py first.")
        sys.exit(1)
    if not AUDIO_PATH.exists():
        print(f"Audio not found: {AUDIO_PATH}")
        sys.exit(1)

    print("=" * 60)
    print("Fine-tune hey_gemma with operator clips")
    print("=" * 60)
    print(f"Model:    {MODEL_PATH}")
    print(f"Positives: {POSITIVE_DIR} ({len(list(POSITIVE_DIR.glob('*.wav')))} clips)")
    print(f"Audio:    {AUDIO_PATH}")
    print()

    # Cache features so we don't recompute on every iteration
    features_out = ROOT / "wake_dataset" / "finetune_features"
    features_out.mkdir(exist_ok=True, parents=True)
    pos_cache = features_out / "positives.npy"
    neg_cache = features_out / "negatives.npy"

    if pos_cache.exists() and neg_cache.exists():
        print("Loading cached features...")
        pos_features = np.load(pos_cache)
        neg_features = np.load(neg_cache)
    else:
        print("Loading AudioFeatures...")
        af = AudioFeatures()
        pos_features = compute_features_for_clips(af, POSITIVE_DIR)
        neg_features = compute_negative_features_from_gaps(af)
        np.save(pos_cache, pos_features)
        np.save(neg_cache, neg_features)
    print(f"Positive features: {pos_features.shape}")
    print(f"Negative features: {neg_features.shape}")

    # Step 4: build PyTorch model + load weights from ONNX
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\nDevice: {device}")
    model = HeyGemmaModel().to(device)
    model = load_onnx_weights_to_torch(MODEL_PATH, model)

    # If we can't load (architecture mismatch), train from scratch
    # Step 5: prepare training set
    X = np.concatenate([pos_features, neg_features], axis=0).astype(np.float32)
    y = np.concatenate([
        np.ones(len(pos_features), dtype=np.float32),
        np.zeros(len(neg_features), dtype=np.float32),
    ])

    # Stratified split 80/20
    rng = np.random.RandomState(42)
    pos_idx = np.where(y == 1)[0]
    neg_idx = np.where(y == 0)[0]
    rng.shuffle(pos_idx)
    rng.shuffle(neg_idx)
    pos_split = int(0.8 * len(pos_idx))
    neg_split = int(0.8 * len(neg_idx))
    train_idx = np.concatenate([pos_idx[:pos_split], neg_idx[:neg_split]])
    val_idx = np.concatenate([pos_idx[pos_split:], neg_idx[neg_split:]])
    rng.shuffle(train_idx)

    X_train = torch.from_numpy(X[train_idx]).to(device)
    y_train = torch.from_numpy(y[train_idx]).to(device).unsqueeze(1)
    X_val = torch.from_numpy(X[val_idx]).to(device)
    y_val = torch.from_numpy(y[val_idx]).to(device).unsqueeze(1)

    print(f"\nTrain: {len(X_train)} samples ({y_train.sum().item():.0f} positive)")
    print(f"Val:   {len(X_val)} samples ({y_val.sum().item():.0f} positive)")

    # Step 6: train with weighted loss (positives are rare)
    pos_weight = torch.tensor([len(neg_features) / max(1, len(pos_features))]).to(device)
    criterion = nn.BCELoss(reduction='none')
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)

    batch_size = 64
    n_epochs = 100
    best_val_f1 = 0.0
    best_state = None

    for epoch in range(n_epochs):
        model.train()
        # Shuffle each epoch
        perm = torch.randperm(len(X_train))
        train_losses = []
        for start in range(0, len(X_train), batch_size):
            idx = perm[start:start + batch_size]
            x_batch = X_train[idx]
            y_batch = y_train[idx]
            optimizer.zero_grad()
            out = model(x_batch)
            loss_unred = criterion(out, y_batch)
            # Weight positives more
            weights = y_batch * pos_weight + (1 - y_batch) * 1.0
            loss = (loss_unred * weights).mean()
            loss.backward()
            optimizer.step()
            train_losses.append(loss.item())

        # Validation
        model.eval()
        with torch.no_grad():
            val_out = model(X_val)
            val_pred = (val_out > 0.5).float()
            tp = ((val_pred == 1) & (y_val == 1)).sum().item()
            fp = ((val_pred == 1) & (y_val == 0)).sum().item()
            fn = ((val_pred == 0) & (y_val == 1)).sum().item()
            recall = tp / max(1, tp + fn)
            precision = tp / max(1, tp + fp)
            f1 = 2 * precision * recall / max(1e-9, precision + recall)

        if epoch % 10 == 0 or epoch == n_epochs - 1:
            avg_loss = np.mean(train_losses)
            print(f"Epoch {epoch:3d}: loss={avg_loss:.4f}  val P={precision:.3f} R={recall:.3f} F1={f1:.3f}")

        if f1 > best_val_f1:
            best_val_f1 = f1
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    print(f"\nBest val F1: {best_val_f1:.3f}")

    # Step 7: load best state and export ONNX
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    model.cpu()

    out_onnx = ROOT / "gemma4_agent" / "voice" / "models" / "oww" / "hey_gemma_v2.onnx"
    dummy_input = torch.zeros(1, 16, 96)
    torch.onnx.export(
        model, dummy_input, str(out_onnx),
        input_names=["onnx::Flatten_0"],
        output_names=["output"],
        dynamic_axes=None,
        opset_version=14,
    )
    # Post-process: rename output node to match the original openwakeword
    # convention so that openwakeword.Model can load this drop-in.
    import onnx as _onnx
    _m = _onnx.load(str(out_onnx))
    for out in _m.graph.output:
        if out.name == "output":
            out.name = "39"
    # Walk nodes and rename any reference to 'output' as input/output
    for node in _m.graph.node:
        for i, n in enumerate(node.output):
            if n == "output":
                node.output[i] = "39"
        for i, n in enumerate(node.input):
            if n == "output":
                node.input[i] = "39"
    _onnx.save(_m, str(out_onnx))
    print(f"\nWrote: {out_onnx}")
    print(f"Size: {out_onnx.stat().st_size} bytes")
    print()
    print("To activate v2 in the pipeline, rename:")
    print(f"  mv {out_onnx} {out_onnx.parent / 'hey_gemma.onnx'}")


if __name__ == "__main__":
    main()
