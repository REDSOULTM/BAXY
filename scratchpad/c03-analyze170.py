from pathlib import Path
import json
import os
import hashlib
import sys
import numpy as np

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from baxy_mind.voice import _looks_like_echo
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-analysis170'
out.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-sidecar169-private'
metadata=json.loads((private/'barge169.json').read_text(encoding='utf-8'))
arrays=np.load(private/'barge169.npz')
prereg={'method':'Offline exact first post-decision snapshot169. Recompute unchanged _looks_like_echo and centered normalized all-sample correlation on actual guard history, then entire available four-second ring. Report signed sample positions, not tune thresholds. No playback, generation, source mutation or acceptance.', 'inputs':{str(private/name):hashlib.sha256((private/name).read_bytes()).hexdigest() for name in ['barge169.json','barge169.npz']}}
(out/'PREREG.json').write_text(json.dumps(prereg,indent=2),encoding='utf-8')
def scores(mic,ref):
    mic=mic.astype(np.float64).reshape(-1)
    ref=ref.astype(np.float64).reshape(-1)
    mic-=mic.mean()
    products=np.correlate(ref,mic,mode='valid')
    totals=np.r_[0.,np.cumsum(ref)]
    squares=np.r_[0.,np.cumsum(ref*ref)]
    sums=totals[len(mic):]-totals[:-len(mic)]
    energy=squares[len(mic):]-squares[:-len(mic)]-sums*sums/len(mic)
    norm=np.linalg.norm(mic)*np.sqrt(np.maximum(energy,0))
    corr=np.divide(np.abs(products),norm,out=np.zeros_like(products),where=norm>1e-6)
    pos=int(corr.argmax())
    return pos,float(corr[pos])
mic=arrays['echo_microphone']
ref=arrays['echo_reference']
guard_pos,guard_score=scores(mic,ref)
end=metadata['referenceCursor']-len(mic)
written=metadata['loopbackWritten']
ring=arrays['loopback_ring']
first=max(0,written-len(ring))
history=ring[np.arange(first,written)%len(ring)]
full_pos,full_score=scores(mic,history)
statistics={}
for name in arrays.files:
    values=arrays[name].astype(np.float64)
    statistics[name]={'shape':list(values.shape),'peak':float(np.max(np.abs(values))),'rms':float(np.sqrt(np.mean(values**2)))}
row={'metadata':metadata,'statistics':statistics,'guardEchoDecision':_looks_like_echo(mic,ref),'guardBestScore':guard_score,'guardBestLagSamples':len(ref)-len(mic)-guard_pos,'fullRingBestScore':full_score,'fullRingMatchEnd':first+full_pos+len(mic),'pairedReferenceEnd':end,'fullRingMatchLagSamples':end-(first+full_pos+len(mic)),'guardHistoryMatchesRing':bool(np.array_equal(ref,ring[np.arange(end-len(ref),end)%len(ring)]))}
(out/'RESULTS.json').write_text(json.dumps(row,indent=2),encoding='utf-8')
print(json.dumps(row,indent=2))
