"""One-variable decoder contrast on frozen202 segments and original197 humans."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time
import numpy as np
from scipy.io import wavfile
import sherpa_onnx

root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'src'))
from baxy_mind.voice import _decode_offline_text
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-greedy203';out.mkdir(exist_ok=False)
inputs=json.loads((base/'astra-segment201-retry/RESULTS.json').read_text(encoding='utf-8'))
beam=json.loads((base/'astra-decode202/RESULTS.json').read_text(encoding='utf-8'))
humans=json.loads((base/'astra-human195/DOWNLOADS.json').read_text(encoding='utf-8'))
original_beam=[r for r in json.loads((base/'astra-human197/RESULTS.json').read_text(encoding='utf-8')) if r['recognizer']=='parakeet']
manifest_path=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save(out/'PREREG.json',{'method':'Same42 saved product-segmented clips as202 and four originals as197. Only decoding_method becomes greedy_search; same installed sherpa-onnx1.13.4, int8 Parakeet v3 models, CPU6, max_active_paths8, no hotwords/gain/padding changes. Compare every output to previously preserved beam reading; additional2s all-zero control.',
 'hypothesis':'Decoder, rather than complete acoustic erasure, causes observed empty/truncated text. Prior source used greedy (biblioteca/.../parakeet_v3_uso_correcto_2026-06-10.md). Public report #3267 and unmerged proposed fix #3657 are hypotheses, not proof for installed1.13.4.',
 'sources':['https://github.com/k2-fsa/sherpa-onnx/issues/3267','https://github.com/k2-fsa/sherpa-onnx/pull/3657','https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html'],
 'limitation':'Greedy does not replace the contextual-hotword/wake contract without regression. No product/asset/runtime changes or AEC promotion from this diagnostic.',
 'segments':inputs,'originals':humans,'runtimeSha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest()})
stt=Path(manifest['stt_dir'])
recognizer=sherpa_onnx.OfflineRecognizer.from_transducer(encoder=str(stt/'encoder.int8.onnx'),decoder=str(stt/'decoder.int8.onnx'),joiner=str(stt/'joiner.int8.onnx'),tokens=str(stt/'tokens.txt'),num_threads=6,model_type='nemo_transducer',decoding_method='greedy_search',max_active_paths=8)
save(out/'API.json',{'wrapperMethods':[v for v in dir(recognizer) if not v.startswith('_')],
 'nativeMethods':[v for v in dir(recognizer.recognizer) if not v.startswith('_')] if hasattr(recognizer,'recognizer') else [],'sherpaVersion':sherpa_onnx.__version__})
results=[]
def decode(label,audio,previous):
    start=time.monotonic();text=_decode_offline_text(recognizer,audio)
    row={**label,'text':text,'beamText':previous,'seconds':time.monotonic()-start}
    results.append(row);save(out/'RESULTS.json',results);print(json.dumps(row,ensure_ascii=True),flush=True)
for row in inputs:
    path=Path(row['privateOutput']);assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    with np.load(path) as archive:
        for segment in row['segments']:
            previous=next(r for r in beam if r['case']==row['case'] and r['segment']==segment['index'])
            decode({k:previous[k] for k in ['case','human','condition','engine','segment','humanOverlapSamples']},archive[f'segment{segment["index"]}'],previous['text'])
for i,row in enumerate(humans):
    path=Path(row['asset']);assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    rate,audio=wavfile.read(path);assert rate==16000
    audio=np.r_[np.zeros(16000,np.float32),audio,np.zeros(16000,np.float32)]
    decode({'original':True,'human':i},audio,next(r['text'] for r in original_beam if r['input']==i))
decode({'silenceControl':True},np.zeros(32000,np.float32),None)
save(out/'COMPLETE.json',{'readings':len(results),'sourceChanged':False})
