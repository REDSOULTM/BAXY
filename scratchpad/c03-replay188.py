"""Replay exact187 native inputs through both DTLN sizes, retaining negative results."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time
import numpy as np
import psutil

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from baxy_mind.voice import SileroVad, _looks_like_echo
from dtln_stream182 import EchoCanceller

base=root/'artifacts/comprobaciones/C03'
source=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-sidecar187-private'
assert not any(p.info['name'] in {'Baxy.exe','llama-server.exe','piper.exe'} for p in psutil.process_iter(['name']))
index=json.loads((base/'astra-sidecar187/INDEX.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256(Path(r['privatePath']).read_bytes()).hexdigest()==r['sha256'] for r in index)
tap=np.load(source/'tap187.npz')
mic,reference,live_clean,observed=(tap[k] for k in ['microphone','reference','clean','observations'])
n=len(mic)
assert n and np.isfinite(observed).all()
out=base/'astra-replay188';out.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-replay188-private';private.mkdir(exist_ok=False)
prereg={'method':'Exact187 native microphone and full4512sample history, cold128/512 through continuous182.128 must reproduce captured float32 output bit for bit. Same fresh Silero state, fixed observed speaking mask and unchanged energy/guard criterion for comparison. No effect routing or audio playback.',
 'limitations':'Fresh offline VAD may differ from live resets at utterance boundaries. Report agreement separately. Fixed speaking mask is not counterfactual playback after a different early interruption. No near-speech fidelity or human acceptance established.',
 'inputs':index,'frames':n,'seconds':n*.032,'referenceContinuous':bool(np.array_equal(reference[1:,:-512],reference[:-1,512:]))}
(out/'PREREG.json').write_text(json.dumps(prereg,indent=2),encoding='utf-8')
vad=SileroVad()
rows=[]
for units in [128,512]:
    engine=EchoCanceller(units)
    vad.reset()
    clean=np.empty_like(mic)
    # probability,energy,floor,guard,run,DSPms
    measures=np.zeros((n,6),np.float64)
    floor=.002;run=0;fires=[]
    try:
        for i in range(n):
            start=time.perf_counter()
            frame,raw,ref=engine.process(mic[i],reference[i])
            cost=(time.perf_counter()-start)*1000
            clean[i]=frame
            p=vad.process(frame)
            energy=float(np.sqrt(np.mean(frame.astype(np.float64)**2)))
            if p<.5:
                floor=.98*floor+.02*energy
            guard=False
            if p>=.5 and bool(observed[i,3]):
                guard=_looks_like_echo(raw,ref)
                if not guard and energy>=max(.004,floor*1.8):
                    run+=1
                    if run==3:
                        fires.append({'frame':i,'seconds':i*.032,'probability':float(p),'energy':energy,'noiseFloor':floor})
                else:
                    run=0
            else:
                run=0
            measures[i]=[p,energy,floor,float(guard),run,cost]
    finally:
        engine.close()
    output_path=private/f'dtln{units}.npz'
    np.savez(output_path,clean=clean,measures=measures)
    differences=np.flatnonzero(np.any(clean!=live_clean,axis=1))
    probability_difference=np.abs(measures[:,0]-observed[:,4])
    row={'units':units,'frames':n,'livePcmBitIdentical':not len(differences),
         'firstDifferentPcmFrame':int(differences[0]) if len(differences) else None,
         'freshVadMaxDifferenceFromLive':float(probability_difference.max()),
         'freshVadExactAgreementFrames':int(np.count_nonzero(probability_difference==0)),
         'firstDifferentVadFrame':int(np.flatnonzero(probability_difference>0)[0]) if np.any(probability_difference>0) else None,
         'candidateInterruptionsWithFixedSpeakingMask':fires,
         'speechFrames':int(np.count_nonzero(measures[:,0]>=.5)),
         'dspMs':{'mean':float(measures[:,5].mean()),'p99':float(np.quantile(measures[:,5],.99)),'max':float(measures[:,5].max())},
         'privateOutput':str(output_path),'sha256':hashlib.sha256(output_path.read_bytes()).hexdigest()}
    rows.append(row)
    (out/'RESULTS.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print(json.dumps(row),flush=True)
    if units==128:
        assert row['livePcmBitIdentical'], 'Captured187 DTLN128 replay differs'
(out/'COMPLETE.json').write_text(json.dumps({'models':2,'exit':'complete','sourceChanged':False}),encoding='utf-8')
