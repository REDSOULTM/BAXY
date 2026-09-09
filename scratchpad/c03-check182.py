"""Streaming parity to179/180, alignment, ownership and per512 cost."""
from pathlib import Path
import hashlib
import json
import os
import sys
import threading
import time
import wave
import numpy as np
from scipy.signal import correlate, correlation_lags

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'scratchpad'))
from dtln_stream182 import EchoCanceller
base=root/'artifacts/comprobaciones/C03';out=base/'astra-stream182';out.mkdir(exist_ok=False)
priv=Path(os.environ['LOCALAPPDATA'])/'BAXY'
def save(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def read(p):
    with wave.open(str(p),'rb') as f:
        assert f.getframerate()==16000 and f.getnchannels()==1
        return np.frombuffer(f.readframes(f.getnframes()),'<i2').astype(np.float32)/32768
save(out/'PREREG.json',{'method':'Same native149 and synthetic near-only/mix129. Stream exactly four128hops per512input; three zero warmup hops at init matches author padding; no percall padding/final normalization. Compare saved PCM179/180 bit-for-bit; verify raw echo guard pair delayed384samples independently by index, wrong-thread/closed/invalid-frame behavior. p99 per512 includes both models/FFT; no physical/UI/acceptance.', 'units':[128,512],'sourceSha256':hashlib.sha256((root/'scratchpad/dtln_stream182.py').read_bytes()).hexdigest()})
tap=np.load(priv/'C03-voice149-private/tap149.npz')
native=(tap['microphone'].ravel(),np.r_[tap['reference'][0,:-512],tap['reference'][:,-512:].ravel()].astype(np.float32))
# Reuse exact reference from179 INPUTS by reproducing its127 mapping, no resampling difference.
import datetime as dt
from scipy.signal import resample_poly
cap=json.loads((base/'astra-voice127/AUDIO_RESULT.json').read_text(encoding='utf-8'))
origins={k:dt.datetime.fromisoformat(v['streamReadyUtc']).timestamp() for k,v in cap['streams'].items()}
offset=round((origins['microphone']-origins['loopback'])*16000)
with wave.open(str(priv/'C03-voice127-private/loopback.wav'),'rb') as f:
    loop=np.frombuffer(f.readframes(f.getnframes()),'<i2').reshape(-1,f.getnchannels()).mean(axis=1)/32768
    loop=resample_poly(loop,16000,f.getframerate()).astype(np.float32)
cases=[('native_echo149',*native)]
for name in ['near_only','physical_echo_plus_synthetic_near']:
    mic=read(priv/f'C03-speex129-private/{name}-raw.wav');far=np.zeros_like(mic)
    ix=np.arange(len(mic))+offset;valid=(ix>=0)&(ix<len(loop))
    if name!='near_only':far[valid]=loop[ix[valid]]
    cases.append((name,mic,np.r_[np.zeros(4000,np.float32),far]*32768))
rows=[]
for units,stage in [(128,179),(512,180)]:
    for name,mic,ref in cases:
        expected=read(priv/f'C03-dtln{stage}-private/{name}-dtln{units}.wav')
        engine=EchoCanceller(units);chunks=[];cost=[]
        expected_mic=np.r_[np.zeros(384,np.float32),mic]*32768
        ref_ext=np.r_[np.zeros(384,np.float32),ref]
        for start in range(0,len(mic)-511,512):
            t=time.perf_counter()
            clean,paired_mic,paired_ref=engine.process(mic[start:start+512],ref[start:start+4512])
            cost.append((time.perf_counter()-t)*1000);chunks.append(clean)
            assert np.array_equal(paired_mic,expected_mic[start:start+512])
            assert np.array_equal(paired_ref,ref_ext[start:start+4512])
        clean=np.concatenate(chunks)
        quant=np.clip(clean*32768,-32768,32767).astype('<i2')
        expected_quant=np.clip(expected[:len(clean)]*32768,-32768,32767).astype('<i2')
        assert np.array_equal(quant,expected_quant),(units,name,int(np.max(abs(quant.astype(int)-expected_quant.astype(int)))))
        row={'units':units,'case':name,'samples':len(clean),'pcmIdentical':True,'guardPairDelaySamples':384,'mean512Ms':float(np.mean(cost)),'p99512Ms':float(np.quantile(cost,.99)),'max512Ms':max(cost),'outputPeak':float(np.max(abs(clean)))}
        if name=='near_only':
            c=correlate(clean,mic,method='fft');lags=correlation_lags(len(clean),len(mic));ix=np.flatnonzero((lags>=0)&(lags<1024))
            row['observedLagSamples']=int(lags[ix[np.argmax(abs(c[ix]))]])
        failures=[]
        def wrong_thread():
            try:engine.process(np.zeros(512),np.zeros(4512))
            except RuntimeError as e:failures.append(str(e))
        thread=threading.Thread(target=wrong_thread);thread.start();thread.join()
        assert failures==['echo_canceller_wrong_thread']
        for bad in [np.zeros(511),np.full(512,np.nan)]:
            try:engine.process(bad,np.zeros(4512))
            except ValueError:pass
            else:raise AssertionError('invalid frame accepted')
        engine.close();engine.close()
        try:engine.process(np.zeros(512),np.zeros(4512))
        except RuntimeError as e:assert str(e)=='echo_canceller_closed'
        else:raise AssertionError('closed engine accepted audio')
        rows.append(row);save(out/'RESULTS.json',rows);print(json.dumps(row),flush=True)
save(out/'COMPLETE.json',{'cases':len(rows),'checks':'PCM parity, reference alignment, ownership/closed/invalid input all pass; no runtime promotion or source changes.'})
