"""Independent local observer of preserved179/180, same raw and normalized windows."""
from pathlib import Path
import hashlib
import json
import os
import sys
import wave
import numpy as np
import sherpa_onnx

root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'src'),str(root/'scripts')]
sys.stdout.reconfigure(encoding='utf-8')
from baxy_mind.voice import resolve_streaming_stt_directory
from test_mind_voice import transcribe_streaming
base=root/'artifacts/comprobaciones/C03';out=base/'astra-observe181';out.mkdir(exist_ok=False)
priv=Path(os.environ['LOCALAPPDATA'])/'BAXY'
first,last=json.loads((priv/'C03-webrtc174-private/ASR.json').read_text(encoding='utf-8'))[0]['windowSamples']
stt=resolve_streaming_stt_directory();assert stt is not None
def save(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
save(out/'PREREG.json',{'method':'Same175 independent Nemotron CPU6/greedy/auto,0.66s final silence; same fixed131 crop and raw/peak0.8 variants. Existing179/180 near-only and mixture, no resynthesis/new processing/hints; preserve all results.', 'windowSamples':[first,last],'recognizer':str(stt),'scope':'Synthetic component evidence; not human or physical acceptance.'})
recognizer=sherpa_onnx.OnlineRecognizer.from_transducer(encoder=str(stt/'encoder.int8.onnx'),decoder=str(stt/'decoder.int8.onnx'),joiner=str(stt/'joiner.int8.onnx'),tokens=str(stt/'tokens.txt'),num_threads=6,model_type='nemo_transducer',decoding_method='greedy_search',enable_endpoint_detection=False,provider='cpu')
rows=[]
for stage,units in [(179,128),(180,512)]:
    index=json.loads((base/f'astra-dtln{stage}/PRIVATE_INDEX.json').read_text(encoding='utf-8'))
    assert all(hashlib.sha256(Path(r['privatePath']).read_bytes()).hexdigest()==r['sha256'] for r in index)
    for case in ['near_only','physical_echo_plus_synthetic_near']:
        path=priv/f'C03-dtln{stage}-private/{case}-dtln{units}.wav'
        with wave.open(str(path),'rb') as f:pcm=np.frombuffer(f.readframes(f.getnframes()),'<i2').astype(np.float32)/32768
        window=pcm[max(0,first):min(len(pcm),last)]
        for norm in [False,True]:
            audio=window*.8/max(1e-9,float(np.max(abs(window)))) if norm else window
            text,seconds=transcribe_streaming(recognizer,np.r_[audio,np.zeros(10560,np.float32)])
            row={'stage':stage,'units':units,'case':case,'normalized':norm,'text':text,'seconds':seconds}
            rows.append(row);save(out/'RESULTS.json',rows);print(json.dumps(row,ensure_ascii=False),flush=True)
