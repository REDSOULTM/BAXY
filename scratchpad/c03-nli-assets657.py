"""Fetch pinned public CPU NLI assets without changing BAXY runtime."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import urllib.request

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-nli-assets657'
out.mkdir(exist_ok=False)
repo = 'MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli'
revision = '0a71e92a985b6e1ad1828cf67ce9c459639c1dca'
destination = Path('D:/BAXYRuntime/experiments/models/minilm-nli-0a71e92a')
destination.mkdir(exist_ok=True)
with urllib.request.urlopen(f'https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true',timeout=30) as response:
    metadata = json.load(response)
assert metadata['sha'] == revision
names = {'README.md','config.json','onnx/model.onnx','tokenizer.json','tokenizer_config.json','special_tokens_map.json'}
files = [r for r in metadata['siblings'] if r['rfilename'] in names]
assert len(files) == len(names)
def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
write(out / 'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'repo':repo,'revision':revision,
    'destination':str(destination),'files':files,'runtime_modified':False,
    'purpose':'656 same-writer judge still accepts four unsupported assertions. Evaluate a trained multilingual NLI model on CPU before another runtime layer. Acquisition alone is not quality evidence.',
    'inheritance':['astra-native-fact-judge656','artifacts/research/full_catalog_mdeberta_v2_onnx.json','experiments/mind_router_spike/export_benchmark_mdeberta_onnx.py'],
    'inheritance_limit':'Existing mDeBERTa checkpoints are operation classifiers, not entailment checkpoints. Reuse CPU/ONNX measurement approach, not their weights or quality scores.',
    'sources':['https://huggingface.co/'+repo,'https://aclanthology.org/2024.emnlp-main.499/','https://github.com/Liyan06/MiniCheck'],
    'profile_plan':'Official ONNX FP32 and tokenizer, native pair premise/hypothesis; confirm config label order, CPUExecutionProvider, attention mask, sequence length and no truncation. Same31 cases656 with deterministic factual premises in the reply language; language selection declared fixture metadata. Compare 2/4 CPU threads with separate processes. No zero-shot topic template, no sampling or forced answer text. Quantization requires a later parity/quality comparison; no global rejection from one profile.',
    'privacy':'Only public metadata and model files requested; no user/history/panel payload sent to a remote inference service.'})
verified = []
for item in files:
    name = item['rfilename']
    path = destination / name
    path.parent.mkdir(exist_ok=True)
    if path.exists():
        data = path.read_bytes()
    else:
        partial = path.with_name(path.name+'.partial657')
        assert not partial.exists()
        with urllib.request.urlopen(f'https://huggingface.co/{repo}/resolve/{revision}/{name}?download=true',timeout=60) as response, partial.open('xb') as stream:
            while chunk := response.read(4*1024*1024):
                stream.write(chunk)
        data = partial.read_bytes()
    assert len(data) == item['size'], name
    digest = hashlib.sha256(data).hexdigest()
    if 'lfs' in item:
        assert digest == item['lfs']['sha256'], name
    else:
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest() == item['blobId'], name
    if not path.exists():
        os.replace(partial,path)
    verified.append({'path':str(path),'bytes':len(data),'sha256':digest})
    del data
    print('Verified '+name,flush=True)
write(out / 'RESULT.json',{'verified':verified,'runtime_modified':False,'inference_run':False})
write(out / 'PINS.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
with (root / '.gitattributes').open('a',encoding='utf-8',newline='\n') as f:
    f.write('/artifacts/comprobaciones/C03/astra-nli-assets657/** -text\n')
print('Assets verified; no inference or promotion.',flush=True)
