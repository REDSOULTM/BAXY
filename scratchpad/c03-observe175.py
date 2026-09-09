"""Two-observer check of174 preserved PCM; no AEC or synthesis changes."""
from pathlib import Path
import hashlib
import json
import os
import sys
import wave
import time
import numpy as np
import sherpa_onnx

root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'src'),str(root/'scripts')]
sys.stdout.reconfigure(encoding='utf-8')
from baxy_mind.voice import resolve_streaming_stt_directory
from test_mind_voice import transcribe_streaming
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-observe175'
out.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-webrtc174-private'
prior=json.loads((private/'ASR.json').read_text(encoding='utf-8'))
first,last=prior[0]['windowSamples']
index=json.loads((private/'OUTPUT_INDEX.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256(Path(r['privatePath']).read_bytes()).hexdigest()==r['sha256'] for r in index)
def save(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
streaming=resolve_streaming_stt_directory()
assert streaming is not None
stt=Path(json.loads((Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json').read_text(encoding='utf-8'))['stt_dir'])
save(out/'PREREG.json',{'method':'Same six near/mix raw/Speex/WebRTC174 outputs, same fixed131 crop. Parakeet raw already174; now normalized peak0.8 with Parakeet; independent Nemotron raw and normalized plus0.66s final silence per116. No hints/resynthesis/AEC changes. Retain every result; do not substitute normalized success for raw product success.', 'windowSamples':[first,last],'streamingModel':str(streaming),'inputsIndexSha256':hashlib.sha256((private/'OUTPUT_INDEX.json').read_bytes()).hexdigest()})
offline=sherpa_onnx.OfflineRecognizer.from_transducer(encoder=str(stt/'encoder.int8.onnx'),decoder=str(stt/'decoder.int8.onnx'),joiner=str(stt/'joiner.int8.onnx'),tokens=str(stt/'tokens.txt'),num_threads=6,model_type='nemo_transducer',decoding_method='modified_beam_search',max_active_paths=8)
online=sherpa_onnx.OnlineRecognizer.from_transducer(encoder=str(streaming/'encoder.int8.onnx'),decoder=str(streaming/'decoder.int8.onnx'),joiner=str(streaming/'joiner.int8.onnx'),tokens=str(streaming/'tokens.txt'),num_threads=6,model_type='nemo_transducer',decoding_method='greedy_search',enable_endpoint_detection=False,provider='cpu')
rows=[]
for item in prior:
    path=private/f"{item['case']}-{item['method']}.wav"
    with wave.open(str(path),'rb') as f:
        pcm=np.frombuffer(f.readframes(f.getnframes()),'<i2').astype(np.float32)/32768
    pcm=pcm[max(0,first):min(len(pcm),last)]
    for name, normalized in [('parakeet',True),('nemotron',False),('nemotron',True)]:
        signal=pcm*.8/max(1e-9,float(np.max(abs(pcm)))) if normalized else pcm
        start=time.perf_counter()
        if name=='parakeet':
            stream=offline.create_stream(); stream.accept_waveform(16000,signal); offline.decode_stream(stream)
            text=str(stream.result.text or '').strip()
        else:
            text,_=transcribe_streaming(online,np.r_[signal,np.zeros(10560,np.float32)])
        row={'case':item['case'],'method':item['method'],'observer':name,'normalized':normalized,'text':text,'seconds':time.perf_counter()-start}
        rows.append(row)
        save(private/'OBSERVE175.json',rows)
        print(json.dumps(row,ensure_ascii=False),flush=True)
save(out/'RESULT_INDEX.json',{'privatePath':str(private/'OBSERVE175.json'),'sha256':hashlib.sha256((private/'OBSERVE175.json').read_bytes()).hexdigest(),'rows':len(rows)})
