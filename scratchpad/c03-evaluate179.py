"""Run the author's exact process_file math, substituting in-memory audio I/O only."""
from pathlib import Path
import ast
import datetime as dt
import gc
import hashlib
import json
import os
import sys
import time
import types
import wave
import numpy as np
from scipy.signal import resample_poly
import psutil
import sherpa_onnx

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-dtln179'
folder=Path('D:/BAXYRuntime/experiments/voice/dtln179')
sys.path[:0]=[str(folder/'python'),str(root/'src')]
sys.stdout.reconfigure(encoding='utf-8')
from ai_edge_litert.interpreter import Interpreter
from baxy_mind.voice import SileroVad
privbase=Path(os.environ['LOCALAPPDATA'])/'BAXY'
private=privbase/'C03-dtln179-private'
private.mkdir(exist_ok=False)
def save(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def read(path):
    with wave.open(str(path),'rb') as f:
        rate=f.getframerate()
        signal=np.frombuffer(f.readframes(f.getnframes()),'<i2').reshape(-1,f.getnchannels()).mean(axis=1)/32768
    return np.asarray(resample_poly(signal,16000,rate) if rate!=16000 else signal,dtype=np.float32)
for row in json.loads((out/'DOWNLOADS.json').read_text(encoding='utf-8')):
    assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256']
source=folder/'run_aec.py'
tree=ast.parse(source.read_text(encoding='utf-8'))
function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='process_file')
module=ast.Module(body=[function],type_ignores=[])
compiled=compile(ast.fix_missing_locations(module),str(source),'exec')
tap=np.load(privbase/'C03-voice149-private/tap149.npz')
cases=[('native_echo149',tap['microphone'].ravel().astype(np.float32),tap['reference'][:,-512:].ravel().astype(np.float32)/32768)]
cap=json.loads((base/'astra-voice127/AUDIO_RESULT.json').read_text(encoding='utf-8'))
origins={k:dt.datetime.fromisoformat(v['streamReadyUtc']).timestamp() for k,v in cap['streams'].items()}
offset=round((origins['microphone']-origins['loopback'])*16000)
loop=read(privbase/'C03-voice127-private/loopback.wav')
for name in ['physical_echo','near_only','physical_echo_plus_synthetic_near']:
    mic=read(privbase/f'C03-speex129-private/{name}-raw.wav');ref=np.zeros_like(mic)
    positions=np.arange(len(mic))+offset;valid=(positions>=0)&(positions<len(loop))
    if name!='near_only':ref[valid]=loop[positions[valid]]
    cases.append((name,mic,ref))
cases.append(('cold_silence',np.zeros(32000,np.float32),np.zeros(32000,np.float32)))
save(out/'INPUTS.json',{'cases':[{'name':n,'samples':len(m),'micFloat32Sha256':hashlib.sha256(m.tobytes()).hexdigest(),'refFloat32Sha256':hashlib.sha256(r.tobytes()).hexdigest()} for n,m,r in cases], 'algorithm':'Unmodified AST process_file from author run_aec.py. sf.read/write replaced with array I/O; no TensorFlow import/environment mutation. CPU LiteRT2.2.0 Interpreter, num_threads1, XNNPACK default. Fresh interpreter pair and function states per case; author padding/clipping policy retained.'})
stt=Path(json.loads((Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json').read_text(encoding='utf-8'))['stt_dir'])
recognizer=sherpa_onnx.OfflineRecognizer.from_transducer(encoder=str(stt/'encoder.int8.onnx'),decoder=str(stt/'decoder.int8.onnx'),joiner=str(stt/'joiner.int8.onnx'),tokens=str(stt/'tokens.txt'),num_threads=6,model_type='nemo_transducer',decoding_method='modified_beam_search',max_active_paths=8)
first,last=json.loads((privbase/'C03-webrtc174-private/ASR.json').read_text(encoding='utf-8'))[0]['windowSamples']
vad=SileroVad();rows=[]
for name,mic,ref in cases:
    before=psutil.Process().memory_info().rss
    initial=time.perf_counter()
    interpreters=[Interpreter(model_path=str(folder/f'dtln_aec_128_{i}.tflite'),num_threads=1) for i in [1,2]]
    for interpreter in interpreters:interpreter.allocate_tensors()
    load_seconds=time.perf_counter()-initial
    result=[]
    def load_signal(path):
        assert path in ['input_mic.wav','input_lpb.wav']
        return (mic if path=='input_mic.wav' else ref),16000
    def store_signal(path,audio,rate):
        assert path=='output.wav' and rate==16000
        result.append(np.asarray(audio,dtype=np.float32).copy())
    namespace={'np':np,'sf':types.SimpleNamespace(read=load_signal,write=store_signal)}
    exec(compiled,namespace)
    start=time.perf_counter()
    namespace['process_file'](*interpreters,'input_mic.wav','output.wav')
    seconds=time.perf_counter()-start
    assert len(result)==1
    clean=result[0]
    assert len(clean)==len(mic) and np.isfinite(clean).all()
    memory=psutil.Process().memory_info().rss-before
    del interpreters;gc.collect()
    vad.reset();floor=.002;run=longest=speech=qualified=0;first_qualified=None
    for start in range(0,len(clean)-511,512):
        frame=clean[start:start+512];p=vad.process(frame)
        energy=float(np.sqrt(np.mean(frame.astype(np.float64)**2)))
        if p<.5:floor=.98*floor+.02*energy
        speech+=int(p>=.5)
        if p>=.5 and energy>=max(.004,floor*1.8):
            qualified+=1;run+=1;longest=max(longest,run)
            if first_qualified is None:first_qualified=start/16000
        else:run=0
    path=private/f'{name}-dtln128.wav'
    pcm=np.clip(clean*32768,-32768,32767).astype('<i2')
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm.tobytes())
    words=[]
    if name in ['near_only','physical_echo_plus_synthetic_near']:
        window=pcm[max(0,first):min(len(clean),last)].astype(np.float32)/32768
        for norm in [False,True]:
            audio=window*.8/max(1e-9,float(np.max(abs(window)))) if norm else window
            stream=recognizer.create_stream();stream.accept_waveform(16000,audio);recognizer.decode_stream(stream)
            words.append({'normalized':norm,'text':str(stream.result.text or '').strip()})
    row={'case':name,'samples':len(clean),'loadSeconds':load_seconds,'processingSeconds':seconds,'processingMsPer8msHop':seconds/(len(mic)/128)*1000,'rssDeltaBytes':memory,'speechFrames':speech,'qualifiedFramesWithoutGuard':qualified,'maxConsecutiveWithoutGuard':longest,'firstQualifiedSeconds':first_qualified,'transcripts':words,'rms':float(np.sqrt(np.mean(clean.astype(np.float64)**2)))}
    rows.append(row);save(out/'RESULTS.json',rows);print(json.dumps(row,ensure_ascii=False),flush=True)
save(out/'PRIVATE_INDEX.json',[{'privatePath':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in private.iterdir() if p.is_file()])
save(out/'COMPLETE.json',{'rows':len(rows),'runtime':sys.executable,'sourceUnchanged':True,'promoted':False,'physicalAcceptance':False})
