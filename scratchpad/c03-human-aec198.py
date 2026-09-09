"""Paired human near-only/double-talk controls; experimental, no product edit."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time
import numpy as np
from scipy.io import wavfile

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from baxy_mind.speex_aec import EchoCanceller as Speex
from baxy_mind.voice import SileroVad, _looks_like_echo
from dtln_stream182 import EchoCanceller as Dtln

base=root/'artifacts/comprobaciones/C03'
out=base/'astra-human-aec198';out.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-human-aec198-private';private.mkdir(exist_ok=False)
source=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-sidecar187-private/tap187.npz'
assert hashlib.sha256(source.read_bytes()).hexdigest()=='40ef4756216c7add36bb28f22d6dcb742fa8649366c17898e0a8aef7363b452f'
tap=np.load(source)
mic,ref,observed=[tap[k] for k in ['microphone','reference','observations']]
assert np.array_equal(ref[1:,:-512],ref[:-1,512:])
n=len(mic);samples=n*512
active=np.flatnonzero(np.sqrt(np.mean(ref[:,-512:].astype(np.float64)**2,axis=1))>=20)
onset=int(active[0])*512+16000
inputs=json.loads((base/'astra-human195/DOWNLOADS.json').read_text(encoding='utf-8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save(out/'PREREG.json',{
 'method':'Same exact187 captured mic/reference sequence for all four195 human recordings. Each original scaled once to full-clip RMS0.01, inserted one second after first reference block RMS>=20PCM (onset sample31872). No gain/lag sweep. Near-only uses zero reference; mixed adds preserved187 microphone and its exact reference. Raw, product Speex, experimental DTLN128; both AECs start fresh for each condition.',
 'onsetSample':onset,'frames':n,'targetNearRms':.01,'inputs':inputs,'echoSha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'recognitionPlan':'All24 windows (4 humans x2 conditions x3 engines), same near onset minus1s to end plus1s; already-known algorithm latency24/32ms fits trailing margin. Both existing recognizers without expected-text hints or gain normalization.',
 'limitation':'Constructed double-talk with human recording plus physical echo, not simultaneous physical human speaker; fixed observed speaking mask does not simulate subsequent playback after a counterfactual interruption. No corpus reserve or final audio acceptance; original197 recognizer errors preserved.'})
assert onset==31872
vad=SileroVad();results=[]
for human_index,row in enumerate(inputs):
    original_path=Path(row['asset'])
    assert hashlib.sha256(original_path.read_bytes()).hexdigest()==row['sha256']
    rate,audio=wavfile.read(original_path);assert rate==16000 and audio.dtype==np.float32
    rms=float(np.sqrt(np.mean(audio.astype(np.float64)**2)))
    gain=.01/rms
    near=np.zeros(samples,np.float32)
    assert onset+len(audio)+16000 < samples
    near[onset:onset+len(audio)]=audio*gain
    for condition in ['near_only','mixed']:
        incoming=near.reshape(n,512)+(mic if condition=='mixed' else 0)
        reference=ref if condition=='mixed' else np.zeros_like(ref)
        assert np.max(np.abs(incoming))<1
        for engine_name in ['raw','speex','dtln128']:
            engine=Speex() if engine_name=='speex' else Dtln(128) if engine_name=='dtln128' else None
            clean=np.empty_like(incoming);measures=np.zeros((n,6),np.float64)
            vad.reset();floor=.002;run=0;fires=[]
            try:
                for i in range(n):
                    begin=time.perf_counter()
                    if engine:
                        frame,paired_mic,paired_ref=engine.process(incoming[i],reference[i])
                    else:
                        frame,paired_mic,paired_ref=incoming[i],incoming[i]*32768,reference[i]
                    elapsed=(time.perf_counter()-begin)*1000
                    clean[i]=frame
                    p=vad.process(frame);energy=float(np.sqrt(np.mean(frame.astype(np.float64)**2)))
                    if p<.5:floor=.98*floor+.02*energy
                    guard=False
                    if p>=.5 and bool(observed[i,3]):
                        guard=_looks_like_echo(paired_mic,paired_ref)
                        if not guard and energy>=max(.004,floor*1.8):
                            run+=1
                            if run==3:fires.append({'frame':i,'seconds':i*.032,'afterNearOnsetSeconds':i*.032-onset/16000})
                        else:run=0
                    else:run=0
                    measures[i]=[p,energy,floor,float(guard),run,elapsed]
            finally:
                if engine:engine.close()
            target=private/f'h{human_index}-{condition}-{engine_name}.npz'
            np.savez(target,clean=clean,measures=measures)
            first,last=onset-16000,onset+len(audio)+16000
            record={'human':human_index,'config':row['config'],'id':row['id'],'condition':condition,'engine':engine_name,
                    'gain':gain,'inputOriginalRms':rms,'nearRms':.01,'windowSamples':[first,last],
                    'privateOutput':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                    'candidateInterruptionsWithFixedSpeakingMask':fires,
                    'dspMs':{'mean':float(measures[:,5].mean()),'p99':float(np.quantile(measures[:,5],.99)),'max':float(measures[:,5].max())},
                    'nearWindowOutputRms':float(np.sqrt(np.mean(clean.ravel()[onset:onset+len(audio)].astype(np.float64)**2)))}
            results.append(record);save(out/'RESULTS.json',results)
            print(json.dumps({'human':human_index,'condition':condition,'engine':engine_name,'candidates':len(fires),'p99ms':record['dspMs']['p99']}),flush=True)
save(out/'COMPLETE.json',{'conditions':len(results),'sourceChanged':False})
