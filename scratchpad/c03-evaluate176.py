"""Observe AEC3 intermediate audio, compare final to174; no product effects."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import sys
import wave
import zipfile
import numpy as np
from scipy.signal import resample_poly
import sherpa_onnx

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-linear176'
folder=Path('D:/BAXYRuntime/experiments/voice/webrtc176')
wheels=list((folder/'wheels').glob('*.whl'))
assert len(wheels)==1
wheel=wheels[0]
with zipfile.ZipFile(wheel) as z:
    for name in z.namelist():
        assert (folder/'python'/name).resolve().is_relative_to((folder/'python').resolve())
    z.extractall(folder/'python')
sys.path[:0]=[str(folder/'python'),str(root/'src')]
sys.stdout.reconfigure(encoding='utf-8')
from pywebrtc_audio import EchoCanceller
from baxy_mind.voice import SileroVad
privbase=Path(os.environ['LOCALAPPDATA'])/'BAXY'
private=privbase/'C03-linear176-private'
private.mkdir(exist_ok=False)
def save(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def read(path):
    with wave.open(str(path),'rb') as f:
        rate=f.getframerate()
        raw=np.frombuffer(f.readframes(f.getnframes()),'<i2').reshape(-1,f.getnchannels()).mean(axis=1)/32768
    return np.asarray(resample_poly(raw,16000,rate) if rate!=16000 else raw,dtype=np.float32)
def pcm(audio):
    return np.clip(audio*32768,-32768,32767).astype('<i2')
def write(path,audio):
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm(audio).tobytes())
tap=np.load(privbase/'C03-voice149-private/tap149.npz')
cases=[('native_echo149',tap['microphone'].ravel().astype(np.float32),tap['reference'][:,-512:].ravel().astype(np.float32)/32768)]
capture=json.loads((base/'astra-voice127/AUDIO_RESULT.json').read_text(encoding='utf-8'))
origins={k:dt.datetime.fromisoformat(v['streamReadyUtc']).timestamp() for k,v in capture['streams'].items()}
offset=round((origins['microphone']-origins['loopback'])*16000)
loop=read(privbase/'C03-voice127-private/loopback.wav')
for name in ['near_only','physical_echo_plus_synthetic_near']:
    mic=read(privbase/f'C03-speex129-private/{name}-raw.wav')
    ref=np.zeros_like(mic)
    ix=np.arange(len(mic))+offset
    valid=(ix>=0)&(ix<len(loop))
    if name!='near_only':ref[valid]=loop[ix[valid]]
    cases.append((name,mic,ref))
stt=Path(json.loads((Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json').read_text(encoding='utf-8'))['stt_dir'])
recognizer=sherpa_onnx.OfflineRecognizer.from_transducer(encoder=str(stt/'encoder.int8.onnx'),decoder=str(stt/'decoder.int8.onnx'),joiner=str(stt/'joiner.int8.onnx'),tokens=str(stt/'tokens.txt'),num_threads=6,model_type='nemo_transducer',decoding_method='modified_beam_search',max_active_paths=8)
first,last=json.loads((privbase/'C03-webrtc174-private/ASR.json').read_text(encoding='utf-8'))[0]['windowSamples']
vad=SileroVad()
rows=[]
for name,mic,ref in cases:
    engine=EchoCanceller(16000,1,0)
    final,linear,metrics=[],[],[]
    for start in range(0,len(mic)-159,160):
        final.append(engine.process(np.ascontiguousarray(mic[start:start+160]),np.ascontiguousarray(ref[start:start+160])))
        linear.append(engine.last_linear_frame())
        if start%1600==0:
            metrics.append({'seconds':start/16000,**engine.diagnostic_metrics()})
    signals={'final':np.concatenate(final),'linear':np.concatenate(linear)}
    prior=read(privbase/f'C03-webrtc174-private/{name}-webrtc.wav')
    difference=pcm(signals['final']).astype(np.int32)-pcm(prior).astype(np.int32)
    parity={'finalPcmIdenticalTo174':bool(np.array_equal(pcm(signals['final']),pcm(prior))), 'maxPcmDifference':int(np.max(abs(difference))), 'rmsPcmDifference':float(np.sqrt(np.mean(difference.astype(np.float64)**2)))}
    for stage,signal in signals.items():
        assert np.isfinite(signal).all()
        write(private/f'{name}-{stage}.wav',signal)
        vad.reset();floor=.002;run=longest=voiced=0
        for start in range(0,len(signal)-511,512):
            frame=signal[start:start+512]
            p=vad.process(frame)
            energy=float(np.sqrt(np.mean(frame.astype(np.float64)**2)))
            if p<.5:floor=.98*floor+.02*energy
            voiced+=int(p>=.5)
            run=run+1 if p>=.5 and energy>=max(.004,floor*1.8) else 0
            longest=max(longest,run)
        transcripts=[]
        if name!='native_echo149':
            window=signal[max(0,first):min(len(signal),last)]
            for norm in [False,True]:
                audio=window*.8/max(1e-9,float(np.max(abs(window)))) if norm else window
                stream=recognizer.create_stream();stream.accept_waveform(16000,audio);recognizer.decode_stream(stream)
                transcripts.append({'normalized':norm,'text':str(stream.result.text or '').strip()})
        row={'case':name,'stage':stage,**parity,'speechFrames':voiced,'longestQualifiedWithoutGuard':longest,'transcripts':transcripts}
        rows.append(row);save(out/'RESULTS.json',rows);print(json.dumps(row,ensure_ascii=False),flush=True)
    save(private/f'{name}-metrics.json',metrics)
save(out/'BUILD.json',{'wheel':str(wheel),'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'bytes':wheel.stat().st_size,'source':'Local diagnostic build, not deployed','runtime':sys.executable})
save(out/'PRIVATE_INDEX.json',[{'privatePath':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in private.iterdir() if p.is_file()])
