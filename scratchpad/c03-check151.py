"""Fixed eight frame phases over the exact continuous mic/reference149 arrays."""
from pathlib import Path
import hashlib
import json
import os
import sys

import numpy as np

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'src'))
from baxy_mind.voice import SileroVad, _looks_like_echo
from baxy_mind.speex_aec import EchoCanceller

out = root/'artifacts/comprobaciones/C03/astra-phase151'
out.mkdir(exist_ok=False)
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-voice149-private'
index = json.loads((root/'artifacts/comprobaciones/C03/astra-voice149/OBSERVATION_INDEX.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256(Path(r['privatePath']).read_bytes()).hexdigest()==r['sha256'] for r in index)
(out/'PREREG.json').write_text(json.dumps({'source':149,'phases':list(range(0,512,64)),
    'method':'Same recorded microphone/reference shifted together; fresh native AEC and Silero states per phase, existing thresholds and raw guard. Phase0 must reproduce clean PCM bit-for-bit. No playback/new capture/source mutation/ASR.',
    'limits':'Offline detector component, speaking interval estimated from actual event and frame observation clocks. Does not reproduce whole segmentation/VAD reset/UI or prove physical acceptance.'}, indent=2),encoding='utf-8')
data=np.load(private/'tap149.npz')
meta=json.loads((private/'tap149.json').read_text(encoding='utf-8'))
mic=data['microphone'].ravel()
ref=np.r_[data['reference'][0,:-512],data['reference'][:,-512:].ravel()]
events=[json.loads(s) for s in (root/'artifacts/comprobaciones/C03/astra-voice149/EVENTS.jsonl').read_text(encoding='utf-8').splitlines()]
start=next(e['monotonic'] for e in events if e.get('speaking') is True)
end=next(e['monotonic'] for e in events if e.get('speaking') is False and e['monotonic']>start)
origin=meta['frames'][0]['time']
rows=[]
for phase in range(0,512,64):
    aec=EchoCanceller()
    vad=SileroVad()
    floor,count=.002,0
    candidates,barge,clean_rows=[],[],[]
    try:
        for first in range(phase,len(mic)-511,512):
            clean,raw,history=aec.process(mic[first:first+512], ref[first:first+4512])
            clean_rows.append(clean)
            probability=vad.process(clean)
            energy=float(np.sqrt(np.mean(clean**2)))
            if probability<.5:
                floor=.98*floor+.02*energy
            now=origin+first/16000
            if start<=now<=end and probability>=.5:
                if _looks_like_echo(raw,history):
                    count=0
                elif energy>=max(.004,floor*1.8):
                    count+=1
                    candidates.append(round(now-start,3))
                    if count==3:
                        barge.append(round(now-start,3))
                else:
                    count=0
        row={'phase':phase,'candidatesSeconds':candidates,'bargeSequencesSeconds':barge}
        if phase==0:
            row['cleanPcmIdentical']=bool(np.array_equal(np.asarray(clean_rows),data['clean']))
            assert row['cleanPcmIdentical']
        rows.append(row)
        print(json.dumps(row),flush=True)
    finally:
        aec.close()
(out/'RESULTS.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
