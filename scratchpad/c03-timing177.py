"""Compare actual signal onset and near-component preservation, no new inference."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import wave
import numpy as np
from scipy.signal import correlate, correlation_lags, resample_poly

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-timing177'
out.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY'
inputs=[]
def read(path):
    inputs.append({'privatePath':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    with wave.open(str(path),'rb') as f:
        rate=f.getframerate()
        audio=np.frombuffer(f.readframes(f.getnframes()),'<i2').reshape(-1,f.getnchannels()).mean(axis=1)/32768
    return resample_poly(audio,16000,rate) if rate!=16000 else audio
capture=json.loads((base/'astra-voice127/AUDIO_RESULT.json').read_text(encoding='utf-8'))
origins={k:dt.datetime.fromisoformat(v['streamReadyUtc']).timestamp() for k,v in capture['streams'].items()}
offset=round((origins['microphone']-origins['loopback'])*16000)
loop=read(private/'C03-voice127-private/loopback.wav')
near=read(private/'C03-speex129-private/near_only-raw.wav')
ix=np.arange(len(near))+offset
ref=np.zeros_like(near);valid=(ix>=0)&(ix<len(loop));ref[valid]=loop[ix[valid]]
events=[json.loads(s) for s in (base/'astra-voice127/EVENTS.jsonl').read_text(encoding='utf-8').splitlines()]
start=next(e for e in events if e.get('speaking'))
start_sample=round((dt.datetime.fromisoformat(start['utc']).timestamp()-origins['microphone'])*16000)
prereg={'method':'No playback/AEC/ASR. First160-sample frames after speaking with reference RMS20PCM (existing echo guard minimum); exact first nonzero synthetic near sample. Measured near-only lag per176 stage before projecting mixed stage onto known near. Projection is diagnostic, not source separation or fidelity score. Preserve approximate127 streamReadyUtc alignment; do not select cutoff/lag from mixed output.', 'sampleRate':16000,'speakingSample':start_sample}
(out/'PREREG.json').write_text(json.dumps(prereg,indent=2),encoding='utf-8')
first_ref=next(i for i in range(max(0,start_sample//160*160),len(ref)-159,160) if np.sqrt(np.mean(ref[i:i+160]**2))*32768>=20)
first_near=int(np.flatnonzero(near!=0)[0]);last_near=int(np.flatnonzero(near!=0)[-1])
results={'speakingSeconds':start_sample/16000,'referenceRms20OnsetSeconds':first_ref/16000,'firstNonzeroNearSeconds':first_near/16000,'lastNonzeroNearSeconds':last_near/16000,'nearMinusReferenceOnsetMs':(first_near-first_ref)/16,'stages':[]}
for stage in ['linear','final']:
    only=read(private/f'C03-linear176-private/near_only-{stage}.wav')
    mix=read(private/f'C03-linear176-private/physical_echo_plus_synthetic_near-{stage}.wav')
    corr=correlate(only,near,method='fft');lags=correlation_lags(len(only),len(near))
    allowed=np.flatnonzero((lags>=0)&(lags<512));lag=int(lags[allowed[np.argmax(abs(corr[allowed]))]])
    rows=[]
    for i in range(first_near,last_near,4800):
        n=near[i:i+4800]; y=mix[i+lag:i+lag+len(n)];n=n[:len(y)]
        a=float(np.dot(n,y)/(np.dot(n,n)+1e-20))
        rows.append({'nearSeconds':round(i/16000,4),'nearRms':float(np.sqrt(np.mean(n*n))),'mixtureOutputRms':float(np.sqrt(np.mean(y*y))),'projectionGain':a,'normalizedCorrelation':float(np.dot(n,y)/(np.linalg.norm(n)*np.linalg.norm(y)+1e-20))})
    results['stages'].append({'stage':stage,'nearOnlyObservedLagSamples':lag,'windows':rows})
(out/'RESULTS.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
(out/'INPUT_INDEX.json').write_text(json.dumps(inputs,indent=2),encoding='utf-8')
print(json.dumps(results,indent=2))
