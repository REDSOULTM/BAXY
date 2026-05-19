"""v7 fine-tune: fix the silence-fires-wake bug discovered 2026-05-19.

The v5 model was tested in real production today and it fires on
silence / mic ambient noise. Operator reported "wake activates by
itself" -- inspection of session 20260519_123719 confirmed:
  5 wakes in 38s with rms=0.0000 to 0.0042 (essentially silence)
  Whisper_transcription=null for all (no speech to transcribe)

Root cause: v5's training negatives were synthetic noise at rms ~500-4000.
The model never saw "true silence" or "mic thermal noise" as negative,
so it doesn't know to keep score low there. Especially since the
operator's mic captures low-level ambient sounds that share spectral
features with "hey gemma" when no real speech is present.

v7 strategy:
1. Add THOUSANDS of true-silence and mic-ambient-noise samples as
   negatives:
   - Pure zeros (np.zeros)
   - Very-low gaussian noise (rms ~10-100, simulating mic floor)
   - The ACTUAL recordings from session 20260519_123719 (the false
     positives) as hard negatives.
2. Keep positives identical to v5 (no change there -- recall works).
3. Continue from v5 weights (transfer learning).
4. Heavy negative oversampling: train ratio 1 positive : 5 negatives.
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

# v7 inherits v5 positives + adds silence/mic-noise + real FPs as negatives
MODEL_V5_PATH = ROOT / "gemma4_agent" / "voice" / "models" / "oww" / "hey_gemma.onnx"
MODEL_OUT_PATH = ROOT / "gemma4_agent" / "voice" / "models" / "oww" / "hey_gemma_v7.onnx"

WAKE_DATASET = ROOT / "wake_dataset"
POSITIVE_DIR = WAKE_DATASET / "positive"
EXPECTED_JSON = ROOT / "gemma4_agent" / "voice" / "tests" / "testaudio_v2_expected.json"
AUDIO_PATH = ROOT / "gemma4_agent" / "voice" / "tests" / "Grabación (2).wav"
RECORDINGS_DIR = Path.home() / ".gemma4" / "recordings"

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


def streaming_features_with_offsets(af, audio, n_offsets=5):
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


def build_dataset_v7():
    """Reuse v5 positives if cached, add v7-specific negatives."""
    af = AudioFeatures()
    rng = np.random.RandomState(42)

    # Re-use v5 positives from cache (saves ~5 min of computation)
    v5_pos_cache = WAKE_DATASET / "finetune_features" / "v5_positives.npy"
    if v5_pos_cache.exists():
        print("Reusing v5 positive features...")
        pos_features = np.load(v5_pos_cache)
        print(f"Positives: {pos_features.shape}")
    else:
        pos_files = sorted(POSITIVE_DIR.glob("*.wav"))
        print(f"Computing positives: {len(pos_files)} × 4 aug × 5 offsets")
        pos_features = []
        for i, p in enumerate(pos_files):
            audio = _load_wav(p)
            pos_features.extend(streaming_features_with_offsets(af, audio, n_offsets=5))
            for _ in range(3):
                aug = augment_audio(audio, rng)
                pos_features.extend(streaming_features_with_offsets(af, aug, n_offsets=5))
            if (i + 1) % 25 == 0:
                print(f"  {i+1}/{len(pos_files)}")
        pos_features = np.stack(pos_features)
        print(f"Positives: {pos_features.shape}")

    # ===== NEGATIVES =====
    neg_features = []

    # CRITICAL NEW: SILENCE -- pure zeros at multiple lengths (model must
    # output low score on silence)
    print("Adding 500 pure silence samples...")
    for _ in range(500):
        clip = np.zeros(STREAM_WINDOW_SAMPLES, dtype=np.int16)
        neg_features.append(compute_feature(af, clip))

    # CRITICAL NEW: Mic thermal noise -- very low gaussian (rms 5-50)
    # This is what the operator's mic captures when nobody is talking.
    print("Adding 1500 mic thermal noise samples (low-energy)...")
    for _ in range(1500):
        level = rng.uniform(5, 80)  # very low, simulates mic floor
        clip = rng.normal(0, level, STREAM_WINDOW_SAMPLES).astype(np.int16)
        neg_features.append(compute_feature(af, clip))

    # CRITICAL NEW: The actual false-positive recordings from production
    print("Adding production false-positive recordings as hard negatives...")
    fp_count = 0
    for session_dir in sorted(RECORDINGS_DIR.iterdir() if RECORDINGS_DIR.exists() else []):
        if not session_dir.is_dir():
            continue
        manifest_path = session_dir / "manifest.jsonl"
        if not manifest_path.exists():
            continue
        # Check if any turn in this session had no transcription (silent wake = FP)
        try:
            for line in manifest_path.read_text(encoding="utf-8").splitlines():
                entry = json.loads(line)
                # Heuristic: a wake with no transcription AND no TTS = false positive
                if entry.get("whisper_transcription") is None and entry.get("tts_samples", 0) == 0:
                    wav_name = entry.get("user_wav")
                    if not wav_name:
                        continue
                    wav_path = session_dir / wav_name
                    if not wav_path.exists():
                        continue
                    audio = _load_wav(wav_path)
                    # Take multiple windows from this FP recording
                    n_windows = max(1, len(audio) // STREAM_WINDOW_SAMPLES)
                    for w in range(n_windows):
                        start = w * STREAM_WINDOW_SAMPLES
                        end = start + STREAM_WINDOW_SAMPLES
                        if end > len(audio):
                            break
                        sub = audio[start:end]
                        neg_features.append(compute_feature(af, sub))
                        fp_count += 1
        except Exception as exc:
            print(f"  Skip session {session_dir.name}: {exc}")
    print(f"Production FP samples: {fp_count} from {RECORDINGS_DIR}")

    # Sliding window gaps from Grabación (2) (same as v5)
    audio = _load_wav(AUDIO_PATH)
    with open(EXPECTED_JSON, encoding="utf-8") as fh:
        expected = json.load(fh)
    wake_times = sorted(float(w["timestamp_s"]) for w in expected["wakes"])
    forbidden = [(ts - 0.4, ts + 1.0) for ts in wake_times]
    t = 0.0
    duration_s = len(audio) / SAMPLE_RATE
    while t + STREAM_WINDOW_S <= duration_s:
        end = t + STREAM_WINDOW_S
        if not any(not (end <= fs or t >= fe) for fs, fe in forbidden):
            start_idx = int(t * SAMPLE_RATE)
            clip = audio[start_idx:start_idx + STREAM_WINDOW_SAMPLES]
            neg_features.append(compute_feature(af, clip))
        t += 0.16
    print(f"Negs after Grabación gaps: {len(neg_features)}")

    # Light synthetic noise (less than v5 had, focus is on silence/ambient)
    print("Adding 1000 light synthetic background variations...")
    for _ in range(1000):
        base = rng.normal(0, rng.uniform(300, 2000), STREAM_WINDOW_SAMPLES)
        if rng.random() < 0.3:
            n_tones = rng.randint(1, 4)
            for _ in range(n_tones):
                ts_idx = rng.randint(0, STREAM_WINDOW_SAMPLES - 800)
                tl = rng.randint(300, 2000)
                te = min(ts_idx + tl, STREAM_WINDOW_SAMPLES)
                freq = rng.uniform(150, 3000)
                t_ax = np.arange(te - ts_idx) / SAMPLE_RATE
                tone = np.sin(2 * np.pi * freq * t_ax) * rng.uniform(300, 3000)
                base[ts_idx:te] += tone
        clip = np.clip(base, -32768, 32767).astype(np.int16)
        neg_features.append(compute_feature(af, clip))

    print(f"FINAL negatives: {len(neg_features)}")
    neg_features = np.stack(neg_features)
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


def load_v5_weights(model: HeyGemmaModel, onnx_path: Path):
    """Load weights from current production hey_gemma.onnx (v5) into PyTorch."""
    import onnx
    from onnx import numpy_helper
    m = onnx.load(str(onnx_path))
    init = {i.name: numpy_helper.to_array(i) for i in m.graph.initializer}
    # v5 was exported by torch with our HeyGemmaModel architecture,
    # so the param names should match. Try the most likely mappings.
    mappings_to_try = [
        # Mapping 1: original openwakeword style
        {
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
        },
    ]
    print(f"ONNX initializers: {list(init.keys())[:15]}")
    # Try each mapping
    with torch.no_grad():
        for mapping in mappings_to_try:
            loaded = 0
            for oname, tname in mapping.items():
                if oname not in init:
                    continue
                try:
                    param = dict(model.named_parameters())[tname]
                    arr = torch.from_numpy(init[oname].copy())
                    if arr.shape == param.shape:
                        param.copy_(arr)
                        loaded += 1
                except Exception:
                    pass
            if loaded >= 5:
                print(f"Loaded {loaded}/{len(mapping)} weights from v5")
                return
    print("WARN: Could not load v5 weights; training from scratch")


def main():
    pos_cache = WAKE_DATASET / "finetune_features" / "v7_positives.npy"
    neg_cache = WAKE_DATASET / "finetune_features" / "v7_negatives.npy"

    if pos_cache.exists() and neg_cache.exists():
        print("Loading v7 cached features...")
        pos = np.load(pos_cache)
        neg = np.load(neg_cache)
    else:
        pos, neg = build_dataset_v7()
        pos_cache.parent.mkdir(parents=True, exist_ok=True)
        np.save(pos_cache, pos)
        np.save(neg_cache, neg)
    print(f"Positives: {pos.shape}, Negatives: {neg.shape}")
    print(f"Ratio neg:pos = {len(neg)/len(pos):.2f}")

    # Streaming-real validation set
    print("\nBuilding streaming validation set...")
    af = AudioFeatures()
    audio = _load_wav(AUDIO_PATH)
    with open(EXPECTED_JSON, encoding="utf-8") as fh:
        expected = json.load(fh)
    wake_times = sorted(float(w["timestamp_s"]) for w in expected["wakes"])
    rng = np.random.RandomState(123)
    forbidden = [(ts - 0.4, ts + 1.0) for ts in wake_times]

    val_pos = []
    val_wakes = rng.choice(len(wake_times), 25, replace=False)
    for wi in val_wakes:
        wt = wake_times[wi]
        center = int(wt * SAMPLE_RATE)
        start = max(0, center - STREAM_WINDOW_SAMPLES // 2)
        end = start + STREAM_WINDOW_SAMPLES
        if end > len(audio):
            continue
        val_pos.append(compute_feature(af, audio[start:end]))
    val_pos = np.stack(val_pos)

    # Validation negatives include silence + ambient + gaps
    val_neg = []
    # Pure silence in validation
    for _ in range(30):
        val_neg.append(compute_feature(af, np.zeros(STREAM_WINDOW_SAMPLES, dtype=np.int16)))
    # Mic ambient
    for _ in range(50):
        level = rng.uniform(5, 80)
        clip = rng.normal(0, level, STREAM_WINDOW_SAMPLES).astype(np.int16)
        val_neg.append(compute_feature(af, clip))
    # Gap windows
    while len(val_neg) < 200:
        t = rng.uniform(0, len(audio) / SAMPLE_RATE - STREAM_WINDOW_S)
        end = t + STREAM_WINDOW_S
        if any(not (end <= fs or t >= fe) for fs, fe in forbidden):
            continue
        si = int(t * SAMPLE_RATE)
        val_neg.append(compute_feature(af, audio[si:si + STREAM_WINDOW_SAMPLES]))
    val_neg = np.stack(val_neg)
    print(f"Stream val: {len(val_pos)} pos, {len(val_neg)} neg (incl. 30 silence + 50 mic-ambient)")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = HeyGemmaModel().to(device)
    load_v5_weights(model, MODEL_V5_PATH)
    model.to(device)

    X_train = np.concatenate([pos, neg]).astype(np.float32)
    y_train = np.concatenate([np.ones(len(pos)), np.zeros(len(neg))]).astype(np.float32)
    X_val = np.concatenate([val_pos, val_neg]).astype(np.float32)
    y_val = np.concatenate([np.ones(len(val_pos)), np.zeros(len(val_neg))]).astype(np.float32)

    print(f"\nTrain: {len(X_train)} ({y_train.sum():.0f} pos)")
    print(f"Stream val: {len(X_val)} ({y_val.sum():.0f} pos)")

    X_train_t = torch.from_numpy(X_train).to(device)
    y_train_t = torch.from_numpy(y_train).to(device).unsqueeze(1)
    X_val_t = torch.from_numpy(X_val).to(device)
    y_val_t = torch.from_numpy(y_val).to(device).unsqueeze(1)

    # Low LR for fine-tune from v5
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-3)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=150)

    def focal_loss(pred, target, gamma=2.0, alpha=0.5):
        eps = 1e-7
        pred = pred.clamp(eps, 1 - eps)
        pos = -alpha * (1 - pred) ** gamma * target * torch.log(pred)
        neg = -(1 - alpha) * pred ** gamma * (1 - target) * torch.log(1 - pred)
        return (pos + neg).mean()

    best_val_f1 = 0
    best_state = None
    patience = 40
    epochs_no_improve = 0

    # Track silence false positive rate explicitly
    silence_mask = np.zeros(len(X_val), dtype=bool)
    silence_mask[len(val_pos):len(val_pos) + 80] = True  # first 80 negs are silence+ambient

    for epoch in range(150):
        model.train()
        perm = torch.randperm(len(X_train_t))
        losses = []
        for s in range(0, len(X_train_t), 256):
            idx = perm[s:s + 256]
            optimizer.zero_grad()
            out = model(X_train_t[idx])
            loss = focal_loss(out, y_train_t[idx])
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
        scheduler.step()

        model.eval()
        with torch.no_grad():
            vo = model(X_val_t).cpu().numpy().flatten()
            vy = y_val_t.cpu().numpy().flatten()
            silence_scores = vo[silence_mask]
            silence_max = float(silence_scores.max())

            best_local_f1, best_p, best_r, best_thr = 0, 0, 0, 0.5
            for thr in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9]:
                pred = (vo > thr).astype(np.float32)
                tp = ((pred == 1) & (vy == 1)).sum()
                fp = ((pred == 1) & (vy == 0)).sum()
                fn = ((pred == 0) & (vy == 1)).sum()
                p = tp / max(1, tp + fp)
                r = tp / max(1, tp + fn)
                f1 = 2 * p * r / max(1e-9, p + r)
                # Penalize configs that allow silence to score > 0.5
                if f1 > best_local_f1 and silence_max < 0.5:
                    best_local_f1, best_p, best_r, best_thr = f1, p, r, thr

        if epoch % 10 == 0 or epoch == 149:
            print(f"Epoch {epoch:3d}: loss={np.mean(losses):.4f}  "
                  f"P={best_p:.3f} R={best_r:.3f} F1={best_local_f1:.3f} thr={best_thr}  "
                  f"silence_max={silence_max:.3f}")

        if best_local_f1 > best_val_f1:
            best_val_f1 = best_local_f1
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            epochs_no_improve = 0
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= patience:
                print(f"Early stop @ {epoch}")
                break

    print(f"\nBest streaming F1: {best_val_f1:.3f}")
    if best_state is None:
        print("WARN: no improvement, using last state")
        best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    model.eval().cpu()

    # Final silence check
    with torch.no_grad():
        silence_input = torch.zeros(1, 16, 96)
        silence_score = float(model(silence_input).item())
        print(f"\nFINAL silence score (zero input): {silence_score:.4f}")
        ambient_input = torch.from_numpy(
            np.random.RandomState(0).normal(0, 0.001, (1, 16, 96)).astype(np.float32)
        )
        ambient_score = float(model(ambient_input).item())
        print(f"FINAL ambient noise score: {ambient_score:.4f}")

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
