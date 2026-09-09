"""Independent Nemotron observation of unchanged generated187 and loopback189."""
from pathlib import Path
import hashlib
import json
import os
import sys
import wave
import numpy as np
from scipy.signal import resample_poly
import sherpa_onnx

root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'src'),str(root/'scripts')]
sys.stdout.reconfigure(encoding='utf-8')
from baxy_mind.voice import resolve_streaming_stt_directory
from test_mind_voice import transcribe_streaming
base=root/'artifacts/comprobaciones/C03';private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-sidecar187-private'
out=base/'astra-observe191';out.mkdir(exist_ok=False)
index=json.loads((base/'astra-sidecar187/INDEX.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256(Path(r['privatePath']).read_bytes()).hexdigest()==r['sha256'] for r in index)
capture=json.loads((base/'astra-sidecar187/AUDIO_RESULT.json').read_text(encoding='utf-8'))
record=capture['streams']['loopback'];path=Path(record['privatePath'])
assert hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256']
with wave.open(str(path),'rb') as wav:
    assert wav.getframerate()==48000 and wav.getnchannels()==2
    pcm=np.frombuffer(wav.readframes(wav.getnframes()),'<i2').astype(np.float32).reshape(-1,2).mean(axis=1)/32768
loop=resample_poly(pcm,1,3).astype(np.float32)
generated=np.load(private/'generated187.npz')
windows=[r for r in json.loads((base/'astra-observe189/PREREG.json').read_text(encoding='utf-8'))['windows'] if r['channel']=='loopback']
stt=resolve_streaming_stt_directory();assert stt is not None
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save(out/'PREREG.json',{'method':'Nemotron already installed, CPU6/greedy/auto,0.66s flush as181. Original187 Piper resampled22050->16000 with1s padding each side as190; physical loopback uses unchanged189 windows. Raw and peak0.8, no text hints/new synthesis/playback.', 'inputs':index,'loopbackSha256':record['sha256'],'windows':windows,'recognizer':str(stt),'limitation':'Independent ASR is not an infallible listener. Original vs loopback comparison separates where a reading first fails; not final audio/human acceptance.'})
recognizer=sherpa_onnx.OnlineRecognizer.from_transducer(encoder=str(stt/'encoder.int8.onnx'),decoder=str(stt/'decoder.int8.onnx'),joiner=str(stt/'joiner.int8.onnx'),tokens=str(stt/'tokens.txt'),num_threads=6,model_type='nemo_transducer',decoding_method='greedy_search',enable_endpoint_detection=False,provider='cpu')
rows=[]
for i,window in enumerate(windows):
    original=resample_poly(generated[f'audio{i}'],320,441).astype(np.float32)
    original=np.r_[np.zeros(16000,np.float32),original,np.zeros(16000,np.float32)]
    first,last=window['samples']
    for label,audio in [('original',original),('loopback',loop[first:last])]:
        for normalized in [False,True]:
            signal=audio*.8/max(1e-9,float(np.max(abs(audio)))) if normalized else audio
            text,seconds=transcribe_streaming(recognizer,np.r_[signal,np.zeros(10560,np.float32)])
            row={'output':i+1,'condition':label,'normalized':normalized,'text':text,'seconds':seconds}
            rows.append(row);save(out/'RESULTS.json',rows);print(json.dumps(row,ensure_ascii=False),flush=True)
save(out/'COMPLETE.json',{'readings':len(rows),'exit':'complete'})
