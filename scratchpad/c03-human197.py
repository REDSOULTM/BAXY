"""Baseline recognition of four unchanged human recordings before AEC mixing."""
from pathlib import Path
import gc
import hashlib
import json
import os
import sys
import time
import numpy as np
from scipy.io import wavfile
import sherpa_onnx

root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'src'),str(root/'scripts')]
from baxy_mind.voice import resolve_streaming_stt_directory
from test_mind_voice import transcribe_streaming

base=root/'artifacts/comprobaciones/C03'
out=base/'astra-human197';out.mkdir(exist_ok=False)
inputs=json.loads((base/'astra-human195/DOWNLOADS.json').read_text(encoding='utf-8'))
manifest_path=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save(out/'PREREG.json',{'method':'All four195 native float32 mono16k WAVs, unchanged raw amplitude; 1s zeros before/after. Parakeet registered CPU6 beam8, then independent Nemotron CPU6 greedy with0.66s flush. No text hints, gain adjustment, selection by output or audio playback.',
 'purpose':'Establish original recognizer fidelity before attributing word loss to AEC; not human input or C03 reserve acceptance.',
 'inputs':inputs,'runtimeManifestSha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest()})
signals=[]
for row in inputs:
    path=Path(row['asset'])
    assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    rate,audio=wavfile.read(path)
    assert rate==16000 and audio.dtype==np.float32 and audio.ndim==1
    signals.append(np.r_[np.zeros(16000,np.float32),audio,np.zeros(16000,np.float32)])
results=[]
for name in ['parakeet','nemotron']:
    stt=Path(manifest['stt_dir']) if name=='parakeet' else resolve_streaming_stt_directory()
    assert stt is not None
    common=dict(encoder=str(stt/'encoder.int8.onnx'),decoder=str(stt/'decoder.int8.onnx'),joiner=str(stt/'joiner.int8.onnx'),tokens=str(stt/'tokens.txt'),num_threads=6,model_type='nemo_transducer')
    if name=='parakeet':
        recognizer=sherpa_onnx.OfflineRecognizer.from_transducer(**common,decoding_method='modified_beam_search',max_active_paths=8)
    else:
        recognizer=sherpa_onnx.OnlineRecognizer.from_transducer(**common,decoding_method='greedy_search',enable_endpoint_detection=False,provider='cpu')
    for i,(row,audio) in enumerate(zip(inputs,signals)):
        start=time.monotonic()
        if name=='parakeet':
            stream=recognizer.create_stream();stream.accept_waveform(16000,audio);recognizer.decode_stream(stream)
            text=str(stream.result.text or '').strip()
        else:
            text,_=transcribe_streaming(recognizer,np.r_[audio,np.zeros(10560,np.float32)])
        result={'input':i,'config':row['config'],'id':row['id'],'recognizer':name,'text':text,'seconds':time.monotonic()-start}
        results.append(result);save(out/'RESULTS.json',results)
        print(json.dumps(result,ensure_ascii=True),flush=True)
    del recognizer;gc.collect()
save(out/'COMPLETE.json',{'readings':len(results),'sourceChanged':False})
