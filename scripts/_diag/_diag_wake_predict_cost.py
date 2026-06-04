"""Time-boxed measurement of per-predict cost for the carter wake model.

SAFE: uses the pure-onnxruntime LiveKitWakeRuntime (2 threads, no spinning)
and only 3 negative clips. No full eval. Diagnostic only.
"""
import sys, time, glob, shutil, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import _ort_throttle  # noqa: E402
_ort_throttle.apply(2)

import soundfile as sf  # noqa: E402
sys.path.insert(0, str(ROOT))
from gemma4_agent.voice.livekit_runtime import LiveKitWakeRuntime  # noqa: E402

td = tempfile.mkdtemp()
mdl = ROOT / "gemma4_agent" / "voice" / "models" / "livekit"
shutil.copy(mdl / "melspectrogram.onnx", td)
shutil.copy(mdl / "embedding_model.onnx", td)
shutil.copy(ROOT / "output" / "hey_carter" / "hey_carter.onnx", td)
rt = LiveKitWakeRuntime(Path(td), classifier_stem="hey_carter")
print("runtime loaded:", rt.load(), rt.last_error)

files = sorted(glob.glob(str(
    ROOT / "data/wake_universal_eval/negatives/LibriSpeech/dev-clean/**/*.flac"
), recursive=True))[:3]
SR, WIN, HOP = 16000, 32000, 8000
total_predicts = 0
t0 = time.time()
for f in files:
    a, sr = sf.read(f, dtype="int16")
    if a.ndim > 1:
        a = a.mean(axis=1).astype("int16")
    dur = len(a) / SR
    nwin = max(1, (len(a) - WIN) // HOP + 1)
    tc = time.time()
    cnt = 0
    for i in range(nwin):
        w = a[i * HOP:i * HOP + WIN]
        if len(w) < WIN:
            break
        rt.predict(w)
        total_predicts += 1
        cnt += 1
    print(f"  clip dur={dur:.1f}s windows={cnt} clip_time={time.time()-tc:.2f}s")
el = time.time() - t0
print("total predicts:", total_predicts, "elapsed:", round(el, 2))
print("per-predict ms:", round(el / max(1, total_predicts) * 1000, 2))
