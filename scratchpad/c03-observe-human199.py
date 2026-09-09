"""Recognize every198 condition without hints; keep paired raw controls."""
from pathlib import Path
import gc
import hashlib
import json
import os
import re
import sys
import time
import numpy as np
import sherpa_onnx

root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'src'),str(root/'scripts')]
from baxy_mind.voice import resolve_streaming_stt_directory
from test_mind_voice import transcribe_streaming

base=root/'artifacts/comprobaciones/C03'
out=base/'astra-observe-human199';out.mkdir(exist_ok=False)
inputs=json.loads((base/'astra-human-aec198/RESULTS.json').read_text(encoding='utf-8'))
assert len(inputs)==24 and (base/'astra-human-aec198/COMPLETE.json').exists()
humans=json.loads((base/'astra-human195/DOWNLOADS.json').read_text(encoding='utf-8'))
manifest_path=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def edit_distance(reference,hypothesis):
    previous=list(range(len(hypothesis)+1))
    for i,word in enumerate(reference,1):
        current=[i]
        for j,other in enumerate(hypothesis,1):
            current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(word!=other)))
        previous=current
    return previous[-1]
save(out/'PREREG.json',{'method':'All24 saved198 signals, fixed preregistered near-speech windows, raw amplitude. Same two local recognizers as197; no expected text hints. Surface WER lower-case Unicode words, punctuation ignored; numbers/homophones may differ semantically, so WER is diagnostic, not pass/fail.',
 'inputs':inputs,'runtimeManifestSha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
 'limitation':'Recorded human speech mixed numerically with captured echo; no physical near speaker or C03 reserved turns. Original and scaled raw controls remain visible; no selection of successful recognizer readings.'})
signals=[]
for row in inputs:
    path=Path(row['privateOutput']);assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    first,last=row['windowSamples']
    with np.load(path) as values:signals.append(values['clean'].ravel()[first:last].copy())
results=[]
for name in ['parakeet','nemotron']:
    stt=Path(manifest['stt_dir']) if name=='parakeet' else resolve_streaming_stt_directory()
    common=dict(encoder=str(stt/'encoder.int8.onnx'),decoder=str(stt/'decoder.int8.onnx'),joiner=str(stt/'joiner.int8.onnx'),tokens=str(stt/'tokens.txt'),num_threads=6,model_type='nemo_transducer')
    recognizer=(sherpa_onnx.OfflineRecognizer.from_transducer(**common,decoding_method='modified_beam_search',max_active_paths=8) if name=='parakeet'
                else sherpa_onnx.OnlineRecognizer.from_transducer(**common,decoding_method='greedy_search',enable_endpoint_detection=False,provider='cpu'))
    for row,audio in zip(inputs,signals):
        start=time.monotonic()
        if name=='parakeet':
            stream=recognizer.create_stream();stream.accept_waveform(16000,audio);recognizer.decode_stream(stream)
            text=str(stream.result.text or '').strip()
        else:
            text,_=transcribe_streaming(recognizer,np.r_[audio,np.zeros(10560,np.float32)])
        expected=re.findall(r'\w+',humans[row['human']]['transcription'].lower())
        words=re.findall(r'\w+',text.lower())
        errors=edit_distance(expected,words)
        result={k:row[k] for k in ['human','config','id','condition','engine']}
        result.update(recognizer=name,text=text,wordEdits=errors,referenceWords=len(expected),surfaceWer=errors/len(expected),seconds=time.monotonic()-start)
        results.append(result);save(out/'RESULTS.json',results)
        print(json.dumps(result,ensure_ascii=True),flush=True)
    del recognizer;gc.collect()
save(out/'COMPLETE.json',{'readings':len(results),'sourceChanged':False})
