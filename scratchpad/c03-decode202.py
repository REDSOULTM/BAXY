"""Decode every actual201 segmentation result with the product final ASR helper."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time
import numpy as np
import sherpa_onnx

root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'src'))
from baxy_mind.voice import _decode_offline_text
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-decode202';out.mkdir(exist_ok=False)
inputs=json.loads((base/'astra-segment201-retry/RESULTS.json').read_text(encoding='utf-8'))
assert len(inputs)==24
humans=json.loads((base/'astra-human195/DOWNLOADS.json').read_text(encoding='utf-8'))
manifest=json.loads((Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json').read_text(encoding='utf-8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save(out/'PREREG.json',{'method':'All42 native _DecodeRequest clips from actual capture-loop201; registered ParakeetCPU6/beam8 via product _decode_offline_text without hotword hints, gain, padding or hand-made text. All segments retained, including those outside human-speech interval.',
 'scope':'Final ASR stage only, not Core/router/UI/audio output or authenticated wake. Source201 isolates direct-mode segmentation with speakingFalse and preprocessed input.',
 'inputs':inputs})
stt=Path(manifest['stt_dir'])
recognizer=sherpa_onnx.OfflineRecognizer.from_transducer(encoder=str(stt/'encoder.int8.onnx'),decoder=str(stt/'decoder.int8.onnx'),joiner=str(stt/'joiner.int8.onnx'),tokens=str(stt/'tokens.txt'),num_threads=6,model_type='nemo_transducer',decoding_method='modified_beam_search',max_active_paths=8)
results=[]
for row in inputs:
    path=Path(row['privateOutput']);assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    with np.load(path) as archive:
        for segment in row['segments']:
            pcm=archive[f'segment{segment["index"]}'];start=time.monotonic()
            text=_decode_offline_text(recognizer,pcm)
            result={k:row[k] for k in ['case','human','config','id','condition','engine']}
            delay={'raw':0,'speex':512,'dtln128':384}[row['engine']]
            near_first=31872+delay;near_last=near_first+humans[row['human']]['samples']
            overlap=max(0,min(segment['lastSample'],near_last)-max(segment['firstSample'],near_first))
            result.update(segment=segment['index'],firstSample=segment['firstSample'],lastSample=segment['lastSample'],humanOverlapSamples=overlap,text=text,seconds=time.monotonic()-start)
            results.append(result);save(out/'RESULTS.json',results)
            print(json.dumps(result,ensure_ascii=True),flush=True)
assert len(results)==42
save(out/'COMPLETE.json',{'readings':len(results),'sourceChanged':False})
