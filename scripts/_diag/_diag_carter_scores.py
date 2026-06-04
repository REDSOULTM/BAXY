"""Per-phrase + score-distribution diagnostic for hey_carter universal held-out."""
from __future__ import annotations
import sys, wave
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ort_throttle
_ort_throttle.apply(n_threads=2)
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gemma4_agent.voice.livekit_runtime import LiveKitWakeRuntime, WINDOW_SAMPLES
POS = ROOT / "data" / "wake_universal_eval" / "positives_carter"
MD = ROOT / "gemma4_agent" / "voice" / "models" / "livekit"
PHRASES = {"p0":"hey carter","p1":"oye carter","p2":"Hey Carter!","p3":"carter(bare)","p4":"ey carter"}

def load(p):
    with wave.open(str(p),"rb") as w:
        sr=w.getframerate(); raw=w.readframes(w.getnframes())
    return np.frombuffer(raw,dtype=np.int16), sr

def score(rt,a):
    if a.size<WINDOW_SAMPLES:
        pad=np.zeros(WINDOW_SAMPLES,dtype=a.dtype); pad[-a.size:]=a; return rt.predict(pad)
    best=0.0; hop=WINDOW_SAMPLES//4
    for s in range(0,a.size-WINDOW_SAMPLES+1,hop): best=max(best,rt.predict(a[s:s+WINDOW_SAMPLES]))
    return best

rt=LiveKitWakeRuntime(MD,classifier_stem="hey_gemma"); rt.load()
clf=ROOT/"output"/"hey_carter"/"hey_carter.onnx"
rt._clf=rt._make_session(clf); rt._clf_input=rt._clf.get_inputs()[0].name
byphrase=defaultdict(list); allscores=[]
for f in sorted(POS.glob("*.wav")):
    a,sr=load(f)
    if sr!=16000 or a.size==0: continue
    s=score(rt,a); allscores.append(s)
    pid=f.stem.split("__")[1]  # p0..p4
    byphrase[pid].append(s)
print("=== per-phrase mean score + recall@0.25 ===")
for pid in sorted(byphrase):
    v=np.array(byphrase[pid])
    print("  %-4s %-14s n=%3d  mean=%.3f  median=%.3f  recall@0.25=%.3f  recall@0.1=%.3f"
          % (pid, PHRASES.get(pid,"?"), len(v), v.mean(), np.median(v),
             (v>=0.25).mean(), (v>=0.1).mean()))
a=np.array(allscores)
print("=== global score distribution (n=%d) ===" % len(a))
for q in [50,60,70,75,80,90]:
    print("  p%d = %.3f" % (q, np.percentile(a,q)))
print("  frac>=0.5=%.3f  >=0.25=%.3f  >=0.1=%.3f  >=0.05=%.3f" % ((a>=0.5).mean(),(a>=0.25).mean(),(a>=0.1).mean(),(a>=0.05).mean()))
